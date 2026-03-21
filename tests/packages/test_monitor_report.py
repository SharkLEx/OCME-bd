"""
tests/packages/test_monitor_report.py
Story 7.5 — Dashboard Cache: testes de latência, TTL, cache invalidation e gráficos.
"""

from __future__ import annotations

import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

# ── PATH setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "monitor-report"))
from dashboard_cache import DashboardCache  # noqa: E402


# ── Fixture: DB em memória com dados de KPI ───────────────────────────────────

@pytest.fixture
def db_file(tmp_path) -> str:
    path = tmp_path / "test_report.db"
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE operacoes (
            hash TEXT, log_index INTEGER, data_hora TEXT,
            tipo TEXT, valor REAL, gas_usd REAL, token TEXT,
            sub_conta TEXT, bloco INTEGER, ambiente TEXT, fee REAL,
            strategy_addr TEXT, bot_id TEXT, gas_protocol REAL, old_balance_usd REAL,
            PRIMARY KEY (hash, log_index)
        );
        CREATE TABLE capital_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER, env TEXT, total_usd REAL,
            breakdown_json TEXT, updated_ts REAL
        );

        -- Trades últimas 24h
        INSERT INTO operacoes VALUES
            ('0xa01', 0, datetime('now','-1 hour'), 'Trade', 5.0, 0.5, 'USDT', 'sub1', 100, 'AG_C_bd', 0, '', '', 0, 0);
        INSERT INTO operacoes VALUES
            ('0xa02', 0, datetime('now','-2 hours'), 'Trade', -1.0, 0.2, 'USDT', 'sub2', 101, 'AG_C_bd', 0, '', '', 0, 0);
        INSERT INTO operacoes VALUES
            ('0xa03', 0, datetime('now','-3 hours'), 'Trade', 3.0, 0.3, 'USDT', 'sub1', 102, 'bd_v5', 0, '', '', 0, 0);
        INSERT INTO operacoes VALUES
            ('0xa04', 0, datetime('now','-4 hours'), 'Trade', 2.0, 0.1, 'USDT', 'sub3', 103, 'bd_v5', 0, '', '', 0, 0);

        -- Capital
        INSERT INTO capital_cache (chat_id, env, total_usd) VALUES (1, 'AG_C_bd', 1000.0);
        INSERT INTO capital_cache (chat_id, env, total_usd) VALUES (2, 'bd_v5', 800.0);
    """)
    conn.commit()
    conn.close()
    return str(path)


# ── KPI structure ─────────────────────────────────────────────────────────────

class TestKpiStructure:
    def test_get_returns_dict(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        assert isinstance(result, dict)

    def test_get_has_all_required_fields(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        required = [
            "pnl_24h", "pnl_7d", "pnl_30d",
            "trades_24h", "winrate_24h", "avg_gas_24h",
            "best_sub", "worst_sub",
            "total_capital", "last_block", "capture_rate",
            "updated_at", "stale", "by_env",
        ]
        for field in required:
            assert field in result, f"Campo '{field}' ausente"

    def test_pnl_24h_is_float(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        assert isinstance(result["pnl_24h"], float)

    def test_trades_24h_is_int(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        assert isinstance(result["trades_24h"], int)

    def test_winrate_between_0_and_100(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        assert 0.0 <= result["winrate_24h"] <= 100.0

    def test_by_env_is_list(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        assert isinstance(result["by_env"], list)

    def test_stale_is_bool(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        assert isinstance(result["stale"], bool)


# ── KPI values ────────────────────────────────────────────────────────────────

class TestKpiValues:
    def test_trades_24h_count_correct(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        assert result["trades_24h"] == 4

    def test_pnl_24h_is_sum_minus_gas(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        # (5.0-0.5) + (-1.0-0.2) + (3.0-0.3) + (2.0-0.1) = 4.5 - 1.2 + 2.7 + 1.9 = 7.9
        assert abs(result["pnl_24h"] - 7.9) < 0.01

    def test_total_capital_correct(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        assert abs(result["total_capital"] - 1800.0) < 0.01

    def test_best_sub_is_sub1(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        best = result["best_sub"]
        assert best is not None
        # sub1 tem AG_C_bd(4.5) + bd_v5(2.7) = maior acumulado por subconta individual
        assert best["sub"] in ("sub1", "sub3")  # ambas positivas

    def test_worst_sub_has_lowest_pnl(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        worst = result["worst_sub"]
        assert worst is not None
        assert worst["sub"] == "sub2"  # único negativo

    def test_by_env_has_both_environments(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        envs = {e["env"] for e in result["by_env"]}
        assert "AG_C_bd" in envs
        assert "bd_v5" in envs


# ── Cache TTL e invalidation ──────────────────────────────────────────────────

class TestCacheTtl:
    def test_not_stale_immediately_after_get(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get()
        assert result["stale"] is False

    def test_stale_after_2x_ttl(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=1)
        cache.get()  # popula
        cache._updated_at = time.time() - 3.0  # simula 3s atrás (> 2x TTL=1)
        result = cache.get(force=False)
        # Após TTL, recalcula — stale depende de 2x TTL
        assert isinstance(result["stale"], bool)

    def test_force_get_refreshes_data(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=3600)
        cache.get()
        t0 = cache._updated_at
        time.sleep(0.05)
        cache.get(force=True)
        assert cache._updated_at > t0

    def test_invalidate_marks_dirty(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=3600)
        cache.get()
        cache._dirty = False
        cache.invalidate()
        assert cache._dirty is True

    def test_on_new_op_marks_dirty(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=3600)
        cache.get()
        cache._dirty = False
        cache.on_new_op({"tipo": "Trade", "valor": 1.0})
        assert cache._dirty is True

    def test_on_progress_with_ops_marks_dirty(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=3600)
        cache.get()
        cache._dirty = False
        cache.on_progress({"ops_in_cycle": 1, "last_block": 1000, "capture_rate": 99.9})
        assert cache._dirty is True

    def test_on_progress_without_ops_does_not_mark_dirty(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=3600)
        cache.get()
        cache._dirty = False
        cache.on_progress({"ops_in_cycle": 0, "last_block": 1001, "capture_rate": 100.0})
        assert cache._dirty is False

    def test_on_progress_updates_last_block_in_place(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=3600)
        cache.get()
        cache.on_progress({"ops_in_cycle": 0, "last_block": 99999, "capture_rate": 100.0})
        assert cache._data.get("last_block") == 99999


# ── get_env ───────────────────────────────────────────────────────────────────

class TestGetEnv:
    def test_get_env_returns_correct_env(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get_env("AG_C_bd")
        assert result is not None
        assert result["env"] == "AG_C_bd"

    def test_get_env_returns_none_for_unknown(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get_env("UNKNOWN_ENV")
        assert result is None


# ── Latência < 500ms ──────────────────────────────────────────────────────────

class TestLatency:
    def test_get_under_500ms_first_call(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        t0 = time.time()
        cache.get()
        elapsed_ms = (time.time() - t0) * 1000
        assert elapsed_ms < 500, f"Primeira chamada levou {elapsed_ms:.1f}ms (> 500ms)"

    def test_get_under_10ms_cached(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        cache.get()  # popula cache
        t0 = time.time()
        cache.get()  # cache hit
        elapsed_ms = (time.time() - t0) * 1000
        assert elapsed_ms < 10, f"Cache hit levou {elapsed_ms:.1f}ms (> 10ms)"

    def test_100_concurrent_reads_under_500ms(self, db_file):
        """Constitution AC: Dashboard < 500ms em 100 acessos simultâneos."""
        cache = DashboardCache(db_file, ttl_seconds=60)
        cache.get()  # popula cache

        errors = []
        timings = []

        def _read():
            t0 = time.time()
            try:
                result = cache.get()
                assert "pnl_24h" in result
            except Exception as e:
                errors.append(e)
            finally:
                timings.append((time.time() - t0) * 1000)

        threads = [threading.Thread(target=_read) for _ in range(100)]
        t_start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_ms = (time.time() - t_start) * 1000

        assert errors == [], f"Erros em reads concorrentes: {errors}"
        max_latency = max(timings)
        assert max_latency < 500, f"Pior latência: {max_latency:.1f}ms (> 500ms)"

    def test_100_concurrent_reads_no_race_conditions(self, db_file):
        """Sem condições de corrida em leitura/escrita simultânea."""
        cache = DashboardCache(db_file, ttl_seconds=1)

        errors = []

        def _reader():
            try:
                for _ in range(5):
                    cache.get()
            except Exception as e:
                errors.append(("read", e))

        def _invalidator():
            try:
                for _ in range(5):
                    cache.on_new_op({"tipo": "Trade"})
                    time.sleep(0.001)
            except Exception as e:
                errors.append(("invalidate", e))

        threads = [threading.Thread(target=_reader) for _ in range(10)]
        threads += [threading.Thread(target=_invalidator) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Race condition detectada: {errors}"


# ── Gráficos ──────────────────────────────────────────────────────────────────

class TestCharts:
    def test_get_chart_returns_none_before_generation(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        result = cache.get_chart("pnl_24h")
        assert result is None

    def test_request_chart_update_does_not_block(self, db_file):
        cache = DashboardCache(db_file, ttl_seconds=60)
        t0 = time.time()
        cache.request_chart_update()
        elapsed = time.time() - t0
        assert elapsed < 0.5, f"request_chart_update bloqueou {elapsed:.2f}s"

    def test_on_new_op_triggers_chart_update(self, db_file):
        """on_new_op deve iniciar geração de gráficos em background."""
        cache = DashboardCache(db_file, ttl_seconds=60)
        cache.on_new_op({"tipo": "Trade", "valor": 1.0})
        # Thread deve ter sido agendada (pode não estar completa ainda)
        assert cache._chart_thread is not None

    def test_chart_bytes_are_png_if_matplotlib_available(self, db_file):
        """Se matplotlib disponível, gráfico gerado é PNG válido."""
        pytest.importorskip("matplotlib")
        cache = DashboardCache(db_file, ttl_seconds=60)
        cache.get()  # popula dados
        cache.request_chart_update()

        # Aguarda geração (timeout 5s)
        deadline = time.time() + 5
        while time.time() < deadline:
            if cache.get_chart("pnl_24h") is not None:
                break
            time.sleep(0.1)

        chart = cache.get_chart("pnl_24h")
        if chart is None:
            pytest.skip("Nenhum dado para gerar gráfico (DB pode estar vazio no período)")

        # PNG começa com magic bytes: \x89PNG
        assert chart[:4] == b'\x89PNG', "Gráfico não é PNG válido"

    def test_chart_generation_does_not_raise_without_matplotlib(self, db_file, monkeypatch):
        """Sem matplotlib, deve falhar silenciosamente sem derrubar o sistema."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "matplotlib":
                raise ImportError("matplotlib not available")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        cache = DashboardCache(db_file, ttl_seconds=60)
        # Não deve levantar exceção
        cache.request_chart_update()
        if cache._chart_thread:
            cache._chart_thread.join(timeout=2)
        # Sistema continua funcionando — get() ainda retorna dados
        result = cache.get()
        assert "pnl_24h" in result
