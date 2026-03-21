from __future__ import annotations
# ==============================================================================
# subscription_worker.py — WEbdEX Monitor Engine — On-chain Subscription Worker
# Story 14.3: Webhook On-chain Auto-ativação de Subscription
#
# Responsabilidades:
#   - Pollar eventos `Subscribed` do contrato WEbdEXSubscription (Polygon)
#   - Persistir subscriptions no SQLite com idempotência (ON CONFLICT DO NOTHING)
#   - Atualizar `users.subscription_expires` quando wallet bate com usuário
#   - Notificar usuário via Telegram quando chat_id encontrado
#   - Checkpoint de bloco em config(chave='sub_last_block')
# ==============================================================================

import os
import time
import threading
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from webdex_config import logger
from webdex_db import DB_LOCK, conn, cursor, get_config, set_config

# ── Importa helper de envio (graceful — pode não estar disponível no boot) ────
try:
    from webdex_bot_core import send_html
except Exception:
    send_html = None  # type: ignore[assignment]

# ==============================================================================
# ⚙️ PARÂMETROS
# ==============================================================================
_POLL_INTERVAL_S   = 60          # pollar a cada 60 segundos
_BOOT_WAIT_S       = 30          # aguarda 30s ao iniciar (boot warmup)
_BLOCKS_PER_POLL   = 500         # máx de blocos por iteração
_WALLET_LOCK_TIMEOUT = 30        # timeout para per-wallet lock (segundos)
_CONFIG_KEY_LAST_BLOCK = "sub_last_block"

# Contrato WEbdEXSubscription v1.1.0 — Polygon Mainnet
_CONTRACT_ADDRESS = "0x6481d77f95b654F89A1C8D993654d5f877fe6E22"

# Todos os eventos Subscribed mapeiam para tier 'pro' (sem campo tier no contrato)
TIER_MAP: dict[str, str] = {}  # não utilizado — todos são 'pro'

# ABI mínima — apenas o evento Subscribed
_SUBSCRIBED_ABI = [
    {
        "name": "Subscribed",
        "type": "event",
        "anonymous": False,
        "inputs": [
            {"name": "wallet",  "type": "address", "indexed": True},
            {"name": "paidBy",  "type": "address", "indexed": True},
            {"name": "months",  "type": "uint256", "indexed": False},
            {"name": "expiry",  "type": "uint256", "indexed": False},
            {"name": "paidBD",  "type": "uint256", "indexed": False},
        ],
    }
]

# ==============================================================================
# 🔒 Per-wallet lock registry (race condition guard)
# ==============================================================================
_wallet_locks: dict[str, threading.Lock] = {}
_wallet_locks_meta: threading.Lock = threading.Lock()


def _get_wallet_lock(wallet: str) -> threading.Lock:
    """Retorna (ou cria) o Lock específico desta wallet."""
    key = wallet.lower()
    with _wallet_locks_meta:
        if key not in _wallet_locks:
            _wallet_locks[key] = threading.Lock()
        return _wallet_locks[key]


# ==============================================================================
# 🗃️ DB — ensure subscriptions table e coluna subscription_expires em users
# ==============================================================================

def _ensure_subscriptions_table() -> None:
    """Cria tabela subscriptions e coluna subscription_expires em users (SQLite)."""
    with DB_LOCK:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address  TEXT    NOT NULL COLLATE NOCASE,
                chat_id         INTEGER,
                tier            TEXT    NOT NULL DEFAULT 'pro',
                status          TEXT    NOT NULL DEFAULT 'active',
                activated_at    TEXT    NOT NULL,
                expires_at      TEXT,
                tx_hash         TEXT    NOT NULL,
                log_index       INTEGER NOT NULL,
                months          INTEGER NOT NULL DEFAULT 1,
                metadata        TEXT    DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sub_tx
            ON subscriptions(tx_hash, log_index)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sub_wallet
            ON subscriptions(wallet_address COLLATE NOCASE)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sub_chat
            ON subscriptions(chat_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sub_expires
            ON subscriptions(expires_at)
        """)

        # Adiciona coluna subscription_expires em users se não existir
        try:
            conn.execute("ALTER TABLE users ADD COLUMN subscription_expires TEXT")
        except Exception:
            pass  # já existe — ignorar

        conn.commit()


# ==============================================================================
# 🔗 Web3 — inicializa provider com POA middleware (Polygon)
# ==============================================================================

def _build_web3():
    """Cria instância Web3 com ExtraDataToPOAMiddleware para Polygon."""
    from web3 import Web3

    rpc_url = os.environ.get("RPC_URL", "").strip()
    if not rpc_url:
        # fallback para RPC público Polygon
        rpc_url = "https://polygon-rpc.com"

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))

    # Aplica POA middleware (Polygon usa extraData extendido)
    try:
        from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    except ImportError:
        try:
            from web3.middleware import geth_poa_middleware
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        except Exception as e:
            logger.warning("[sub_worker] POA middleware não disponível: %s", e)

    return w3


def _build_contract(w3):
    """Retorna instância do contrato WEbdEXSubscription."""
    from web3 import Web3
    addr = Web3.to_checksum_address(_CONTRACT_ADDRESS)
    return w3.eth.contract(address=addr, abi=_SUBSCRIBED_ABI)


# ==============================================================================
# 🔍 CHECKPOINT — leitura e escrita de sub_last_block na config
# ==============================================================================

def _get_last_block(w3) -> int:
    """Lê o último bloco processado do config. Fallback: bloco atual - 1000."""
    val = get_config(_CONFIG_KEY_LAST_BLOCK, "")
    if val:
        try:
            return int(val)
        except ValueError:
            pass
    # Primeira execução — começa 1000 blocos atrás para não perder eventos recentes
    try:
        current = w3.eth.block_number
        return max(0, current - 1000)
    except Exception:
        return 0


def _save_last_block(block: int) -> None:
    """Persiste o checkpoint de bloco no config."""
    set_config(_CONFIG_KEY_LAST_BLOCK, str(block))


# ==============================================================================
# 💾 PERSISTÊNCIA — INSERT idempotente + update users
# ==============================================================================

def _persist_subscription(
    wallet: str,
    chat_id: Optional[int],
    months: int,
    expiry_ts: int,
    tx_hash: str,
    log_index: int,
    paid_bd: int,
) -> bool:
    """
    Insere subscription no SQLite com ON CONFLICT (tx_hash, log_index) DO NOTHING.
    Retorna True se inserção foi nova, False se já existia (duplicata idempotente).
    """
    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    expires_at: Optional[str] = None
    if expiry_ts > 0:
        try:
            expires_dt = datetime.fromtimestamp(expiry_ts, tz=timezone.utc)
            expires_at = expires_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            expires_at = None

    metadata = json.dumps({"paid_bd": str(paid_bd)})

    with DB_LOCK:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO subscriptions
                (wallet_address, chat_id, tier, status, activated_at, expires_at,
                 tx_hash, log_index, months, metadata)
            VALUES (?, ?, 'pro', 'active', ?, ?, ?, ?, ?, ?)
            """,
            (wallet.lower(), chat_id, now_str, expires_at,
             tx_hash.lower(), log_index, months, metadata),
        )
        inserted = cur.rowcount > 0

        if inserted and expires_at:
            # Atualiza subscription_expires na tabela users (se wallet registrada)
            conn.execute(
                """
                UPDATE users
                   SET subscription_expires = ?
                 WHERE LOWER(wallet) = LOWER(?)
                   AND (subscription_expires IS NULL OR subscription_expires < ?)
                """,
                (expires_at, wallet, expires_at),
            )

        conn.commit()

    return inserted


# ==============================================================================
# 🔍 LOOKUP — busca chat_id por wallet na tabela users
# ==============================================================================

def _get_chat_id_for_wallet(wallet: str) -> Optional[int]:
    """Retorna chat_id do usuário registrado com esta wallet, ou None."""
    with DB_LOCK:
        row = cursor.execute(
            "SELECT chat_id FROM users WHERE LOWER(wallet) = LOWER(?) AND chat_id IS NOT NULL LIMIT 1",
            (wallet,),
        ).fetchone()
    if row:
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return None
    return None


# ==============================================================================
# 📬 NOTIFICAÇÃO — Telegram
# ==============================================================================

def _notify_subscription(chat_id: int, wallet: str, months: int, expires_at: Optional[str]) -> None:
    """Envia mensagem de boas-vindas/confirmação de subscription ao usuário."""
    if send_html is None:
        logger.warning("[sub_worker] send_html não disponível — notificação ignorada.")
        return

    w_short = wallet[:6] + "..." + wallet[-4:] if len(wallet) > 10 else wallet
    exp_str = expires_at if expires_at else "N/A"

    text = (
        f"🎉 <b>Subscription ativada!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 Carteira: <code>{w_short}</code>\n"
        f"⭐ Plano: <b>PRO</b>\n"
        f"🗓️ Duração: <b>{months} {'mês' if months == 1 else 'meses'}</b>\n"
        f"⏰ Válida até: <code>{exp_str}</code>\n\n"
        f"<i>Sua assinatura foi detectada on-chain e ativada automaticamente.</i>"
    )

    try:
        send_html(chat_id, text)
    except Exception as e:
        logger.warning("[sub_worker] falha ao notificar chat_id=%s: %s", chat_id, e)


# ==============================================================================
# 🔄 CICLO PRINCIPAL — poll e processa eventos Subscribed
# ==============================================================================

def _process_event(event, w3) -> None:
    """Processa um evento Subscribed individual com per-wallet lock."""
    try:
        wallet    = str(event["args"]["wallet"]).lower()
        months    = int(event["args"]["months"])
        expiry_ts = int(event["args"]["expiry"])
        paid_bd   = int(event["args"]["paidBD"])
        tx_hash   = w3.to_hex(event["transactionHash"]) if hasattr(event["transactionHash"], "hex") else str(event["transactionHash"])
        log_index = int(event["logIndex"])
    except Exception as e:
        logger.error("[sub_worker] Falha ao parsear evento: %s", e)
        return

    wallet_lock = _get_wallet_lock(wallet)
    acquired = wallet_lock.acquire(timeout=_WALLET_LOCK_TIMEOUT)
    if not acquired:
        logger.warning("[sub_worker] Timeout ao adquirir lock para wallet %s — pulando evento", wallet[:12])
        return

    try:
        chat_id = _get_chat_id_for_wallet(wallet)

        expires_at: Optional[str] = None
        if expiry_ts > 0:
            try:
                expires_dt = datetime.fromtimestamp(expiry_ts, tz=timezone.utc)
                expires_at = expires_dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                expires_at = None

        is_new = _persist_subscription(
            wallet=wallet,
            chat_id=chat_id,
            months=months,
            expiry_ts=expiry_ts,
            tx_hash=tx_hash,
            log_index=log_index,
            paid_bd=paid_bd,
        )

        if is_new:
            logger.info(
                "[sub_worker] Nova subscription: wallet=%s months=%d expires=%s tx=%s",
                wallet[:12], months, expires_at or "N/A", tx_hash[:18],
            )
            if chat_id:
                _notify_subscription(chat_id, wallet, months, expires_at)
        else:
            logger.debug("[sub_worker] Evento duplicado ignorado: tx=%s log=%d", tx_hash[:18], log_index)

    finally:
        wallet_lock.release()


def _subscription_poll_cycle(w3, contract) -> None:
    """
    Busca eventos Subscribed do último bloco processado até o bloco atual.
    Atualiza checkpoint após processamento bem-sucedido.
    """
    try:
        current_block = w3.eth.block_number
    except Exception as e:
        logger.error("[sub_worker] Falha ao obter bloco atual: %s", e)
        return

    from_block = _get_last_block(w3) + 1
    to_block   = min(current_block, from_block + _BLOCKS_PER_POLL - 1)

    if from_block > current_block:
        logger.debug("[sub_worker] Sem blocos novos (from=%d current=%d)", from_block, current_block)
        return

    logger.debug("[sub_worker] Buscando eventos de bloco %d até %d", from_block, to_block)

    try:
        events = contract.events.Subscribed.get_logs(
            fromBlock=from_block,
            toBlock=to_block,
        )
    except Exception as e:
        logger.error("[sub_worker] Falha ao buscar logs de eventos: %s", e)
        return

    if events:
        logger.info("[sub_worker] %d evento(s) Subscribed encontrado(s) [blocos %d-%d]",
                    len(events), from_block, to_block)

    for event in events:
        try:
            _process_event(event, w3)
        except Exception as e:
            logger.error("[sub_worker] Erro ao processar evento: %s", e)

    # Atualiza checkpoint mesmo que não haja eventos — avança a janela
    _save_last_block(to_block)


# ==============================================================================
# 🧵 WORKER — thread registrada no _THREAD_REGISTRY do webdex_main.py
# ==============================================================================

def subscription_worker() -> None:
    """
    Worker on-chain de subscription.
    Aguarda 30s no boot, depois pollar eventos Subscribed a cada 60s.
    Registrado em webdex_main._THREAD_REGISTRY como 'subscription_worker'.
    """
    logger.info("[sub_worker] Worker iniciado — aguardando %ds (boot warmup)...", _BOOT_WAIT_S)
    time.sleep(_BOOT_WAIT_S)

    # Garante tabela existente (idempotente)
    try:
        _ensure_subscriptions_table()
        logger.info("[sub_worker] Tabela subscriptions pronta.")
    except Exception as e:
        logger.error("[sub_worker] Falha ao criar tabela subscriptions: %s", e)

    # Inicializa Web3 e contrato
    w3 = None
    contract = None

    while True:
        # Reconecta se necessário (graceful degradation)
        if w3 is None or contract is None:
            try:
                w3 = _build_web3()
                contract = _build_contract(w3)
                logger.info("[sub_worker] Web3 conectado ao contrato %s", _CONTRACT_ADDRESS[:12])
            except Exception as e:
                logger.error("[sub_worker] Falha ao inicializar Web3: %s — retry em %ds", e, _POLL_INTERVAL_S)
                w3 = None
                contract = None
                time.sleep(_POLL_INTERVAL_S)
                continue

        try:
            _subscription_poll_cycle(w3, contract)
        except Exception as e:
            logger.error("[sub_worker] Erro no ciclo de polling: %s", e)
            # Reset de conexão para forçar reconexão na próxima iteração
            w3 = None
            contract = None

        time.sleep(_POLL_INTERVAL_S)
