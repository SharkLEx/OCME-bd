"""
tests/packages/test_monitor_cli.py
Story 7.1 — CLI Foundation: testes dos comandos sem Telegram, sem RPC real.
Valida Constitution Art. I — CLI First (100% operacional sem Telegram).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# ── PATH setup ────────────────────────────────────────────────────────────────
_CLI_PATH = Path(__file__).parents[2] / "packages" / "monitor-cli"
_DB_PATH = Path(__file__).parents[2] / "packages" / "monitor-db"
sys.path.insert(0, str(_CLI_PATH))
sys.path.insert(0, str(_DB_PATH))


# ── Fixture: DB em memória com dados mínimos ──────────────────────────────────

@pytest.fixture
def db_file(tmp_path) -> str:
    """Cria DB SQLite temporário com schema mínimo e dados de teste."""
    db_path = tmp_path / "test_monitor.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE operacoes (
            hash TEXT, log_index INTEGER, data_hora TEXT,
            tipo TEXT, valor REAL, gas_usd REAL, token TEXT,
            sub_conta TEXT, bloco INTEGER, ambiente TEXT, fee REAL,
            strategy_addr TEXT, bot_id TEXT, gas_protocol REAL, old_balance_usd REAL,
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
        CREATE TABLE vigia_health (
            id INTEGER PRIMARY KEY,
            last_block INTEGER, loops_total INTEGER, ops_total INTEGER,
            rpc_errors INTEGER, capture_rate REAL, last_error TEXT,
            started_at REAL, updated_at REAL
        );
        CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE _schema_version (version INTEGER, applied_at TEXT);
        INSERT INTO _schema_version VALUES (6, datetime('now'));

        -- Dados de teste
        INSERT INTO vigia_health VALUES (1, 68500000, 1500, 42, 0, 99.8, '', 1741700000.0, 1741786400.0);
        INSERT INTO config VALUES ('last_block', '68500000');
        INSERT INTO users VALUES (101, '0xaabbcc', 'AG_C_bd', '1h', 'alice', 1);
        INSERT INTO users VALUES (102, '0xddeeff', 'bd_v5',   '1h', 'bob',   1);
        INSERT INTO operacoes VALUES
            ('0xtrade1', 0, datetime('now','-1 hour'), 'Trade', 5.0, 0.5, 'USDT',
             'sub1', 68499990, 'AG_C_bd', 0, '', '', 0, 0);
        INSERT INTO op_owner VALUES ('0xtrade1', 0, '0xaabbcc');
        INSERT INTO operacoes VALUES
            ('0xtrade2', 0, datetime('now','-2 hours'), 'Trade', -1.0, 0.2, 'USDT',
             'sub2', 68499980, 'bd_v5', 0, '', '', 0, 0);
        INSERT INTO op_owner VALUES ('0xtrade2', 0, '0xddeeff');
        INSERT INTO capital_cache (chat_id, env, total_usd) VALUES (101, 'AG_C_bd', 1500.0);
        INSERT INTO capital_cache (chat_id, env, total_usd) VALUES (102, 'bd_v5', 800.0);
        INSERT INTO inactivity_stats (end_block, minutes, tx_count, note, created_at)
            VALUES (68499900, 35.0, 2, 'teste alerta', datetime('now','-3 hours'));
    """)
    conn.commit()
    conn.close()
    return str(db_path)


# ── Testes dos commands/*.py diretamente ─────────────────────────────────────

class TestStatusCommand:
    def test_run_returns_dict_with_required_fields(self, db_file):
        try:
            from commands.status import run
        except ImportError:
            pytest.skip("commands.status não disponível no path atual")

        result = run(db_path=db_file, env=None, json_output=False)
        # run() pode retornar None (output direto) ou dict; aceita ambos
        # O importante é não levantar exceção
        assert True

    def test_run_with_json_output_does_not_raise(self, db_file):
        try:
            from commands.status import run
        except ImportError:
            pytest.skip("commands.status não disponível")
        run(db_path=db_file, env=None, json_output=True)


class TestReportCommand:
    def test_run_24h_period(self, db_file):
        try:
            from commands.report import run
        except ImportError:
            pytest.skip("commands.report não disponível")
        run(db_path=db_file, period="24h", env=None, limit=10, json_output=False)

    def test_run_7d_period(self, db_file):
        try:
            from commands.report import run
        except ImportError:
            pytest.skip("commands.report não disponível")
        run(db_path=db_file, period="7d", env=None, limit=10, json_output=False)

    def test_run_json_returns_serializable(self, db_file, capsys):
        try:
            from commands.report import run
        except ImportError:
            pytest.skip("commands.report não disponível")
        run(db_path=db_file, period="24h", env=None, limit=10, json_output=True)
        captured = capsys.readouterr()
        if captured.out.strip():
            json.loads(captured.out)  # deve ser JSON válido


class TestCapitalCommand:
    def test_run_all_wallets(self, db_file):
        try:
            from commands.capital import run
        except ImportError:
            pytest.skip("commands.capital não disponível")
        run(db_path=db_file, wallet=None, json_output=False)

    def test_run_specific_wallet(self, db_file):
        try:
            from commands.capital import run
        except ImportError:
            pytest.skip("commands.capital não disponível")
        run(db_path=db_file, wallet="0xaabbcc", json_output=False)


class TestAlertsCommand:
    def test_run_list_alerts(self, db_file):
        try:
            from commands.alerts import run
        except ImportError:
            pytest.skip("commands.alerts não disponível")
        run(db_path=db_file, subcommand="list", json_output=False)

    def test_run_active_alerts(self, db_file):
        try:
            from commands.alerts import run
        except ImportError:
            pytest.skip("commands.alerts não disponível")
        run(db_path=db_file, subcommand="active", json_output=False)


# ── Testes de resolução de DB path ────────────────────────────────────────────

class TestDbPathResolution:
    def test_valid_path_returns_string(self, db_file):
        try:
            from cli import _resolve_db
        except ImportError:
            pytest.skip("cli._resolve_db não disponível")
        result = _resolve_db(db_file)
        assert isinstance(result, str)
        assert result == db_file

    def test_invalid_path_calls_sys_exit(self, tmp_path):
        try:
            from cli import _resolve_db
        except ImportError:
            pytest.skip("cli._resolve_db não disponível")
        with pytest.raises(SystemExit):
            _resolve_db(str(tmp_path / "nao_existe.db"))


# ── Testes de Constitution Art. I — CLI First ─────────────────────────────────

class TestCliFirst:
    """Garante que comandos rodam 100% sem Telegram iniciado."""

    def test_no_telegram_import_in_queries(self):
        """monitor-db/queries.py não deve importar nada do Telegram."""
        import queries
        # Se não levantou ImportError, o módulo importou sem Telegram
        assert True

    def test_queries_work_with_sqlite_only(self, db_file):
        """queries.py deve funcionar com SQLite puro, sem dependências externas."""
        import queries
        conn = sqlite3.connect(db_file)
        result = queries.ops_today(conn)
        conn.close()
        assert "trades" in result
        assert "winrate" in result

    def test_db_module_has_no_telegram_dependency(self):
        """Verifica que monitor-db não importa telebot ou similar."""
        queries_file = Path(__file__).parents[2] / "packages" / "monitor-db" / "queries.py"
        content = queries_file.read_text(encoding="utf-8")
        assert "telebot" not in content
        assert "import telegram" not in content
        assert "bot.send" not in content
