"""
webdex_v4_monitor.py — Monitor do Subaccount v4 WEbdEX
=======================================================
Monitora movimentações de USDT e LOOP no subaccount v4 na Polygon.
Relatório Discord a cada 2 horas via webhook dedicado.

Contratos:
  Manager    : 0x9b4314878f58C3Ca53EC0087AcC8c9A30DF773E0
  Subaccount : 0x7c5241688eCd253ca3D13172620be22902a4414c

Tokens:
  USDT : 0xc2132D05D31c914a87C6611C10748AEb04B58e8F (6 decimals)
  LOOP : 0xc4CF5093676e8a61404f51bC6Ceaec5279Ce8645 (9 decimals)
"""
from __future__ import annotations

import os
import time
import sqlite3
import threading
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
logger = logging.getLogger("WEbdEX")

V4_SUBACCOUNT   = "0x7c5241688eCd253ca3D13172620be22902a4414c"
V4_MANAGER      = "0x9b4314878f58C3Ca53EC0087AcC8c9A30DF773E0"

TOKEN_USDT = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
TOKEN_LOOP = "0xc4CF5093676e8a61404f51bC6Ceaec5279Ce8645"

TOKEN_INFO = {
    TOKEN_USDT.lower(): {"sym": "USDT", "dec": 6,  "icon": "🔵"},
    TOKEN_LOOP.lower(): {"sym": "LOOP", "dec": 9,  "icon": "🟣"},
}

POLL_INTERVAL   = 300        # segundos entre polls (5 min)
BLOCKS_PER_POLL = 150        # ~5 min @ 2s/bloco Polygon
REPORT_INTERVAL = 7200       # segundos entre relatórios (2h)
MIN_TXS_REPORT  = 1          # mínimo de txs para enviar relatório

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_V4_SUB", "").strip()

# Importações do monitor-engine (disponíveis no contexto do container)
try:
    from webdex_db import DB_LOCK, DB_PATH
    from webdex_config import RPC_URL, RPC_FALLBACK, Web3
except ImportError:
    # fallback para testes isolados
    DB_LOCK = threading.Lock()
    DB_PATH = os.getenv("DB_PATH", "webdex_v5_final.db")
    RPC_URL = os.getenv("RPC_URL", "https://rpc.ankr.com/polygon")
    RPC_FALLBACK = os.getenv("RPC_FALLBACK", "https://polygon-bor-rpc.publicnode.com")
    from web3 import Web3

# ERC-20 Transfer event signature
TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _ensure_v4_schema(conn: sqlite3.Connection) -> None:
    """Cria tabelas v4_events e v4_reports se não existirem."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS v4_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          DATETIME NOT NULL DEFAULT (datetime('now')),
            tx_hash     TEXT NOT NULL,
            log_index   INTEGER NOT NULL DEFAULT 0,
            event_type  TEXT NOT NULL,
            token_sym   TEXT NOT NULL,
            token_addr  TEXT NOT NULL,
            amount_raw  TEXT NOT NULL,
            amount_usd  REAL NOT NULL DEFAULT 0,
            from_addr   TEXT,
            to_addr     TEXT,
            block_num   INTEGER,
            reported    INTEGER NOT NULL DEFAULT 0,
            UNIQUE(tx_hash, log_index)
        );

        CREATE INDEX IF NOT EXISTS v4_events_ts_idx       ON v4_events(ts);
        CREATE INDEX IF NOT EXISTS v4_events_reported_idx ON v4_events(reported);
        CREATE INDEX IF NOT EXISTS v4_events_token_idx    ON v4_events(token_sym);

        CREATE TABLE IF NOT EXISTS v4_reports (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ts            DATETIME NOT NULL DEFAULT (datetime('now')),
            period_start  DATETIME NOT NULL,
            period_end    DATETIME NOT NULL,
            total_in_usd  REAL NOT NULL DEFAULT 0,
            total_out_usd REAL NOT NULL DEFAULT 0,
            tx_count      INTEGER NOT NULL DEFAULT 0,
            discord_sent  INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS v4_state (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()
    logger.info("[v4] Schema pronto (v4_events, v4_reports, v4_state)")


# ---------------------------------------------------------------------------
# Web3 helpers
# ---------------------------------------------------------------------------

def _make_w3(rpc: str) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
    try:
        from web3.middleware import geth_poa_middleware
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        try:
            from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        except Exception:
            pass
    return w3


def _get_w3() -> Optional[Web3]:
    """Retorna Web3 conectado, tentando RPC_URL e RPC_FALLBACK."""
    for rpc in [RPC_URL, RPC_FALLBACK, "https://rpc.ankr.com/polygon"]:
        if not rpc:
            continue
        try:
            w3 = _make_w3(rpc)
            if w3.is_connected():
                return w3
        except Exception:
            continue
    logger.error("[v4] Nenhum RPC disponível")
    return None


# ---------------------------------------------------------------------------
# State helpers (último bloco processado)
# ---------------------------------------------------------------------------

def _get_last_block(conn: sqlite3.Connection) -> Optional[int]:
    row = conn.execute(
        "SELECT value FROM v4_state WHERE key='last_block'"
    ).fetchone()
    return int(row[0]) if row else None


def _set_last_block(conn: sqlite3.Connection, block: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO v4_state(key,value) VALUES('last_block',?)",
        (str(block),)
    )
    conn.commit()


def _get_last_report_ts(conn: sqlite3.Connection) -> Optional[float]:
    row = conn.execute(
        "SELECT value FROM v4_state WHERE key='last_report_ts'"
    ).fetchone()
    return float(row[0]) if row else None


def _set_last_report_ts(conn: sqlite3.Connection, ts: float) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO v4_state(key,value) VALUES('last_report_ts',?)",
        (str(ts),)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Event fetching
# ---------------------------------------------------------------------------

def _decode_transfer_amount(data: str, decimals: int) -> float:
    """Decodifica o campo `data` de um evento Transfer ERC-20."""
    try:
        raw = int(data, 16)
        return raw / (10 ** decimals)
    except Exception:
        return 0.0


def _fetch_transfer_events(w3: Web3, token_addr: str, from_block: int, to_block: int) -> list:
    """
    Busca eventos Transfer de um token onde o subaccount é from ou to.
    Retorna lista de dicts com os dados relevantes.
    """
    sub_padded = "0x" + V4_SUBACCOUNT.lower().replace("0x", "").zfill(64)
    token_cs   = Web3.to_checksum_address(token_addr)
    tok_info   = TOKEN_INFO.get(token_addr.lower(), {"sym": "?", "dec": 18, "icon": "⬜"})
    events     = []

    # Dois filtros: sub como FROM e sub como TO
    for idx, topic_slot in enumerate([1, 2]):
        topics = [TRANSFER_TOPIC, None, None]
        topics[topic_slot] = sub_padded

        try:
            logs = w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock":   to_block,
                "address":   token_cs,
                "topics":    topics,
            })
        except Exception as e:
            logger.warning("[v4] get_logs erro (token=%s slot=%d): %s", tok_info["sym"], topic_slot, e)
            continue

        for log in logs:
            try:
                from_addr = "0x" + log["topics"][1].hex()[-40:]
                to_addr   = "0x" + log["topics"][2].hex()[-40:]
                amount    = _decode_transfer_amount(log["data"].hex() if isinstance(log["data"], bytes) else log["data"], tok_info["dec"])
                is_in     = to_addr.lower() == V4_SUBACCOUNT.lower()
                events.append({
                    "tx_hash":    log["transactionHash"].hex(),
                    "log_index":  log["logIndex"],
                    "event_type": "deposit" if is_in else "withdrawal",
                    "token_sym":  tok_info["sym"],
                    "token_addr": token_addr.lower(),
                    "amount_raw": str(int(log["data"], 16) if isinstance(log["data"], str) else int(log["data"].hex(), 16)),
                    "amount_usd": amount,  # sem conversão de preço por ora
                    "from_addr":  from_addr,
                    "to_addr":    to_addr,
                    "block_num":  log["blockNumber"],
                })
            except Exception as e:
                logger.debug("[v4] skip log: %s", e)

    return events


# ---------------------------------------------------------------------------
# Persist events
# ---------------------------------------------------------------------------

def _persist_events(conn: sqlite3.Connection, events: list) -> int:
    """Salva eventos no banco. Retorna quantos foram inseridos (novos)."""
    inserted = 0
    for ev in events:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO v4_events
                    (tx_hash, log_index, event_type, token_sym, token_addr,
                     amount_raw, amount_usd, from_addr, to_addr, block_num, reported)
                VALUES (?,?,?,?,?,?,?,?,?,?,0)
            """, (
                ev["tx_hash"], ev["log_index"], ev["event_type"],
                ev["token_sym"], ev["token_addr"],
                ev["amount_raw"], ev["amount_usd"],
                ev["from_addr"], ev["to_addr"], ev["block_num"],
            ))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except Exception as e:
            logger.warning("[v4] persist erro: %s", e)
    conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# Discord report
# ---------------------------------------------------------------------------

def _build_report_embed(period_start: datetime, period_end: datetime,
                         events: list) -> dict:
    """Constrói payload de embed Discord para o relatório 2h."""
    tz_br = timezone(timedelta(hours=-3))
    start_br = period_start.astimezone(tz_br).strftime("%d/%m %H:%M")
    end_br   = period_end.astimezone(tz_br).strftime("%H:%M BRT")

    # Agregar por tipo e token
    totals = {"deposit": {}, "withdrawal": {}}
    biggest = None

    for ev in events:
        etype  = ev["event_type"]
        sym    = ev["token_sym"]
        amount = ev["amount_usd"]
        totals[etype][sym] = totals[etype].get(sym, 0) + amount
        if biggest is None or amount > biggest["amount"]:
            biggest = {"amount": amount, "sym": sym, "hash": ev["tx_hash"], "type": etype}

    # Calcular líquido USDT
    in_usdt  = totals["deposit"].get("USDT", 0)
    out_usdt = totals["withdrawal"].get("USDT", 0)
    in_loop  = totals["deposit"].get("LOOP", 0)
    out_loop = totals["withdrawal"].get("LOOP", 0)
    liquido  = in_usdt - out_usdt

    liquido_icon = "📈" if liquido >= 0 else "📉"
    color = 0x00C853 if liquido >= 0 else 0xD32F2F  # verde / vermelho

    lines = [
        f"**Período:** {start_br} – {end_br}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"**Entradas:**",
        f"  🔵 USDT: `+${in_usdt:,.2f}`",
        f"  🟣 LOOP: `+{in_loop:,.4f}`",
        f"**Saídas:**",
        f"  🔵 USDT: `-${out_usdt:,.2f}`",
        f"  🟣 LOOP: `-{out_loop:,.4f}`",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{liquido_icon} **Líquido USDT:** `{'+'if liquido>=0 else ''}${liquido:,.2f}`",
        f"📊 **Operações:** `{len(events)}`",
    ]

    if biggest:
        hash_short = biggest["hash"][:6] + "..." + biggest["hash"][-4:]
        arrow = "↑" if biggest["type"] == "deposit" else "↓"
        lines.append(f"⚡ **Maior tx:** `{arrow}${biggest['amount']:,.2f} {biggest['sym']}` ({hash_short})")

    return {
        "embeds": [{
            "title": f"📊 SubAccount v4 WEbdEX",
            "description": "\n".join(lines),
            "color": color,
            "footer": {
                "text": f"Sub: {V4_SUBACCOUNT[:6]}...{V4_SUBACCOUNT[-4:]} | Polygon"
            },
            "timestamp": period_end.isoformat(),
        }]
    }


def _flush_daily_report(conn: sqlite3.Connection, day_start: datetime, day_end: datetime) -> None:
    """
    Relatório diário completo às 21h BRT (00h UTC).
    Agrega TODAS as txs das últimas 24h — independente de já terem sido
    reportadas nos ciclos 2h — e envia embed rico no Discord.
    """
    start_iso = day_start.strftime("%Y-%m-%d %H:%M:%S")
    end_iso   = day_end.strftime("%Y-%m-%d %H:%M:%S")

    rows = conn.execute("""
        SELECT event_type, token_sym, amount_usd, tx_hash
        FROM v4_events
        WHERE ts BETWEEN ? AND ?
        ORDER BY ts ASC
    """, (start_iso, end_iso)).fetchall()

    if not rows:
        logger.info("[v4] Relatório diário: sem txs nas últimas 24h — pulando")
        return

    BRT = timezone(timedelta(hours=-3))
    label_start = day_start.astimezone(BRT).strftime("%d/%m %H:%M")
    label_end   = day_end.astimezone(BRT).strftime("%d/%m %H:%M")

    # Agregar por token e direção
    agg: dict = {}
    for event_type, token_sym, amount_usd, _ in rows:
        key = (token_sym, event_type)
        agg[key] = agg.get(key, 0.0) + amount_usd

    in_usdt  = agg.get(("USDT", "deposit"),    0.0)
    out_usdt = agg.get(("USDT", "withdrawal"), 0.0)
    in_loop  = agg.get(("LOOP", "deposit"),    0.0)
    out_loop = agg.get(("LOOP", "withdrawal"), 0.0)
    liquido  = (in_usdt + in_loop) - (out_usdt + out_loop)
    total_txs = len(rows)

    # Maior tx do dia
    biggest = max(rows, key=lambda r: r[2])
    arrow = "+" if biggest[0] == "deposit" else "-"
    biggest_str = f"{arrow}${biggest[2]:,.2f} {biggest[1]} (`{biggest[3][:8]}...`)"

    color = 0x2ECC71 if liquido >= 0 else 0xE74C3C

    embed = {
        "title": "🗓️ Resumo Diário | SubAccount v4 WEbdEX",
        "description": (
            f"**{label_start} → {label_end} BRT**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        "color": color,
        "fields": [
            {"name": "🔵 Entradas USDT",  "value": f"`+${in_usdt:,.4f}`",   "inline": True},
            {"name": "🟣 Entradas LOOP",  "value": f"`+${in_loop:,.4f}`",   "inline": True},
            {"name": "\u200b",             "value": "\u200b",                 "inline": True},
            {"name": "🔴 Saídas USDT",    "value": f"`-${out_usdt:,.4f}`",  "inline": True},
            {"name": "🔴 Saídas LOOP",    "value": f"`-${out_loop:,.4f}`",  "inline": True},
            {"name": "\u200b",             "value": "\u200b",                 "inline": True},
            {
                "name": "💰 Saldo Líquido do Dia",
                "value": f"**`{'+'if liquido>=0 else ''}{liquido:,.4f} USD`**",
                "inline": True
            },
            {"name": "📦 Total Operações", "value": f"`{total_txs} txs`",   "inline": True},
            {"name": "🏆 Maior Tx",        "value": biggest_str,              "inline": True},
        ],
        "footer": {
            "text": f"Sub: {V4_SUBACCOUNT[:6]}...{V4_SUBACCOUNT[-4:]} | Polygon | Relatório 24h"
        },
        "timestamp": day_end.isoformat(),
    }

    sent = _send_discord_report({"embeds": [embed]})
    logger.info("[v4] Relatório diário: %d txs | +$%.4f | -$%.4f | Discord=%s",
                total_txs, in_usdt + in_loop, out_usdt + out_loop, "OK" if sent else "FAIL")


def _send_discord_report(embed_payload: dict) -> bool:
    """Envia embed para o webhook Discord. Retorna True se OK."""
    if not WEBHOOK_URL:
        logger.warning("[v4] DISCORD_WEBHOOK_V4_SUB não configurado — relatório não enviado")
        return False
    try:
        resp = requests.post(WEBHOOK_URL, json=embed_payload, timeout=20)
        if resp.status_code in (200, 204):
            logger.info("[v4] Relatório Discord enviado OK")
            return True
        logger.warning("[v4] Discord HTTP %d: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.error("[v4] Discord send erro: %s", e)
        return False


def _flush_report(conn: sqlite3.Connection, period_start: datetime, period_end: datetime) -> None:
    """Agrega eventos não reportados e envia relatório Discord."""
    start_iso = period_start.strftime("%Y-%m-%d %H:%M:%S")
    end_iso   = period_end.strftime("%Y-%m-%d %H:%M:%S")

    rows = conn.execute("""
        SELECT tx_hash, log_index, event_type, token_sym, amount_usd, from_addr, to_addr
        FROM v4_events
        WHERE reported = 0
          AND ts BETWEEN ? AND ?
        ORDER BY ts ASC
    """, (start_iso, end_iso)).fetchall()

    if len(rows) < MIN_TXS_REPORT:
        logger.info("[v4] Relatório 2h: %d txs — abaixo do threshold, pulando", len(rows))
        _set_last_report_ts(conn, period_end.timestamp())
        return

    events = [
        {"tx_hash": r[0], "log_index": r[1], "event_type": r[2],
         "token_sym": r[3], "amount_usd": r[4], "from_addr": r[5], "to_addr": r[6]}
        for r in rows
    ]

    total_in  = sum(e["amount_usd"] for e in events if e["event_type"] == "deposit")
    total_out = sum(e["amount_usd"] for e in events if e["event_type"] == "withdrawal")

    embed_payload = _build_report_embed(period_start, period_end, events)
    sent = _send_discord_report(embed_payload)

    # Marcar como reportados
    hashes = [(r[0], r[1]) for r in rows]
    conn.executemany(
        "UPDATE v4_events SET reported=1 WHERE tx_hash=? AND log_index=?", hashes
    )

    # Registrar relatório
    conn.execute("""
        INSERT INTO v4_reports (period_start, period_end, total_in_usd, total_out_usd, tx_count, discord_sent)
        VALUES (?,?,?,?,?,?)
    """, (start_iso, end_iso, total_in, total_out, len(events), 1 if sent else 0))
    conn.commit()

    _set_last_report_ts(conn, period_end.timestamp())
    logger.info("[v4] Relatório 2h: %d txs | +$%.2f | -$%.2f | Discord=%s",
                len(events), total_in, total_out, "OK" if sent else "FAIL")


# ---------------------------------------------------------------------------
# Worker principal
# ---------------------------------------------------------------------------

def v4_subaccount_worker() -> None:
    """
    Worker principal do monitor v4.
    - Poll a cada 5 min: busca Transfer events do subaccount
    - A cada 2h: envia relatório Discord
    Registrar em main.py: threading.Thread(target=v4_subaccount_worker, daemon=True).start()
    """
    logger.info("[v4] Worker iniciado | sub=%s...%s",
                V4_SUBACCOUNT[:6], V4_SUBACCOUNT[-4:])

    # Setup banco
    conn_v4 = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn_v4.execute("PRAGMA journal_mode=WAL")
    conn_v4.execute("PRAGMA synchronous=NORMAL")

    with DB_LOCK:
        _ensure_v4_schema(conn_v4)

    last_report_ts  = None
    last_daily_date = None   # date (UTC) do último relatório diário enviado

    while True:
        try:
            # ---- 1. Fetch on-chain events ----
            w3 = _get_w3()
            if w3 is None:
                logger.warning("[v4] Web3 indisponível, aguardando...")
                time.sleep(POLL_INTERVAL)
                continue

            try:
                latest_block = w3.eth.block_number
            except Exception as e:
                logger.warning("[v4] block_number erro: %s", e)
                time.sleep(POLL_INTERVAL)
                continue

            with DB_LOCK:
                last_block = _get_last_block(conn_v4)

            from_block = last_block + 1 if last_block else max(0, latest_block - 1000)
            to_block   = min(latest_block, from_block + BLOCKS_PER_POLL - 1)

            if from_block > to_block:
                logger.debug("[v4] Sem novos blocos, aguardando...")
                time.sleep(POLL_INTERVAL)
                continue

            all_events = []
            for token_addr in [TOKEN_USDT, TOKEN_LOOP]:
                evs = _fetch_transfer_events(w3, token_addr, from_block, to_block)
                all_events.extend(evs)

            with DB_LOCK:
                inserted = _persist_events(conn_v4, all_events)
                _set_last_block(conn_v4, to_block)

            if all_events:
                logger.info("[v4] Blocos %d→%d | eventos=%d novos=%d",
                            from_block, to_block, len(all_events), inserted)
            else:
                logger.debug("[v4] Blocos %d→%d | sem eventos", from_block, to_block)

            # ---- 2. Relatório 2h ----
            now = datetime.now(timezone.utc)
            with DB_LOCK:
                if last_report_ts is None:
                    last_report_ts = _get_last_report_ts(conn_v4)

            # Calcular próximo período de 2h alinhado (00h, 02h, 04h...)
            hour_2 = (now.hour // 2) * 2  # hora par mais recente
            period_end_naive = now.replace(hour=hour_2, minute=0, second=0, microsecond=0)
            if period_end_naive > now:
                period_end_naive = period_end_naive - timedelta(hours=2)
            period_start_naive = period_end_naive - timedelta(hours=2)

            already_reported = (
                last_report_ts is not None
                and last_report_ts >= period_end_naive.timestamp()
            )

            if not already_reported and now >= period_end_naive:
                with DB_LOCK:
                    _flush_report(conn_v4, period_start_naive, period_end_naive)
                last_report_ts = period_end_naive.timestamp()

            # ---- 3. Relatório diário às 21h BRT (00h UTC) ----
            if now.hour == 0 and now.minute < 6:  # janela 00:00–00:05 UTC
                today_utc = now.date()
                if last_daily_date != today_utc:
                    day_end_dt   = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_start_dt = day_end_dt - timedelta(hours=24)
                    with DB_LOCK:
                        _flush_daily_report(conn_v4, day_start_dt, day_end_dt)
                    last_daily_date = today_utc
                    logger.info("[v4] Relatório diário enviado para %s", today_utc)

        except Exception as e:
            logger.error("[v4] Worker erro inesperado: %s", e, exc_info=True)

        time.sleep(POLL_INTERVAL)
