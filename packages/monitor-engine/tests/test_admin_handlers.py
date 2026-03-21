"""
test_admin_handlers.py — Testes para funções admin (Story 16.3 AC2)

Nota: admin.py não existe como arquivo separado — funções admin estão em
webdex_bot_core.py (_is_admin, is_admin, _get_admin_chat_ids, ADMIN_USER_IDS)
e webdex_db.py (ai_can_use com admin_only mode).

Foco:
- Bloqueio de usuário comum em rotas admin
- _is_admin: verifica ADMIN_USER_IDS corretamente
- _get_admin_chat_ids: retorna lista ordenada de IDs
- Métricas de config: ai_global_enabled, ai_admin_only, ai_mode
"""
from __future__ import annotations

import sys
import unittest.mock as mock
import pytest


def _real_wbc(monkeypatch):
    """Remove o mock de webdex_bot_core, importa o módulo real e normaliza ADMIN_USER_IDS."""
    monkeypatch.delitem(sys.modules, 'webdex_bot_core', raising=False)
    import webdex_bot_core as _wbc
    # O .env real tem IDs diferentes — força o valor do conftest para os testes
    monkeypatch.setattr(_wbc, 'ADMIN_USER_IDS', [123456789])
    return _wbc


# ==============================================================================
# 1. _is_admin — gate de segurança admin
# ==============================================================================

class TestIsAdmin:

    def test_admin_id_from_env_is_recognized(self, monkeypatch):
        """ADMIN_USER_IDS do conftest (123456789) → is_admin retorna True."""
        wbc = _real_wbc(monkeypatch)
        # conftest seta ADMIN_USER_IDS=123456789
        assert wbc._is_admin(123456789) is True

    def test_random_user_not_admin(self, monkeypatch):
        """Usuário comum (não em ADMIN_USER_IDS) → is_admin retorna False."""
        wbc = _real_wbc(monkeypatch)
        assert wbc._is_admin(99999999) is False

    def test_is_admin_zero_not_admin(self, monkeypatch):
        """chat_id=0 não é admin."""
        wbc = _real_wbc(monkeypatch)
        assert wbc._is_admin(0) is False

    def test_is_admin_chat_wraps_is_admin(self, monkeypatch):
        """is_admin_chat(123456789) retorna True."""
        wbc = _real_wbc(monkeypatch)
        assert wbc.is_admin_chat(123456789) is True

    def test_is_admin_chat_handles_non_int_gracefully(self, monkeypatch):
        """is_admin_chat com string inválida retorna False (não crasha)."""
        wbc = _real_wbc(monkeypatch)
        try:
            result = wbc.is_admin_chat('nao_e_numero')
        except Exception as e:
            pytest.fail(f'is_admin_chat não deveria lançar exceção: {e}')
        assert result is False

    def test_is_admin_function_alias(self, monkeypatch):
        """is_admin(chat_id) é alias de is_admin_chat."""
        wbc = _real_wbc(monkeypatch)
        assert wbc.is_admin(123456789) is True
        assert wbc.is_admin(99999) is False


# ==============================================================================
# 2. _get_admin_chat_ids — lista de admins
# ==============================================================================

class TestGetAdminChatIds:

    def test_returns_list_with_env_admin(self, monkeypatch):
        """_get_admin_chat_ids retorna lista com 123456789 (do conftest ADMIN_USER_IDS)."""
        wbc = _real_wbc(monkeypatch)
        ids = wbc._get_admin_chat_ids()
        assert isinstance(ids, list)
        assert 123456789 in ids

    def test_returns_sorted_list(self, monkeypatch):
        """IDs retornados em ordem crescente."""
        wbc = _real_wbc(monkeypatch)
        ids = wbc._get_admin_chat_ids()
        assert ids == sorted(ids)

    def test_multiple_admins_all_returned(self, monkeypatch):
        """Múltiplos admins na env var → todos retornados."""
        wbc = _real_wbc(monkeypatch)
        monkeypatch.setattr(wbc, 'ADMIN_USER_IDS', [111, 222, 333])
        ids = wbc._get_admin_chat_ids()
        assert sorted(ids) == [111, 222, 333]

    def test_empty_admin_ids_returns_empty_list(self, monkeypatch):
        """ADMIN_USER_IDS vazio → lista vazia (sem crash)."""
        wbc = _real_wbc(monkeypatch)
        monkeypatch.setattr(wbc, 'ADMIN_USER_IDS', [])
        ids = wbc._get_admin_chat_ids()
        assert ids == []


# ==============================================================================
# 3. Admin-only gate via AI config (simula bloqueio de rota admin)
# ==============================================================================

class TestAdminGateViaConfig:

    def _patch_db(self, db_conn, monkeypatch):
        import webdex_db
        monkeypatch.setattr(webdex_db, 'conn', db_conn)
        monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
        return webdex_db

    def test_admin_only_mode_blocks_regular_user(self, db_conn, monkeypatch):
        """ai_admin_only=1 → ai_can_use retorna False para usuário comum."""
        wdb = self._patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_global_enabled', '1')
        wdb.set_config('ai_admin_only', '1')

        import webdex_bot_core
        monkeypatch.setattr(webdex_bot_core, '_is_admin', lambda cid: False)

        assert wdb.ai_can_use(99999) is False

    def test_admin_only_mode_allows_admin_user(self, db_conn, monkeypatch):
        """ai_admin_only=1 → ai_can_use retorna True para admin."""
        wdb = self._patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_global_enabled', '1')
        wdb.set_config('ai_admin_only', '1')

        import webdex_bot_core
        monkeypatch.setattr(webdex_bot_core, '_is_admin', lambda cid: True)

        assert wdb.ai_can_use(123456789) is True

    def test_global_disable_blocks_even_admin(self, db_conn, monkeypatch):
        """ai_global_enabled=0 → TODOS bloqueados, incluindo admin."""
        wdb = self._patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_global_enabled', '0')

        assert wdb.ai_can_use(123456789) is False

    def test_admin_metrics_ai_mode_returns_string(self, db_conn, monkeypatch):
        """ai_mode() retorna string de modo configurado."""
        wdb = self._patch_db(db_conn, monkeypatch)
        # Default
        mode = wdb.ai_mode()
        assert isinstance(mode, str)
        assert len(mode) > 0

    def test_admin_can_set_dev_mode(self, db_conn, monkeypatch):
        """Admin pode setar ai_mode=dev."""
        wdb = self._patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_mode', 'dev')
        assert wdb.ai_mode() == 'dev'

    def test_admin_can_set_community_mode(self, db_conn, monkeypatch):
        """Admin pode reverter para modo community."""
        wdb = self._patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_mode', 'dev')
        wdb.set_config('ai_mode', 'community')
        assert wdb.ai_mode() == 'community'


# ==============================================================================
# 4. Utilitários de texto (usados nos relatórios admin)
# ==============================================================================

class TestAdminTextUtils:

    def test_esc_escapes_html_chars(self, monkeypatch):
        """esc() escapa caracteres HTML perigosos."""
        wbc = _real_wbc(monkeypatch)
        assert wbc.esc('<script>') == '&lt;script&gt;'
        assert wbc.esc('&amp;') == '&amp;amp;'

    def test_code_wraps_in_code_tags(self, monkeypatch):
        """code() envolve em <code>.</code>"""
        wbc = _real_wbc(monkeypatch)
        result = wbc.code('0xABC')
        assert result == '<code>0xABC</code>'

    def test_barra_progresso_full_wins(self, monkeypatch):
        """100% wins → 10 blocos verdes."""
        wbc = _real_wbc(monkeypatch)
        result = wbc.barra_progresso(10, 10)
        assert result == '🟩' * 10

    def test_barra_progresso_zero_wins(self, monkeypatch):
        """0% wins → 10 blocos vermelhos."""
        wbc = _real_wbc(monkeypatch)
        result = wbc.barra_progresso(0, 10)
        assert result == '🔴' * 10

    def test_barra_progresso_zero_total_no_crash(self, monkeypatch):
        """Total=0 → sem divisão por zero."""
        wbc = _real_wbc(monkeypatch)
        try:
            result = wbc.barra_progresso(0, 0)
        except ZeroDivisionError:
            pytest.fail('barra_progresso dividiu por zero com total=0')
        assert isinstance(result, str)

    def test_barra_progresso_half_wins(self, monkeypatch):
        """50% wins → 5 verdes + 5 vermelhos."""
        wbc = _real_wbc(monkeypatch)
        result = wbc.barra_progresso(5, 10)
        assert '🟩' * 5 in result
        assert '🔴' * 5 in result
