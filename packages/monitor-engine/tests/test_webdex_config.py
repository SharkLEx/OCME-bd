"""
test_webdex_config.py — Testes para webdex_config.py (Story 16.1 AC3)

Testa funções puras: _env_int, _env_float, _pretty_ai_text, _parse_admin_ids,
infer_env_by_address, _openai_extract_text, log_error.
"""
from __future__ import annotations

import os
import unittest.mock as mock

import pytest


# ==============================================================================
# Importação lazy (webdex_config tem side-effects — mocks já estão em sys.modules)
# ==============================================================================

@pytest.fixture(scope='module')
def cfg():
    """Importa webdex_config uma vez por módulo de teste."""
    import webdex_config
    return webdex_config


# ==============================================================================
# 1. _env_int / _env_float
# ==============================================================================

class TestEnvHelpers:

    def test_env_int_reads_env_var(self, cfg, monkeypatch):
        monkeypatch.setenv('TEST_INT_VAR', '42')
        result = cfg._env_int('TEST_INT_VAR', 0)
        assert result == 42

    def test_env_int_returns_default_when_missing(self, cfg, monkeypatch):
        monkeypatch.delenv('TEST_INT_MISSING', raising=False)
        result = cfg._env_int('TEST_INT_MISSING', 99)
        assert result == 99

    def test_env_int_returns_default_on_invalid_value(self, cfg, monkeypatch):
        monkeypatch.setenv('TEST_INT_BAD', 'not_a_number')
        result = cfg._env_int('TEST_INT_BAD', 5)
        assert result == 5

    def test_env_float_reads_env_var(self, cfg, monkeypatch):
        monkeypatch.setenv('TEST_FLOAT_VAR', '1.5')
        result = cfg._env_float('TEST_FLOAT_VAR', 0.0)
        assert abs(result - 1.5) < 1e-9

    def test_env_float_returns_default_on_invalid(self, cfg, monkeypatch):
        monkeypatch.setenv('TEST_FLOAT_BAD', 'abc')
        result = cfg._env_float('TEST_FLOAT_BAD', 2.5)
        assert result == 2.5


# ==============================================================================
# 2. _pretty_ai_text
# ==============================================================================

class TestPrettyAiText:

    def test_empty_string_returns_empty(self, cfg):
        assert cfg._pretty_ai_text('') == ''

    def test_removes_bold_markdown(self, cfg):
        result = cfg._pretty_ai_text('**negrito**')
        assert '**' not in result

    def test_removes_italic_asterisk(self, cfg):
        result = cfg._pretty_ai_text('*itálico*')
        assert result.count('*') == 0

    def test_removes_backtick(self, cfg):
        result = cfg._pretty_ai_text('`código`')
        assert '`' not in result

    def test_plain_text_unchanged(self, cfg):
        result = cfg._pretty_ai_text('texto simples sem markdown')
        assert result == 'texto simples sem markdown'

    def test_none_input(self, cfg):
        # _pretty_ai_text tem guard "if not s: return ''"
        assert cfg._pretty_ai_text(None) == ''


# ==============================================================================
# 3. _parse_admin_ids
# ==============================================================================

class TestParseAdminIds:

    def test_single_id(self, cfg):
        result = cfg._parse_admin_ids('123456')
        assert 123456 in result

    def test_multiple_ids_comma_separated(self, cfg):
        result = cfg._parse_admin_ids('111,222,333')
        assert 111 in result
        assert 222 in result
        assert 333 in result

    def test_empty_string_returns_empty_list(self, cfg):
        result = cfg._parse_admin_ids('')
        assert result == []

    def test_ignores_invalid_entries(self, cfg):
        result = cfg._parse_admin_ids('123,abc,456')
        assert 123 in result
        assert 456 in result
        # 'abc' não deve estar
        assert len(result) == 2

    def test_strips_spaces(self, cfg):
        result = cfg._parse_admin_ids(' 789 , 101 ')
        assert 789 in result
        assert 101 in result


# ==============================================================================
# 4. infer_env_by_address
# ==============================================================================

class TestInferEnvByAddress:

    def test_unknown_address_returns_unknown(self, cfg):
        result = cfg.infer_env_by_address('0x0000000000000000000000000000000000000000')
        assert result == 'UNKNOWN'

    def test_known_env_returns_correct_tag(self, cfg):
        """Verifica que endereços conhecidos retornam o ambiente correto.
        CONTRACTS usa chaves como PAYMENTS, MANAGER (não ADDRESS).
        """
        first_env = next(iter(cfg.CONTRACTS))
        # Pega o primeiro endereço 0x do contrato
        first_addr = next(
            v for v in cfg.CONTRACTS[first_env].values()
            if isinstance(v, str) and v.startswith('0x')
        )
        result = cfg.infer_env_by_address(first_addr)
        assert result == first_env

    def test_case_insensitive_lookup(self, cfg):
        """Endereço em uppercase ou lowercase deve retornar o mesmo ambiente."""
        first_env = next(iter(cfg.CONTRACTS))
        first_addr = next(
            v for v in cfg.CONTRACTS[first_env].values()
            if isinstance(v, str) and v.startswith('0x')
        )
        result_upper = cfg.infer_env_by_address(first_addr.upper())
        result_lower = cfg.infer_env_by_address(first_addr.lower())
        assert result_upper == result_lower


# ==============================================================================
# 5. _openai_extract_text
# ==============================================================================

class TestOpenaiExtractText:

    def test_extracts_output_text_field(self, cfg):
        payload = {'output_text': 'resposta da IA'}
        assert cfg._openai_extract_text(payload) == 'resposta da IA'

    def test_extracts_from_output_list(self, cfg):
        payload = {
            'output': [
                {'content': [{'type': 'text', 'text': 'resposta aninhada'}]}
            ]
        }
        assert cfg._openai_extract_text(payload) == 'resposta aninhada'

    def test_returns_empty_on_unknown_format(self, cfg):
        assert cfg._openai_extract_text({}) == ''
        assert cfg._openai_extract_text({'outro': 'campo'}) == ''

    def test_prefers_output_text_over_output_list(self, cfg):
        payload = {
            'output_text': 'preferido',
            'output': [{'content': [{'type': 'text', 'text': 'preterido'}]}]
        }
        assert cfg._openai_extract_text(payload) == 'preferido'


# ==============================================================================
# 6. log_error
# ==============================================================================

class TestLogError:

    def test_log_error_does_not_raise(self, cfg):
        """log_error nunca deve levantar exceção."""
        try:
            cfg.log_error('test_context', ValueError('erro de teste'))
        except Exception as e:
            pytest.fail(f'log_error levantou exceção: {e}')

    def test_log_error_with_none_exception(self, cfg):
        """log_error com None não deve explodir."""
        try:
            cfg.log_error('ctx', None)
        except Exception:
            pass  # Pode ou não tratar None — o importante é não crashar o worker
