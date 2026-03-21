"""
test_notification_engine.py — Testes para notification_engine.py (Story 16.4 AC2)

Foco:
- _can_notify / _mark_notified: cooldown de 30min por tipo de evento
- _post_embed: payload correto, graceful em falha de webhook
- _check_milestones: TVL cruza patamar → evento gerado
- _check_new_holders: nova wallet → evento gerado
- run_notification_check: não duplica notificações dentro do cooldown
"""
from __future__ import annotations

import gc
import json
import os
import sqlite3
import tempfile
import time
import unittest.mock as mock

import pytest


def _safe_unlink(path: str) -> None:
    """Remove arquivo de forma segura no Windows (SQLite pode manter handle aberto)."""
    gc.collect()  # força GC do objeto sqlite3.Connection
    try:
        os.unlink(path)
    except PermissionError:
        pass  # Windows: o OS limpará o arquivo temporário eventualmente


# ==============================================================================
# 1. _can_notify / _mark_notified — cooldown
# ==============================================================================

class TestCooldownControl:

    def test_can_notify_first_time_is_true(self):
        """Evento nunca notificado → _can_notify retorna True."""
        import notification_engine as ne
        state = {}
        assert ne._can_notify(state, 'new_holder') is True

    def test_mark_notified_sets_timestamp(self):
        """_mark_notified persiste timestamp no state."""
        import notification_engine as ne
        state = {}
        ne._mark_notified(state, 'milestone')
        assert 'last_milestone' in state
        assert isinstance(state['last_milestone'], float)

    def test_can_notify_false_within_cooldown(self, monkeypatch):
        """Após _mark_notified, _can_notify retorna False (dentro do cooldown)."""
        import notification_engine as ne
        state = {}
        ne._mark_notified(state, 'new_holder')
        # Dentro do cooldown (30 min)
        assert ne._can_notify(state, 'new_holder') is False

    def test_can_notify_true_after_cooldown(self, monkeypatch):
        """Após cooldown expirar, _can_notify volta a True."""
        import notification_engine as ne
        # Simular notificação há mais de COOLDOWN_SECS atrás
        state = {'last_anomaly': time.time() - ne.COOLDOWN_SECS - 10}
        assert ne._can_notify(state, 'anomaly') is True

    def test_different_events_independent_cooldown(self):
        """Cooldown de 'milestone' não afeta 'new_holder'."""
        import notification_engine as ne
        state = {}
        ne._mark_notified(state, 'milestone')
        # new_holder ainda pode notificar
        assert ne._can_notify(state, 'new_holder') is True

    def test_mark_notified_updates_existing_timestamp(self):
        """_mark_notified sobrescreve timestamp antigo."""
        import notification_engine as ne
        state = {'last_new_holder': time.time() - 9999}
        old_ts = state['last_new_holder']
        ne._mark_notified(state, 'new_holder')
        assert state['last_new_holder'] > old_ts


# ==============================================================================
# 2. _post_embed — envio de embed Discord
# ==============================================================================

class TestPostEmbed:

    def test_empty_webhook_url_returns_false(self, monkeypatch):
        """URL vazia → retorna False sem tentar POST."""
        import notification_engine as ne
        result = ne._post_embed('', 'Título', 'Descrição', 0x00FF00)
        assert result is False

    def test_successful_post_returns_true(self, monkeypatch):
        """HTTP 200 → retorna True."""
        import notification_engine as ne

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200

        monkeypatch.setattr(ne.requests, 'post', lambda *a, **kw: mock_resp)

        result = ne._post_embed('https://discord.com/fake', 'Título', 'Desc', 0x00FF00)
        assert result is True

    def test_http_204_also_success(self, monkeypatch):
        """HTTP 204 (No Content) → retorna True."""
        import notification_engine as ne

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 204

        monkeypatch.setattr(ne.requests, 'post', lambda *a, **kw: mock_resp)

        result = ne._post_embed('https://discord.com/fake', 'Test', 'Desc', 0)
        assert result is True

    def test_http_403_returns_false(self, monkeypatch):
        """HTTP 403 (webhook expirado) → retorna False."""
        import notification_engine as ne

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 403

        monkeypatch.setattr(ne.requests, 'post', lambda *a, **kw: mock_resp)

        result = ne._post_embed('https://discord.com/fake', 'Test', 'Desc', 0)
        assert result is False

    def test_exception_during_post_returns_false(self, monkeypatch):
        """Exception no POST → graceful, retorna False."""
        import notification_engine as ne

        def _raise(*a, **kw):
            raise RuntimeError('Network error')

        monkeypatch.setattr(ne.requests, 'post', _raise)

        result = ne._post_embed('https://discord.com/fake', 'Test', 'Desc', 0)
        assert result is False

    def test_post_payload_has_required_fields(self, monkeypatch):
        """Payload enviado tem campo 'embeds' com título, descrição e cor."""
        import notification_engine as ne

        captured = {}

        def _mock_post(url, json=None, timeout=None):
            captured['payload'] = json
            resp = mock.MagicMock()
            resp.status_code = 200
            return resp

        monkeypatch.setattr(ne.requests, 'post', _mock_post)
        ne._post_embed('https://fake', 'Meu Título', 'Minha Desc', 0xFF0000)

        assert 'embeds' in captured['payload']
        embed = captured['payload']['embeds'][0]
        assert embed['title'] == 'Meu Título'
        assert embed['description'] == 'Minha Desc'
        assert embed['color'] == 0xFF0000


# ==============================================================================
# 3. _check_milestones — detecção de TVL milestone
# ==============================================================================

class TestCheckMilestones:

    def _make_db_with_tvl(self, tvl: float) -> str:
        """Cria SQLite temporário com capital_cache."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE capital_cache (wallet TEXT, total_usd REAL)")
        db.execute("INSERT INTO capital_cache VALUES (?, ?)", ('0xtest', tvl))
        db.commit()
        db.close()
        return path

    def test_tvl_above_milestone_generates_event(self, monkeypatch):
        """TVL de $15k com step=$10k → milestone $10k detectado."""
        import notification_engine as ne
        monkeypatch.setattr(ne, 'TVL_MILESTONE_STEP', 10000.0)

        path = self._make_db_with_tvl(15000.0)
        try:
            state = {'last_milestone_tvl': 0}
            events = ne._check_milestones(path, state)
            assert len(events) > 0
            assert events[0]['type'] == 'milestone'
        finally:
            _safe_unlink(path)

    def test_tvl_same_milestone_no_duplicate(self, monkeypatch):
        """TVL já acima do mesmo milestone → não gera novo evento."""
        import notification_engine as ne
        monkeypatch.setattr(ne, 'TVL_MILESTONE_STEP', 10000.0)

        path = self._make_db_with_tvl(15000.0)
        try:
            # Simular que $10k milestone já foi atingido
            state = {'last_milestone_tvl': 10000.0}
            events = ne._check_milestones(path, state)
            assert len(events) == 0
        finally:
            _safe_unlink(path)

    def test_tvl_within_cooldown_no_event(self, monkeypatch):
        """Dentro do cooldown → _can_notify retorna False → sem evento."""
        import notification_engine as ne
        monkeypatch.setattr(ne, 'TVL_MILESTONE_STEP', 10000.0)

        path = self._make_db_with_tvl(15000.0)
        try:
            # Cooldown ativo
            state = {
                'last_milestone_tvl': 0,
                'last_milestone': time.time(),  # marcado agora = dentro do cooldown
            }
            events = ne._check_milestones(path, state)
            assert len(events) == 0
        finally:
            _safe_unlink(path)

    def test_missing_capital_cache_table_graceful(self, monkeypatch):
        """Sem tabela capital_cache → retorna [] sem crash."""
        import notification_engine as ne

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            state = {}
            events = ne._check_milestones(path, state)
            assert events == []
        finally:
            _safe_unlink(path)


# ==============================================================================
# 4. _check_new_holders — detecção de novas wallets
# ==============================================================================

class TestCheckNewHolders:

    def _make_db_with_holders(self, wallets: list) -> str:
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE protocol_ops (wallet TEXT, data_hora TEXT)")
        for w in wallets:
            db.execute("INSERT INTO protocol_ops VALUES (?, datetime('now'))", (w,))
        db.commit()
        db.close()
        return path

    def test_new_wallet_detected(self, monkeypatch):
        """Nova wallet (não em known_wallets) → evento new_holder gerado."""
        import notification_engine as ne

        path = self._make_db_with_holders(['0xnewwallet'])
        try:
            # known_wallets com uma carteira diferente (para não ser "first holder")
            state = {'known_wallets': ['0xoldwallet']}
            events = ne._check_new_holders(path, state)
            assert len(events) > 0
            assert events[0]['type'] == 'new_holder'
        finally:
            _safe_unlink(path)

    def test_known_wallet_no_event(self, monkeypatch):
        """Wallet já conhecida → sem evento new_holder."""
        import notification_engine as ne

        path = self._make_db_with_holders(['0xknown'])
        try:
            state = {'known_wallets': ['0xknown']}
            events = ne._check_new_holders(path, state)
            assert all(e['type'] != 'new_holder' for e in events)
        finally:
            _safe_unlink(path)

    def test_first_holder_no_event(self, monkeypatch):
        """Primeiro holder (known_wallets vazio) → sem evento (ainda não há baseline)."""
        import notification_engine as ne

        path = self._make_db_with_holders(['0xfirst'])
        try:
            state = {}  # sem known_wallets → primeiro boot
            events = ne._check_new_holders(path, state)
            # Não deve gerar evento quando known_wallets está vazio
            assert all(e.get('type') != 'new_holder' for e in events)
        finally:
            _safe_unlink(path)

    def test_missing_protocol_ops_table_graceful(self, monkeypatch):
        """Sem tabela protocol_ops → retorna [] sem crash."""
        import notification_engine as ne

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            state = {}
            events = ne._check_new_holders(path, state)
            assert events == []
        finally:
            _safe_unlink(path)
