"""
monitor-db · Queries tipadas
============================
Funções de consulta reutilizáveis, todas retornam tipos simples (dict/list/int).
Separado dos handlers do bot — testável sem Telegram.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


# ── helpers ──────────────────────────────────────────────────────────────────

def _dt(hours: int = 0, days: int = 0) -> str:
    return (datetime.now() - timedelta(hours=hours, days=days)).strftime("%Y-%m-%d %H:%M:%S")


# ── VIGIA / HEALTH ───────────────────────────────────────────────────────────

def get_vigia_health(conn: sqlite3.Connection) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT last_block, loops_total, ops_total, rpc_errors, capture_rate, "
        "last_error, started_at, updated_at FROM vigia_health WHERE id=1"
    ).fetchone()
    if not row:
        return {}
    return {
        "last_block": row[0], "loops_total": row[1], "ops_total": row[2],
        "rpc_errors": row[3], "capture_rate": row[4],
        "last_error": row[5], "started_at": row[6], "updated_at": row[7],
    }


def upsert_vigia_health(conn: sqlite3.Connection, **kwargs):
    fields = ", ".join(f"{k}=?" for k in kwargs)
    vals   = list(kwargs.values())
    conn.execute(f"UPDATE vigia_health SET {fields} WHERE id=1", vals)
    conn.commit()


# ── PROTOCOL STATUS ───────────────────────────────────────────────────────────

def ops_today(conn: sqlite3.Connection) -> Dict[str, Any]:
    since = _dt(hours=24)
    row = conn.execute("""
        SELECT COUNT(*),
               COALESCE(SUM(CAST(valor AS REAL)), 0),
               COALESCE(SUM(CAST(gas_usd AS REAL)), 0),
               COALESCE(SUM(CAST(valor AS REAL)) - SUM(CAST(gas_usd AS REAL)), 0),
               COUNT(CASE WHEN CAST(valor AS REAL) > 0 THEN 1 END)
        FROM operacoes WHERE tipo='Trade' AND data_hora >= ?
    """, (since,)).fetchone()
    total    = int(row[0] or 0)
    bruto    = float(row[1] or 0)
    gas      = float(row[2] or 0)
    liquido  = float(row[3] or 0)
    wins     = int(row[4] or 0)
    winrate  = (wins / total * 100) if total > 0 else 0.0
    return {
        "period": "24h",
        "trades": total, "bruto": bruto, "gas": gas,
        "liquido": liquido, "wins": wins, "winrate": winrate,
    }


def ops_by_env(conn: sqlite3.Connection, hours: int = 24) -> List[Dict[str, Any]]:
    since = _dt(hours=hours)
    rows = conn.execute("""
        SELECT COALESCE(ambiente,'UNKNOWN'),
               COUNT(*), ROUND(SUM(valor),4), ROUND(SUM(gas_usd),4),
               ROUND(SUM(valor)-SUM(gas_usd),4),
               COUNT(CASE WHEN valor-gas_usd>0 THEN 1 END)
        FROM operacoes WHERE tipo='Trade' AND data_hora>=?
        GROUP BY 1 ORDER BY 5 DESC
    """, (since,)).fetchall()
    return [
        {"env": r[0], "trades": r[1], "bruto": r[2],
         "gas": r[3], "liquido": r[4], "wins": r[5]}
        for r in rows
    ]


def recent_ops(conn: sqlite3.Connection, limit: int = 10) -> List[Dict[str, Any]]:
    rows = conn.execute("""
        SELECT o.data_hora, o.tipo, ROUND(o.valor,4), ROUND(o.gas_usd,4),
               o.token, o.sub_conta, o.ambiente, ow.wallet
        FROM operacoes o
        LEFT JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
        ORDER BY o.data_hora DESC LIMIT ?
    """, (limit,)).fetchall()
    return [
        {"ts": r[0], "tipo": r[1], "valor": r[2], "gas_usd": r[3],
         "token": r[4], "sub_conta": r[5], "ambiente": r[6], "wallet": r[7]}
        for r in rows
    ]


# ── USERS / CAPITAL ──────────────────────────────────────────────────────────

def active_users(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT chat_id, wallet, env, periodo, username FROM users WHERE active=1"
    ).fetchall()
    return [
        {"chat_id": r[0], "wallet": r[1], "env": r[2],
         "periodo": r[3], "username": r[4]}
        for r in rows
    ]


def capital_by_env(conn: sqlite3.Connection) -> Dict[str, float]:
    rows = conn.execute("""
        SELECT COALESCE(env,'AG_C_bd'), SUM(total_usd)
        FROM capital_cache WHERE total_usd > 0
        GROUP BY 1
    """).fetchall()
    return {str(r[0]): float(r[1] or 0) for r in rows}


def wallet_capital(conn: sqlite3.Connection, wallet: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("""
        SELECT c.env, c.total_usd, c.breakdown_json, c.updated_ts
        FROM capital_cache c
        JOIN users u ON u.chat_id = c.chat_id
        WHERE LOWER(u.wallet) = LOWER(?)
    """, (wallet,)).fetchone()
    if not row:
        return None
    return {"env": row[0], "total_usd": float(row[1] or 0),
            "breakdown": row[2], "updated_ts": row[3]}


# ── ALERTS ───────────────────────────────────────────────────────────────────

def last_inactivity(conn: sqlite3.Connection, limit: int = 5) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT end_block, minutes, tx_count, note, created_at "
        "FROM inactivity_stats ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return [
        {"end_block": r[0], "minutes": r[1], "tx_count": r[2],
         "note": r[3], "created_at": r[4]}
        for r in rows
    ]


# ── KPI CACHE ────────────────────────────────────────────────────────────────

def get_kpi(conn: sqlite3.Connection, key: str) -> Optional[str]:
    import time
    row = conn.execute(
        "SELECT value_json, computed_at, ttl_seconds FROM kpi_cache WHERE key=?",
        (key,)
    ).fetchone()
    if not row:
        return None
    if (time.time() - float(row[1])) > int(row[2]):
        return None  # TTL expirado
    return str(row[0])


def set_kpi(conn: sqlite3.Connection, key: str, value_json: str, ttl: int = 15):
    import time
    conn.execute(
        "INSERT OR REPLACE INTO kpi_cache (key, value_json, computed_at, ttl_seconds) VALUES (?,?,?,?)",
        (key, value_json, time.time(), ttl)
    )
    conn.commit()
