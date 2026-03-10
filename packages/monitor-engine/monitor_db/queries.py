# ==============================================================================
# monitor_db/queries.py — Queries tipadas e centralizadas
# OCME bd Monitor Engine — Story 7.3
# ==============================================================================
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any

_lock = threading.Lock()
_tl = threading.local()


def get_cursor(conn: sqlite3.Connection) -> sqlite3.Cursor:
    '''Cursor thread-local — evita "Recursive use of cursors".'''
    if not hasattr(_tl, 'c') or _tl.conn is not conn:
        _tl.c = conn.cursor()
        _tl.conn = conn
    return _tl.c


# ── Config ────────────────────────────────────────────────────────────────────

def config_get(conn: sqlite3.Connection, key: str, default: str = '') -> str:
    with _lock:
        r = get_cursor(conn).execute(
            'SELECT valor FROM config WHERE chave=?', (key,)
        ).fetchone()
        return r[0] if r else default


def config_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    with _lock:
        get_cursor(conn).execute(
            'INSERT OR REPLACE INTO config (chave, valor) VALUES (?,?)', (key, str(value))
        )
        conn.commit()


# ── Operações ─────────────────────────────────────────────────────────────────

def ops_summary(
    conn: sqlite3.Connection,
    wallet: str,
    hours: int = 24,
    env: str | None = None,
) -> dict[str, Any]:
    '''Resumo de operações para uma wallet em um período.'''
    since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    env_clause = "AND o.ambiente = ?" if env else ""
    params: list[Any] = [since, wallet.lower()]
    if env:
        params.append(env)

    with _lock:
        rows = get_cursor(conn).execute(f'''
            SELECT
                COUNT(*)                       AS trade_count,
                COALESCE(SUM(o.valor), 0)      AS profit_gross,
                COALESCE(SUM(o.gas_usd), 0)    AS gas_total,
                COALESCE(SUM(o.fee), 0)        AS fee_total
            FROM operacoes o
            JOIN op_owner ow ON ow.hash = o.hash AND ow.log_index = o.log_index
            WHERE o.data_hora >= ?
              AND LOWER(ow.wallet) = ?
              AND o.tipo = 'Trade'
              {env_clause}
        ''', params).fetchone()

    count, gross, gas, fee = rows or (0, 0.0, 0.0, 0.0)
    return {
        'count': int(count or 0),
        'profit_gross': float(gross or 0),
        'gas_total': float(gas or 0),
        'fee_total': float(fee or 0),
        'profit_net': float((gross or 0) - (gas or 0) - (fee or 0)),
    }


def ops_best_subconta(
    conn: sqlite3.Connection,
    wallet: str,
    hours: int = 24,
) -> dict[str, Any] | None:
    since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    with _lock:
        row = get_cursor(conn).execute('''
            SELECT o.sub_conta, SUM(o.valor) as lucro, COUNT(*) as trades
            FROM operacoes o
            JOIN op_owner ow ON ow.hash = o.hash AND ow.log_index = o.log_index
            WHERE o.data_hora >= ?
              AND LOWER(ow.wallet) = ?
              AND o.tipo = 'Trade'
            GROUP BY o.sub_conta
            ORDER BY lucro DESC
            LIMIT 1
        ''', (since, wallet.lower())).fetchone()
    if not row:
        return None
    return {'id': row[0], 'profit': float(row[1] or 0), 'trades': int(row[2] or 0)}


def ops_last_trade_dt(
    conn: sqlite3.Connection,
    wallet: str,
) -> str | None:
    with _lock:
        row = get_cursor(conn).execute('''
            SELECT MAX(o.data_hora)
            FROM operacoes o
            JOIN op_owner ow ON ow.hash = o.hash AND ow.log_index = o.log_index
            WHERE ow.wallet = LOWER(?)
              AND o.tipo = 'Trade'
        ''', (wallet,)).fetchone()
    return row[0] if row and row[0] else None


def ops_last_inactivity_minutes(conn: sqlite3.Connection, wallet: str) -> float:
    last_dt = ops_last_trade_dt(conn, wallet)
    if not last_dt:
        return 0.0
    try:
        dt = datetime.strptime(last_dt, '%Y-%m-%d %H:%M:%S')
        return (datetime.now() - dt).total_seconds() / 60
    except Exception:
        return 0.0


# ── Capital ───────────────────────────────────────────────────────────────────

def capital_get(conn: sqlite3.Connection, chat_id: int) -> dict[str, Any] | None:
    with _lock:
        row = get_cursor(conn).execute(
            'SELECT env, total_usd, breakdown_json, updated_ts FROM capital_cache WHERE chat_id=?',
            (chat_id,)
        ).fetchone()
    if not row:
        return None
    import json
    return {
        'env': row[0],
        'total_usd': float(row[1] or 0),
        'breakdown': json.loads(row[2]) if row[2] else {},
        'updated_ts': float(row[3] or 0),
    }


def capital_set(conn: sqlite3.Connection, chat_id: int, env: str, total_usd: float, breakdown: dict) -> None:
    import json
    with _lock:
        get_cursor(conn).execute('''
            INSERT OR REPLACE INTO capital_cache (chat_id, env, total_usd, breakdown_json, updated_ts)
            VALUES (?, ?, ?, ?, ?)
        ''', (chat_id, env, total_usd, json.dumps(breakdown), time.time()))
        conn.commit()


# ── Usuários ──────────────────────────────────────────────────────────────────

def user_get(conn: sqlite3.Connection, chat_id: int) -> dict[str, Any] | None:
    with _lock:
        row = get_cursor(conn).execute(
            'SELECT chat_id, wallet, env, active, periodo, ai_enabled, username FROM users WHERE chat_id=?',
            (chat_id,)
        ).fetchone()
    if not row:
        return None
    return {
        'chat_id': row[0], 'wallet': row[1], 'env': row[2] or 'AG_C_bd',
        'active': bool(row[3]), 'periodo': row[4] or '24h',
        'ai_enabled': bool(row[5]), 'username': row[6],
    }


def user_touch(conn: sqlite3.Connection, chat_id: int, username: str | None = None) -> None:
    with _lock:
        get_cursor(conn).execute(
            'UPDATE users SET last_seen_ts=?, username=COALESCE(?, username) WHERE chat_id=?',
            (time.time(), username, chat_id)
        )
        conn.commit()


def block_ts_get(conn: sqlite3.Connection, block: int) -> int | None:
    with _lock:
        row = get_cursor(conn).execute(
            'SELECT ts FROM block_time_cache WHERE bloco=?', (block,)
        ).fetchone()
    return int(row[0]) if row and row[0] else None


def block_ts_set(conn: sqlite3.Connection, block: int, ts: int) -> None:
    with _lock:
        get_cursor(conn).execute(
            'INSERT OR REPLACE INTO block_time_cache (bloco, ts) VALUES (?,?)', (block, ts)
        )
        conn.commit()
