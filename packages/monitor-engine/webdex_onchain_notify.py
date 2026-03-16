from __future__ import annotations
"""
webdex_onchain_notify.py — Monitor On-Chain WEbdEX

Notifica #webdex-on-chain no Discord para:
  1. Nova carteira conectada  → primeiro OpenPosition no PAYMENTS
  2. Novo holder LOOP         → primeiro Transfer no LP_LOOP (9 dec)
  3. Novo envio LOOP          → Transfer significativo no LP_LOOP
  4. Novo holder WEbdEX       → GIGANTESCA conquista no TOKENPASS
  5. Relatório 2h             → IA comenta holders + supply WEbdEX
  6. LP transfers             → depósito/retirada/P2P acima de $500
"""

import time
import json
import logging
import os
import threading

from webdex_config import (
    logger, Web3, CONTRACTS, TOKENS_MAP,
    ABI_PAYMENTS, ABI_ERC20_TRANSFER,
    ADDR_LPLPUSD, ADDR_LPUSDT0, ADDR_USDT0,
)
from webdex_chain import (
    rpc_pool, web3,
    TOPIC_OPENPOSITION, TOPIC_TRANSFER,
    _is_429_error,
)
from webdex_db import DB_LOCK, cursor, conn, get_config, set_config
from webdex_discord_sync import _async_post

# ─────────────────────────────────────────────────────────────
# Endereços monitorados
# ─────────────────────────────────────────────────────────────
_PAYMENTS_AG  = Web3.to_checksum_address(CONTRACTS["AG_C_bd"]["PAYMENTS"])
_PAYMENTS_BD  = Web3.to_checksum_address(CONTRACTS["bd_v5"]["PAYMENTS"])

# LP_LOOP = token LOOP real (9 decimais) — ambos os ambientes
_LP_LOOP_AG   = Web3.to_checksum_address(CONTRACTS["AG_C_bd"]["LP_LOOP"])
_LP_LOOP_BD   = Web3.to_checksum_address(CONTRACTS["bd_v5"]["LP_LOOP"])
_LP_LOOP_LIST = [_LP_LOOP_AG, _LP_LOOP_BD]
_LOOP_DECIMALS = 9  # LP_LOOP token — conforme TOKEN_CONFIG (ADDR_LPLPUSD dec=9)

# WEbdEX token (TOKENPASS) — a cereja do bolo
_WEBDEX_TOKEN   = Web3.to_checksum_address(CONTRACTS["AG_C_bd"]["TOKENPASS"])
_WEBDEX_DECIMALS = 9
_WEBDEX_SUPPLY   = 369_369_369  # supply total on-chain
_WEBDEX_SYMBOL   = "WEbdEX"

# Carteira de deploy/lock (guarda tokens não circulantes)
# Definir WEBDEX_LOCKED_WALLET no .env para cálculo dinâmico de circulação.
# Fallback: valor real aferido em 2026-03-15 via Polygonscan
_WEBDEX_LOCKED_WALLET = os.getenv("WEBDEX_LOCKED_WALLET", "").strip()
_WEBDEX_CIRCULATING_FALLBACK = 17_880_110_829_994_900  # raw 9 dec = 17,880,110.8299949

# ABI mínima para totalSupply + balanceOf do WEbdEX token
_ABI_TOTAL_SUPPLY = [
    {"name": "totalSupply", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"name": "balanceOf", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint256"}]},
]

# Relatório 2h — controle de tempo
_REPORT_INTERVAL   = 7_200   # 2 horas em segundos
_last_webdex_report = 0.0    # timestamp do último relatório

# ─────────────────────────────────────────────────────────────
# Cores Discord
# ─────────────────────────────────────────────────────────────
_COLOR_WALLET   = 0xFFD700  # dourado — conquista desbloqueada
_COLOR_HOLDER   = 0xFFD700  # dourado — novo holder
_COLOR_TRANSFER = 0xA855F7  # roxo   — envio de token

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
_POLL_INTERVAL   = 30
_BLOCKS_PER_POLL = 50
_CONFIG_LAST_BLOCK = "onchain_notify_last_block"
_POLYGONSCAN_TX  = "https://polygonscan.com/tx/{}"
_POLYGONSCAN_ADDR = "https://polygonscan.com/address/{}"

# Mínimo de tokens para notificar envio (evita spam de micro-transfers)
_MIN_TRANSFER_TOKENS = 1  # 1 LOOP mínimo (8 decimals)


# ─────────────────────────────────────────────────────────────
# Setup tabelas SQLite
# ─────────────────────────────────────────────────────────────

def _ensure_tables():
    with DB_LOCK:
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS onchain_seen_wallets (
                wallet TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS onchain_seen_holders (
                holder TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS onchain_seen_webdex_holders (
                holder TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS onchain_notified_transfers (
                tx_hash   TEXT    NOT NULL,
                log_index INTEGER NOT NULL,
                PRIMARY KEY (tx_hash, log_index)
            );
        """)
        conn.commit()


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _short(addr: str) -> str:
    return f"{addr[:6]}…{addr[-4:]}"


def _fmt_tokens(raw: int, decimals: int = 18) -> str:
    val = raw / (10 ** decimals)
    if val >= 1_000_000:
        return f"{val / 1_000_000:,.2f}M"
    if val >= 1_000:
        return f"{val:,.2f}"
    return f"{val:.4f}".rstrip("0").rstrip(".")


def _is_new_wallet(wallet: str) -> bool:
    w = wallet.lower()
    with DB_LOCK:
        row = cursor.execute(
            "SELECT 1 FROM onchain_seen_wallets WHERE wallet=?", (w,)
        ).fetchone()
        return row is None


def _mark_wallet(wallet: str):
    with DB_LOCK:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO onchain_seen_wallets (wallet) VALUES (?)",
                (wallet.lower(),)
            )
            conn.commit()
        except Exception:
            pass


def _is_new_holder(addr: str) -> bool:
    a = addr.lower()
    with DB_LOCK:
        row = cursor.execute(
            "SELECT 1 FROM onchain_seen_holders WHERE holder=?", (a,)
        ).fetchone()
        return row is None


def _mark_holder(addr: str):
    with DB_LOCK:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO onchain_seen_holders (holder) VALUES (?)",
                (addr.lower(),)
            )
            conn.commit()
        except Exception:
            pass


def _transfer_notified(tx_hash: str, log_index: int) -> bool:
    with DB_LOCK:
        return cursor.execute(
            "SELECT 1 FROM onchain_notified_transfers WHERE tx_hash=? AND log_index=?",
            (tx_hash, log_index)
        ).fetchone() is not None


def _mark_transfer(tx_hash: str, log_index: int):
    with DB_LOCK:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO onchain_notified_transfers VALUES (?,?)",
                (tx_hash, log_index)
            )
            conn.commit()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# 1. NOVA CARTEIRA CONECTADA
# ─────────────────────────────────────────────────────────────

def _fmt_profit(profit_raw: int) -> str:
    """Formata lucro em USDT (6 decimais). Retorna '' se zero."""
    if profit_raw == 0:
        return ""
    val  = profit_raw / 1e6
    sign = "+" if val >= 0 else ""
    return f"{sign}${val:,.2f} USDT"


def _check_new_wallets(from_b: int, to_b: int):
    """Detecta novas carteiras via OpenPosition nos contratos PAYMENTS."""
    try:
        logs = rpc_pool.get_logs({
            "fromBlock": Web3.to_hex(from_b),
            "toBlock":   Web3.to_hex(to_b),
            "address":   [_PAYMENTS_AG, _PAYMENTS_BD],
            "topics":    [TOPIC_OPENPOSITION],
        })
    except Exception as e:
        logger.warning("[onchain] get_logs wallets: %s", e)
        return

    contract_ag = web3.eth.contract(address=_PAYMENTS_AG, abi=json.loads(ABI_PAYMENTS))
    contract_bd = web3.eth.contract(address=_PAYMENTS_BD, abi=json.loads(ABI_PAYMENTS))

    for log in logs:
        try:
            contract_addr = log["address"].lower()
            contract = contract_ag if contract_addr == _PAYMENTS_AG.lower() else contract_bd

            decoded = contract.events.OpenPosition().process_log(log)
            user    = decoded["args"]["user"]
            tx_hash = log["transactionHash"].hex()

            if not _is_new_wallet(user):
                continue

            # Extrai lucro da 1ª operação
            profit_raw = 0
            try:
                profit_raw = int(decoded["args"]["details"]["profit"])
            except Exception:
                pass

            _notify_new_wallet(user, tx_hash, profit_raw)
            _mark_wallet(user)
            logger.info("[onchain] Nova carteira: %s", _short(user))

        except Exception as e:
            logger.warning("[onchain] Erro ao processar wallet log: %s", e)


def _notify_new_wallet(wallet: str, tx_hash: str, profit_raw: int = 0):
    profit_line = ""
    if profit_raw:
        fmt = _fmt_profit(profit_raw)
        if fmt:
            profit_line = f"💰 1ª operação: **{fmt}**\n"

    _async_post({"embeds": [{
        "title": "🏆 CONQUISTA DESBLOQUEADA",
        "description": (
            f"**Nova Carteira Conectada — WEbdEX**\n\n"
            f"👤 [`{_short(wallet)}`]({_POLYGONSCAN_ADDR.format(wallet)})\n"
            f"{profit_line}\n"
            f"[🔗 Ver no Polygonscan]({_POLYGONSCAN_TX.format(tx_hash)})"
        ),
        "color": _COLOR_WALLET,
        "footer": {"text": "WEbdEX Protocol · Polygon"},
    }]})


# ─────────────────────────────────────────────────────────────
# 2. NOVO HOLDER DO TOKEN (TOKENPASS / LOOP)
# ─────────────────────────────────────────────────────────────

def _check_new_holders(from_b: int, to_b: int):
    """Detecta novos holders do LP_LOOP (LOOP, 8 dec) via Transfer events."""
    ZERO = "0x0000000000000000000000000000000000000000"

    try:
        logs = rpc_pool.get_logs({
            "fromBlock": Web3.to_hex(from_b),
            "toBlock":   Web3.to_hex(to_b),
            "address":   _LP_LOOP_LIST,
            "topics":    [TOPIC_TRANSFER],
        })
    except Exception as e:
        logger.warning("[onchain] get_logs holders: %s", e)
        return

    for log in logs:
        try:
            lp_addr  = log["address"]
            contract = web3.eth.contract(address=lp_addr, abi=json.loads(ABI_ERC20_TRANSFER))
            decoded  = contract.events.Transfer().process_log(log)
            to_addr  = decoded["args"]["to"]
            tx_hash  = log["transactionHash"].hex()

            # Ignora mint-para-zero (burn)
            if to_addr.lower() == ZERO:
                continue

            if not _is_new_holder(to_addr):
                continue

            amount = decoded["args"]["value"]
            _notify_new_holder(to_addr, amount, tx_hash)
            _mark_holder(to_addr)
            logger.info("[onchain] Novo holder LOOP: %s", _short(to_addr))

        except Exception as e:
            logger.warning("[onchain] Erro ao processar holder log: %s", e)


def _notify_new_holder(addr: str, amount: int, tx_hash: str):
    amt_fmt = _fmt_tokens(amount, _LOOP_DECIMALS)
    _async_post({"embeds": [{
        "title": "🪙 Novo Holder — LOOP Token",
        "description": (
            f"👤 [`{_short(addr)}`]({_POLYGONSCAN_ADDR.format(addr)})\n"
            f"💰 Recebeu: `{amt_fmt} LOOP`\n\n"
            f"[🔗 Ver no Polygonscan]({_POLYGONSCAN_TX.format(tx_hash)})"
        ),
        "color": _COLOR_HOLDER,
        "footer": {"text": "WEbdEX Protocol · TOKENPASS"},
    }]})


# ─────────────────────────────────────────────────────────────
# 3. NOVOS ENVIOS DE TOKEN (TOKENPASS)
# ─────────────────────────────────────────────────────────────

def _check_token_transfers(from_b: int, to_b: int):
    """Notifica transfers significativos no LP_LOOP (LOOP, 8 dec)."""
    ZERO    = "0x0000000000000000000000000000000000000000"
    MIN_RAW = _MIN_TRANSFER_TOKENS * (10 ** _LOOP_DECIMALS)

    try:
        logs = rpc_pool.get_logs({
            "fromBlock": Web3.to_hex(from_b),
            "toBlock":   Web3.to_hex(to_b),
            "address":   _LP_LOOP_LIST,
            "topics":    [TOPIC_TRANSFER],
        })
    except Exception as e:
        logger.warning("[onchain] get_logs transfers: %s", e)
        return

    for log in logs:
        try:
            lp_addr   = log["address"]
            contract  = web3.eth.contract(address=lp_addr, abi=json.loads(ABI_ERC20_TRANSFER))
            decoded   = contract.events.Transfer().process_log(log)
            from_addr = decoded["args"]["from"]
            to_addr   = decoded["args"]["to"]
            amount    = decoded["args"]["value"]
            tx_hash   = log["transactionHash"].hex()
            log_index = log["logIndex"]

            # Ignora mint (from=zero) e burn (to=zero)
            if from_addr.lower() == ZERO or to_addr.lower() == ZERO:
                continue

            # Ignora micro-transfers
            if amount < MIN_RAW:
                continue

            if _transfer_notified(tx_hash, log_index):
                continue

            _notify_transfer(from_addr, to_addr, amount, tx_hash)
            _mark_transfer(tx_hash, log_index)
            logger.info(
                "[onchain] Transfer LOOP: %s → %s (%s)",
                _short(from_addr), _short(to_addr), _fmt_tokens(amount, _LOOP_DECIMALS)
            )

        except Exception as e:
            logger.warning("[onchain] Erro ao processar transfer log: %s", e)


def _notify_transfer(from_addr: str, to_addr: str, amount: int, tx_hash: str):
    amt_fmt = _fmt_tokens(amount, _LOOP_DECIMALS)
    _async_post({"embeds": [{
        "title": "📤 Envio de Token — LOOP",
        "description": (
            f"💰 `{amt_fmt} LOOP`\n\n"
            f"📤 De:   [`{_short(from_addr)}`]({_POLYGONSCAN_ADDR.format(from_addr)})\n"
            f"📥 Para: [`{_short(to_addr)}`]({_POLYGONSCAN_ADDR.format(to_addr)})\n\n"
            f"[🔗 Ver no Polygonscan]({_POLYGONSCAN_TX.format(tx_hash)})"
        ),
        "color": _COLOR_TRANSFER,
        "footer": {"text": "WEbdEX Protocol · TOKENPASS"},
    }]})


# ─────────────────────────────────────────────────────────────
# 4. NOVO HOLDER DO TOKEN WEbdEX (TOKENPASS) — GIGANTESCA CONQUISTA
# ─────────────────────────────────────────────────────────────

def _is_new_webdex_holder(addr: str) -> bool:
    a = addr.lower()
    with DB_LOCK:
        return cursor.execute(
            "SELECT 1 FROM onchain_seen_webdex_holders WHERE holder=?", (a,)
        ).fetchone() is None


def _mark_webdex_holder(addr: str):
    with DB_LOCK:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO onchain_seen_webdex_holders (holder) VALUES (?)",
                (addr.lower(),)
            )
            conn.commit()
        except Exception:
            pass


def _count_webdex_holders() -> int:
    """Retorna total de endereços no DB (histórico — inclui saldo zero)."""
    with DB_LOCK:
        row = cursor.execute(
            "SELECT COUNT(*) FROM onchain_seen_webdex_holders"
        ).fetchone()
        return row[0] if row else 0


_active_holders_cache: dict = {"count": 0, "ts": 0.0}
_ACTIVE_CACHE_TTL = 7_200  # 2 horas — mesmo intervalo do relatório


def _count_active_webdex_holders() -> int:
    """Conta holders com saldo > 0 via balanceOf. Cacheado por 2h."""
    import time as _t
    now = _t.time()
    if now - _active_holders_cache["ts"] < _ACTIVE_CACHE_TTL and _active_holders_cache["count"] > 0:
        return _active_holders_cache["count"]

    abi = [{"name": "balanceOf", "type": "function", "stateMutability": "view",
            "inputs": [{"name": "account", "type": "address"}],
            "outputs": [{"type": "uint256"}]}]
    c = web3.eth.contract(address=_WEBDEX_TOKEN, abi=abi)

    with DB_LOCK:
        rows = cursor.execute(
            "SELECT holder FROM onchain_seen_webdex_holders"
        ).fetchall()

    ativos = 0
    for (addr,) in rows:
        try:
            if c.functions.balanceOf(web3.to_checksum_address(addr)).call() > 0:
                ativos += 1
        except Exception:
            pass

    _active_holders_cache["count"] = ativos
    _active_holders_cache["ts"]    = now
    logger.info("[onchain] Holders ativos WEbdEX: %d / %d no DB", ativos, len(rows))
    return ativos


def _backfill_webdex_holders():
    """
    Varre histórico de Transfer events do token WEbdEX e popula
    onchain_seen_webdex_holders. Salva progresso a cada batch — retoma de onde
    parou em caso de restart antes de concluir.
    """
    _BACKFILL_DONE_KEY     = "webdex_holders_backfill_done"
    _BACKFILL_PROGRESS_KEY = "webdex_holders_backfill_block"

    if get_config(_BACKFILL_DONE_KEY):
        return  # já concluído anteriormente

    ZERO    = "0x0000000000000000000000000000000000000000"
    BATCH   = 2000
    _DEPLOY_BLOCK = 47_993_248  # bloco do primeiro Transfer do token WEbdEX

    try:
        current = web3.eth.block_number
        total_start = _DEPLOY_BLOCK

        # Retoma do último bloco processado (se houver)
        saved = get_config(_BACKFILL_PROGRESS_KEY)
        from_b = int(saved) + 1 if saved else total_start

        if from_b >= current:
            # progresso salvo já cobre tudo
            set_config(_BACKFILL_DONE_KEY, "1")
            return

        logger.info(
            "[onchain] Backfill WEbdEX holders — bloco %d → %d (%d blocos restantes)",
            from_b, current, current - from_b,
        )

        contract = web3.eth.contract(
            address=_WEBDEX_TOKEN, abi=json.loads(ABI_ERC20_TRANSFER)
        )
        found = 0

        while from_b < current:
            to_b = min(from_b + BATCH - 1, current)
            try:
                logs = rpc_pool.get_logs({
                    "fromBlock": Web3.to_hex(from_b),
                    "toBlock":   Web3.to_hex(to_b),
                    "address":   _WEBDEX_TOKEN,
                    "topics":    [TOPIC_TRANSFER],
                })
                for log in logs:
                    try:
                        decoded = contract.events.Transfer().process_log(log)
                        to_addr = decoded["args"]["to"]
                        if to_addr.lower() != ZERO and _is_new_webdex_holder(to_addr):
                            _mark_webdex_holder(to_addr)
                            found += 1
                    except Exception:
                        pass
            except Exception as e:
                logger.warning("[onchain] Backfill batch %d: %s", from_b, e)
                time.sleep(3)

            # Salva progresso a cada batch — retoma aqui em caso de restart
            set_config(_BACKFILL_PROGRESS_KEY, str(to_b))
            from_b = to_b + 1
            time.sleep(0.15)

        set_config(_BACKFILL_DONE_KEY, "1")
        logger.info(
            "[onchain] Backfill concluído — %d novos holders WEbdEX | total DB: %d",
            found, _count_webdex_holders(),
        )

    except Exception as e:
        logger.warning("[onchain] Backfill falhou: %s", e)


def _check_webdex_holders(from_b: int, to_b: int):
    """Detecta novos holders do token WEbdEX (TOKENPASS) — notificação GIGANTE."""
    ZERO = "0x0000000000000000000000000000000000000000"
    try:
        logs = rpc_pool.get_logs({
            "fromBlock": Web3.to_hex(from_b),
            "toBlock":   Web3.to_hex(to_b),
            "address":   _WEBDEX_TOKEN,
            "topics":    [TOPIC_TRANSFER],
        })
    except Exception as e:
        logger.warning("[onchain] get_logs webdex_holders: %s", e)
        return

    contract = web3.eth.contract(address=_WEBDEX_TOKEN, abi=json.loads(ABI_ERC20_TRANSFER))

    for log in logs:
        try:
            decoded = contract.events.Transfer().process_log(log)
            to_addr = decoded["args"]["to"]
            tx_hash = log["transactionHash"].hex()

            if to_addr.lower() == ZERO:
                continue
            if not _is_new_webdex_holder(to_addr):
                continue

            amount       = decoded["args"]["value"]
            holder_count = _count_webdex_holders() + 1  # +1 o atual
            _notify_webdex_holder(to_addr, amount, tx_hash, holder_count)
            _mark_webdex_holder(to_addr)
            logger.info("[onchain] 💎 Novo holder WEbdEX #%d: %s", holder_count, _short(to_addr))

        except Exception as e:
            logger.warning("[onchain] Erro ao processar webdex holder log: %s", e)


def _notify_webdex_holder(addr: str, amount: int, tx_hash: str, holder_count: int):
    amt_fmt = _fmt_tokens(amount, _WEBDEX_DECIMALS)

    description = (
        f"**A família WEbdEX acabou de crescer.**\n\n"
        f"🌍 Holder **#{holder_count:,}** na rede\n"
        f"👤 [`{_short(addr)}`]({_POLYGONSCAN_ADDR.format(addr)})\n"
        f"💎 Recebeu: `{amt_fmt} {_WEBDEX_SYMBOL}`\n\n"
        f"📊 Supply total: `{_WEBDEX_SUPPLY:,} {_WEBDEX_SYMBOL}`\n\n"
        f"[🔗 Ver no Polygonscan]({_POLYGONSCAN_TX.format(tx_hash)})"
    )

    _async_post({"embeds": [{
        "title": f"💎 NOVO HOLDER #{holder_count:,} — TOKEN {_WEBDEX_SYMBOL}",
        "description": description,
        "color": 0xFFD700,
        "footer": {"text": f"WEbdEX Protocol · Token de Soberania Digital · Polygon"},
        "thumbnail": {"url": "https://webdex.app/logo.png"},
    }]})


# ─────────────────────────────────────────────────────────────
# 5. RELATÓRIO 2H — IA COMENTA ACHIEVEMENTS DO TOKEN WEbdEX
# ─────────────────────────────────────────────────────────────

def _webdex_periodic_report():
    """Gera e posta relatório a cada 2h com IA comentando o token WEbdEX."""
    global _last_webdex_report

    now = time.time()
    if now - _last_webdex_report < _REPORT_INTERVAL:
        return
    _last_webdex_report = now

    try:
        holder_count  = _count_active_webdex_holders()

        # Circulação real = totalSupply - carteira de lock (deploy wallet)
        try:
            c = web3.eth.contract(address=_WEBDEX_TOKEN, abi=_ABI_TOTAL_SUPPLY)
            total_raw = c.functions.totalSupply().call()

            if _WEBDEX_LOCKED_WALLET:
                try:
                    locked_raw = c.functions.balanceOf(
                        Web3.to_checksum_address(_WEBDEX_LOCKED_WALLET)
                    ).call()
                    # Valida: locked deve representar entre 50% e 99.9% do supply
                    if total_raw > 0 and 0.5 <= locked_raw / total_raw <= 0.999:
                        circ_raw = total_raw - locked_raw
                    else:
                        circ_raw = _WEBDEX_CIRCULATING_FALLBACK
                except Exception:
                    circ_raw = _WEBDEX_CIRCULATING_FALLBACK
            else:
                circ_raw = _WEBDEX_CIRCULATING_FALLBACK

            supply_fmt = f"{circ_raw / (10 ** _WEBDEX_DECIMALS):,.2f}"
        except Exception:
            supply_fmt = f"{_WEBDEX_CIRCULATING_FALLBACK / (10 ** _WEBDEX_DECIMALS):,.2f}"

        # Gera mensagem com IA
        try:
            from webdex_ai import call_openai
            prompt = (
                f"Você é a voz oficial do protocolo WEbdEX no Discord, canal #webdex-on-chain. "
                f"Escreva uma mensagem curta (4-6 linhas), inspiradora e poderosa sobre o token WEbdEX. "
                f"Dados atuais: {holder_count} holders confirmados, {supply_fmt} WEbdEX em circulação (dos 369.369.369 totais). "
                f"Mencione crescimento, soberania financeira, comunidade e potencial do protocolo. "
                f"Use 1-2 emojis no máximo. Seja direto, impactante, sem exageros. "
                f"NÃO use markdown (sem **, sem #). Responda APENAS o texto da mensagem, sem prefácio."
            )
            ai_text = call_openai(
                [{"role": "user", "content": prompt}],
                model="anthropic/claude-haiku-4-5"
            )
        except Exception as e:
            logger.warning("[onchain] IA report falhou: %s", e)
            ai_text = (
                f"O token WEbdEX continua crescendo. "
                f"{holder_count} holders confirmados na rede. "
                f"{supply_fmt} WEbdEX em circulação. "
                f"A soberania financeira não para."
            )

        _async_post({"embeds": [{
            "title": f"📡 TOKEN {_WEBDEX_SYMBOL} — RELATÓRIO DE CRESCIMENTO",
            "description": (
                f"{ai_text}\n\n"
                f"──────────────────────\n"
                f"👥 Holders ativos: **{holder_count:,}**\n"
                f"💎 Em circulação: **{supply_fmt} {_WEBDEX_SYMBOL}**\n"
                f"🔗 [Ver token no Polygonscan]({_POLYGONSCAN_ADDR.format(_WEBDEX_TOKEN)})"
            ),
            "color": 0x6C3FE8,
            "footer": {"text": "WEbdEX Protocol · Relatório automático a cada 2h"},
        }]})
        logger.info("[onchain] Relatório WEbdEX postado — %d holders", holder_count)

    except Exception as e:
        logger.warning("[onchain] Erro no relatório WEbdEX: %s", e)


# ─────────────────────────────────────────────────────────────
# 6. LP TOKEN TRANSFERS (LPLPUSD)
# ─────────────────────────────────────────────────────────────

_LP_TOKENS: dict = {}  # preenchido em _init_lp_tokens()

_ABI_LP_MINI = json.dumps([
    {
        "name": "getReserves", "type": "function", "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "reserve0", "type": "uint112"},
            {"name": "reserve1", "type": "uint112"},
            {"name": "blockTimestampLast", "type": "uint32"},
        ],
    },
    {
        "name": "totalSupply", "type": "function", "stateMutability": "view",
        "inputs": [], "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "token0", "type": "function", "stateMutability": "view",
        "inputs": [], "outputs": [{"name": "", "type": "address"}],
    },
])

_COLOR_LP_DEPOSIT    = 0x00FFB2  # verde  — capital entrando
_COLOR_LP_WITHDRAWAL = 0xFF6B35  # laranja — capital saindo
_COLOR_LP_PTRANSFER  = 0x38BDF8  # azul   — movimento interno

_MIN_LP_USD = 500.0  # mínimo $500 para notificar

_lp_price_cache: dict = {}  # lp_addr_lower → (price_usd, timestamp)
_LP_CACHE_TTL = 300  # 5 min


def _init_lp_tokens():
    """Popula _LP_TOKENS após imports estarem disponíveis."""
    global _LP_TOKENS
    try:
        _stable = ADDR_USDT0.lower()
        _LP_TOKENS = {
            ADDR_LPLPUSD.lower(): {
                "sym":    "LP-USD",
                "icon":   "🟣",
                "dec":    9,
                "stable": _stable,
            },
            # ADDR_LPUSDT0 removido: não implementa getReserves (não é Uniswap V2 pair)
        }
    except Exception as e:
        logger.warning("[onchain] _init_lp_tokens: %s", e)


def _lp_price_usd(lp_addr: str) -> float:
    """USD por 1 LP token (18 dec). Usa reserva do token estável × 2 / totalSupply."""
    import time as _t
    now = _t.time()
    key = lp_addr.lower()
    cached = _lp_price_cache.get(key)
    if cached and (now - cached[1]) < _LP_CACHE_TTL:
        return cached[0]
    try:
        contract = web3.eth.contract(
            address=Web3.to_checksum_address(lp_addr),
            abi=json.loads(_ABI_LP_MINI),
        )
        r0, r1, _ = contract.functions.getReserves().call()
        total     = contract.functions.totalSupply().call()
        token0    = contract.functions.token0().call().lower()
        if total == 0:
            return 0.0

        meta         = _LP_TOKENS.get(key, {})
        stable_addr  = meta.get("stable", "")
        lp_dec       = meta.get("dec", 18)
        stable_dec   = 6  # USDT0 = 6 decimais

        stable_reserve = r0 if token0 == stable_addr else r1
        tvl_usd        = 2 * (stable_reserve / (10 ** stable_dec))
        price          = tvl_usd / (total / (10 ** lp_dec))

        _lp_price_cache[key] = (price, now)
        return price
    except Exception as e:
        logger.warning("[onchain] lp price (%s…): %s", lp_addr[:10], e)
        return 0.0


def _lp_value_usd(lp_addr: str, raw_amount: int) -> float:
    dec   = _LP_TOKENS.get(lp_addr.lower(), {}).get("dec", 18)
    return _lp_price_usd(lp_addr) * (raw_amount / (10 ** dec))


def _check_lp_transfers(from_b: int, to_b: int):
    """Monitora Transfer do LP token — depósito, retirada e P2P acima de $500."""
    if not _LP_TOKENS:
        return

    ZERO   = "0x0000000000000000000000000000000000000000"
    lp_list = [Web3.to_checksum_address(a) for a in _LP_TOKENS]

    try:
        logs = rpc_pool.get_logs({
            "fromBlock": Web3.to_hex(from_b),
            "toBlock":   Web3.to_hex(to_b),
            "address":   lp_list,
            "topics":    [TOPIC_TRANSFER],
        })
    except Exception as e:
        logger.warning("[onchain] get_logs lp: %s", e)
        return

    for log in logs:
        try:
            lp_addr   = log["address"]
            contract  = web3.eth.contract(
                address=lp_addr, abi=json.loads(ABI_ERC20_TRANSFER)
            )
            decoded   = contract.events.Transfer().process_log(log)
            from_addr = decoded["args"]["from"]
            to_addr   = decoded["args"]["to"]
            amount    = decoded["args"]["value"]
            tx_hash   = log["transactionHash"].hex()
            log_index = log["logIndex"]

            if _transfer_notified(tx_hash, log_index):
                continue

            value_usd = _lp_value_usd(lp_addr, amount)
            if value_usd < _MIN_LP_USD:
                continue

            meta     = _LP_TOKENS.get(lp_addr.lower(), {})
            sym      = meta.get("sym", "LP")
            icon     = meta.get("icon", "🟣")
            dec      = meta.get("dec", 18)
            amt_fmt  = _fmt_tokens(amount, dec)
            val_fmt  = f"${value_usd:,.2f}"

            is_mint = from_addr.lower() == ZERO
            is_burn = to_addr.lower()   == ZERO

            if is_mint:
                _notify_lp_deposit(to_addr, amt_fmt, val_fmt, sym, icon, tx_hash)
                logger.info("[onchain] LP deposit: %s %s (%s)", amt_fmt, sym, val_fmt)
            elif is_burn:
                _notify_lp_withdrawal(from_addr, amt_fmt, val_fmt, sym, icon, tx_hash)
                logger.info("[onchain] LP withdraw: %s %s (%s)", amt_fmt, sym, val_fmt)
            else:
                _notify_lp_ptransfer(from_addr, to_addr, amt_fmt, val_fmt, sym, icon, tx_hash)
                logger.info("[onchain] LP P2P: %s %s (%s)", amt_fmt, sym, val_fmt)

            _mark_transfer(tx_hash, log_index)

        except Exception as e:
            logger.warning("[onchain] Erro ao processar LP log: %s", e)


def _notify_lp_deposit(addr: str, amt_fmt: str, val_fmt: str,
                        sym: str, icon: str, tx_hash: str):
    _async_post({"embeds": [{
        "title": f"🟢 Depósito de Liquidez — {sym}",
        "description": (
            f"{icon} `{amt_fmt} {sym}`  ≈  **{val_fmt} USD**\n\n"
            f"👤 [`{_short(addr)}`]({_POLYGONSCAN_ADDR.format(addr)})\n\n"
            f"[🔗 Ver no Polygonscan]({_POLYGONSCAN_TX.format(tx_hash)})"
        ),
        "color": _COLOR_LP_DEPOSIT,
        "footer": {"text": "WEbdEX Protocol · Liquidity Pool"},
    }]})


def _notify_lp_withdrawal(addr: str, amt_fmt: str, val_fmt: str,
                           sym: str, icon: str, tx_hash: str):
    _async_post({"embeds": [{
        "title": f"🔴 Retirada de Liquidez — {sym}",
        "description": (
            f"{icon} `{amt_fmt} {sym}`  ≈  **{val_fmt} USD**\n\n"
            f"👤 [`{_short(addr)}`]({_POLYGONSCAN_ADDR.format(addr)})\n\n"
            f"[🔗 Ver no Polygonscan]({_POLYGONSCAN_TX.format(tx_hash)})"
        ),
        "color": _COLOR_LP_WITHDRAWAL,
        "footer": {"text": "WEbdEX Protocol · Liquidity Pool"},
    }]})


def _notify_lp_ptransfer(from_addr: str, to_addr: str, amt_fmt: str,
                          val_fmt: str, sym: str, icon: str, tx_hash: str):
    _async_post({"embeds": [{
        "title": f"🔄 Transferência LP — {sym}",
        "description": (
            f"{icon} `{amt_fmt} {sym}`  ≈  **{val_fmt} USD**\n\n"
            f"📤 De:   [`{_short(from_addr)}`]({_POLYGONSCAN_ADDR.format(from_addr)})\n"
            f"📥 Para: [`{_short(to_addr)}`]({_POLYGONSCAN_ADDR.format(to_addr)})\n\n"
            f"[🔗 Ver no Polygonscan]({_POLYGONSCAN_TX.format(tx_hash)})"
        ),
        "color": _COLOR_LP_PTRANSFER,
        "footer": {"text": "WEbdEX Protocol · Liquidity Pool"},
    }]})


# ─────────────────────────────────────────────────────────────
# Worker principal — combina os 3 monitors em um loop
# ─────────────────────────────────────────────────────────────

def onchain_notify_worker():
    """
    Thread background: monitora eventos on-chain WEbdEX a cada 30s.
    Cobre: nova carteira, novo holder LOOP, envios de token, LP transfers.
    """
    _ensure_tables()
    _init_lp_tokens()
    logger.info("[onchain] Worker iniciado → PAYMENTS + LP_LOOP + WEbdEX token + LP-USD")

    # Backfill histórico de holders WEbdEX em thread separada
    threading.Thread(target=_backfill_webdex_holders, name="webdex_holders_backfill", daemon=True).start()

    try:
        last_block = int(get_config(_CONFIG_LAST_BLOCK) or 0)
    except Exception:
        last_block = 0

    if last_block == 0:
        try:
            last_block = web3.eth.block_number - 100
        except Exception:
            last_block = 0

    while True:
        try:
            current = web3.eth.block_number
            if current <= last_block:
                time.sleep(_POLL_INTERVAL)
                continue

            from_b = last_block + 1
            to_b   = min(current, last_block + _BLOCKS_PER_POLL)

            _check_new_wallets(from_b, to_b)
            _check_new_holders(from_b, to_b)
            _check_token_transfers(from_b, to_b)
            _check_webdex_holders(from_b, to_b)
            _check_lp_transfers(from_b, to_b)
            _webdex_periodic_report()

            last_block = to_b
            set_config(_CONFIG_LAST_BLOCK, str(last_block))

        except Exception as e:
            if _is_429_error(e):
                logger.warning("[onchain] Rate limit RPC — aguardando 60s")
                time.sleep(60)
                continue
            logger.warning("[onchain] Erro no worker: %s", e)
            time.sleep(10)
            continue

        time.sleep(_POLL_INTERVAL)
