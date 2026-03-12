"""
tests/packages/test_monitor_db.py
Story 7.3 — Schema Versionado: testes de queries.py com DB em memória.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

# ── PATH setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "monitor-db"))
from queries import (  # noqa: E402
    ops_today,
    ops_by_env,
    recent_ops,
    active_users,
    capital_by_env,
    wallet_capital,
    last_inactivity,
    get_kpi,
    set_kpi,
)


# ── Fixture: DB em memória com schema mínimo ──────────────────────────────────

@pytest.fixture
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE operacoes (
            hash TEXT, log_index INTEGER, data_hora TEXT,
            tipo TEXT, valor REAL, gas_usd REAL, token TEXT,
            sub_conta TEXT, bloco INTEGER, ambiente TEXT, fee REAL,
            strategy_addr TEXT, bot_id TEXT, gas_protocol REAL,
            old_balance_usd REAL,
            PRIMARY KEY (hash, log_index)
        );
        CREATE TABLE op_owner (
            hash TEXT, log_index INTEGER, wallet TEXT,
            PRIMARY KEY (hash, log_index)
        );
        CREATE TABLE users (
            chat_id INTEGER PRIMARY KEY,
            wallet TEXT, env TEXT, periodo TEXT, username TEXT,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE capital_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER, env TEXT, total_usd REAL,
            breakdown_json TEXT, updated_ts REAL
        );
        CREATE TABLE inactivity_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            end_block INTEGER, minutes REAL, tx_count INTEGER,
            note TEXT, created_at TEXT
        );
        CREATE TABLE kpi_cache (
            key TEXT PRIMARY KEY,
            value_json TEXT, computed_at REAL, ttl_seconds INTEGER
        );
    """)
    conn.commit()
    return conn


def _insert_trade(conn, hash_: str, log_idx: int, valor: float, gas: float,
                  env: str = "AG_C_bd", sub: str = "sub1",
                  ts: str = None):
    ts = ts or "2026-03-12 10:00:00"
    conn.execute(
        "INSERT INTO operacoes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (hash_, log_idx, ts, "Trade", valor, gas, "USDT", sub, 1000, env, 0, "", "", 0, 0),
    )
    conn.execute(
        "INSERT INTO op_owner VALUES (?,?,?)",
        (hash_, log_idx, "0xwallet"),
    )
    conn.commit()


# ── ops_today ─────────────────────────────────────────────────────────────────

class TestOpsToday:
    def test_empty_db_returns_zeros(self, db):
        result = ops_today(db)
        assert result["trades"] == 0
        assert result["bruto"] == 0.0
        assert result["liquido"] == 0.0
        assert result["winrate"] == 0.0

    def test_single_winning_trade(self, db):
        _insert_trade(db, "0xabc", 0, valor=5.0, gas=0.5)
        result = ops_today(db)
        assert result["trades"] == 1
        assert result["wins"] == 1
        assert result["winrate"] == 100.0
        assert abs(result["bruto"] - 5.0) < 0.001
        assert abs(result["liquido"] - 4.5) < 0.001

    def test_mixed_trades_winrate(self, db):
        _insert_trade(db, "0x001", 0, valor=3.0, gas=0.1)
        _insert_trade(db, "0x002", 0, valor=-1.0, gas=0.1)
        _insert_trade(db, "0x003", 0, valor=2.0, gas=0.1)
        result = ops_today(db)
        assert result["trades"] == 3
        assert result["wins"] == 2
        assert abs(result["winrate"] - 66.67) < 0.1

    def test_period_field_is_24h(self, db):
        result = ops_today(db)
        assert result["period"] == "24h"


# ── ops_by_env ────────────────────────────────────────────────────────────────

class TestOpsByEnv:
    def test_empty_returns_empty_list(self, db):
        result = ops_by_env(db)
        assert result == []

    def test_groups_by_environment(self, db):
        _insert_trade(db, "0xa01", 0, valor=2.0, gas=0.1, env="AG_C_bd")
        _insert_trade(db, "0xa02", 0, valor=3.0, gas=0.2, env="bd_v5")
        _insert_trade(db, "0xa03", 0, valor=1.0, gas=0.1, env="AG_C_bd")
        result = ops_by_env(db)
        envs = {r["env"] for r in result}
        assert "AG_C_bd" in envs
        assert "bd_v5" in envs
        ag = next(r for r in result if r["env"] == "AG_C_bd")
        assert ag["trades"] == 2

    def test_liquido_is_bruto_minus_gas(self, db):
        _insert_trade(db, "0xb01", 0, valor=10.0, gas=1.0, env="AG_C_bd")
        result = ops_by_env(db)
        assert len(result) == 1
        assert abs(result[0]["liquido"] - 9.0) < 0.001


# ── recent_ops ────────────────────────────────────────────────────────────────

class TestRecentOps:
    def test_returns_most_recent_first(self, db):
        _insert_trade(db, "0xc01", 0, valor=1.0, gas=0.1, ts="2026-03-12 08:00:00")
        _insert_trade(db, "0xc02", 0, valor=2.0, gas=0.1, ts="2026-03-12 09:00:00")
        result = recent_ops(db, limit=10)
        assert len(result) == 2
        assert result[0]["ts"] > result[1]["ts"]

    def test_limit_respected(self, db):
        for i in range(5):
            _insert_trade(db, f"0xd{i:02d}", 0, valor=float(i), gas=0.1)
        result = recent_ops(db, limit=3)
        assert len(result) == 3

    def test_result_has_required_fields(self, db):
        _insert_trade(db, "0xe01", 0, valor=1.0, gas=0.1)
        result = recent_ops(db, limit=1)
        assert len(result) == 1
        rec = result[0]
        for field in ["ts", "tipo", "valor", "gas_usd", "token", "sub_conta", "ambiente"]:
            assert field in rec


# ── kpi_cache ─────────────────────────────────────────────────────────────────

class TestKpiCache:
    def test_get_missing_key_returns_none(self, db):
        assert get_kpi(db, "nonexistent") is None

    def test_set_and_get_returns_value(self, db):
        set_kpi(db, "test_key", '{"val": 42}', ttl=60)
        result = get_kpi(db, "test_key")
        assert result == '{"val": 42}'

    def test_expired_ttl_returns_none(self, db):
        # TTL de 0 segundos → imediatamente expirado
        conn_time = time.time() - 10  # simula computed_at no passado
        db.execute(
            "INSERT OR REPLACE INTO kpi_cache VALUES (?,?,?,?)",
            ("expired_key", '{"val": 1}', conn_time, 5),
        )
        db.commit()
        assert get_kpi(db, "expired_key") is None

    def test_overwrite_existing_key(self, db):
        set_kpi(db, "dup", '{"v": 1}', ttl=60)
        set_kpi(db, "dup", '{"v": 2}', ttl=60)
        assert get_kpi(db, "dup") == '{"v": 2}'


# ── capital_by_env ────────────────────────────────────────────────────────────

class TestCapitalByEnv:
    def test_empty_returns_empty_dict(self, db):
        result = capital_by_env(db)
        assert result == {}

    def test_sums_capital_per_env(self, db):
        db.execute("INSERT INTO users VALUES (1, '0xaa', 'AG_C_bd', '1h', 'alice', 1)")
        db.execute("INSERT INTO users VALUES (2, '0xbb', 'bd_v5', '1h', 'bob', 1)")
        db.execute("INSERT INTO capital_cache (chat_id, env, total_usd) VALUES (1, 'AG_C_bd', 500.0)")
        db.execute("INSERT INTO capital_cache (chat_id, env, total_usd) VALUES (2, 'bd_v5', 300.0)")
        db.commit()
        result = capital_by_env(db)
        assert abs(result.get("AG_C_bd", 0) - 500.0) < 0.01
        assert abs(result.get("bd_v5", 0) - 300.0) < 0.01


# ── last_inactivity ───────────────────────────────────────────────────────────

class TestLastInactivity:
    def test_empty_returns_empty_list(self, db):
        assert last_inactivity(db) == []

    def test_returns_most_recent(self, db):
        db.execute(
            "INSERT INTO inactivity_stats (end_block, minutes, tx_count, note, created_at) VALUES (?,?,?,?,?)",
            (1000, 45.0, 3, "teste", "2026-03-12 10:00:00"),
        )
        db.execute(
            "INSERT INTO inactivity_stats (end_block, minutes, tx_count, note, created_at) VALUES (?,?,?,?,?)",
            (2000, 30.0, 1, "teste2", "2026-03-12 11:00:00"),
        )
        db.commit()
        result = last_inactivity(db, limit=1)
        assert len(result) == 1
        assert result[0]["end_block"] == 2000
