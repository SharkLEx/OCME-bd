from __future__ import annotations
"""
webdex_network_notify.py — Monitor WEbdEXNetworkV5

Notifica Discord (#webdex-on-chain) + Telegram (admins) para:
  1. BalanceNetworkAdd    → PAY FEE RECEBIDO  (payFee chamado)
  2. BalanceNetworkRemove → PAY FEE EXECUTADO (withdrawal chamado)

Contrato: 0xfB2486E93E4Ab8A36d2e6C23004FacaAD3Bad5Db (único, ambos os ambientes)
"""

import time
import json

from webdex_config import logger, Web3, TOKENS_MAP, ADMIN_USER_IDS
from webdex_chain import rpc_pool, web3, _is_429_error
from webdex_db import DB_LOCK, cursor, conn, get_config, set_config
from webdex_discord_sync import _async_post
from webdex_bot_core import send_html

# ─────────────────────────────────────────────────────────────
# Contrato
# ─────────────────────────────────────────────────────────────
_NETWORK_ADDR = Web3.to_checksum_address(
    "0xfB2486E93E4Ab8A36d2e6C23004FacaAD3Bad5Db"
)

# ─────────────────────────────────────────────────────────────
# Topics (keccak256 das assinaturas dos eventos)
# ─────────────────────────────────────────────────────────────
_TOPIC_ADD = Web3.to_hex(Web3.keccak(
    text="BalanceNetworkAdd(address,address,string,address,uint256,uint256)"
))
_TOPIC_REMOVE = Web3.to_hex(Web3.keccak(
    text="BalanceNetworkRemove(address,address,address,uint256,uint256,uint256)"
))

# ─────────────────────────────────────────────────────────────
# ABI
# ─────────────────────────────────────────────────────────────
_ABI_NETWORK = json.dumps([
    {
        "anonymous": False,
        "name": "BalanceNetworkAdd",
        "type": "event",
        "inputs": [
            {"indexed": True,  "name": "manager", "type": "address"},
            {"indexed": True,  "name": "user",    "type": "address"},
            {"indexed": False, "name": "id",      "type": "string"},
            {"indexed": False, "name": "coin",    "type": "address"},
            {"indexed": False, "name": "balance", "type": "uint256"},
            {"indexed": False, "name": "value",   "type": "uint256"},
        ],
    },
    {
        "anonymous": False,
        "name": "BalanceNetworkRemove",
        "type": "event",
        "inputs": [
            {"indexed": True,  "name": "manager", "type": "address"},
            {"indexed": True,  "name": "user",    "type": "address"},
            {"indexed": False, "name": "coin",    "type": "address"},
            {"indexed": False, "name": "balance", "type": "uint256"},
            {"indexed": False, "name": "value",   "type": "uint256"},
            {"indexed": False, "name": "fee",     "type": "uint256"},
        ],
    },
])

# ─────────────────────────────────────────────────────────────
# Cores Discord
# ─────────────────────────────────────────────────────────────
_COLOR_ADD    = 0x00FFB2  # verde  — capital entrando
_COLOR_REMOVE = 0xA855F7  # roxo   — fee executada

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
_POLL_INTERVAL     = 30
_BLOCKS_PER_POLL   = 50
_CONFIG_LAST_BLOCK = "network_notify_last_block"
_POLYGONSCAN_TX    = "https://polygonscan.com/tx/{}"
_POLYGONSCAN_ADDR  = "https://polygonscan.com/address/{}"
_MIN_USD           = 10.0   # mínimo $10 para notificar


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _short(addr: str) -> str:
    return f"{addr[:6]}…{addr[-4:]}"


def _fmt_coin(raw: int, coin_addr: str) -> str:
    """Formata valor com decimais corretos do token."""
    meta = TOKENS_MAP.get(coin_addr.lower())
    dec  = meta["dec"] if meta else 6
    sym  = meta["sym"] if meta else _short(coin_addr)
    val  = raw / (10 ** dec)
    if val >= 1_000_000:
        return f"{val / 1_000_000:,.2f}M {sym}"
    if val >= 1_000:
        return f"{val:,.2f} {sym}"
    return f"{val:.2f} {sym}"


def _usd_value(raw: int, coin_addr: str) -> float:
    """Retorna valor em USD (assume stablecoins = 1:1)."""
    meta = TOKENS_MAP.get(coin_addr.lower())
    dec  = meta["dec"] if meta else 6
    return raw / (10 ** dec)


# ─────────────────────────────────────────────────────────────
# Deduplicação
# ─────────────────────────────────────────────────────────────

def _ensure_table():
    with DB_LOCK:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS network_notified (
                tx_hash   TEXT    NOT NULL,
                log_index INTEGER NOT NULL,
                PRIMARY KEY (tx_hash, log_index)
            )
        """)
        conn.commit()


def _already_notified(tx_hash: str, log_index: int) -> bool:
    with DB_LOCK:
        return cursor.execute(
            "SELECT 1 FROM network_notified WHERE tx_hash=? AND log_index=?",
            (tx_hash, log_index)
        ).fetchone() is not None


def _mark_notified(tx_hash: str, log_index: int):
    with DB_LOCK:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO network_notified VALUES (?,?)",
                (tx_hash, log_index)
            )
            conn.commit()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# Notificações — Discord + Telegram
# ─────────────────────────────────────────────────────────────

def _notify_add(args: dict, tx_hash: str):
    """PAY FEE RECEBIDO — capital entrando na rede."""
    val_fmt  = _fmt_coin(args["value"],   args["coin"])
    acc_id   = args["id"] or _short(args["user"])
    user_url = _POLYGONSCAN_ADDR.format(args["user"])
    tx_url   = _POLYGONSCAN_TX.format(tx_hash)

    # Discord
    _async_post({"embeds": [{
        "title": "⚡ PAY FEE RECEBIDO — WEbdEX Network",
        "description": (
            f"💰 `+{val_fmt}`\n\n"
            f"👤 Conta: `{acc_id}`  ·  [`{_short(args['user'])}`]({user_url})\n\n"
            f"[🔗 Ver no Polygonscan]({tx_url})"
        ),
        "color": _COLOR_ADD,
        "footer": {"text": "WEbdEX Protocol · Polygon"},
    }]})

    # Telegram admins
    tg_text = (
        f"⚡ <b>PAY FEE RECEBIDO — WEbdEX Network</b>\n\n"
        f"💰 <b>+{val_fmt}</b>\n"
        f"👤 Conta: <code>{acc_id}</code>\n"
        f"<a href=\"{tx_url}\">🔗 Ver no Polygonscan</a>"
    )
    _send_admins(tg_text)


def _notify_remove(args: dict, tx_hash: str):
    """PAY FEE EXECUTADO — fee paga para os blocos."""
    val_fmt = _fmt_coin(args["value"],   args["coin"])
    fee_fmt = _fmt_coin(args["fee"],     args["coin"])
    tx_url  = _POLYGONSCAN_TX.format(tx_hash)

    # Discord
    _async_post({"embeds": [{
        "title": "🔋 PAY FEE EXECUTADO — WEbdEX Protocol",
        "description": (
            f"💸 Valor: `{val_fmt}`\n"
            f"💼 Taxa protocolo: `{fee_fmt}`\n\n"
            f"👤 [`{_short(args['user'])}`]({_POLYGONSCAN_ADDR.format(args['user'])})\n\n"
            f"[🔗 Ver no Polygonscan]({tx_url})"
        ),
        "color": _COLOR_REMOVE,
        "footer": {"text": "WEbdEX Protocol · Polygon"},
    }]})

    # Telegram admins
    tg_text = (
        f"🔋 <b>PAY FEE EXECUTADO — WEbdEX Protocol</b>\n\n"
        f"💸 Valor: <b>{val_fmt}</b>\n"
        f"💼 Taxa protocolo: <b>{fee_fmt}</b>\n"
        f"👤 <code>{_short(args['user'])}</code>\n"
        f"<a href=\"{tx_url}\">🔗 Ver no Polygonscan</a>"
    )
    _send_admins(tg_text)


def _send_admins(text: str):
    """Envia mensagem para todos os admins no Telegram."""
    for adm_id in ADMIN_USER_IDS:
        try:
            send_html(int(adm_id), text)
        except Exception as e:
            logger.warning("[network] Telegram admin %s: %s", adm_id, e)


# ─────────────────────────────────────────────────────────────
# Processamento de log
# ─────────────────────────────────────────────────────────────

def _process_log(log, contract):
    try:
        tx_hash   = log["transactionHash"].hex()
        log_index = log["logIndex"]
        topic0    = log["topics"][0].hex() if log["topics"] else ""

        if _already_notified(tx_hash, log_index):
            return

        if topic0 == _TOPIC_ADD:
            decoded = contract.events.BalanceNetworkAdd().process_log(log)
            args    = decoded["args"]
            usd     = _usd_value(args["value"], args["coin"])
            if usd < _MIN_USD:
                return
            _notify_add(args, tx_hash)
            _mark_notified(tx_hash, log_index)
            logger.info("[network] PayFee ADD: +%s | %s", _fmt_coin(args["value"], args["coin"]), _short(args["user"]))

        elif topic0 == _TOPIC_REMOVE:
            decoded = contract.events.BalanceNetworkRemove().process_log(log)
            args    = decoded["args"]
            usd     = _usd_value(args["value"], args["coin"])
            if usd < _MIN_USD:
                return
            _notify_remove(args, tx_hash)
            _mark_notified(tx_hash, log_index)
            logger.info("[network] PayFee REMOVE: %s | %s", _fmt_coin(args["value"], args["coin"]), _short(args["user"]))

    except Exception as e:
        logger.warning("[network] Erro ao processar log: %s", e)


# ─────────────────────────────────────────────────────────────
# Worker principal
# ─────────────────────────────────────────────────────────────

def network_notify_worker():
    """Thread background: monitora WEbdEXNetworkV5 a cada 30s."""
    _ensure_table()
    logger.info("[network] Worker iniciado → %s", _NETWORK_ADDR)

    try:
        last_block = int(get_config(_CONFIG_LAST_BLOCK) or 0)
    except Exception:
        last_block = 0

    if last_block == 0:
        try:
            last_block = web3.eth.block_number - 100
        except Exception:
            last_block = 0

    contract = web3.eth.contract(address=_NETWORK_ADDR, abi=json.loads(_ABI_NETWORK))

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
                "address":   _NETWORK_ADDR,
                "topics":    [[_TOPIC_ADD, _TOPIC_REMOVE]],
            })

            for log in logs:
                _process_log(log, contract)

            last_block = to_b
            set_config(_CONFIG_LAST_BLOCK, str(last_block))

        except Exception as e:
            if _is_429_error(e):
                logger.warning("[network] Rate limit RPC — aguardando 60s")
                time.sleep(60)
                continue
            logger.warning("[network] Erro no worker: %s", e)
            time.sleep(10)
            continue

        time.sleep(_POLL_INTERVAL)
