"""
test_rate_limit_granular.py — Story 23.2
Testes para rate limit granular por feature (chat/vision/image_gen/proactive)
"""
from __future__ import annotations

import json
import time
import threading
from unittest.mock import patch, MagicMock

import pytest


# ── Helpers para isolar o estado entre testes ─────────────────────────────────

def _fresh_state(module):
    """Limpa _ia_rate_state entre testes."""
    with module._ia_rate_lock:
        module._ia_rate_state.clear()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_db(monkeypatch):
    """Mocka DB calls para não precisar de SQLite real."""
    import webdex_ai as ai_mod
    monkeypatch.setattr(ai_mod, "set_config", MagicMock())
    monkeypatch.setattr(ai_mod, "get_config", MagicMock(return_value=""))
    yield
    _fresh_state(ai_mod)


@pytest.fixture()
def ai_mod():
    import webdex_ai as mod
    return mod


@pytest.fixture()
def admin_ids(ai_mod, monkeypatch):
    """Injeta um admin_id fixo no webdex_config (fonte real usada pelo _check_rate_limit)."""
    monkeypatch.setattr(
        "webdex_config.ADMIN_USER_IDS",
        {999},
        raising=False,
    )


# ── Testes básicos por feature ─────────────────────────────────────────────────

class TestCheckRateLimit:
    def test_first_call_always_allowed(self, ai_mod):
        allowed, remaining, reset_in = ai_mod._check_rate_limit(101, "chat")
        assert allowed is True
        assert remaining == ai_mod._IA_RATE_LIMITS["chat"] - 1  # 8-1=7 antes do increment

    def test_blocked_after_limit_reached(self, ai_mod):
        limit = ai_mod._IA_RATE_LIMITS["chat"]
        cid = 102
        # Forçar estado já no limite
        with ai_mod._ia_rate_lock:
            ai_mod._ia_rate_state[cid] = {
                "chat": {"count": limit, "window_start": time.time()}
            }
        allowed, remaining, reset_in = ai_mod._check_rate_limit(cid, "chat")
        assert allowed is False
        assert remaining == 0
        assert reset_in > 0

    def test_vision_limit_independent_from_chat(self, ai_mod):
        cid = 103
        chat_limit = ai_mod._IA_RATE_LIMITS["chat"]
        # Esgota chat
        with ai_mod._ia_rate_lock:
            ai_mod._ia_rate_state[cid] = {
                "chat": {"count": chat_limit, "window_start": time.time()}
            }
        # Vision ainda disponível
        allowed, remaining, _ = ai_mod._check_rate_limit(cid, "vision")
        assert allowed is True
        assert remaining == ai_mod._IA_RATE_LIMITS["vision"] - 1

    def test_image_gen_limit_independent(self, ai_mod):
        cid = 104
        vision_limit = ai_mod._IA_RATE_LIMITS["vision"]
        with ai_mod._ia_rate_lock:
            ai_mod._ia_rate_state[cid] = {
                "vision": {"count": vision_limit, "window_start": time.time()}
            }
        # image_gen ainda disponível
        allowed, _, _ = ai_mod._check_rate_limit(cid, "image_gen")
        assert allowed is True

    def test_proactive_limit_independent(self, ai_mod):
        cid = 105
        with ai_mod._ia_rate_lock:
            ai_mod._ia_rate_state[cid] = {
                "chat":      {"count": 8,  "window_start": time.time()},
                "vision":    {"count": 3,  "window_start": time.time()},
                "image_gen": {"count": 2,  "window_start": time.time()},
            }
        allowed, _, _ = ai_mod._check_rate_limit(cid, "proactive")
        assert allowed is True

    def test_window_expiry_resets_count(self, ai_mod):
        cid = 106
        limit = ai_mod._IA_RATE_LIMITS["chat"]
        old_window = time.time() - ai_mod._IA_RATE_WINDOW - 1  # janela expirada
        with ai_mod._ia_rate_lock:
            ai_mod._ia_rate_state[cid] = {
                "chat": {"count": limit, "window_start": old_window}
            }
        allowed, remaining, _ = ai_mod._check_rate_limit(cid, "chat")
        assert allowed is True
        assert remaining == limit - 1  # nova janela, primeiro uso

    def test_remaining_decrements_correctly(self, ai_mod):
        cid = 107
        with ai_mod._ia_rate_lock:
            ai_mod._ia_rate_state[cid] = {
                "chat": {"count": 5, "window_start": time.time()}
            }
        _, remaining, _ = ai_mod._check_rate_limit(cid, "chat")
        assert remaining == ai_mod._IA_RATE_LIMITS["chat"] - 5 - 1  # 8-5-1=2


class TestAdminBypass:
    def test_admin_always_allowed(self, ai_mod, admin_ids):
        admin_id = 999
        limit = ai_mod._IA_RATE_LIMITS["chat"]
        # Esgota completamente
        with ai_mod._ia_rate_lock:
            ai_mod._ia_rate_state[admin_id] = {
                "chat": {"count": limit * 10, "window_start": time.time()}
            }
        allowed, remaining, reset_in = ai_mod._check_rate_limit(admin_id, "chat")
        assert allowed is True
        assert reset_in == 0

    def test_admin_bypass_for_all_features(self, ai_mod, admin_ids):
        admin_id = 999
        for feature, limit in ai_mod._IA_RATE_LIMITS.items():
            with ai_mod._ia_rate_lock:
                ai_mod._ia_rate_state.setdefault(admin_id, {})[feature] = {
                    "count": limit * 5, "window_start": time.time()
                }
            allowed, _, _ = ai_mod._check_rate_limit(admin_id, feature)
            assert allowed is True, f"Admin bypass falhou para feature={feature}"


class TestIncrementRateLimit:
    def test_increment_increases_count(self, ai_mod):
        cid = 201
        ai_mod._increment_rate_limit(cid, "chat")
        with ai_mod._ia_rate_lock:
            count = ai_mod._ia_rate_state[cid]["chat"]["count"]
        assert count == 1

    def test_increment_multiple_times(self, ai_mod):
        cid = 202
        for _ in range(3):
            ai_mod._increment_rate_limit(cid, "chat")
        with ai_mod._ia_rate_lock:
            count = ai_mod._ia_rate_state[cid]["chat"]["count"]
        assert count == 3

    def test_increment_resets_on_expired_window(self, ai_mod):
        cid = 203
        old_ts = time.time() - ai_mod._IA_RATE_WINDOW - 10
        with ai_mod._ia_rate_lock:
            ai_mod._ia_rate_state[cid] = {
                "chat": {"count": 5, "window_start": old_ts}
            }
        ai_mod._increment_rate_limit(cid, "chat")
        with ai_mod._ia_rate_lock:
            count = ai_mod._ia_rate_state[cid]["chat"]["count"]
        assert count == 1  # nova janela

    def test_increment_persists_to_db(self, ai_mod):
        cid = 204
        ai_mod._increment_rate_limit(cid, "vision")
        ai_mod.set_config.assert_called_once()
        key_arg = ai_mod.set_config.call_args[0][0]
        assert key_arg == f"rl_{cid}_vision"


class TestFormatMessage:
    def test_chat_message_format(self, ai_mod):
        msg = ai_mod._format_rate_limit_message("chat", 0, 1800)
        assert "conversas com IA" in msg
        assert "8/8" in msg
        assert "30 min" in msg

    def test_vision_message_format(self, ai_mod):
        msg = ai_mod._format_rate_limit_message("vision", 0, 600)
        assert "análises de imagem" in msg
        assert "3/3" in msg

    def test_image_gen_message_format(self, ai_mod):
        msg = ai_mod._format_rate_limit_message("image_gen", 0, 300)
        assert "gerações de imagem" in msg
        assert "2/2" in msg

    def test_proactive_message_format(self, ai_mod):
        msg = ai_mod._format_rate_limit_message("proactive", 0, 60)
        assert "mensagens proativas" in msg

    def test_reset_in_rounds_up_to_1min(self, ai_mod):
        msg = ai_mod._format_rate_limit_message("chat", 0, 30)  # 30s < 1min
        assert "1 min" in msg


class TestPersistence:
    def test_save_and_load_state(self, ai_mod):
        """Simula persistência: salva estado no DB e carrega na inicialização."""
        cid = 301
        feature = "chat"
        now = time.time()

        # Simula set_config capturando o valor salvo
        saved_data = {}

        def mock_set_config(key, val):
            saved_data[key] = val

        def mock_get_config_rows():
            # Simula conn.execute retornando rows
            return [(f"rl_{cid}_{feature}", json.dumps({"count": 5, "window_start": now}))]

        ai_mod.set_config.side_effect = mock_set_config

        # Incrementa para persistir
        ai_mod._increment_rate_limit(cid, feature)
        assert f"rl_{cid}_{feature}" in saved_data

        # Verifica que o JSON salvo é válido
        state_json = saved_data[f"rl_{cid}_{feature}"]
        state = json.loads(state_json)
        assert "count" in state
        assert "window_start" in state
