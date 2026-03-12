"""
tests/packages/test_monitor_ai.py
Story 7.4 — IA Contextual: mock da API, verificação de contexto injetado.
Sem chamadas reais à OpenAI/OpenRouter.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── PATH setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "monitor-ai"))
from context_builder import ContextBuilder, _period_hours, _since_dt  # noqa: E402
from ai_engine import AIEngine, _pretty_ai_text  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_file(tmp_path) -> str:
    path = tmp_path / "test_ai.db"
    conn = sqlite3.connect(str(path))
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
            chat_id TEXT PRIMARY KEY,
            wallet TEXT, env TEXT, periodo TEXT, username TEXT,
            active INTEGER DEFAULT 1, admin INTEGER DEFAULT 0
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
        CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT);

        -- Dados de teste
        INSERT INTO users VALUES ('101', '0xaabbcc', 'AG_C_bd', '1h', 'alice', 1, 0);
        INSERT INTO users VALUES ('999', '0xadmin1', 'AG_C_bd', '1h', 'admin', 1, 1);
        INSERT INTO capital_cache (chat_id, env, total_usd, updated_ts)
            VALUES (101, 'AG_C_bd', 1500.0, strftime('%s','now'));
        INSERT INTO operacoes VALUES
            ('0xt1', 0, datetime('now','-1 hour'), 'Trade', 5.0, 0.5,
             'USDT', 'sub1', 68000000, 'AG_C_bd', 0, '', '', 0, 0);
        INSERT INTO op_owner VALUES ('0xt1', 0, '0xaabbcc');
        INSERT INTO operacoes VALUES
            ('0xt2', 0, datetime('now','-2 hours'), 'Trade', -1.5, 0.3,
             'USDT', 'sub2', 68000001, 'AG_C_bd', 0, '', '', 0, 0);
        INSERT INTO op_owner VALUES ('0xt2', 0, '0xaabbcc');
        INSERT INTO operacoes VALUES
            ('0xt3', 0, datetime('now','-3 hours'), 'Trade', 3.0, 0.2,
             'USDT', 'sub1', 68000002, 'bd_v5', 0, '', '', 0, 0);
        INSERT INTO op_owner VALUES ('0xt3', 0, '0xaabbcc');
        INSERT INTO inactivity_stats (end_block, minutes, tx_count, note, created_at)
            VALUES (68000000, 42.0, 5, 'parado', datetime('now','-4 hours'));
        INSERT INTO config VALUES ('ai_global_enabled', '1');
        INSERT INTO config VALUES ('ai_admin_only', '0');
        INSERT INTO config VALUES ('ai_mode', 'full');
    """)
    conn.commit()
    conn.close()
    return str(path)


# ── _period_hours ─────────────────────────────────────────────────────────────

class TestPeriodHours:
    def test_24h(self):
        assert _period_hours("24h") == 24

    def test_7d(self):
        assert _period_hours("7d") == 168

    def test_30d(self):
        assert _period_hours("30d") == 720

    def test_ciclo(self):
        assert _period_hours("ciclo") == 21

    def test_1h(self):
        assert _period_hours("1h") == 1

    def test_unknown_defaults_to_24(self):
        assert _period_hours("xyz") == 24

    def test_case_insensitive(self):
        assert _period_hours("7D") == 168


# ── _pretty_ai_text ───────────────────────────────────────────────────────────

class TestPrettyAiText:
    def test_strips_bold_markdown(self):
        result = _pretty_ai_text("**texto em negrito**")
        assert "**" not in result
        assert "texto em negrito" in result

    def test_strips_backticks(self):
        result = _pretty_ai_text("`código`")
        assert "`" not in result

    def test_strips_headers(self):
        result = _pretty_ai_text("## Título")
        assert "##" not in result

    def test_converts_dashes_to_bullets(self):
        result = _pretty_ai_text("- item um\n- item dois")
        assert "• item um" in result

    def test_empty_string_returns_empty(self):
        assert _pretty_ai_text("") == ""

    def test_multiple_blank_lines_collapsed(self):
        result = _pretty_ai_text("linha1\n\n\n\nlinha2")
        assert result == "linha1\n\nlinha2"

    def test_plain_text_unchanged(self):
        text = "Texto simples sem formatação especial."
        result = _pretty_ai_text(text)
        assert result == text


# ── ContextBuilder ────────────────────────────────────────────────────────────

class TestContextBuilder:
    def test_build_without_wallet_returns_generic_mode(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet=None, period="24h")
        assert ctx["mode"] == "generic"
        assert ctx["has_wallet"] is False

    def test_build_with_wallet_returns_user_mode(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc", period="24h")
        assert ctx["mode"] == "user"
        assert ctx["has_wallet"] is True

    def test_build_includes_all_context_keys(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc", period="24h")
        for key in ["capital", "pnl", "top_subs", "worst_sub", "by_env", "gas_total", "last_inactivity"]:
            assert key in ctx, f"Chave '{key}' ausente no contexto"

    def test_pnl_trades_count_correct(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc", period="24h")
        pnl = ctx["pnl"]
        assert pnl["trades"] == 3

    def test_pnl_wins_correct(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc", period="24h")
        pnl = ctx["pnl"]
        assert pnl["wins"] == 2  # 5.0 e 3.0 positivos

    def test_capital_loaded(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc", period="24h")
        assert abs(ctx["capital"]["total_usd"] - 1500.0) < 0.01

    def test_top_subs_ordered_by_pnl(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc", period="24h")
        subs = ctx["top_subs"]
        assert len(subs) > 0
        # sub1 tem 5.0 e 3.0 — deve ser a melhor
        assert subs[0]["sub"] == "sub1"

    def test_worst_sub_is_negative(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc", period="24h")
        worst = ctx["worst_sub"]
        assert worst is not None
        assert worst["sub"] == "sub2"
        assert worst["liquido"] < 0

    def test_last_inactivity_loaded(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc", period="24h")
        inact = ctx["last_inactivity"]
        assert inact is not None
        assert abs(inact["minutes"] - 42.0) < 0.1

    def test_unknown_wallet_returns_zeros(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0x000000000000000000000000000000000000dead")
        pnl = ctx["pnl"]
        assert pnl["trades"] == 0
        assert pnl["liquido"] == 0.0

    def test_by_env_contains_both_environments(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc", period="24h")
        envs = {e["env"] for e in ctx["by_env"]}
        assert "AG_C_bd" in envs
        assert "bd_v5" in envs

    def test_period_7d_includes_more_data(self, db_file):
        cb = ContextBuilder(db_file)
        ctx_24h = cb.build(wallet="0xaabbcc", period="24h")
        ctx_7d = cb.build(wallet="0xaabbcc", period="7d")
        # 7d tem pelo menos tantos trades quanto 24h
        assert ctx_7d["pnl"]["trades"] >= ctx_24h["pnl"]["trades"]


class TestContextBuilderToSystemPrompt:
    def test_generic_mode_returns_base_prompt(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet=None)
        prompt = cb.to_system_prompt(ctx)
        assert "OCME Intelligence" in prompt
        assert len(prompt) > 50

    def test_user_mode_includes_capital(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc")
        prompt = cb.to_system_prompt(ctx)
        assert "Capital" in prompt or "capital" in prompt
        assert "1,500" in prompt or "1500" in prompt

    def test_user_mode_includes_wallet_truncated(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc")
        prompt = cb.to_system_prompt(ctx)
        assert "0xaabb" in prompt  # primeiros 6 chars

    def test_system_prompt_has_portuguese_instruction(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc")
        prompt = cb.to_system_prompt(ctx)
        assert "português" in prompt.lower()

    def test_system_prompt_has_no_invention_rule(self, db_file):
        cb = ContextBuilder(db_file)
        ctx = cb.build(wallet="0xaabbcc")
        prompt = cb.to_system_prompt(ctx)
        assert "invente" in prompt.lower() or "não invente" in prompt.lower()


# ── AIEngine ──────────────────────────────────────────────────────────────────

class TestAIEngineGovernance:
    def test_disabled_when_no_api_key(self, db_file):
        engine = AIEngine(db_file, api_key="")
        assert not engine.is_enabled()

    def test_enabled_with_valid_api_key(self, db_file):
        engine = AIEngine(db_file, api_key="sk-test-key")
        assert engine.is_enabled()

    def test_admin_only_returns_false_by_default(self, db_file):
        engine = AIEngine(db_file, api_key="sk-test")
        assert not engine.is_admin_only()

    def test_admin_only_enforced_when_set(self, db_file):
        conn = sqlite3.connect(db_file)
        conn.execute("UPDATE config SET value='1' WHERE key='ai_admin_only'")
        conn.commit()
        conn.close()
        engine = AIEngine(db_file, api_key="sk-test")
        reply = engine.answer("olá", chat_id=101)  # chat_id 101 não é admin
        assert "restrito" in reply.lower() or "administrador" in reply.lower()

    def test_disabled_globally_returns_message(self, db_file):
        conn = sqlite3.connect(db_file)
        conn.execute("UPDATE config SET value='0' WHERE key='ai_global_enabled'")
        conn.commit()
        conn.close()
        engine = AIEngine(db_file, api_key="sk-test")
        reply = engine.answer("olá", chat_id=101)
        assert "desabilitada" in reply.lower()


class TestAIEngineMemory:
    def test_memory_starts_empty(self, db_file):
        engine = AIEngine(db_file, api_key="sk-test")
        assert engine.mem_get(101) == []

    def test_mem_add_and_get(self, db_file):
        engine = AIEngine(db_file, api_key="sk-test")
        engine.mem_add(101, "user", "pergunta")
        engine.mem_add(101, "assistant", "resposta")
        mem = engine.mem_get(101)
        assert len(mem) == 2
        assert mem[0]["role"] == "user"
        assert mem[1]["role"] == "assistant"

    def test_mem_clear(self, db_file):
        engine = AIEngine(db_file, api_key="sk-test")
        engine.mem_add(101, "user", "algo")
        engine.mem_clear(101)
        assert engine.mem_get(101) == []

    def test_memory_isolated_per_chat_id(self, db_file):
        engine = AIEngine(db_file, api_key="sk-test")
        engine.mem_add(101, "user", "chat 101")
        engine.mem_add(202, "user", "chat 202")
        assert len(engine.mem_get(101)) == 1
        assert len(engine.mem_get(202)) == 1

    def test_memory_maxlen_enforced(self, db_file):
        engine = AIEngine(db_file, api_key="sk-test")
        for i in range(20):
            engine.mem_add(101, "user", f"msg {i}")
        assert len(engine.mem_get(101)) <= engine._MEMORY_MAX


class TestAIEngineAnswer:
    """Testes com mock da API — sem chamadas reais."""

    def _engine_with_mock(self, db_file, mock_reply="Resposta mockada"):
        engine = AIEngine(db_file, api_key="sk-mock-key")
        engine._call_api = MagicMock(return_value=mock_reply)
        return engine

    def test_answer_calls_api(self, db_file):
        engine = self._engine_with_mock(db_file)
        engine.answer("quanto ganhei?", chat_id=101)
        engine._call_api.assert_called_once()

    def test_answer_returns_string(self, db_file):
        engine = self._engine_with_mock(db_file)
        result = engine.answer("teste", chat_id=101)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_answer_injects_system_prompt_first(self, db_file):
        engine = self._engine_with_mock(db_file)
        engine.answer("olá", chat_id=101)
        messages = engine._call_api.call_args[0][0]
        assert messages[0]["role"] == "system"

    def test_answer_user_message_is_last(self, db_file):
        engine = self._engine_with_mock(db_file)
        engine.answer("minha pergunta", chat_id=101)
        messages = engine._call_api.call_args[0][0]
        assert messages[-1]["role"] == "user"
        assert "minha pergunta" in messages[-1]["content"]

    def test_answer_context_injected_for_user_with_wallet(self, db_file):
        engine = self._engine_with_mock(db_file)
        engine.answer("dados?", chat_id=101, wallet="0xaabbcc")
        messages = engine._call_api.call_args[0][0]
        system_content = messages[0]["content"]
        # Sistema deve conter dados reais
        assert "DADOS REAIS" in system_content or "1,500" in system_content or "1500" in system_content

    def test_answer_without_wallet_uses_generic_prompt(self, db_file):
        engine = self._engine_with_mock(db_file)
        engine.answer("o que é webdex?", chat_id=101, wallet=None)
        messages = engine._call_api.call_args[0][0]
        system_content = messages[0]["content"]
        assert "OCME Intelligence" in system_content

    def test_answer_memory_saved_on_success(self, db_file):
        engine = self._engine_with_mock(db_file, "Boa resposta")
        engine.answer("pergunta", chat_id=101)
        mem = engine.mem_get(101)
        assert len(mem) == 2  # user + assistant

    def test_answer_memory_not_saved_on_error(self, db_file):
        engine = self._engine_with_mock(db_file, "❌ Erro ao conectar")
        engine.answer("pergunta", chat_id=101)
        mem = engine.mem_get(101)
        assert len(mem) == 0  # erro → sem salvar memória

    def test_answer_with_pretty_false_returns_raw(self, db_file):
        engine = self._engine_with_mock(db_file, "**resposta**")
        result = engine.answer("q", chat_id=101, pretty=False)
        assert "**" in result

    def test_answer_with_pretty_true_strips_markdown(self, db_file):
        engine = self._engine_with_mock(db_file, "**resposta**")
        result = engine.answer("q", chat_id=101, pretty=True)
        assert "**" not in result


class TestAIEngineClassifyIntent:
    def test_lucro_classifies_as_resultado(self, db_file):
        e = AIEngine(db_file, api_key="sk-test")
        assert e.classify_intent("qual meu lucro hoje?") == "resultado"

    def test_capital_classifies_correctly(self, db_file):
        e = AIEngine(db_file, api_key="sk-test")
        assert e.classify_intent("qual meu saldo atual?") == "capital"

    def test_gas_classifies_correctly(self, db_file):
        e = AIEngine(db_file, api_key="sk-test")
        assert e.classify_intent("quanto paguei de gás?") == "gas"

    def test_general_for_unknown(self, db_file):
        e = AIEngine(db_file, api_key="sk-test")
        assert e.classify_intent("bom dia") == "general"
