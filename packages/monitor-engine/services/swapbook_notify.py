from __future__ import annotations
"""
webdex_swapbook_notify.py — Monitor do SwapBook WEbdEX

Monitora o contrato SwapBook (0x68c1d845...) na Polygon e notifica
o canal #webdex-on-chain no Discord quando:
  - "Create Swap"  → nova oferta criada no livro de ordens
  - "Swap Tokens"  → swap executado (trade fechado)

Evento do contrato:
  Transaction(address from, address to, string method,
              address leftToken, uint256 leftTokenAmount,
              address rightToken, uint256 rightTokenAmount,
              uint256 swapId, uint256 timeStamp, uint256 fee)
"""

import time
import json
import logging
import threading

from webdex_config import logger, TOKENS_MAP, Web3
from webdex_chain import rpc_pool, web3, _is_429_error
from webdex_db import DB_LOCK, cursor, conn, get_config, set_config
from webdex_discord_sync import _async_post, _WEBHOOK_SWAPS, notify_onchain_event, inc_pulse_stat

# ─────────────────────────────────────────────────────────────
# Contrato
# ─────────────────────────────────────────────────────────────
SWAPBOOK_ADDR = Web3.to_checksum_address("0x68c1d8454f3c8bc9a9eb7d4910aaa67bd687890d")

_ABI_SWAPBOOK = json.dumps([{
    "anonymous": False,
    "inputs": [
        {"indexed": True,  "name": "from",             "type": "address"},
        {"indexed": True,  "name": "to",               "type": "address"},
        {"indexed": False, "name": "method",           "type": "string"},
        {"indexed": False, "name": "leftToken",        "type": "address"},
        {"indexed": False, "name": "leftTokenAmount",  "type": "uint256"},
        {"indexed": False, "name": "rightToken",       "type": "address"},
        {"indexed": False, "name": "rightTokenAmount", "type": "uint256"},
        {"indexed": False, "name": "swapId",           "type": "uint256"},
        {"indexed": False, "name": "timeStamp",        "type": "uint256"},
        {"indexed": False, "name": "fee",              "type": "uint256"},
    ],
    "name": "Transaction",
    "type": "event",
}])

TOPIC_TRANSACTION = Web3.to_hex(
    Web3.keccak(text="Transaction(address,address,string,address,uint256,address,uint256,uint256,uint256,uint256)")
)

# ─────────────────────────────────────────────────────────────
# Cores Discord
# ─────────────────────────────────────────────────────────────
_COLOR_CREATE  = 0x00FFB2  # verde WEbdEX — nova oferta
_COLOR_EXECUTE = 0x38BDF8  # azul WEbdEX  — swap executado

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
_POLL_INTERVAL    = 30   # segundos entre polls
_BLOCKS_PER_POLL  = 50   # ~30s na Polygon (bloco ~2s)
_CONFIG_LAST_BLOCK = "swapbook_last_block"
_POLYGONSCAN_TX   = "https://polygonscan.com/tx/{}"

# ─────────────────────────────────────────────────────────────
# Contador horário em memória (exportado para agendador_horario)
# ─────────────────────────────────────────────────────────────
_swap_lock  = threading.Lock()
_swap_stats: dict = {"create": 0, "execute": 0}


def _inc_swap(method: str) -> None:
    with _swap_lock:
        if method == "Create Swap":
            _swap_stats["create"] += 1
        else:
            _swap_stats["execute"] += 1


def get_swap_stats_and_reset() -> dict:
    """Retorna contadores da hora e zera para próximo ciclo."""
    with _swap_lock:
        stats = {"create": _swap_stats["create"], "execute": _swap_stats["execute"]}
        _swap_stats["create"]  = 0
        _swap_stats["execute"] = 0
    return stats


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _token_label(address: str) -> str:
    """Retorna 'ícone SÍMBOLO' para tokens conhecidos, endereço curto para desconhecidos."""
    meta = TOKENS_MAP.get(address.lower())
    if meta:
        return f"{meta['icon']} {meta['sym']}"
    return f"`{address[:6]}…{address[-4:]}`"


def _fmt_amount(raw: int, address: str) -> str:
    """Formata valor com casas decimais corretas."""
    meta = TOKENS_MAP.get(address.lower())
    dec  = meta["dec"] if meta else 18
    val  = raw / (10 ** dec)
    if val >= 1_000_000:
        return f"{val / 1_000_000:,.2f}M"
    if val >= 1_000:
        return f"{val:,.2f}"
    return f"{val:.4f}".rstrip("0").rstrip(".")


def _short(addr: str) -> str:
    return f"{addr[:6]}…{addr[-4:]}"


# ─────────────────────────────────────────────────────────────
# Deduplicação (SQLite)
# ─────────────────────────────────────────────────────────────

def _ensure_table():
    with DB_LOCK:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS swapbook_notified (
                tx_hash   TEXT    NOT NULL,
                log_index INTEGER NOT NULL,
                PRIMARY KEY (tx_hash, log_index)
            )
        """)
        conn.commit()


def _already_notified(tx_hash: str, log_index: int) -> bool:
    with DB_LOCK:
        return cursor.execute(
            "SELECT 1 FROM swapbook_notified WHERE tx_hash=? AND log_index=?",
            (tx_hash, log_index)
        ).fetchone() is not None


def _mark_notified(tx_hash: str, log_index: int):
    with DB_LOCK:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO swapbook_notified (tx_hash, log_index) VALUES (?,?)",
                (tx_hash, log_index)
            )
            conn.commit()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# Notificações Discord
# ─────────────────────────────────────────────────────────────

def _notify_create(args: dict, tx_hash: str):
    left  = _token_label(args["leftToken"])
    right = _token_label(args["rightToken"])
    l_amt = _fmt_amount(args["leftTokenAmount"],  args["leftToken"])
    r_amt = _fmt_amount(args["rightTokenAmount"], args["rightToken"])

    _async_post({"embeds": [{
        "title": "📋 Nova Oferta — SwapBook WEbdEX",
        "description": (
            f"**{left}  ➜  {right}**\n\n"
            f"`{l_amt}` por `{r_amt}`\n\n"
            f"👤 `{_short(args['from'])}`  ·  Oferta **#{args['swapId']}**\n"
            f"[🔗 Ver no Polygonscan]({_POLYGONSCAN_TX.format(tx_hash)})"
        ),
        "color": _COLOR_CREATE,
        "footer": {"text": "WEbdEX SwapBook · Polygon"},
    }]}, url=_WEBHOOK_SWAPS)


def _notify_execute(args: dict, tx_hash: str):
    left  = _token_label(args["leftToken"])
    right = _token_label(args["rightToken"])
    l_amt = _fmt_amount(args["leftTokenAmount"],  args["leftToken"])
    r_amt = _fmt_amount(args["rightTokenAmount"], args["rightToken"])
    fee   = args["fee"] / 1e18

    _async_post({"embeds": [{
        "title": "✅ Swap Executado — WEbdEX",
        "description": (
            f"**{left}  ➜  {right}**\n\n"
            f"`{l_amt}` ➜ `{r_amt}`\n\n"
            f"👤 Vendedor:  `{_short(args['from'])}`\n"
            f"🤝 Comprador: `{_short(args['to'])}`\n"
            f"🆔 Oferta **#{args['swapId']}**  ·  Taxa: `{fee:.4f} POL`\n"
            f"[🔗 Ver Transação no Polygonscan]({_POLYGONSCAN_TX.format(tx_hash)})"
        ),
        "color": _COLOR_EXECUTE,
        "footer": {"text": "WEbdEX SwapBook · Polygon"},
    }]}, url=_WEBHOOK_SWAPS)


# ─────────────────────────────────────────────────────────────
# Processamento de log
# ─────────────────────────────────────────────────────────────

def _process_log(log):
    try:
        contract = web3.eth.contract(address=SWAPBOOK_ADDR, abi=json.loads(_ABI_SWAPBOOK))
        decoded  = contract.events.Transaction().process_log(log)
        args     = decoded["args"]
        method   = args["method"]

        if method not in ("Create Swap", "Swap Tokens"):
            return

        tx_hash   = log["transactionHash"].hex()
        log_index = log["logIndex"]

        if _already_notified(tx_hash, log_index):
            return

        if method == "Create Swap":
            _notify_create(args, tx_hash)
        else:
            _notify_execute(args, tx_hash)
            # Mirror compacto → #webdex-on-chain (só swaps executados)
            left  = _token_label(args["leftToken"])
            right = _token_label(args["rightToken"])
            l_amt = _fmt_amount(args["leftTokenAmount"],  args["leftToken"])
            r_amt = _fmt_amount(args["rightTokenAmount"], args["rightToken"])
            notify_onchain_event(
                title=f"🔄 SWAP EXECUTADO — Oferta #{args['swapId']}",
                description=(
                    f"**{left}  ➜  {right}**\n"
                    f"`{l_amt}` ➜ `{r_amt}`\n"
                    f"👤 `{_short(args['from'])}` · 🤝 `{_short(args['to'])}`"
                ),
                color=0x38BDF8,
                tx_hash=tx_hash,
            )
            inc_pulse_stat("swaps_exec")

        _inc_swap(method)
        _mark_notified(tx_hash, log_index)
        logger.info("[swapbook] %s #%s | tx %s", method, args["swapId"], tx_hash[:14])

    except Exception as e:
        logger.warning("[swapbook] Erro ao processar log: %s", e)


# ─────────────────────────────────────────────────────────────
# Worker principal
# ─────────────────────────────────────────────────────────────

def swapbook_notify_worker():
    """Thread background: poll eth_getLogs no SwapBook a cada 30s."""
    _ensure_table()
    logger.info("[swapbook] Worker iniciado → %s", SWAPBOOK_ADDR)

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

            logs = rpc_pool.get_logs({
                "fromBlock": Web3.to_hex(from_b),
                "toBlock":   Web3.to_hex(to_b),
                "address":   SWAPBOOK_ADDR,
                "topics":    [TOPIC_TRANSACTION],
            })

            for log in logs:
                _process_log(log)

            last_block = to_b
            set_config(_CONFIG_LAST_BLOCK, str(last_block))

        except Exception as e:
            if _is_429_error(e):
                logger.warning("[swapbook] Rate limit RPC — aguardando 60s")
                time.sleep(60)
                continue
            logger.warning("[swapbook] Erro no worker: %s", e)
            time.sleep(10)
            continue

        time.sleep(_POLL_INTERVAL)
