"""
test_webdex_tools.py — Testes para webdex_tools.py (Story 16.2 AC2)

Foco:
- ToolCircuitBreaker: CLOSED → OPEN (3 falhas) → HALF_OPEN (cooldown) → CLOSED
- _check_rate_limit: sliding window 3600s, max 20 calls/h por chat_id
- execute_tool: integra circuit breaker + rate limit + timeout
- _impl_get_protocol_metrics: busca dados do SQLite mockado
"""
from __future__ import annotations

import time
import threading
import unittest.mock as mock

import pytest


# ==============================================================================
# Setup: importar webdex_tools sem dependências reais
# ==============================================================================

def _get_tools():
    """Importa webdex_tools (mocks já estão em sys.modules via conftest)."""
    import webdex_tools
    return webdex_tools


# ==============================================================================
# 1. ToolCircuitBreaker — máquina de estados
# ==============================================================================

class TestCircuitBreaker:

    def test_new_circuit_is_closed(self):
        """Novo circuit breaker começa CLOSED — tool disponível."""
        import webdex_tools
        cb = webdex_tools.ToolCircuitBreaker()
        assert cb.is_available('get_protocol_metrics') is True

    def test_two_failures_keep_closed(self):
        """2 falhas não atingem threshold → continua CLOSED."""
        import webdex_tools
        cb = webdex_tools.ToolCircuitBreaker()
        cb.record_failure('tool_x')
        cb.record_failure('tool_x')
        assert cb.is_available('tool_x') is True

    def test_three_failures_opens_circuit(self):
        """3 falhas consecutivas → OPEN — tool indisponível."""
        import webdex_tools
        cb = webdex_tools.ToolCircuitBreaker()
        cb.record_failure('tool_x')
        cb.record_failure('tool_x')
        cb.record_failure('tool_x')
        assert cb.is_available('tool_x') is False

    def test_success_resets_failure_count(self):
        """record_success() → reset falhas, estado CLOSED."""
        import webdex_tools
        cb = webdex_tools.ToolCircuitBreaker()
        cb.record_failure('tool_x')
        cb.record_failure('tool_x')
        cb.record_success('tool_x')
        # Após reset, 2 novas falhas não devem abrir
        cb.record_failure('tool_x')
        cb.record_failure('tool_x')
        assert cb.is_available('tool_x') is True

    def test_open_circuit_transitions_to_half_open_after_cooldown(self, monkeypatch):
        """Após cooldown expirar, OPEN → HALF_OPEN → tool disponível para 1 teste."""
        import webdex_tools
        cb = webdex_tools.ToolCircuitBreaker()

        # Abrir o circuit
        cb.record_failure('tool_y')
        cb.record_failure('tool_y')
        cb.record_failure('tool_y')
        assert cb.is_available('tool_y') is False

        # Simular que o tempo de cooldown passou
        cb._open_at['tool_y'] = time.time() - cb._COOLDOWN - 1

        # Deve estar HALF_OPEN → disponível
        assert cb.is_available('tool_y') is True

    def test_half_open_failure_reopens_circuit(self, monkeypatch):
        """Na HALF_OPEN, nova falha → volta OPEN imediatamente."""
        import webdex_tools
        cb = webdex_tools.ToolCircuitBreaker()

        # Forçar estado HALF_OPEN
        cb.record_failure('tool_z')
        cb.record_failure('tool_z')
        cb.record_failure('tool_z')
        cb._open_at['tool_z'] = time.time() - cb._COOLDOWN - 1
        cb.is_available('tool_z')  # transição para HALF_OPEN

        # Nova falha em HALF_OPEN → OPEN
        cb.record_failure('tool_z')
        assert cb.is_available('tool_z') is False

    def test_half_open_success_closes_circuit(self, monkeypatch):
        """Na HALF_OPEN, sucesso → fecha circuit (CLOSED)."""
        import webdex_tools
        cb = webdex_tools.ToolCircuitBreaker()

        # Forçar HALF_OPEN
        cb.record_failure('tool_w')
        cb.record_failure('tool_w')
        cb.record_failure('tool_w')
        cb._open_at['tool_w'] = time.time() - cb._COOLDOWN - 1
        cb.is_available('tool_w')  # HALF_OPEN

        cb.record_success('tool_w')
        assert cb.is_available('tool_w') is True

    def test_independent_tools_dont_interfere(self):
        """Falhas em tool_a não afetam tool_b."""
        import webdex_tools
        cb = webdex_tools.ToolCircuitBreaker()
        cb.record_failure('tool_a')
        cb.record_failure('tool_a')
        cb.record_failure('tool_a')
        assert cb.is_available('tool_b') is True

    def test_circuit_breaker_is_thread_safe(self):
        """record_failure concorrente não corrompe estado."""
        import webdex_tools
        cb = webdex_tools.ToolCircuitBreaker()
        errors = []

        def fail_tool():
            try:
                for _ in range(2):
                    cb.record_failure('concurrent_tool')
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=fail_tool) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)

        assert errors == [], f'Erros em threads: {errors}'


# ==============================================================================
# 2. _check_rate_limit — sliding window
# ==============================================================================

class TestRateLimit:

    def _clear_rate_data(self, chat_id: int):
        """Limpa rate_data do chat_id para isolar testes."""
        import webdex_tools
        with webdex_tools._rate_lock:
            webdex_tools._rate_data.pop(chat_id, None)

    def test_first_call_allowed(self):
        """Primeira call de um chat_id novo é sempre permitida."""
        import webdex_tools
        self._clear_rate_data(10001)
        assert webdex_tools._check_rate_limit(10001) is True

    def test_calls_within_limit_allowed(self):
        """19 calls dentro de 1 hora → todas permitidas."""
        import webdex_tools
        self._clear_rate_data(10002)
        for _ in range(19):
            result = webdex_tools._check_rate_limit(10002)
            assert result is True, f'Call {_ + 1} deveria ser permitida'

    def test_call_at_limit_allowed(self):
        """Call #20 exatamente no limite → permitida."""
        import webdex_tools
        self._clear_rate_data(10003)
        for _ in range(19):
            webdex_tools._check_rate_limit(10003)
        assert webdex_tools._check_rate_limit(10003) is True

    def test_call_over_limit_blocked(self):
        """Call #21 excede limite → bloqueada."""
        import webdex_tools
        self._clear_rate_data(10004)
        for _ in range(20):
            webdex_tools._check_rate_limit(10004)
        assert webdex_tools._check_rate_limit(10004) is False

    def test_old_timestamps_expire(self, monkeypatch):
        """Timestamps mais antigos que 3600s são removidos → janela deslizante."""
        import webdex_tools
        self._clear_rate_data(10005)

        # Injetar 20 timestamps muito antigos (2h atrás — expirados)
        expired = time.time() - webdex_tools._RATE_WINDOW - 100
        with webdex_tools._rate_lock:
            webdex_tools._rate_data[10005] = [expired] * 20

        # Nova call deve ser permitida (timestamps antigos removidos)
        assert webdex_tools._check_rate_limit(10005) is True

    def test_rate_limit_independent_per_chat_id(self):
        """Rate limit de chat_id 10006 não afeta chat_id 10007."""
        import webdex_tools
        self._clear_rate_data(10006)
        self._clear_rate_data(10007)

        # Esgotar limite do 10006
        for _ in range(20):
            webdex_tools._check_rate_limit(10006)
        webdex_tools._check_rate_limit(10006)  # bloqueada

        # 10007 ainda pode fazer call
        assert webdex_tools._check_rate_limit(10007) is True


# ==============================================================================
# 3. execute_tool — integração circuit breaker + rate limit + timeout
# ==============================================================================

class TestExecuteTool:

    def _reset_circuit(self, name: str):
        """Reseta o circuit breaker global para um tool."""
        import webdex_tools
        with webdex_tools._circuit._lock:
            webdex_tools._circuit._states.pop(name, None)
            webdex_tools._circuit._fails.pop(name, None)
            webdex_tools._circuit._open_at.pop(name, None)

    def _clear_rate(self, chat_id: int):
        import webdex_tools
        with webdex_tools._rate_lock:
            webdex_tools._rate_data.pop(chat_id, None)

    def test_rate_limit_returns_message(self):
        """execute_tool com rate limit excedido → mensagem de throttle."""
        import webdex_tools
        chat_id = 20001
        self._clear_rate(chat_id)

        # Esgotar rate limit
        for _ in range(20):
            webdex_tools._check_rate_limit(chat_id)

        result = webdex_tools.execute_tool('get_protocol_metrics', {'metric': 'tvl'}, chat_id=chat_id)
        assert 'limite' in result.lower() or 'aguarde' in result.lower()

    def test_circuit_open_returns_fallback(self):
        """execute_tool com circuit OPEN → fallback message."""
        import webdex_tools
        self._reset_circuit('get_protocol_metrics')

        # Abrir circuit
        for _ in range(3):
            webdex_tools._circuit.record_failure('get_protocol_metrics')

        result = webdex_tools.execute_tool('get_protocol_metrics', {'metric': 'tvl'})
        assert 'indisponível' in result.lower() or 'tente novamente' in result.lower()

    def test_unknown_tool_returns_error(self):
        """execute_tool com nome inválido → erro de tool não reconhecida."""
        import webdex_tools
        result = webdex_tools.execute_tool('tool_que_nao_existe', {})
        assert 'não reconhecida' in result.lower()

    def test_successful_tool_closes_circuit(self, monkeypatch):
        """Tool bem-sucedida → record_success chamado, circuit fecha."""
        import webdex_tools
        self._reset_circuit('get_market_context')

        # Abrir circuit com 2 falhas (abaixo do threshold)
        webdex_tools._circuit.record_failure('get_market_context')
        webdex_tools._circuit.record_failure('get_market_context')

        # Mock da implementação para retornar sucesso
        monkeypatch.setitem(
            webdex_tools._IMPLEMENTATIONS,
            'get_market_context',
            lambda: 'Contexto ok'
        )

        result = webdex_tools.execute_tool('get_market_context', {})
        assert result == 'Contexto ok'
        # Após sucesso, falhas zeradas
        assert webdex_tools._circuit._fails.get('get_market_context', 0) == 0

    def test_tool_error_records_failure(self, monkeypatch):
        """Tool que lança exceção → record_failure chamado."""
        import webdex_tools
        self._reset_circuit('get_user_portfolio')

        initial_fails = webdex_tools._circuit._fails.get('get_user_portfolio', 0)

        def _raise(**kwargs):
            raise RuntimeError('DB error')

        monkeypatch.setitem(webdex_tools._IMPLEMENTATIONS, 'get_user_portfolio', _raise)

        result = webdex_tools.execute_tool('get_user_portfolio', {'wallet': '0xabc'})
        assert 'indisponível' in result.lower() or 'tente novamente' in result.lower()
        assert webdex_tools._circuit._fails.get('get_user_portfolio', 0) > initial_fails

    def test_timeout_records_failure_and_returns_fallback(self, monkeypatch):
        """Tool que trava (timeout) → record_failure + fallback retornado."""
        import webdex_tools
        self._reset_circuit('get_protocol_metrics')

        def _slow(**kwargs):
            time.sleep(60)  # Vai dar timeout

        monkeypatch.setitem(webdex_tools._IMPLEMENTATIONS, 'get_protocol_metrics', _slow)

        # Forçar timeout muito curto para o teste não demorar
        monkeypatch.setitem(webdex_tools.TOOL_TIMEOUTS, 'get_protocol_metrics', 0.1)

        start = time.time()
        result = webdex_tools.execute_tool('get_protocol_metrics', {'metric': 'tvl'})
        elapsed = time.time() - start

        assert elapsed < 2.0, f'execute_tool demorou demais: {elapsed:.1f}s'
        assert 'indisponível' in result.lower() or 'tente novamente' in result.lower()


# ==============================================================================
# 4. _impl_get_protocol_metrics — dados do SQLite mockado
# ==============================================================================

class TestGetProtocolMetrics:

    def _make_cursor_mock(self, tvl_row=None, vol_row=None, apy_row=None):
        """
        Cria mock de cursor SQLite para _impl_get_protocol_metrics.
        A função executa 3 queries em sequência: fl_snapshots, protocol_ops, config.
        """
        cur = mock.MagicMock()
        # fetchone retorna valores diferentes a cada chamada (sequência de 3 queries)
        cur.execute.return_value = cur
        cur.fetchone.side_effect = [tvl_row, vol_row, apy_row]
        return cur

    def test_returns_tvl_from_db(self, monkeypatch):
        """Quando fl_snapshots tem dados → TVL retornado corretamente."""
        import webdex_tools
        import webdex_db

        cur = self._make_cursor_mock(
            tvl_row=(12345.67, '2026-01-01'),
            vol_row=(5, 0.8),
            apy_row=None
        )
        cur_ctx = mock.MagicMock()
        cur_ctx.__enter__ = mock.MagicMock(return_value=cur)
        cur_ctx.__exit__ = mock.MagicMock(return_value=False)

        fake_cursor = mock.MagicMock()
        fake_cursor.execute.return_value = cur
        fake_cursor.fetchone.side_effect = [(12345.67, '2026-01-01'), (5, 0.8), None]

        monkeypatch.setattr(webdex_db, 'cursor', fake_cursor)

        result = webdex_tools._impl_get_protocol_metrics('tvl')
        assert 'TVL' in result
        assert '12,345.67' in result

    def test_returns_volume_24h(self, monkeypatch):
        """Quando protocol_ops tem dados → volume_24h retornado."""
        import webdex_tools
        import webdex_db

        fake_cursor = mock.MagicMock()
        # fl_snapshots → None, protocol_ops → (2, 0.8), config → None
        fake_cursor.execute.return_value = fake_cursor
        fake_cursor.fetchone.side_effect = [None, (2, 0.8), None]

        monkeypatch.setattr(webdex_db, 'cursor', fake_cursor)

        result = webdex_tools._impl_get_protocol_metrics('volume_24h')
        assert 'operaç' in result.lower() or 'ops' in result.lower() or 'gas' in result.lower()

    def test_tvl_unavailable_when_no_data(self, monkeypatch):
        """Sem dados em fl_snapshots → TVL retorna 'dados indisponíveis'."""
        import webdex_tools
        import webdex_db

        fake_cursor = mock.MagicMock()
        # Todos fetchone retornam None
        fake_cursor.execute.return_value = fake_cursor
        fake_cursor.fetchone.return_value = None

        monkeypatch.setattr(webdex_db, 'cursor', fake_cursor)

        result = webdex_tools._impl_get_protocol_metrics('tvl')
        assert 'indispon' in result.lower()
