"""
test_subscription_worker.py — Testes para subscription_worker.py (Story 16.4 AC1)

Foco:
- _persist_subscription: idempotência (ON CONFLICT DO NOTHING)
- _get_wallet_lock: per-wallet lock registry, race condition guard
- _get_chat_id_for_wallet: lookup chat_id por wallet
- _notify_subscription: graceful quando send_html indisponível
- _process_event: evento malformado não crasha
"""
from __future__ import annotations

import threading
import time
import unittest.mock as mock
from datetime import datetime, timezone

import pytest


# ==============================================================================
# Setup: patch conn/cursor/DB_LOCK para testes isolados
# ==============================================================================

def _patch_sw(db_conn, monkeypatch):
    """Redireciona conn/cursor/DB_LOCK do subscription_worker para db_conn de teste."""
    import subscription_worker as sw
    import webdex_db

    monkeypatch.setattr(webdex_db, 'conn', db_conn)
    monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
    monkeypatch.setattr(sw, 'conn', db_conn)
    monkeypatch.setattr(sw, 'cursor', db_conn.cursor())
    return sw


def _ensure_subscriptions(db_conn):
    """Recria tabela subscriptions com schema correto + adiciona coluna subscription_expires."""
    db_conn.executescript("""
        DROP TABLE IF EXISTS subscriptions;
        CREATE TABLE subscriptions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_address  TEXT    NOT NULL COLLATE NOCASE,
            chat_id         INTEGER,
            tier            TEXT    NOT NULL DEFAULT 'pro',
            status          TEXT    NOT NULL DEFAULT 'active',
            activated_at    TEXT    NOT NULL,
            expires_at      TEXT,
            tx_hash         TEXT    NOT NULL,
            log_index       INTEGER NOT NULL,
            months          INTEGER NOT NULL DEFAULT 1,
            metadata        TEXT    DEFAULT '{}'
        );
        CREATE UNIQUE INDEX idx_sub_tx_test
            ON subscriptions (tx_hash, log_index);
    """)
    # _persist_subscription atualiza users.subscription_expires — garantir coluna existe
    try:
        db_conn.execute("ALTER TABLE users ADD COLUMN subscription_expires TEXT")
        db_conn.commit()
    except Exception:
        pass  # coluna já existe
    db_conn.commit()


# ==============================================================================
# 1. _get_wallet_lock — per-wallet lock registry
# ==============================================================================

class TestWalletLock:

    def test_same_wallet_returns_same_lock(self):
        """Mesma wallet → mesmo objeto Lock (singleton)."""
        import subscription_worker as sw
        sw._wallet_locks.clear()

        lock1 = sw._get_wallet_lock('0xabc')
        lock2 = sw._get_wallet_lock('0xabc')
        assert lock1 is lock2

    def test_different_wallets_different_locks(self):
        """Wallets diferentes → locks diferentes."""
        import subscription_worker as sw
        sw._wallet_locks.clear()

        lock1 = sw._get_wallet_lock('0xaaa')
        lock2 = sw._get_wallet_lock('0xbbb')
        assert lock1 is not lock2

    def test_wallet_normalized_lowercase(self):
        """'0xABC' e '0xabc' → mesmo lock (lowercase normalization)."""
        import subscription_worker as sw
        sw._wallet_locks.clear()

        lock1 = sw._get_wallet_lock('0xABC')
        lock2 = sw._get_wallet_lock('0xabc')
        assert lock1 is lock2

    def test_wallet_lock_is_threading_lock(self):
        """Lock retornado é um threading.Lock."""
        import subscription_worker as sw
        sw._wallet_locks.clear()

        lock = sw._get_wallet_lock('0xtest')
        assert hasattr(lock, 'acquire') and hasattr(lock, 'release')

    def test_concurrent_wallet_lock_access_no_crash(self):
        """Acesso concurrent ao registry não causa race condition."""
        import subscription_worker as sw
        sw._wallet_locks.clear()
        errors = []

        def _get_lock(wallet):
            try:
                sw._get_wallet_lock(wallet)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_get_lock, args=(f'0x{i:040x}',)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3)

        assert errors == [], f'Erros concorrentes: {errors}'


# ==============================================================================
# 2. _persist_subscription — idempotência crítica
# ==============================================================================

class TestPersistSubscription:

    def test_first_persist_returns_true(self, db_conn, monkeypatch):
        """Primeira inserção retorna True (nova subscription)."""
        _ensure_subscriptions(db_conn)
        sw = _patch_sw(db_conn, monkeypatch)

        result = sw._persist_subscription(
            wallet='0xfirstwallet',
            chat_id=20001,
            months=1,
            expiry_ts=int(time.time()) + 2592000,
            tx_hash='0xhash001',
            log_index=0,
            paid_bd=0,
        )
        assert result is True

    def test_duplicate_persist_returns_false(self, db_conn, monkeypatch):
        """Mesmo tx_hash + log_index → segunda inserção retorna False."""
        _ensure_subscriptions(db_conn)
        sw = _patch_sw(db_conn, monkeypatch)

        kwargs = dict(
            wallet='0xdupwallet',
            chat_id=20002,
            months=1,
            expiry_ts=int(time.time()) + 2592000,
            tx_hash='0xduphash',
            log_index=0,
            paid_bd=0,
        )
        sw._persist_subscription(**kwargs)
        result = sw._persist_subscription(**kwargs)  # segunda vez
        assert result is False

    def test_three_calls_same_hash_idempotent(self, db_conn, monkeypatch):
        """3 chamadas com mesmo hash → apenas 1 registro no banco."""
        _ensure_subscriptions(db_conn)
        sw = _patch_sw(db_conn, monkeypatch)

        for _ in range(3):
            sw._persist_subscription(
                wallet='0xtriplewallet',
                chat_id=20003,
                months=2,
                expiry_ts=int(time.time()) + 5184000,
                tx_hash='0xtriplehash',
                log_index=0,
                paid_bd=100,
            )

        count = db_conn.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE tx_hash='0xtriplehash'"
        ).fetchone()[0]
        assert count == 1

    def test_different_log_index_creates_new_record(self, db_conn, monkeypatch):
        """Mesmo tx_hash, log_index diferente → novo registro (evento diferente)."""
        _ensure_subscriptions(db_conn)
        sw = _patch_sw(db_conn, monkeypatch)

        r1 = sw._persist_subscription(
            wallet='0xmultiwallet',
            chat_id=20004,
            months=1,
            expiry_ts=int(time.time()) + 2592000,
            tx_hash='0xmultihash',
            log_index=0,
            paid_bd=0,
        )
        r2 = sw._persist_subscription(
            wallet='0xmultiwallet',
            chat_id=20004,
            months=1,
            expiry_ts=int(time.time()) + 2592000,
            tx_hash='0xmultihash',
            log_index=1,  # log_index diferente
            paid_bd=0,
        )
        assert r1 is True
        assert r2 is True

    def test_persist_with_zero_expiry(self, db_conn, monkeypatch):
        """expiry_ts=0 → expires_at=None, sem crash."""
        _ensure_subscriptions(db_conn)
        sw = _patch_sw(db_conn, monkeypatch)

        try:
            result = sw._persist_subscription(
                wallet='0xnoexpiry',
                chat_id=20005,
                months=1,
                expiry_ts=0,
                tx_hash='0xnoexpiryhash',
                log_index=0,
                paid_bd=0,
            )
        except Exception as e:
            pytest.fail(f'_persist_subscription falhou com expiry_ts=0: {e}')

        assert result is True


# ==============================================================================
# 3. _get_chat_id_for_wallet — lookup wallet → chat_id
# ==============================================================================

class TestGetChatIdForWallet:

    def test_registered_wallet_returns_chat_id(self, db_conn, monkeypatch):
        """Wallet registrada → chat_id retornado."""
        sw = _patch_sw(db_conn, monkeypatch)
        import webdex_db
        webdex_db.upsert_user(30001, wallet='0xregistered')

        result = sw._get_chat_id_for_wallet('0xregistered')
        assert result == 30001

    def test_unknown_wallet_returns_none(self, db_conn, monkeypatch):
        """Wallet não registrada → None."""
        sw = _patch_sw(db_conn, monkeypatch)
        result = sw._get_chat_id_for_wallet('0xunknown999')
        assert result is None

    def test_wallet_lookup_case_insensitive(self, db_conn, monkeypatch):
        """Lookup case-insensitive: '0xABC' encontra '0xabc'."""
        sw = _patch_sw(db_conn, monkeypatch)
        import webdex_db
        webdex_db.upsert_user(30002, wallet='0xabc123')

        result = sw._get_chat_id_for_wallet('0xABC123')
        assert result == 30002

    def test_user_without_wallet_not_found(self, db_conn, monkeypatch):
        """Wallet inexistente no banco → retorna None."""
        sw = _patch_sw(db_conn, monkeypatch)
        # Nenhum usuário com esta wallet foi inserido
        result = sw._get_chat_id_for_wallet('0xnonexistent_wallet_xyz999')
        assert result is None


# ==============================================================================
# 4. _notify_subscription — graceful sem send_html
# ==============================================================================

class TestNotifySubscription:

    def test_notify_without_send_html_no_crash(self, db_conn, monkeypatch):
        """send_html=None → _notify_subscription não crasha (graceful)."""
        import subscription_worker as sw
        monkeypatch.setattr(sw, 'send_html', None)

        try:
            sw._notify_subscription(
                chat_id=40001,
                wallet='0xnotifywallet',
                months=1,
                expires_at='2026-12-31 00:00:00',
            )
        except Exception as e:
            pytest.fail(f'_notify_subscription não deveria crashar: {e}')

    def test_notify_calls_send_html_with_correct_chat_id(self, db_conn, monkeypatch):
        """send_html disponível → chamada com chat_id correto."""
        import subscription_worker as sw

        calls = []
        monkeypatch.setattr(sw, 'send_html', lambda chat_id, text, **kw: calls.append(chat_id))

        sw._notify_subscription(
            chat_id=40002,
            wallet='0xnotifywallet2',
            months=3,
            expires_at='2027-03-31 00:00:00',
        )

        assert 40002 in calls

    def test_notify_message_contains_plan_info(self, db_conn, monkeypatch):
        """Mensagem de notificação contém info de plano PRO."""
        import subscription_worker as sw

        messages = []
        monkeypatch.setattr(sw, 'send_html', lambda chat_id, text, **kw: messages.append(text))

        sw._notify_subscription(
            chat_id=40003,
            wallet='0xprowallet',
            months=6,
            expires_at='2027-06-01 00:00:00',
        )

        assert len(messages) == 1
        assert 'PRO' in messages[0] or 'pro' in messages[0].lower()


# ==============================================================================
# 5. _process_event — malformed event graceful
# ==============================================================================

class TestProcessEvent:

    def test_malformed_event_no_crash(self, db_conn, monkeypatch):
        """Evento malformado (missing keys) → log de erro, sem crash."""
        _ensure_subscriptions(db_conn)
        sw = _patch_sw(db_conn, monkeypatch)

        bad_event = {'args': {}}  # sem keys obrigatórias
        w3_mock = mock.MagicMock()

        try:
            sw._process_event(bad_event, w3_mock)
        except Exception as e:
            pytest.fail(f'_process_event não deveria propagar exceção: {e}')

    def test_event_with_invalid_types_no_crash(self, db_conn, monkeypatch):
        """Evento com tipos errados → graceful (não crasha o loop)."""
        _ensure_subscriptions(db_conn)
        sw = _patch_sw(db_conn, monkeypatch)

        bad_event = {'args': {'wallet': None, 'months': 'invalid', 'expiry': None, 'paidBD': None}}
        w3_mock = mock.MagicMock()

        try:
            sw._process_event(bad_event, w3_mock)
        except Exception as e:
            pytest.fail(f'_process_event propagou exceção com tipos inválidos: {e}')
