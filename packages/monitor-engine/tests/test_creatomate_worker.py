"""
test_creatomate_worker.py — Testes para creatomate_worker.py (Story 16.4 AC3)

Foco:
- gerar_video_ciclo: sem API key → retorna None (graceful)
- gerar_video_ciclo: parâmetros corretos enviados (modifications com pnl, ops, tvl)
- gerar_video_ciclo: timeout de poll → retorna None (não trava bot)
- gerar_video_ciclo: erro HTTP → graceful (retorna None)
- gerar_video_ciclo: render succeeded → retorna bytes do vídeo
- _request: timeout configurado
"""
from __future__ import annotations

import json
import time
import unittest.mock as mock
import urllib.error
import urllib.request

import pytest


# ==============================================================================
# 1. gerar_video_ciclo — sem API key
# ==============================================================================

class TestGerarVideoCicloNoApiKey:

    def test_no_api_key_returns_none(self, monkeypatch):
        """Sem CREATOMATE_API_KEY configurada → retorna None sem crash."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', '')

        result = cw.gerar_video_ciclo({'profit': 100, 'ops_count': 5, 'tvl_total': 1_000_000})
        assert result is None

    def test_no_api_key_does_not_call_api(self, monkeypatch):
        """Sem API key → _request não é chamado."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', '')

        called = {'n': 0}
        monkeypatch.setattr(cw, '_request', lambda *a, **kw: called.__setitem__('n', called['n'] + 1))

        cw.gerar_video_ciclo({'profit': 50, 'ops_count': 3, 'tvl_total': 500_000})
        assert called['n'] == 0


# ==============================================================================
# 2. gerar_video_ciclo — parâmetros enviados corretamente
# ==============================================================================

class TestGerarVideoCicloParams:

    def test_positive_pnl_uses_plus_sign(self, monkeypatch):
        """Lucro positivo → pnl_sinal='+' nos modifications."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        captured_payload = {}

        def _mock_request(method, path, body=None):
            if method == 'POST':
                captured_payload.update(body)
                return [{'id': 'render_001', 'status': 'succeeded', 'url': 'http://fake/video.mp4'}]
            return {'status': 'succeeded', 'url': 'http://fake/video.mp4'}

        monkeypatch.setattr(cw, '_request', _mock_request)
        monkeypatch.setattr(cw, '_download_bytes', lambda url: b'fake_video_bytes')

        cw.gerar_video_ciclo({'profit': 150.0, 'ops_count': 10, 'tvl_total': 2_000_000})

        assert captured_payload.get('modifications', {}).get('pnl_sinal') == '+'

    def test_negative_pnl_no_sign(self, monkeypatch):
        """Prejuízo → pnl_sinal='' (sem sinal)."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        captured_payload = {}

        def _mock_request(method, path, body=None):
            if method == 'POST':
                captured_payload.update(body)
                return [{'id': 'render_002', 'status': 'succeeded', 'url': 'http://fake/video.mp4'}]
            return {'status': 'succeeded', 'url': 'http://fake/video.mp4'}

        monkeypatch.setattr(cw, '_request', _mock_request)
        monkeypatch.setattr(cw, '_download_bytes', lambda url: b'fake_video_bytes')

        cw.gerar_video_ciclo({'profit': -50.0, 'ops_count': 3, 'tvl_total': 1_500_000})

        assert captured_payload.get('modifications', {}).get('pnl_sinal') == ''

    def test_tvl_converted_to_millions(self, monkeypatch):
        """TVL de 2_500_000 → tvl_milhoes='2.50'."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        captured_mods = {}

        def _mock_request(method, path, body=None):
            if method == 'POST':
                captured_mods.update(body.get('modifications', {}))
                return [{'id': 'render_003', 'status': 'succeeded', 'url': 'http://fake/video.mp4'}]
            return {'status': 'succeeded', 'url': 'http://fake/video.mp4'}

        monkeypatch.setattr(cw, '_request', _mock_request)
        monkeypatch.setattr(cw, '_download_bytes', lambda url: b'video')

        cw.gerar_video_ciclo({'profit': 0, 'ops_count': 0, 'tvl_total': 2_500_000})

        assert captured_mods.get('tvl_milhoes') == '2.50'

    def test_ops_count_in_modifications(self, monkeypatch):
        """ops_count passado como string nos modifications."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        captured_mods = {}

        def _mock_request(method, path, body=None):
            if method == 'POST':
                captured_mods.update(body.get('modifications', {}))
                return [{'id': 'render_004', 'status': 'succeeded', 'url': 'http://fake/video.mp4'}]
            return {'status': 'succeeded', 'url': 'http://fake/video.mp4'}

        monkeypatch.setattr(cw, '_request', _mock_request)
        monkeypatch.setattr(cw, '_download_bytes', lambda url: b'video')

        cw.gerar_video_ciclo({'profit': 10, 'ops_count': 42, 'tvl_total': 1_000_000})

        assert captured_mods.get('ops_count') == '42'

    def test_render_succeeded_returns_video_bytes(self, monkeypatch):
        """Render succeeded → retorna bytes do vídeo."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        video_bytes = b'fake_mp4_content_12345'

        def _mock_request(method, path, body=None):
            if method == 'POST':
                return [{'id': 'render_success', 'status': 'succeeded', 'url': 'http://fake/video.mp4'}]
            return {'status': 'succeeded', 'url': 'http://fake/video.mp4'}

        monkeypatch.setattr(cw, '_request', _mock_request)
        monkeypatch.setattr(cw, '_download_bytes', lambda url: video_bytes)

        result = cw.gerar_video_ciclo({'profit': 100, 'ops_count': 5, 'tvl_total': 1_000_000})
        assert result == video_bytes


# ==============================================================================
# 3. gerar_video_ciclo — timeout e error handling
# ==============================================================================

class TestGerarVideoGraceful:

    def test_render_failed_returns_none(self, monkeypatch):
        """Render com status 'failed' → retorna None."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        def _mock_request(method, path, body=None):
            if method == 'POST':
                return [{'id': 'render_fail', 'status': 'failed', 'url': None}]
            return {'status': 'failed', 'error_message': 'Template error'}

        monkeypatch.setattr(cw, '_request', _mock_request)

        result = cw.gerar_video_ciclo({'profit': 0, 'ops_count': 0, 'tvl_total': 0})
        assert result is None

    def test_poll_timeout_returns_none(self, monkeypatch):
        """Render demora mais que _POLL_TIMEOUT → retorna None sem travar."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        # Forçar timeout muito curto para o teste não demorar
        monkeypatch.setattr(cw, '_POLL_TIMEOUT', 0)
        monkeypatch.setattr(cw, '_POLL_INTERVAL', 1)

        call_count = {'n': 0}

        def _mock_request(method, path, body=None):
            call_count['n'] += 1
            if method == 'POST':
                return [{'id': 'render_slow', 'status': 'planned', 'url': None}]
            return {'status': 'planned', 'url': None}

        monkeypatch.setattr(cw, '_request', _mock_request)

        start = time.time()
        result = cw.gerar_video_ciclo({'profit': 0, 'ops_count': 0, 'tvl_total': 0})
        elapsed = time.time() - start

        assert result is None
        assert elapsed < 5.0, f'gerar_video_ciclo demorou demais: {elapsed:.1f}s'

    def test_http_error_returns_none(self, monkeypatch):
        """HTTPError na chamada à API → retorna None (graceful)."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        def _raise_http(*a, **kw):
            raise urllib.error.HTTPError(
                'http://fake', 403, 'Forbidden', {}, None
            )

        monkeypatch.setattr(cw, '_request', _raise_http)

        try:
            result = cw.gerar_video_ciclo({'profit': 0, 'ops_count': 0, 'tvl_total': 0})
        except Exception as e:
            pytest.fail(f'gerar_video_ciclo não deveria propagar exceção: {e}')

        assert result is None

    def test_generic_exception_returns_none(self, monkeypatch):
        """Exception genérica → retorna None (graceful degradation)."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        def _raise(*a, **kw):
            raise RuntimeError('Connection refused')

        monkeypatch.setattr(cw, '_request', _raise)

        result = cw.gerar_video_ciclo({'profit': 50, 'ops_count': 5, 'tvl_total': 1_000_000})
        assert result is None

    def test_missing_render_id_returns_none(self, monkeypatch):
        """Resposta POST sem render_id → retorna None."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        def _mock_request(method, path, body=None):
            if method == 'POST':
                return [{'status': 'pending'}]  # sem 'id'
            return {}

        monkeypatch.setattr(cw, '_request', _mock_request)

        result = cw.gerar_video_ciclo({'profit': 0, 'ops_count': 0, 'tvl_total': 0})
        assert result is None

    def test_dados_defaults_when_missing(self, monkeypatch):
        """Dados parciais (dict vazio) → usa defaults, sem KeyError."""
        import creatomate_worker as cw
        monkeypatch.setattr(cw, '_API_KEY', 'fake-key')

        def _mock_request(method, path, body=None):
            if method == 'POST':
                return [{'id': 'render_def', 'status': 'succeeded', 'url': 'http://fake/v.mp4'}]
            return {'status': 'succeeded', 'url': 'http://fake/v.mp4'}

        monkeypatch.setattr(cw, '_request', _mock_request)
        monkeypatch.setattr(cw, '_download_bytes', lambda url: b'video')

        try:
            result = cw.gerar_video_ciclo({})  # dict vazio — usa defaults
        except KeyError as e:
            pytest.fail(f'gerar_video_ciclo lançou KeyError com dict vazio: {e}')

        assert result == b'video'
