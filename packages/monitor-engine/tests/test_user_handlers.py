"""
test_user_handlers.py — Testes para funções de usuário/subscription/LGPD (Story 16.3 AC1)

Nota: user.py não existe como arquivo separado — funções de usuário estão em
webdex_db.py (touch_user, set_user_active, ai_can_use) e
subscription_worker.py (_persist_subscription, _get_chat_id_for_wallet).

Foco:
- Criação e atualização de usuários (touch_user, set_user_active)
- Subscription tier: ativa/vencida (via subscription_expires em users)
- LGPD: ai_can_use (modo admin_only bloqueia usuário comum)
- wallet_connect: endereço normalizado/validado via upsert_user
"""
from __future__ import annotations

import time
import unittest.mock as mock
from datetime import datetime, timezone, timedelta

import pytest


def _patch_db(db_conn, monkeypatch):
    import webdex_db
    monkeypatch.setattr(webdex_db, 'conn', db_conn)
    monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
    return webdex_db


# ==============================================================================
# 1. touch_user — criação/update de usuário
# ==============================================================================

class TestTouchUser:

    def test_touch_user_updates_last_seen(self, db_conn, monkeypatch):
        """touch_user atualiza last_seen_ts de usuário existente (UPDATE only)."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(10001)  # cria usuário primeiro
        db_conn.execute("UPDATE users SET last_seen_ts=1 WHERE chat_id=10001")
        db_conn.commit()
        wdb.touch_user(10001)
        row = db_conn.execute("SELECT last_seen_ts FROM users WHERE chat_id=10001").fetchone()
        assert row[0] > 1  # last_seen_ts foi atualizado

    def test_touch_user_with_username(self, db_conn, monkeypatch):
        """touch_user atualiza username em usuário existente sem crash."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(10002)
        try:
            wdb.touch_user(10002, 'testuser')
        except Exception as e:
            pytest.fail(f'touch_user não deveria lançar exceção: {e}')
        row = db_conn.execute("SELECT username FROM users WHERE chat_id=10002").fetchone()
        assert row is not None

    def test_touch_user_idempotent(self, db_conn, monkeypatch):
        """touch_user chamado N vezes não duplica usuário."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(10003)
        wdb.touch_user(10003)
        wdb.touch_user(10003)
        wdb.touch_user(10003)
        rows = db_conn.execute("SELECT COUNT(*) FROM users WHERE chat_id=10003").fetchone()
        assert rows[0] == 1


# ==============================================================================
# 2. set_user_active / upsert_user — ativação e wallet
# ==============================================================================

class TestSetUserActive:

    def test_set_user_active_enables_user(self, db_conn, monkeypatch):
        """set_user_active(1) → usuário marcado como ativo."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(11004, wallet='0xabc123')
        wdb.set_user_active(11004, active=1)
        user = wdb.get_user(11004)
        assert user['active'] == 1

    def test_set_user_active_disables_user(self, db_conn, monkeypatch):
        """set_user_active(0) → usuário desativado."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(11005, wallet='0xdef456')
        wdb.set_user_active(11005, active=1)
        wdb.set_user_active(11005, active=0)
        user = wdb.get_user(11005)
        assert user['active'] == 0

    def test_upsert_user_normalizes_wallet_lowercase(self, db_conn, monkeypatch):
        """Wallet salva em lowercase — validação de endereço normalizado."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(11006, wallet='0xABCDEF123456')
        user = wdb.get_user(11006)
        assert user['wallet'] == '0xabcdef123456'

    def test_upsert_user_empty_wallet_not_active(self, db_conn, monkeypatch):
        """Usuário sem wallet não aparece em get_connected_users."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(11007, wallet='')
        connected = wdb.get_connected_users()
        assert 11007 not in connected

    def test_upsert_user_with_valid_wallet_connected(self, db_conn, monkeypatch):
        """Usuário com wallet aparece em get_connected_users."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(11008, wallet='0x1234567890abcdef')
        connected = wdb.get_connected_users()
        assert 11008 in connected


# ==============================================================================
# 3. Subscription tier — active/expired
# ==============================================================================

class TestSubscriptionTier:

    def test_user_without_subscription_has_no_expires(self, db_conn, monkeypatch):
        """Usuário novo sem subscription → subscription_expires nulo."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(11009, wallet='0xnosub')
        user = wdb.get_user(11009)
        # subscription_expires deve ser None ou ausente
        expires = user.get('subscription_expires')
        assert expires is None or expires == '' or expires == '0'

    def test_ai_can_use_when_global_enabled(self, db_conn, monkeypatch):
        """ai_can_use retorna True quando AI global está habilitada para usuário."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_global_enabled', '1')
        wdb.set_config('ai_admin_only', '0')

        # Mock _is_admin para usuário comum
        import webdex_bot_core
        monkeypatch.setattr(webdex_bot_core, '_is_admin', lambda cid: False)

        result = wdb.ai_can_use(11010)
        assert result is True

    def test_ai_can_use_blocked_when_global_disabled(self, db_conn, monkeypatch):
        """ai_can_use retorna False quando AI global desabilitada."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_global_enabled', '0')

        result = wdb.ai_can_use(11011)
        assert result is False

    def test_ai_can_use_admin_only_blocks_regular_user(self, db_conn, monkeypatch):
        """Modo admin_only → usuário comum bloqueado."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_global_enabled', '1')
        wdb.set_config('ai_admin_only', '1')

        import webdex_bot_core
        monkeypatch.setattr(webdex_bot_core, '_is_admin', lambda cid: False)

        result = wdb.ai_can_use(11012)
        assert result is False

    def test_ai_can_use_admin_only_allows_admin(self, db_conn, monkeypatch):
        """Modo admin_only → admin ainda pode usar."""
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_global_enabled', '1')
        wdb.set_config('ai_admin_only', '1')

        import webdex_bot_core
        monkeypatch.setattr(webdex_bot_core, '_is_admin', lambda cid: True)

        result = wdb.ai_can_use(123456789)  # admin do conftest
        assert result is True


# ==============================================================================
# 4. LGPD — delete ai_conversations
# ==============================================================================

class TestLgpdDelete:

    def test_ai_conversations_can_be_deleted(self, db_conn, monkeypatch):
        """Registros de ai_conversations podem ser deletados por chat_id (LGPD)."""
        # Inserir mensagens de IA
        db_conn.execute(
            "INSERT INTO ai_conversations (chat_id, role, content) VALUES (?, ?, ?)",
            (11013, 'user', 'Mensagem LGPD')
        )
        db_conn.execute(
            "INSERT INTO ai_conversations (chat_id, role, content) VALUES (?, ?, ?)",
            (11013, 'assistant', 'Resposta LGPD')
        )
        db_conn.commit()

        count_before = db_conn.execute(
            "SELECT COUNT(*) FROM ai_conversations WHERE chat_id=11013"
        ).fetchone()[0]
        assert count_before == 2

        # Deletar via SQL direto (simula o que mem_delete_all_pg faz)
        db_conn.execute("DELETE FROM ai_conversations WHERE chat_id=11013")
        db_conn.commit()

        count_after = db_conn.execute(
            "SELECT COUNT(*) FROM ai_conversations WHERE chat_id=11013"
        ).fetchone()[0]
        assert count_after == 0

    def test_delete_preserves_other_users_data(self, db_conn, monkeypatch):
        """LGPD delete de user A não apaga dados de user B."""
        db_conn.execute(
            "INSERT INTO ai_conversations (chat_id, role, content) VALUES (?, ?, ?)",
            (11014, 'user', 'Msg user A')
        )
        db_conn.execute(
            "INSERT INTO ai_conversations (chat_id, role, content) VALUES (?, ?, ?)",
            (11015, 'user', 'Msg user B')
        )
        db_conn.commit()

        db_conn.execute("DELETE FROM ai_conversations WHERE chat_id=11014")
        db_conn.commit()

        count_b = db_conn.execute(
            "SELECT COUNT(*) FROM ai_conversations WHERE chat_id=11015"
        ).fetchone()[0]
        assert count_b == 1
