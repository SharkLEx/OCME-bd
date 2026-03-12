"""
tests/packages/test_monitor_core.py
Story 7.2 — Vigia Modular: testes do EventEmitter, RpcPool e BlockTimeCache.
Sem RPC real — usa mocks.
"""

from __future__ import annotations

import sqlite3
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── PATH setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "monitor-core"))
from vigia import _EventBus, _is_429_error, RpcPool, BlockTimeCache  # noqa: E402


# ── _is_429_error ─────────────────────────────────────────────────────────────

class TestIs429Error:
    def test_detects_429_in_message(self):
        assert _is_429_error(Exception("HTTP 429 Too Many Requests"))

    def test_detects_rate_limit(self):
        assert _is_429_error(Exception("rate limit exceeded"))

    def test_detects_too_many(self):
        assert _is_429_error(Exception("too many requests"))

    def test_normal_error_is_not_429(self):
        assert not _is_429_error(Exception("connection refused"))

    def test_timeout_is_not_429(self):
        assert not _is_429_error(Exception("timeout"))


# ── _EventBus ─────────────────────────────────────────────────────────────────

class TestEventBus:
    def test_on_returns_self_for_chaining(self):
        bus = _EventBus()
        result = bus.on("op", lambda x: x)
        assert result is bus

    def test_emit_calls_registered_listener(self):
        bus = _EventBus()
        received = []
        bus.on("test", lambda x: received.append(x))
        bus.emit("test", {"valor": 1})
        assert received == [{"valor": 1}]

    def test_emit_calls_multiple_listeners(self):
        bus = _EventBus()
        calls = []
        bus.on("ev", lambda x: calls.append("A"))
        bus.on("ev", lambda x: calls.append("B"))
        bus.emit("ev", None)
        assert calls == ["A", "B"]

    def test_emit_unknown_event_does_not_raise(self):
        bus = _EventBus()
        bus.emit("nonexistent", {})  # não deve levantar exceção

    def test_listener_exception_does_not_propagate(self):
        bus = _EventBus()
        bus.on("bad", lambda x: (_ for _ in ()).throw(RuntimeError("boom")))
        bus.on("bad", lambda x: None)
        # Não deve levantar — erros em callbacks são swallowed com warning
        bus.emit("bad", {})

    def test_different_events_are_isolated(self):
        bus = _EventBus()
        received_a = []
        received_b = []
        bus.on("a", lambda x: received_a.append(x))
        bus.on("b", lambda x: received_b.append(x))
        bus.emit("a", 1)
        assert received_a == [1]
        assert received_b == []

    def test_multiple_emits_accumulate(self):
        bus = _EventBus()
        log = []
        bus.on("op", lambda x: log.append(x))
        bus.emit("op", "first")
        bus.emit("op", "second")
        assert log == ["first", "second"]


# ── RpcPool ───────────────────────────────────────────────────────────────────

class TestRpcPool:
    """Testa RpcPool sem RPC real usando mocks de Web3."""

    def _make_mock_w3(self):
        w3 = MagicMock()
        w3.eth.block_number = 1000000
        w3.eth.get_logs.return_value = []
        w3.middleware_onion.inject = MagicMock()
        return w3

    def _make_pool(self) -> RpcPool:
        """Cria RpcPool com Web3 completamente mockado (sem RPC real)."""
        mock_w3 = self._make_mock_w3()
        with patch("web3.Web3") as MockW3:
            MockW3.HTTPProvider = MagicMock(return_value=MagicMock())
            MockW3.return_value = mock_w3
            pool = RpcPool.__new__(RpcPool)
            # Inicializa diretamente sem chamar __init__ que precisa de Web3 real
            pool._lock = threading.Lock()
            pool._instances = [mock_w3]
            pool._errors = [0]
            pool._cooldown_until = [0.0]
            import itertools
            pool._cycle = itertools.cycle(range(1))
            pool.primary = mock_w3
            pool._Web3 = MagicMock()
        return pool

    def test_mark_error_sets_cooldown(self):
        pool = self._make_pool()
        pool.mark_error(0)
        assert pool._cooldown_until[0] > time.time()

    def test_mark_ok_resets_errors(self):
        pool = self._make_pool()
        pool.mark_error(0)
        pool.mark_ok(0)
        assert pool._errors[0] == 0
        assert pool._cooldown_until[0] == 0.0

    def test_cooldown_increases_with_repeated_errors(self):
        pool = self._make_pool()
        pool.mark_error(0)
        cd1 = pool._cooldown_until[0] - time.time()
        pool.mark_ok(0)
        pool.mark_error(0)
        pool.mark_error(0)
        cd2 = pool._cooldown_until[0] - time.time()
        assert cd2 > cd1  # erros acumulados aumentam cooldown

    def test_mark_error_increments_error_count(self):
        pool = self._make_pool()
        pool.mark_error(0)
        pool.mark_error(0)
        assert pool._errors[0] == 2

    def test_cooldown_capped_at_300s(self):
        pool = self._make_pool()
        # Simula muitos erros consecutivos
        for _ in range(20):
            pool.mark_error(0)
        cd = pool._cooldown_until[0] - time.time()
        assert cd <= 305  # pequena margem pelo tempo de execução


# ── BlockTimeCache ────────────────────────────────────────────────────────────

class TestBlockTimeCache:
    @pytest.fixture
    def db_path(self, tmp_path) -> str:
        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE block_time_cache (bloco INTEGER PRIMARY KEY, block_ts REAL)")
        conn.commit()
        conn.close()
        return str(db_file)

    def test_get_missing_returns_none(self, db_path):
        cache = BlockTimeCache(db_path)
        assert cache.get(999999) is None

    def test_set_and_get_returns_value(self, db_path):
        cache = BlockTimeCache(db_path)
        ts = 1741786400.0
        cache.set(1000000, ts)
        assert cache.get(1000000) == ts

    def test_overwrite_existing_block(self, db_path):
        cache = BlockTimeCache(db_path)
        cache.set(100, 111.0)
        cache.set(100, 222.0)
        assert cache.get(100) == 222.0

    def test_thread_safety_concurrent_writes(self, db_path):
        cache = BlockTimeCache(db_path)
        errors = []

        def write_block(n):
            try:
                cache.set(n, float(n * 1000))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_block, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        # Verifica que alguns blocos foram escritos corretamente
        assert cache.get(0) == 0.0
        assert cache.get(10) == 10000.0
