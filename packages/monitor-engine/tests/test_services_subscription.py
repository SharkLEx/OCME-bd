"""
test_services_subscription.py — Testes para services/subscription.py

Story 7.4 | Epic 7 — Modularização do Monolito Python
Cobertura alvo: >= 90%

Testa:
- get_user_tier: free (sem sub), pro (sub ativa), institucional, expirada
- can_use_feature: free features, pro features, features desconhecidas
- get_rate_limit_config: config por tier
- is_subscription_active / get_subscription_expiry
- Graceful degradation quando DB falha
"""
from __future__ import annotations

import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta
from unittest import mock

import pytest

# conftest.py já seta DB_PATH=:memory: e mocks de telebot/web3
# Garante que os módulos mockados estão antes do import do projeto
os.environ.setdefault('DB_PATH', ':memory:')


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_db():
    """Cria SQLite :memory: com tabelas subscriptions e users."""
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_address  TEXT    NOT NULL,
            chat_id         INTEGER,
            tier            TEXT    NOT NULL DEFAULT 'pro',
            status          TEXT    NOT NULL DEFAULT 'active',
            activated_at    TEXT    NOT NULL,
            expires_at      TEXT,
            tx_hash         TEXT    NOT NULL,
            log_index       INTEGER NOT NULL DEFAULT 0,
            months          INTEGER NOT NULL DEFAULT 1,
            metadata        TEXT    DEFAULT '{}'
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id              INTEGER PRIMARY KEY,
            username             TEXT,
            subscription_expires TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS config (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    db.commit()
    return db


def _future_iso(days: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _past_iso(days: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    return _make_db()


@pytest.fixture
def mock_db(db):
    """Patcha webdex_db com DB em memória para testes de subscription."""
    import threading
    lock = threading.Lock()

    with mock.patch.dict(sys.modules, {
        'webdex_db': mock.MagicMock(
            DB_LOCK=lock,
            conn=db,
        ),
    }):
        yield db


# ── Testes de get_user_tier ───────────────────────────────────────────────────

class TestGetUserTier:

    def test_free_when_no_subscription(self, mock_db):
        from services.subscription import get_user_tier
        assert get_user_tier(999) == "free"

    def test_pro_with_active_subscription(self, mock_db):
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xABC", 100, "pro", "active", _past_iso(5), _future_iso(25), "0xTXHASH1"),
        )
        mock_db.commit()

        from services.subscription import get_user_tier
        assert get_user_tier(100) == "pro"

    def test_free_with_expired_subscription(self, mock_db):
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xDEF", 200, "pro", "active", _past_iso(35), _past_iso(5), "0xTXHASH2"),
        )
        mock_db.commit()

        from services.subscription import get_user_tier
        assert get_user_tier(200) == "free"

    def test_free_with_inactive_subscription(self, mock_db):
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xGHI", 300, "pro", "cancelled", _past_iso(10), _future_iso(20), "0xTXHASH3"),
        )
        mock_db.commit()

        from services.subscription import get_user_tier
        assert get_user_tier(300) == "free"

    def test_institutional_tier(self, mock_db):
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xINST", 400, "institutional", "active", _past_iso(1), _future_iso(365), "0xTXHASH4"),
        )
        mock_db.commit()

        from services.subscription import get_user_tier
        assert get_user_tier(400) == "institutional"

    def test_fallback_to_users_subscription_expires(self, mock_db):
        """Verifica fallback para users.subscription_expires quando subscriptions está vazia."""
        mock_db.execute(
            "INSERT INTO users (chat_id, subscription_expires) VALUES (?, ?)",
            (500, _future_iso(15)),
        )
        mock_db.commit()

        from services.subscription import get_user_tier
        assert get_user_tier(500) == "pro"

    def test_fallback_expired_returns_free(self, mock_db):
        mock_db.execute(
            "INSERT INTO users (chat_id, subscription_expires) VALUES (?, ?)",
            (600, _past_iso(3)),
        )
        mock_db.commit()

        from services.subscription import get_user_tier
        assert get_user_tier(600) == "free"

    def test_graceful_degradation_on_db_error(self):
        with mock.patch.dict(sys.modules, {
            'webdex_db': mock.MagicMock(
                DB_LOCK=mock.MagicMock(),
                conn=mock.MagicMock(
                    execute=mock.MagicMock(side_effect=Exception("DB unavailable"))
                ),
            ),
        }):
            from importlib import import_module, reload
            import services.subscription as sub_mod
            # get_user_tier deve retornar "free" sem levantar exceção
            result = sub_mod.get_user_tier(999)
            assert result == "free"


# ── Testes de can_use_feature ────────────────────────────────────────────────

class TestCanUseFeature:

    def test_free_feature_always_allowed(self, mock_db):
        from services.subscription import can_use_feature
        # Usuário sem subscription pode usar features free
        assert can_use_feature(999, "ask") is True
        assert can_use_feature(999, "monitor") is True
        assert can_use_feature(999, "rank") is True

    def test_pro_feature_blocked_for_free(self, mock_db):
        from services.subscription import can_use_feature
        assert can_use_feature(999, "vision") is False
        assert can_use_feature(999, "image_gen") is False
        assert can_use_feature(999, "card") is False

    def test_pro_feature_allowed_for_pro(self, mock_db):
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xPRO", 700, "pro", "active", _past_iso(1), _future_iso(30), "0xTXHASH5"),
        )
        mock_db.commit()

        from services.subscription import can_use_feature
        assert can_use_feature(700, "vision") is True
        assert can_use_feature(700, "image_gen") is True

    def test_institutional_feature_blocked_for_pro(self, mock_db):
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xPRO2", 800, "pro", "active", _past_iso(1), _future_iso(30), "0xTXHASH6"),
        )
        mock_db.commit()

        from services.subscription import can_use_feature
        assert can_use_feature(800, "api_access") is False

    def test_unknown_feature_always_allowed(self, mock_db):
        from services.subscription import can_use_feature
        assert can_use_feature(999, "feature_does_not_exist") is True

    def test_institutional_allows_all(self, mock_db):
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xINST2", 900, "institutional", "active", _past_iso(1), _future_iso(365), "0xTXHASH7"),
        )
        mock_db.commit()

        from services.subscription import can_use_feature
        assert can_use_feature(900, "api_access") is True
        assert can_use_feature(900, "vision") is True
        assert can_use_feature(900, "ask") is True


# ── Testes de get_rate_limit_config ──────────────────────────────────────────

class TestGetRateLimitConfig:

    def test_free_config(self, mock_db):
        from services.subscription import get_rate_limit_config
        config = get_rate_limit_config(999)
        assert config["chat"] == 5
        assert config["vision"] == 0
        assert config["image_gen"] == 0

    def test_pro_config(self, mock_db):
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xRLC", 1001, "pro", "active", _past_iso(1), _future_iso(30), "0xTXHASH8"),
        )
        mock_db.commit()

        from services.subscription import get_rate_limit_config
        config = get_rate_limit_config(1001)
        assert config["chat"] == 8
        assert config["vision"] == 3
        assert config["image_gen"] == 2

    def test_institutional_config(self, mock_db):
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xRLI", 1002, "institutional", "active", _past_iso(1), _future_iso(365), "0xTXHASH9"),
        )
        mock_db.commit()

        from services.subscription import get_rate_limit_config
        config = get_rate_limit_config(1002)
        assert config["chat"] == 20
        assert config["vision"] == 10


# ── Testes auxiliares ────────────────────────────────────────────────────────

class TestHelpers:

    def test_is_subscription_active_true(self, mock_db):
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xACT", 1100, "pro", "active", _past_iso(1), _future_iso(30), "0xTXHASH10"),
        )
        mock_db.commit()

        from services.subscription import is_subscription_active
        assert is_subscription_active(1100) is True

    def test_is_subscription_active_false_for_free(self, mock_db):
        from services.subscription import is_subscription_active
        assert is_subscription_active(9999) is False

    def test_get_subscription_expiry_returns_date(self, mock_db):
        expiry = _future_iso(30)
        mock_db.execute(
            "INSERT INTO subscriptions (wallet_address, chat_id, tier, status, activated_at, expires_at, tx_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("0xEXP", 1200, "pro", "active", _past_iso(1), expiry, "0xTXHASH11"),
        )
        mock_db.commit()

        from services.subscription import get_subscription_expiry
        result = get_subscription_expiry(1200)
        assert result == expiry

    def test_get_subscription_expiry_none_for_free(self, mock_db):
        from services.subscription import get_subscription_expiry
        assert get_subscription_expiry(9998) is None
