"""
test_webdex_ai_memory.py — Testes para webdex_ai_memory.py (Story 16.2 AC1)

Foco:
- AIMemoryManager: load_context, append, get_context, delete_all (LGPD)
- Graceful degradation: PostgreSQL offline → deque em RAM, sem crash
- Cache deque maxlen=20
- get_manager: singleton por chat_id
- mem_add_pg / mem_get_pg / mem_delete_all_pg: wrappers
"""
from __future__ import annotations

import time
import threading
import unittest.mock as mock
from collections import deque

import pytest


# ==============================================================================
# Helpers: mock de conexão PostgreSQL
# ==============================================================================

def _make_pg_mock(rows=None, rowcount=0):
    """Cria mock de conexão psycopg2 configurável."""
    cur_mock = mock.MagicMock()
    cur_mock.fetchall.return_value = rows or []
    cur_mock.fetchone.return_value = None
    cur_mock.rowcount = rowcount

    conn_mock = mock.MagicMock()
    # context manager para `with conn.cursor() as cur:`
    conn_mock.cursor.return_value.__enter__ = mock.MagicMock(return_value=cur_mock)
    conn_mock.cursor.return_value.__exit__ = mock.MagicMock(return_value=False)
    return conn_mock, cur_mock


# ==============================================================================
# 1. AIMemoryManager — load_context
# ==============================================================================

class TestAIMemoryManagerLoad:

    def test_load_context_populates_cache(self, monkeypatch):
        """load_context com PG disponível → preenche _cache com mensagens."""
        import webdex_ai_memory as aim

        pg_rows = [('assistant', 'Olá!'), ('user', 'Oi')]  # ordem DESC do PG
        conn_mock, _ = _make_pg_mock(rows=pg_rows)

        monkeypatch.setattr(aim, '_get_conn', lambda: conn_mock)
        monkeypatch.setattr(aim, '_release_conn', lambda c: None)

        mgr = aim.AIMemoryManager(chat_id=111, platform='telegram')
        mgr.load_context()

        assert mgr._loaded is True
        ctx = mgr.get_context()
        # reversed(rows) → ordem cronológica ASC
        assert len(ctx) == 2
        assert ctx[0]['role'] == 'user'    # 'Oi' (era último na DESC)
        assert ctx[1]['role'] == 'assistant'  # 'Olá!' (era primeiro na DESC)

    def test_load_context_pg_unavailable_no_crash(self, monkeypatch):
        """PG indisponível → _loaded=True, cache vazio, sem exceção."""
        import webdex_ai_memory as aim

        monkeypatch.setattr(aim, '_get_conn', lambda: None)

        mgr = aim.AIMemoryManager(chat_id=222, platform='telegram')
        mgr.load_context()

        assert mgr._loaded is True
        assert mgr.get_context() == []

    def test_load_context_pg_error_no_crash(self, monkeypatch):
        """PG conexão falha no execute → graceful degradation."""
        import webdex_ai_memory as aim

        conn_mock = mock.MagicMock()
        conn_mock.cursor.return_value.__enter__.side_effect = Exception('PG error')
        conn_mock.cursor.return_value.__exit__ = mock.MagicMock(return_value=False)

        monkeypatch.setattr(aim, '_get_conn', lambda: conn_mock)
        monkeypatch.setattr(aim, '_release_conn', lambda c: None)

        mgr = aim.AIMemoryManager(chat_id=333, platform='telegram')
        try:
            mgr.load_context()
        except Exception as e:
            pytest.fail(f'load_context lançou exceção com PG error: {e}')

        assert mgr._loaded is True

    def test_load_context_empty_pg_result(self, monkeypatch):
        """PG retorna vazio → cache fica vazio, sem erro."""
        import webdex_ai_memory as aim

        conn_mock, _ = _make_pg_mock(rows=[])
        monkeypatch.setattr(aim, '_get_conn', lambda: conn_mock)
        monkeypatch.setattr(aim, '_release_conn', lambda c: None)

        mgr = aim.AIMemoryManager(chat_id=444, platform='telegram')
        mgr.load_context()

        assert mgr.get_context() == []


# ==============================================================================
# 2. AIMemoryManager — append / _persist
# ==============================================================================

class TestAIMemoryManagerAppend:

    def test_append_adds_to_cache_immediately(self, monkeypatch):
        """append() → adiciona ao _cache imediatamente (sem esperar thread)."""
        import webdex_ai_memory as aim

        # Mock _persist para não usar PG
        monkeypatch.setattr(aim, '_get_conn', lambda: None)

        mgr = aim.AIMemoryManager(chat_id=555, platform='telegram')
        mgr._loaded = True

        mgr.append('user', 'Qual é o TVL?')

        ctx = mgr.get_context()
        assert len(ctx) == 1
        assert ctx[0]['role'] == 'user'
        assert ctx[0]['content'] == 'Qual é o TVL?'

    def test_append_multiple_messages(self, monkeypatch):
        """Múltiplos appends → ordem preservada no cache."""
        import webdex_ai_memory as aim

        monkeypatch.setattr(aim, '_get_conn', lambda: None)

        mgr = aim.AIMemoryManager(chat_id=666, platform='telegram')
        mgr._loaded = True

        mgr.append('user', 'msg 1')
        mgr.append('assistant', 'resposta 1')
        mgr.append('user', 'msg 2')

        ctx = mgr.get_context()
        assert len(ctx) == 3
        assert ctx[0]['content'] == 'msg 1'
        assert ctx[2]['content'] == 'msg 2'

    def test_cache_respects_maxlen(self, monkeypatch):
        """Cache não excede maxlen=20 — deque descarta mensagens antigas."""
        import webdex_ai_memory as aim

        monkeypatch.setattr(aim, '_get_conn', lambda: None)

        mgr = aim.AIMemoryManager(chat_id=777, platform='telegram')
        mgr._loaded = True

        for i in range(25):
            mgr.append('user', f'msg {i}')

        ctx = mgr.get_context()
        assert len(ctx) == 20  # maxlen=20
        # As primeiras 5 foram descartadas
        assert ctx[0]['content'] == 'msg 5'
        assert ctx[-1]['content'] == 'msg 24'

    def test_persist_calls_pg_insert(self, monkeypatch):
        """_persist() executa INSERT no PostgreSQL."""
        import webdex_ai_memory as aim

        conn_mock, cur_mock = _make_pg_mock()
        monkeypatch.setattr(aim, '_get_conn', lambda: conn_mock)
        monkeypatch.setattr(aim, '_release_conn', lambda c: None)

        mgr = aim.AIMemoryManager(chat_id=888, platform='telegram')
        mgr._persist('user', 'test content')

        # Verifica que execute foi chamado (INSERT)
        assert cur_mock.execute.called
        call_args = cur_mock.execute.call_args[0][0]
        assert 'INSERT' in call_args.upper()


# ==============================================================================
# 3. AIMemoryManager — get_context
# ==============================================================================

class TestAIMemoryManagerGetContext:

    def test_get_context_triggers_load_if_not_loaded(self, monkeypatch):
        """get_context() sem load prévio → dispara load_context automaticamente."""
        import webdex_ai_memory as aim

        monkeypatch.setattr(aim, '_get_conn', lambda: None)

        mgr = aim.AIMemoryManager(chat_id=999, platform='telegram')
        assert mgr._loaded is False

        ctx = mgr.get_context()  # deve triggar load

        assert mgr._loaded is True
        assert isinstance(ctx, list)

    def test_get_context_returns_list(self, monkeypatch):
        """get_context() sempre retorna list (não deque)."""
        import webdex_ai_memory as aim

        monkeypatch.setattr(aim, '_get_conn', lambda: None)

        mgr = aim.AIMemoryManager(chat_id=1000, platform='telegram')
        mgr._loaded = True

        ctx = mgr.get_context()
        assert isinstance(ctx, list)


# ==============================================================================
# 4. AIMemoryManager — delete_all (LGPD)
# ==============================================================================

class TestAIMemoryManagerDeleteAll:

    def test_delete_all_clears_cache(self, monkeypatch):
        """delete_all() limpa o cache local."""
        import webdex_ai_memory as aim

        conn_mock, cur_mock = _make_pg_mock(rowcount=5)
        monkeypatch.setattr(aim, '_get_conn', lambda: conn_mock)
        monkeypatch.setattr(aim, '_release_conn', lambda c: None)

        mgr = aim.AIMemoryManager(chat_id=1111, platform='telegram')
        mgr._loaded = True
        mgr.append('user', 'mensagem a deletar')

        assert len(mgr._cache) == 1

        result = mgr.delete_all()

        assert len(mgr._cache) == 0
        assert result == 5  # rowcount do mock

    def test_delete_all_pg_unavailable_clears_cache_only(self, monkeypatch):
        """PG offline → cache limpo, retorna 0 (não lança exceção)."""
        import webdex_ai_memory as aim

        monkeypatch.setattr(aim, '_get_conn', lambda: None)

        mgr = aim.AIMemoryManager(chat_id=2222, platform='telegram')
        mgr._loaded = True
        mgr.append('user', 'mensagem')

        result = mgr.delete_all()

        assert len(mgr._cache) == 0
        assert result == 0

    def test_delete_all_executes_delete_sql(self, monkeypatch):
        """delete_all() executa DELETE no PostgreSQL."""
        import webdex_ai_memory as aim

        conn_mock, cur_mock = _make_pg_mock(rowcount=3)
        monkeypatch.setattr(aim, '_get_conn', lambda: conn_mock)
        monkeypatch.setattr(aim, '_release_conn', lambda c: None)

        mgr = aim.AIMemoryManager(chat_id=3333, platform='telegram')
        mgr.delete_all()

        call_sql = cur_mock.execute.call_args[0][0]
        assert 'DELETE' in call_sql.upper()
        assert 'ai_conversations' in call_sql.lower()


# ==============================================================================
# 5. get_manager — singleton por chat_id
# ==============================================================================

class TestGetManager:

    def test_get_manager_returns_same_instance(self, monkeypatch):
        """get_manager com mesmo chat_id retorna a mesma instância."""
        import webdex_ai_memory as aim

        monkeypatch.setattr(aim, '_get_conn', lambda: None)
        # Limpar managers cache do módulo
        aim._managers.clear()

        mgr1 = aim.get_manager(9001, 'telegram')
        mgr2 = aim.get_manager(9001, 'telegram')

        assert mgr1 is mgr2

    def test_get_manager_different_chat_ids(self, monkeypatch):
        """chat_ids diferentes → instâncias diferentes."""
        import webdex_ai_memory as aim

        monkeypatch.setattr(aim, '_get_conn', lambda: None)
        aim._managers.clear()

        mgr1 = aim.get_manager(9001, 'telegram')
        mgr2 = aim.get_manager(9002, 'telegram')

        assert mgr1 is not mgr2


# ==============================================================================
# 6. mem_delete_all_pg — LGPD wrapper
# ==============================================================================

class TestMemDeleteAll:

    def test_mem_delete_all_removes_from_registry(self, monkeypatch):
        """mem_delete_all_pg remove instância do _managers registry."""
        import webdex_ai_memory as aim

        monkeypatch.setattr(aim, '_get_conn', lambda: None)
        aim._managers.clear()

        # Registrar o manager
        mgr = aim.get_manager(7777, 'telegram')
        assert 7777 in aim._managers

        aim.mem_delete_all_pg(7777, 'telegram')

        assert 7777 not in aim._managers

    def test_mem_delete_all_pg_unknown_chat_id_no_crash(self, monkeypatch):
        """chat_id não registrado → não lança exceção."""
        import webdex_ai_memory as aim

        monkeypatch.setattr(aim, '_get_conn', lambda: None)
        aim._managers.clear()

        try:
            aim.mem_delete_all_pg(99999, 'telegram')
        except Exception as e:
            pytest.fail(f'mem_delete_all_pg falhou para chat_id desconhecido: {e}')
