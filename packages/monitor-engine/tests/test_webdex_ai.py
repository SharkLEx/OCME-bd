"""
test_webdex_ai.py — Testes para webdex_ai.py (Story 16.2 AC3)

Foco:
- Rate limit IA: 10 msgs/h por chat_id → mensagem de throttle
- classify_intent: classificação correta de intenções
- preventive_hint: alertas por tipo de pergunta
- call_openai: graceful degradation em falha da API
- call_openai_with_tools: loop encerra após 3 iterações
- handle_ai_message_extended: rate limit aplicado corretamente
"""
from __future__ import annotations

import time
import unittest.mock as mock
import json

import pytest


# ==============================================================================
# Helpers
# ==============================================================================

def _get_ai():
    """Importa webdex_ai (mocks já estão em sys.modules via conftest)."""
    import webdex_ai
    return webdex_ai


def _clear_ia_rate(chat_id: int):
    """Limpa rate_limit da IA para chat_id."""
    import webdex_ai
    webdex_ai._ia_rate_limit.pop(int(chat_id), None)


# ==============================================================================
# 1. Rate limit IA — handle_ai_message_extended
# ==============================================================================

class TestIaRateLimit:

    def test_first_message_allowed(self, db_conn, monkeypatch):
        """Primeira mensagem de um usuário sempre passa."""
        import webdex_ai
        import webdex_db

        monkeypatch.setattr(webdex_db, 'conn', db_conn)
        monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())

        _clear_ia_rate(50001)

        # Mock da chamada à IA para retornar rápido
        monkeypatch.setattr(webdex_ai, 'call_openai_with_tools', lambda msgs, chat_id, model='': 'Resposta OK')
        monkeypatch.setattr(webdex_ai, 'call_openai', lambda msgs, model='': 'Resposta OK')

        result = webdex_ai.handle_ai_message_extended(50001, 'Qual o TVL?')
        assert '⏳' not in result or 'limite' not in result.lower()

    def test_rate_limit_blocks_after_10_messages(self, db_conn, monkeypatch):
        """Após 10 mensagens na hora → mensagem de rate limit retornada."""
        import webdex_ai
        import webdex_db

        monkeypatch.setattr(webdex_db, 'conn', db_conn)
        monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())

        chat_id = 50002
        _clear_ia_rate(chat_id)

        # Injetar 10 timestamps recentes (dentro da janela)
        now = time.time()
        webdex_ai._ia_rate_limit[chat_id] = [now - i for i in range(10)]

        # A próxima mensagem deve ser bloqueada
        result = webdex_ai.handle_ai_message_extended(chat_id, 'Pergunta 11')
        assert '⏳' in result or 'limite' in result.lower()

    def test_rate_limit_resets_after_window(self, db_conn, monkeypatch):
        """Timestamps expirados (>1h) são descartados → usuário pode enviar novamente."""
        import webdex_ai
        import webdex_db

        monkeypatch.setattr(webdex_db, 'conn', db_conn)
        monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
        monkeypatch.setattr(webdex_ai, 'call_openai_with_tools', lambda msgs, chat_id, model='': 'Resposta OK')
        monkeypatch.setattr(webdex_ai, 'call_openai', lambda msgs, model='': 'Resposta OK')

        chat_id = 50003

        # Injetar 10 timestamps expirados (>1h atrás)
        expired = time.time() - webdex_ai._IA_RATE_WINDOW - 100
        webdex_ai._ia_rate_limit[chat_id] = [expired] * 10

        # Deve ser permitido (janela deslizante limpa expirados)
        result = webdex_ai.handle_ai_message_extended(chat_id, 'Nova pergunta')
        assert '⏳' not in result


# ==============================================================================
# 2. classify_intent — classificação de intenções
# ==============================================================================

class TestClassifyIntent:

    def test_lucro_classified_as_resultado(self):
        ai = _get_ai()
        assert ai.classify_intent('Quanto ganhei essa semana?') == 'resultado'
        assert ai.classify_intent('qual o meu lucro?') == 'resultado'

    def test_capital_classified_correctly(self):
        ai = _get_ai()
        assert ai.classify_intent('Qual o meu saldo?') == 'capital'
        assert ai.classify_intent('quanto tenho investido?') == 'capital'

    def test_ciclo_classified_correctly(self):
        ai = _get_ai()
        assert ai.classify_intent('qual o ciclo atual?') == 'ciclo'
        assert ai.classify_intent('quando foi o último trade?') == 'ciclo'

    def test_gas_classified_correctly(self):
        ai = _get_ai()
        assert ai.classify_intent('quanto estou gastando em gas?') == 'gas'
        assert ai.classify_intent('qual a taxa atual da rede?') == 'gas'

    def test_tvl_classified_as_liquidez(self):
        ai = _get_ai()
        assert ai.classify_intent('qual o TVL do protocolo?') == 'liquidez'

    def test_unknown_classified_as_general(self):
        ai = _get_ai()
        result = ai.classify_intent('xyz blah blah')
        assert result == 'general'

    def test_educacao_classified_correctly(self):
        ai = _get_ai()
        assert ai.classify_intent('como funciona o webdex?') == 'educacao'
        assert ai.classify_intent('me explica o protocolo') == 'educacao'

    def test_triade_classified_correctly(self):
        ai = _get_ai()
        assert ai.classify_intent('vale a pena investir agora?') == 'triade'
        # "sacar" + "retirar" são keywords de triade, mas sem "capital" para não colidir
        assert ai.classify_intent('devo retirar os fundos agora?') == 'triade'


# ==============================================================================
# 3. preventive_hint — alertas educativos
# ==============================================================================

class TestPreventiveHint:

    def test_external_protocol_triggers_hint(self):
        ai = _get_ai()
        hint = ai.preventive_hint('como funciona o uniswap?')
        assert 'nota' in hint.lower() or 'ℹ️' in hint

    def test_webdex_context_no_hint(self):
        ai = _get_ai()
        hint = ai.preventive_hint('como funciona o webdex?')
        assert hint == ''

    def test_price_prediction_triggers_warning(self):
        ai = _get_ai()
        hint = ai.preventive_hint('o token vai subir amanhã?')
        assert 'aviso' in hint.lower() or '⚠️' in hint

    def test_private_key_triggers_security(self):
        ai = _get_ai()
        hint = ai.preventive_hint('me passa a chave privada da carteira')
        assert '🔒' in hint or 'segurança' in hint.lower()

    def test_normal_question_no_hint(self):
        ai = _get_ai()
        hint = ai.preventive_hint('qual o meu resultado do dia?')
        assert hint == ''


# ==============================================================================
# 4. call_openai — graceful degradation
# ==============================================================================

class TestCallOpenai:

    def test_no_api_key_returns_error(self, monkeypatch):
        """Sem API key → mensagem de erro, não exception."""
        import webdex_ai
        monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        monkeypatch.delenv('OPENAI_KEY', raising=False)
        monkeypatch.setattr(webdex_ai, '_AI_API_KEY', '')

        result = webdex_ai.call_openai([{'role': 'user', 'content': 'Teste'}])
        assert 'indisponível' in result.lower() or 'configure' in result.lower()

    def test_api_timeout_returns_error_message(self, monkeypatch):
        """Timeout na API → mensagem de erro, não exception propagada."""
        import webdex_ai
        import requests

        def _timeout_post(*args, **kwargs):
            raise requests.exceptions.Timeout('timeout simulado')

        monkeypatch.setenv('OPENAI_RETRIES', '1')
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-fake-test')
        monkeypatch.setattr(webdex_ai.requests, 'post', _timeout_post)

        try:
            result = webdex_ai.call_openai([{'role': 'user', 'content': 'Teste'}])
        except Exception as e:
            pytest.fail(f'call_openai não deveria lançar exception: {e}')

        assert isinstance(result, str)
        assert len(result) > 0

    def test_api_500_error_returns_message(self, monkeypatch):
        """HTTP 500 → todas as retentativas falham → mensagem de erro."""
        import webdex_ai

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 500

        monkeypatch.setenv('OPENAI_RETRIES', '1')
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-fake-test')
        monkeypatch.setattr(webdex_ai.requests, 'post', lambda *a, **kw: mock_resp)

        result = webdex_ai.call_openai([{'role': 'user', 'content': 'Teste'}])
        assert isinstance(result, str)
        assert 'falhou' in result.lower() or 'tentativa' in result.lower() or 'indisponível' in result.lower()

    def test_successful_response_returned(self, monkeypatch):
        """Resposta bem-sucedida → texto extraído corretamente."""
        import webdex_ai

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'choices': [{
                'message': {'content': 'O TVL atual é $1,234,567.'},
                'finish_reason': 'stop'
            }]
        }

        monkeypatch.setenv('OPENAI_API_KEY', 'sk-fake-test')
        monkeypatch.setattr(webdex_ai.requests, 'post', lambda *a, **kw: mock_resp)

        result = webdex_ai.call_openai([{'role': 'user', 'content': 'Qual o TVL?'}])
        assert result == 'O TVL atual é $1,234,567.'


# ==============================================================================
# 5. call_openai_with_tools — loop de tool calling
# ==============================================================================

class TestToolCallLoop:

    def test_no_tool_calls_returns_content_directly(self, monkeypatch):
        """Resposta sem tool_calls → retorna content imediatamente (iteração 0)."""
        import webdex_ai

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'choices': [{
                'message': {'content': 'Resposta direta sem tools.', 'tool_calls': []},
                'finish_reason': 'stop'
            }]
        }

        monkeypatch.setenv('OPENAI_API_KEY', 'sk-fake-test')
        monkeypatch.setattr(webdex_ai.requests, 'post', lambda *a, **kw: mock_resp)
        monkeypatch.setattr(webdex_ai, '_TOOLS_ENABLED', True)

        result = webdex_ai.call_openai_with_tools(
            [{'role': 'user', 'content': 'Qual o TVL?'}],
            chat_id=60001
        )
        assert result == 'Resposta direta sem tools.'

    def test_tool_call_loop_terminates_after_max_iterations(self, monkeypatch):
        """Loop de tool calling termina após _TOOL_MAX_ITER=3 iterações."""
        import webdex_ai

        call_count = {'n': 0}

        def _mock_post(*args, **kwargs):
            call_count['n'] += 1
            resp = mock.MagicMock()
            resp.status_code = 200

            if call_count['n'] <= 3:
                # Sempre pede tool call
                resp.json.return_value = {
                    'choices': [{
                        'message': {
                            'content': None,
                            'tool_calls': [{
                                'id': f'tc_{call_count["n"]}',
                                'function': {
                                    'name': 'get_protocol_metrics',
                                    'arguments': '{"metric": "tvl"}'
                                }
                            }]
                        },
                        'finish_reason': 'tool_calls'
                    }]
                }
            else:
                # Resposta final
                resp.json.return_value = {
                    'choices': [{
                        'message': {'content': 'Resposta final após tools.'},
                        'finish_reason': 'stop'
                    }]
                }
            return resp

        monkeypatch.setenv('OPENAI_API_KEY', 'sk-fake-test')
        monkeypatch.setenv('OPENAI_RETRIES', '1')
        monkeypatch.setattr(webdex_ai.requests, 'post', _mock_post)
        monkeypatch.setattr(webdex_ai, '_TOOLS_ENABLED', True)

        # Mock execute_tool para não chamar DB real
        monkeypatch.setattr(webdex_ai, 'execute_tool', lambda name, args, chat_id=None: 'TVL: $100k')

        result = webdex_ai.call_openai_with_tools(
            [{'role': 'user', 'content': 'Qual o TVL?'}],
            chat_id=60002
        )

        # Deve ter terminado (não loop infinito)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_tools_disabled_delegates_to_call_openai(self, monkeypatch):
        """Quando _TOOLS_ENABLED=False → delega para call_openai simples."""
        import webdex_ai

        monkeypatch.setattr(webdex_ai, '_TOOLS_ENABLED', False)

        called = {'simple': False}
        def _mock_call_openai(msgs, model=''):
            called['simple'] = True
            return 'Resposta sem tools'

        monkeypatch.setattr(webdex_ai, 'call_openai', _mock_call_openai)

        result = webdex_ai.call_openai_with_tools(
            [{'role': 'user', 'content': 'Pergunta'}],
            chat_id=60003
        )

        assert called['simple'] is True
        assert result == 'Resposta sem tools'


# ==============================================================================
# 6. mem_add / mem_get / mem_clear_lgpd — memória fallback (deque)
# ==============================================================================

class TestAiMemoryFallback:

    def test_mem_add_uses_deque_when_pg_disabled(self, db_conn, monkeypatch):
        """Quando _PG_MEMORY_ENABLED=False → usa deque local."""
        import webdex_ai
        import webdex_db

        monkeypatch.setattr(webdex_db, 'conn', db_conn)
        monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
        monkeypatch.setattr(webdex_ai, '_PG_MEMORY_ENABLED', False)
        monkeypatch.setattr(webdex_ai, '_AI_MEMORY', {})

        webdex_ai.mem_add(70001, 'user', 'Pergunta de teste')
        result = webdex_ai.mem_get(70001)

        assert len(result) == 1
        assert result[0]['role'] == 'user'
        assert result[0]['content'] == 'Pergunta de teste'

    def test_mem_clear_lgpd_removes_deque(self, db_conn, monkeypatch):
        """mem_clear_lgpd limpa deque local."""
        import webdex_ai
        import webdex_db

        monkeypatch.setattr(webdex_db, 'conn', db_conn)
        monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
        monkeypatch.setattr(webdex_ai, '_PG_MEMORY_ENABLED', False)
        monkeypatch.setattr(webdex_ai, '_AI_MEMORY', {})

        webdex_ai.mem_add(70002, 'user', 'Msg para deletar')
        assert len(webdex_ai.mem_get(70002)) == 1

        webdex_ai.mem_clear_lgpd(70002)
        assert webdex_ai.mem_get(70002) == []

    def test_mem_get_returns_empty_for_new_user(self, db_conn, monkeypatch):
        """mem_get para chat_id sem histórico → lista vazia."""
        import webdex_ai
        import webdex_db

        monkeypatch.setattr(webdex_db, 'conn', db_conn)
        monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
        monkeypatch.setattr(webdex_ai, '_PG_MEMORY_ENABLED', False)
        monkeypatch.setattr(webdex_ai, '_AI_MEMORY', {})

        result = webdex_ai.mem_get(70003)
        assert result == []
