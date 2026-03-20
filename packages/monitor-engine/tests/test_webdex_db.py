"""
test_webdex_db.py — Testes para webdex_db.py (Story 16.1 AC2)

Testa funções puras e funções de banco usando db_conn fixture (SQLite :memory:).
Estratégia: patch webdex_db.conn e webdex_db.cursor para usar db_conn fixture.
"""
from __future__ import annotations

import sqlite3
import threading
import unittest.mock as mock
from datetime import datetime

import pytest


# ==============================================================================
# Helpers de patch — injeta db_conn no módulo webdex_db
# ==============================================================================

def _patch_db(db_conn, monkeypatch):
    """Redireciona conn/cursor do módulo webdex_db para o db_conn do teste."""
    import webdex_db
    monkeypatch.setattr(webdex_db, 'conn', db_conn)
    monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
    return webdex_db


# ==============================================================================
# 1. get_config / set_config
# ==============================================================================

class TestGetSetConfig:

    def test_get_config_returns_default_when_missing(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        result = wdb.get_config('chave_inexistente', 'valor_padrao')
        assert result == 'valor_padrao'

    def test_set_and_get_config(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('test_key', 'test_value')
        result = wdb.get_config('test_key')
        assert result == 'test_value'

    def test_set_config_overwrites_existing(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('key', 'valor1')
        wdb.set_config('key', 'valor2')
        assert wdb.get_config('key') == 'valor2'

    def test_get_config_returns_empty_string_by_default(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        result = wdb.get_config('nao_existe')
        assert result == ''

    def test_set_config_accepts_numeric_string(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('numero', '42')
        assert wdb.get_config('numero') == '42'


# ==============================================================================
# 2. ai_global_enabled / ai_admin_only / ai_mode
# ==============================================================================

class TestAiConfigFlags:

    def test_ai_global_enabled_default_true(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        # Sem config → padrão é '1' → True
        assert wdb.ai_global_enabled() is True

    def test_ai_global_enabled_false_when_set_to_zero(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_global_enabled', '0')
        assert wdb.ai_global_enabled() is False

    def test_ai_admin_only_default_false(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.ai_admin_only() is False

    def test_ai_admin_only_true_when_set(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_admin_only', '1')
        assert wdb.ai_admin_only() is True

    def test_ai_mode_defaults_to_community(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.ai_mode() == 'community'

    def test_ai_mode_dev_when_set(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_mode', 'dev')
        assert wdb.ai_mode() == 'dev'

    def test_ai_mode_developer_alias(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.set_config('ai_mode', 'developer')
        assert wdb.ai_mode() == 'dev'


# ==============================================================================
# 3. upsert_user / get_user
# ==============================================================================

class TestUserCRUD:

    def test_get_user_returns_none_when_not_found(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        result = wdb.get_user(999999)
        assert result is None

    def test_upsert_creates_new_user(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(12345, wallet='0xabc', env='AG_C_bd')
        user = wdb.get_user(12345)
        assert user is not None
        assert user['chat_id'] == 12345
        assert user['wallet'] == '0xabc'
        assert user['env'] == 'AG_C_bd'

    def test_upsert_updates_existing_user(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(12345, wallet='0xoriginal')
        wdb.upsert_user(12345, wallet='0xatualizada')
        user = wdb.get_user(12345)
        assert user['wallet'] == '0xatualizada'

    def test_upsert_wallet_stored_lowercase(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(12345, wallet='0xABCDEF')
        user = wdb.get_user(12345)
        assert user['wallet'] == '0xabcdef'

    def test_upsert_preserves_other_fields_on_partial_update(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(12345, wallet='0xabc', periodo='7d', active=1)
        wdb.upsert_user(12345, env='bd_v5')  # só atualiza env
        user = wdb.get_user(12345)
        assert user['periodo'] == '7d'
        assert user['active'] == 1
        assert user['env'] == 'bd_v5'

    def test_get_user_returns_expected_keys(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(12345)
        user = wdb.get_user(12345)
        expected_keys = {'chat_id', 'wallet', 'rpc', 'env', 'active', 'periodo', 'pending', 'sub_filter'}
        assert expected_keys.issubset(user.keys())


# ==============================================================================
# 4. get_connected_users
# ==============================================================================

class TestConnectedUsers:

    def test_get_connected_users_empty(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        result = wdb.get_connected_users()
        assert result == []

    def test_get_connected_users_returns_users_with_wallet(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(111, wallet='0xabc')
        wdb.upsert_user(222, wallet='')  # sem wallet — não deve aparecer
        wdb.upsert_user(333, wallet='0xdef')
        result = wdb.get_connected_users()
        assert 111 in result
        assert 333 in result
        assert 222 not in result

    def test_get_connected_users_returns_list_of_ints(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        wdb.upsert_user(555, wallet='0x123')
        result = wdb.get_connected_users()
        assert all(isinstance(x, int) for x in result)


# ==============================================================================
# 5. normalize_txhash / period_to_hours
# ==============================================================================

class TestPureFunctions:

    def test_normalize_txhash_lowercase(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.normalize_txhash('0xABCDEF') == '0xabcdef'

    def test_normalize_txhash_strips_spaces(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        result = wdb.normalize_txhash('  0xabc  ')
        assert result == '0xabc'

    def test_normalize_txhash_empty(self, db_conn, monkeypatch):
        """normalize_txhash('') → '0x' (comportamento real: sempre adiciona prefixo)."""
        wdb = _patch_db(db_conn, monkeypatch)
        result = wdb.normalize_txhash('')
        assert result == '0x'

    def test_period_to_hours_24h(self, db_conn, monkeypatch):
        """'24h' não é um caso especial — cai no default=24."""
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.period_to_hours('24h') == 24

    def test_period_to_hours_7d(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.period_to_hours('7d') == 168

    def test_period_to_hours_30d(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.period_to_hours('30d') == 720

    def test_period_to_hours_unknown_returns_24(self, db_conn, monkeypatch):
        """Período desconhecido (incluindo '1h') → default 24."""
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.period_to_hours('1h') == 24
        assert wdb.period_to_hours('qualquer') == 24

    def test_percentile_empty_list(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb._percentile([], 50) == 0.0

    def test_percentile_single_element(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb._percentile([42.0], 50) == 42.0

    def test_std_empty_list(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb._std([]) == 0.0


# ==============================================================================
# 6. Thread safety — DB_LOCK
# ==============================================================================

class TestThreadSafety:

    def test_concurrent_set_config_no_crash(self, db_conn, monkeypatch):
        """Múltiplas threads escrevendo config simultaneamente — sem deadlock/crash."""
        wdb = _patch_db(db_conn, monkeypatch)
        errors = []

        def write_config(i):
            try:
                wdb.set_config(f'key_{i}', str(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_config, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == [], f'Erros em threads: {errors}'

    def test_concurrent_upsert_user_no_crash(self, db_conn, monkeypatch):
        """Upsert de diferentes chat_ids em paralelo — sem race condition."""
        wdb = _patch_db(db_conn, monkeypatch)
        errors = []

        def upsert(chat_id):
            try:
                wdb.upsert_user(chat_id, wallet=f'0x{chat_id:040x}')
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=upsert, args=(i + 1000,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == [], f'Erros em threads: {errors}'
