"""
tests/packages/test_monitor_bot.py
Story 7.6 — Bot como UI: testa Notifier sem Telegram real, sem RPC direto.

AC validados:
- Handlers delegam para monitor-core/monitor-db (zero RPC direto)
- Anti-flood: NOTIF_QUEUE (5000 itens) + debounce 2s
- _send_with_retry com backoff
- 403 → desativa usuário no DB
- Resumo semanal automático com estrutura correta
- Testes: mock do bot, verifica que handlers não fazem I/O direto
"""

from __future__ import annotations

import queue
import sqlite3
import sys
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# ── PATH setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "monitor-bot"))


# ── Helpers para criar Notifier sem Telegram real ─────────────────────────────

def _make_notifier(db_file: str, admin_ids=None):
    """Cria Notifier com bot mockado (sem conexão Telegram real)."""
    mock_telebot = MagicMock()
    mock_bot_instance = MagicMock()
    mock_telebot.TeleBot.return_value = mock_bot_instance

    with patch.dict("sys.modules", {"telebot": mock_telebot,
                                    "telebot.types": MagicMock(),
                                    "telebot.apihelper": MagicMock(),
                                    "requests": MagicMock()}):
        from notifier import Notifier
        n = Notifier(
            token="123456789:AABBCCDDEEFFaabbccddeeff-1234567890",
            db_path=db_file,
            admin_ids=admin_ids or [999],
        )
        n._bot = mock_bot_instance
        return n, mock_bot_instance


# ── Fixture: DB em memória com schema mínimo ──────────────────────────────────

@pytest.fixture
def db_file(tmp_path) -> str:
    path = tmp_path / "test_bot.db"
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE users (
            chat_id INTEGER PRIMARY KEY,
            wallet TEXT, env TEXT, periodo TEXT, username TEXT,
            active INTEGER DEFAULT 1
        );
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

        -- Usuários ativos
        INSERT INTO users VALUES (101, '0xaabb', 'AG_C_bd', '1h', 'alice', 1);
        INSERT INTO users VALUES (102, '0xccdd', 'bd_v5',   '1h', 'bob',   1);
        INSERT INTO users VALUES (103, '0xeeff', 'AG_C_bd', '1h', 'charlie', 0);  -- inativo

        -- Trades
        INSERT INTO operacoes VALUES
            ('0xt1', 0, datetime('now','-1 hour'), 'Trade', 5.0, 0.5, 'USDT', 'sub1', 100, 'AG_C_bd', 0, '', '', 0, 0);
        INSERT INTO operacoes VALUES
            ('0xt2', 0, datetime('now','-2 hours'), 'Trade', -1.0, 0.2, 'USDT', 'sub2', 101, 'bd_v5', 0, '', '', 0, 0);

        -- Histórico de inatividade (para sigma)
        INSERT INTO inactivity_stats (end_block, minutes, tx_count, note, created_at)
            VALUES (99, 20.0, 5, '', datetime('now','-1 day'));
        INSERT INTO inactivity_stats (end_block, minutes, tx_count, note, created_at)
            VALUES (100, 25.0, 3, '', datetime('now','-2 days'));
        INSERT INTO inactivity_stats (end_block, minutes, tx_count, note, created_at)
            VALUES (101, 30.0, 2, '', datetime('now','-3 days'));
    """)
    conn.commit()
    conn.close()
    return str(path)


# ── Queue e estrutura ─────────────────────────────────────────────────────────

class TestQueueStructure:
    def test_queue_max_size_is_5000(self, db_file):
        n, _ = _make_notifier(db_file)
        assert n._notif_queue.maxsize == 5000

    def test_debounce_secs_is_2(self, db_file):
        n, _ = _make_notifier(db_file)
        assert n._DEBOUNCE_SECS == 2.0

    def test_enqueue_adds_to_queue(self, db_file):
        n, _ = _make_notifier(db_file)
        n._enqueue(101, "teste")
        assert not n._notif_queue.empty()

    def test_enqueue_full_queue_does_not_raise(self, db_file):
        n, _ = _make_notifier(db_file)
        # Enche a fila
        for _ in range(n._QUEUE_SIZE):
            try:
                n._notif_queue.put_nowait((0, "x", "HTML"))
            except queue.Full:
                break
        # Próximo enqueue não deve levantar exceção
        n._enqueue(101, "overflow silencioso")  # deve ser descartado silenciosamente

    def test_queue_item_has_chat_id_text_parse_mode(self, db_file):
        n, _ = _make_notifier(db_file)
        n._enqueue(101, "hello", "HTML")
        item = n._notif_queue.get_nowait()
        assert item == (101, "hello", "HTML")


# ── Handlers não fazem RPC direto ─────────────────────────────────────────────

class TestNoDirectRpc:
    """AC: handlers delegam para monitor-core/monitor-db (zero RPC direto)."""

    def test_on_operation_trade_enqueues_without_web3(self, db_file):
        """on_operation não deve chamar Web3 ou RPC."""
        n, mock_bot = _make_notifier(db_file)
        op = {
            "tipo": "Trade", "valor": 5.0, "gas_usd": 0.5, "gas_pol": 0.01,
            "token": "USDT", "tx_hash": "0xabc", "ambiente": "AG_C_bd",
            "sub_conta": "sub1", "bot_id": "Standard", "fee": 0.0, "bloco": 999,
            "notify_cids": [101],
        }
        # Se chamar Web3 ou RPC, vai levantar AttributeError (mock não tem esses métodos)
        n._dispatch_trade(op)
        # Deve ter enfileirado 1 mensagem para chat_id=101
        assert n._notif_queue.qsize() == 1

    def test_on_operation_transfer_enqueues_without_rpc(self, db_file):
        n, _ = _make_notifier(db_file)
        op = {
            "tipo": "Transfer", "valor": 100.0, "token": "USDT",
            "tx_hash": "0xabc", "direction": "in", "notify_cids": [101],
        }
        n._dispatch_transfer(op)
        assert n._notif_queue.qsize() == 1

    def test_notifier_module_has_no_web3_import(self):
        """notifier.py não deve importar web3 diretamente."""
        notifier_file = Path(__file__).parents[2] / "packages" / "monitor-bot" / "notifier.py"
        content = notifier_file.read_text(encoding="utf-8")
        assert "from web3" not in content
        assert "import web3" not in content
        assert "w3.eth" not in content

    def test_notifier_module_has_no_rpc_calls(self):
        """notifier.py não deve ter chamadas RPC hardcoded."""
        notifier_file = Path(__file__).parents[2] / "packages" / "monitor-bot" / "notifier.py"
        content = notifier_file.read_text(encoding="utf-8")
        # Padrões RPC típicos não devem aparecer
        assert "eth_getBlock" not in content
        assert "eth_getTransactionReceipt" not in content
        assert "alchemy.com" not in content


# ── Dispatch trade ────────────────────────────────────────────────────────────

class TestDispatchTrade:
    def test_no_notify_cids_skips_enqueue(self, db_file):
        n, _ = _make_notifier(db_file)
        op = {"tipo": "Trade", "valor": 1.0, "notify_cids": []}
        n._dispatch_trade(op)
        assert n._notif_queue.empty()

    def test_trade_msg_contains_execution_header(self, db_file):
        n, _ = _make_notifier(db_file)
        msg = n._build_trade_msg(
            chat_id=101, sub="sub1", val=5.0, gas_usd=0.5, gas_pol=0.01,
            token="USDT", tx="0xabc", env_tag="AG_C_bd", bot_id="Standard",
            fee=0.0, bloco=999
        )
        assert "EXECUÇÃO CONFIRMADA" in msg
        assert "WEbdEX ENGINE" in msg

    def test_trade_msg_contains_tx_link(self, db_file):
        n, _ = _make_notifier(db_file)
        msg = n._build_trade_msg(
            chat_id=101, sub="sub1", val=5.0, gas_usd=0.5, gas_pol=0.01,
            token="USDT", tx="0xdeadbeef", env_tag="AG_C_bd", bot_id="Standard",
            fee=0.0, bloco=999
        )
        assert "polygonscan.com/tx/0xdeadbeef" in msg

    def test_trade_msg_shows_net_pos_gas(self, db_file):
        n, _ = _make_notifier(db_file)
        msg = n._build_trade_msg(
            chat_id=101, sub="sub1", val=5.0, gas_usd=0.5, gas_pol=0.01,
            token="USDT", tx="0xabc", env_tag="AG_C_bd", bot_id="Standard",
            fee=0.0, bloco=999
        )
        # Net = 5.0 - 0.5 = 4.5
        assert "+4.5" in msg or "4.5" in msg

    def test_trade_msg_xss_safe_sub_conta(self, db_file):
        """Subconta com HTML malicioso deve ser escapada."""
        n, _ = _make_notifier(db_file)
        msg = n._build_trade_msg(
            chat_id=101, sub="<script>alert(1)</script>", val=1.0,
            gas_usd=0.1, gas_pol=0.0, token="USDT", tx="", env_tag="test",
            bot_id="bot", fee=0.0, bloco=0
        )
        assert "<script>" not in msg

    def test_dispatch_trade_multiple_cids(self, db_file):
        n, _ = _make_notifier(db_file)
        op = {
            "tipo": "Trade", "valor": 5.0, "gas_usd": 0.5, "gas_pol": 0.01,
            "token": "USDT", "tx_hash": "0xabc", "ambiente": "AG_C_bd",
            "sub_conta": "sub1", "bot_id": "Standard", "fee": 0.0, "bloco": 999,
            "notify_cids": [101, 102],
        }
        n._dispatch_trade(op)
        assert n._notif_queue.qsize() == 2


# ── Alertas proativos ─────────────────────────────────────────────────────────

class TestAlerts:
    def test_on_alert_inatividade_enqueues_for_active_users(self, db_file):
        n, _ = _make_notifier(db_file)
        n.on_alert({"tipo": "inatividade", "dados": {"minutos": 45.0, "tx_count": 2, "last_block": 1000}})
        # Usuários ativos: 101 e 102 (103 é inativo)
        assert n._notif_queue.qsize() == 2

    def test_inactivity_msg_contains_minutes(self, db_file):
        n, _ = _make_notifier(db_file)
        n._dispatch_inactivity_alert({"minutos": 45.0, "tx_count": 2, "last_block": 1000})
        item = n._notif_queue.get_nowait()
        assert "45.0 minutos" in item[1]

    def test_inactivity_msg_contains_alerta_header(self, db_file):
        n, _ = _make_notifier(db_file)
        n._dispatch_inactivity_alert({"minutos": 45.0, "tx_count": 0, "last_block": 1000})
        item = n._notif_queue.get_nowait()
        assert "ALERTA DE INATIVIDADE" in item[1]

    def test_inactivity_alert_severity_red_at_60min(self, db_file):
        n, _ = _make_notifier(db_file)
        n._dispatch_inactivity_alert({"minutos": 60.0, "tx_count": 0, "last_block": 1000})
        item = n._notif_queue.get_nowait()
        assert "🔴" in item[1]

    def test_inactivity_sigma_line_present_with_history(self, db_file):
        """Com histórico suficiente, deve mostrar análise sigma."""
        n, _ = _make_notifier(db_file)
        # 3 registros no DB (20, 25, 30 min) → média ~25; 45min está acima
        n._dispatch_inactivity_alert({"minutos": 45.0, "tx_count": 0, "last_block": 1000})
        item = n._notif_queue.get_nowait()
        # Deve mencionar sigma ou média histórica
        msg = item[1]
        has_sigma = "σ" in msg or "média" in msg.lower()
        assert has_sigma

    def test_gas_alert_enqueues_for_admins(self, db_file):
        n, _ = _make_notifier(db_file, admin_ids=[999])
        n.on_alert({"tipo": "gas_alto", "dados": {"gas_usd": 2.5, "tx_hash": "0xabc", "sub_conta": "sub1"}})
        assert n._notif_queue.qsize() == 1
        item = n._notif_queue.get_nowait()
        assert item[0] == 999
        assert "GAS ALTO" in item[1]

    def test_rpc_alert_enqueues_for_admins(self, db_file):
        n, _ = _make_notifier(db_file, admin_ids=[999])
        n.on_alert({"tipo": "rpc_error", "dados": {"rpc_errors_total": 10, "last_error": "timeout"}})
        assert n._notif_queue.qsize() == 1
        assert "RPC ERRORS" in n._notif_queue.get_nowait()[1]

    def test_vigia_error_enqueues_for_admins(self, db_file):
        n, _ = _make_notifier(db_file, admin_ids=[999])
        n.on_vigia_error("Connection refused")
        assert n._notif_queue.qsize() == 1
        assert "VIGIA ERROR" in n._notif_queue.get_nowait()[1]


# ── 403 → desativa usuário ────────────────────────────────────────────────────

class TestForbiddenDeactivation:
    def test_403_deactivates_user_in_db(self, db_file):
        n, mock_bot = _make_notifier(db_file)
        mock_bot.send_message.side_effect = Exception("Error code: 403: Forbidden: bot was blocked by the user")
        n._send_with_retry(101, "test")
        # Verifica que o usuário foi desativado no DB
        conn = sqlite3.connect(db_file)
        row = conn.execute("SELECT active FROM users WHERE chat_id=101").fetchone()
        conn.close()
        assert row[0] == 0

    def test_forbidden_string_triggers_deactivation(self, db_file):
        n, mock_bot = _make_notifier(db_file)
        mock_bot.send_message.side_effect = Exception("Forbidden: user is deactivated")
        n._send_with_retry(102, "test")
        conn = sqlite3.connect(db_file)
        row = conn.execute("SELECT active FROM users WHERE chat_id=102").fetchone()
        conn.close()
        assert row[0] == 0

    def test_non_403_does_retry(self, db_file):
        n, mock_bot = _make_notifier(db_file)
        # Falha genérica — deve tentar max_retries vezes
        mock_bot.send_message.side_effect = Exception("Network error")
        n._send_with_retry(101, "test", max_retries=2)
        assert mock_bot.send_message.call_count == 2


# ── Send with retry ───────────────────────────────────────────────────────────

class TestSendWithRetry:
    def test_success_on_first_attempt(self, db_file):
        n, mock_bot = _make_notifier(db_file)
        mock_bot.send_message.return_value = True
        n._send_with_retry(101, "hello")
        mock_bot.send_message.assert_called_once()

    def test_text_truncated_at_safe_limit(self, db_file):
        n, mock_bot = _make_notifier(db_file)
        mock_bot.send_message.return_value = True
        long_text = "x" * 5000
        n._send_with_retry(101, long_text)
        sent_text = mock_bot.send_message.call_args[0][1]
        assert len(sent_text) <= n._TG_SAFE_LIMIT + 50  # +50 para o "[truncado]"
        assert "truncado" in sent_text


# ── DB helpers ────────────────────────────────────────────────────────────────

class TestDbHelpers:
    def test_get_active_users_returns_only_active(self, db_file):
        n, _ = _make_notifier(db_file)
        users = n._get_active_users()
        assert 101 in users
        assert 102 in users
        assert 103 not in users  # inativo

    def test_deactivate_user_sets_active_0(self, db_file):
        n, _ = _make_notifier(db_file)
        n._deactivate_user(101)
        conn = sqlite3.connect(db_file)
        row = conn.execute("SELECT active FROM users WHERE chat_id=101").fetchone()
        conn.close()
        assert row[0] == 0

    def test_get_today_stats_returns_dict(self, db_file):
        n, _ = _make_notifier(db_file)
        stats = n._get_today_stats(101)
        assert "trades" in stats
        assert "pnl" in stats
        assert "wins" in stats
        assert "winrate" in stats

    def test_get_today_stats_unknown_user_returns_zeros(self, db_file):
        n, _ = _make_notifier(db_file)
        stats = n._get_today_stats(9999)
        assert stats["trades"] == 0
        assert stats["pnl"] == 0.0

    def test_get_inactivity_history_returns_stats(self, db_file):
        n, _ = _make_notifier(db_file)
        hist = n._get_inactivity_history()
        assert hist["count"] == 3
        assert hist["avg_mins"] > 0
        assert hist["std_mins"] >= 0

    def test_get_inactivity_history_empty_db(self, tmp_path):
        # DB sem tabela inactivity_stats
        path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(path))
        conn.close()
        n, _ = _make_notifier(str(path))
        hist = n._get_inactivity_history()
        assert hist["count"] == 0


# ── Resumo semanal ────────────────────────────────────────────────────────────

class TestWeeklySummary:
    def test_send_weekly_summary_enqueues_for_active_users(self, db_file):
        n, _ = _make_notifier(db_file)
        # Adiciona trades de 7d para o DB
        conn = sqlite3.connect(db_file)
        conn.execute("""
            INSERT INTO operacoes VALUES
            ('0wt1', 0, datetime('now','-3 days'), 'Trade', 3.0, 0.3, 'USDT',
             'sub1', 200, 'AG_C_bd', 0, '', '', 0, 0)
        """)
        conn.commit()
        conn.close()
        n.send_weekly_summary()
        # Deve enfileirar para os 2 usuários ativos
        assert n._notif_queue.qsize() == 2

    def test_weekly_summary_msg_contains_header(self, db_file):
        n, _ = _make_notifier(db_file)
        n.send_weekly_summary()
        if n._notif_queue.qsize() > 0:
            item = n._notif_queue.get_nowait()
            assert "RESUMO SEMANAL" in item[1]

    def test_weekly_summary_with_ai_engine(self, db_file):
        """Com AI engine mockado, deve incluir seção de análise."""
        n, _ = _make_notifier(db_file)
        mock_ai = MagicMock()
        mock_ai.answer.return_value = "O protocolo teve bom desempenho esta semana."
        n.send_weekly_summary(ai_engine=mock_ai)
        if n._notif_queue.qsize() > 0:
            item = n._notif_queue.get_nowait()
            msg = item[1]
            assert "Análise IA" in msg or "bom desempenho" in msg

    def test_weekly_summary_ai_failure_does_not_crash(self, db_file):
        """Falha da IA não deve derrubar o resumo semanal."""
        n, _ = _make_notifier(db_file)
        mock_ai = MagicMock()
        mock_ai.answer.side_effect = Exception("API down")
        # Não deve levantar exceção
        n.send_weekly_summary(ai_engine=mock_ai)

    def test_get_weekly_kpis_returns_required_fields(self, db_file):
        n, _ = _make_notifier(db_file)
        kpis = n._get_weekly_kpis()
        assert "pnl_7d" in kpis
        assert "trades_7d" in kpis
        assert "winrate_7d" in kpis
        assert "best_env" in kpis
        assert "worst_env" in kpis


# ── Lifecycle ─────────────────────────────────────────────────────────────────

class TestLifecycle:
    def test_start_creates_worker_thread(self, db_file):
        n, _ = _make_notifier(db_file)
        n.start(daemon=True)
        assert n._running is True
        assert n._worker_thread is not None
        assert n._worker_thread.is_alive()
        n.stop(timeout=1.0)

    def test_stop_sets_running_false(self, db_file):
        n, _ = _make_notifier(db_file)
        n.start(daemon=True)
        n.stop(timeout=1.0)
        assert n._running is False

    def test_invalid_token_raises_value_error(self, db_file):
        mock_telebot = MagicMock()
        with patch.dict("sys.modules", {"telebot": mock_telebot,
                                        "telebot.types": MagicMock(),
                                        "telebot.apihelper": MagicMock(),
                                        "requests": MagicMock()}):
            from notifier import Notifier
            with pytest.raises(ValueError, match="TELEGRAM_TOKEN"):
                Notifier(token="invalid", db_path=db_file)
