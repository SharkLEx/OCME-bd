"""
test_webdex_monitor.py — Testes para webdex_monitor.py (Story 16.1 AC4)

Foco:
- _profit_emoji: função pura, sem dependências
- registrar_operacao: idempotência (INSERT OR IGNORE — não insere duplicatas)
- _clean_tx_cache: limpeza por TTL
- _get_tx_and_receipt_safely: cache hit/miss
- HEALTH dict: estrutura obrigatória
- Graceful degradation: _today_stats/_today_wins/_today_streak retornam defaults em erro
"""
from __future__ import annotations

import time
import unittest.mock as mock

import pytest


# ==============================================================================
# Setup: patch conn/cursor do webdex_monitor para usar db_conn do teste
# ==============================================================================

def _patch_monitor(db_conn, monkeypatch):
    """
    webdex_monitor importa conn/cursor de webdex_db no nível do módulo.
    Patch direto no módulo webdex_monitor.
    """
    import webdex_monitor
    import webdex_db

    monkeypatch.setattr(webdex_db, 'conn', db_conn)
    monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
    monkeypatch.setattr(webdex_monitor, 'conn', db_conn)
    monkeypatch.setattr(webdex_monitor, 'cursor', db_conn.cursor())
    return webdex_monitor


# ==============================================================================
# Schema extra para operacoes (monitor usa campos adicionais)
# ==============================================================================

def _ensure_operacoes_full(db_conn):
    """Garante que operacoes tem todas as colunas que webdex_monitor usa."""
    cols = {r[1] for r in db_conn.execute('PRAGMA table_info(operacoes)').fetchall()}
    extra = {
        'hash': 'TEXT',
        'data_hora': 'TEXT',
        'valor': 'REAL',
        'gas_usd': 'REAL',
        'token': 'TEXT',
        'sub_conta': 'TEXT',
        'fee': 'REAL',
        'strategy_addr': 'TEXT',
        'bot_id': 'TEXT',
        'gas_protocol': 'REAL',
        'old_balance_usd': 'REAL',
    }
    for col, typ in extra.items():
        if col not in cols:
            try:
                db_conn.execute(f'ALTER TABLE operacoes ADD COLUMN {col} {typ}')
            except Exception:
                pass
    db_conn.commit()


# ==============================================================================
# 1. _profit_emoji — função pura
# ==============================================================================

class TestProfitEmoji:

    def test_large_profit_returns_money_bag(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        assert m._profit_emoji(10.0) == '💰'
        assert m._profit_emoji(100.0) == '💰'
        assert m._profit_emoji(10.0001) == '💰'

    def test_small_profit_returns_green(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        assert m._profit_emoji(0.0) == '🟢'
        assert m._profit_emoji(5.0) == '🟢'
        assert m._profit_emoji(9.99) == '🟢'

    def test_small_loss_returns_red(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        assert m._profit_emoji(-1.0) == '🔴'
        assert m._profit_emoji(-2.0) == '🔴'

    def test_large_loss_returns_alarm(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        assert m._profit_emoji(-2.01) == '🚨'
        assert m._profit_emoji(-100.0) == '🚨'

    def test_zero_is_green(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        assert m._profit_emoji(0) == '🟢'


# ==============================================================================
# 2. HEALTH dict — estrutura obrigatória
# ==============================================================================

class TestHealthDict:

    def test_health_has_required_keys(self, db_conn, monkeypatch):
        """HEALTH deve ter campos que alimentam o dashboard de observabilidade."""
        m = _patch_monitor(db_conn, monkeypatch)
        required = {
            'started_at', 'last_block_seen', 'last_fetch_ok_ts',
            'vigia_loops', 'logs_trade', 'logs_transfer',
            'last_error', 'blocks_processed', 'capture_rate'
        }
        assert required.issubset(m.HEALTH.keys())

    def test_health_capture_rate_starts_at_100(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        assert m.HEALTH['capture_rate'] == 100.0

    def test_health_started_at_is_recent(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        # started_at deve ser um timestamp recente (últimas 24h)
        assert abs(time.time() - m.HEALTH['started_at']) < 86400


# ==============================================================================
# 3. registrar_operacao — idempotência crítica
# ==============================================================================

class TestRegistrarOperacao:

    def _setup(self, db_conn):
        _ensure_operacoes_full(db_conn)

    def test_registrar_operacao_returns_true_on_first_insert(self, db_conn, monkeypatch):
        self._setup(db_conn)
        m = _patch_monitor(db_conn, monkeypatch)
        result = m.registrar_operacao(
            tx_hash='0xabc123', log_index=0, tipo='Trade',
            valor=1.5, gas_usd=0.01, token='USDT',
            sub_id='sub1', bloco=100000,
            owner_wallet='0xowner', ambiente='AG_C_bd'
        )
        assert result is True

    def test_registrar_operacao_idempotent_same_tx(self, db_conn, monkeypatch):
        """Mesmo tx_hash + log_index → segunda inserção retorna False (não duplica)."""
        self._setup(db_conn)
        m = _patch_monitor(db_conn, monkeypatch)
        m.registrar_operacao(
            tx_hash='0xdeadbeef', log_index=0, tipo='Trade',
            valor=2.0, gas_usd=0.02, token='USDT',
            sub_id='sub1', bloco=100001,
            owner_wallet='0xowner'
        )
        result_duplicate = m.registrar_operacao(
            tx_hash='0xdeadbeef', log_index=0, tipo='Trade',
            valor=2.0, gas_usd=0.02, token='USDT',
            sub_id='sub1', bloco=100001,
            owner_wallet='0xowner'
        )
        assert result_duplicate is False

    def test_registrar_operacao_different_log_index_allowed(self, db_conn, monkeypatch):
        """Mesmo tx_hash mas log_index diferente → deve inserir (evento diferente)."""
        self._setup(db_conn)
        m = _patch_monitor(db_conn, monkeypatch)
        r1 = m.registrar_operacao(
            tx_hash='0xmultilog', log_index=0, tipo='Trade',
            valor=1.0, gas_usd=0.01, token='USDT',
            sub_id='sub1', bloco=100002, owner_wallet='0xowner'
        )
        r2 = m.registrar_operacao(
            tx_hash='0xmultilog', log_index=1, tipo='Trade',
            valor=1.0, gas_usd=0.01, token='USDT',
            sub_id='sub1', bloco=100002, owner_wallet='0xowner'
        )
        assert r1 is True
        assert r2 is True

    def test_registrar_operacao_normalizes_txhash(self, db_conn, monkeypatch):
        """tx_hash sem 0x deve ser normalizado para 0x + lowercase."""
        self._setup(db_conn)
        m = _patch_monitor(db_conn, monkeypatch)
        # Insere sem 0x
        m.registrar_operacao(
            tx_hash='ABCDEF1234', log_index=0, tipo='Trade',
            valor=1.0, gas_usd=0.01, token='USDT',
            sub_id='sub1', bloco=100003, owner_wallet='0xowner'
        )
        # Tenta inserir com 0x + lowercase (mesmo hash normalizado)
        result = m.registrar_operacao(
            tx_hash='0xabcdef1234', log_index=0, tipo='Trade',
            valor=1.0, gas_usd=0.01, token='USDT',
            sub_id='sub1', bloco=100003, owner_wallet='0xowner'
        )
        assert result is False  # duplicata detectada


# ==============================================================================
# 4. _clean_tx_cache — limpeza por TTL
# ==============================================================================

class TestCleanTxCache:

    def test_clean_removes_expired_entries(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        # Injeta entrada expirada no cache
        m._TX_CACHE_TS['0xold_tx'] = time.time() - m._TX_CACHE_TTL - 10
        m._TX_CACHE_TS['0xnew_tx'] = time.time()

        m._clean_tx_cache()

        assert '0xold_tx' not in m._TX_CACHE_TS
        assert '0xnew_tx' in m._TX_CACHE_TS

    def test_clean_keeps_fresh_entries(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        m._TX_CACHE_TS['0xfresh'] = time.time() - 10  # 10s atrás, bem dentro do TTL

        m._clean_tx_cache()

        assert '0xfresh' in m._TX_CACHE_TS

    def test_clean_empty_cache_no_crash(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        m._TX_CACHE_TS.clear()
        try:
            m._clean_tx_cache()
        except Exception as e:
            pytest.fail(f'_clean_tx_cache falhou com cache vazio: {e}')


# ==============================================================================
# 5. _get_tx_and_receipt_safely — cache hit/miss
# ==============================================================================

class TestGetTxReceiptSafely:

    def test_cached_tx_returns_none_none(self, db_conn, monkeypatch):
        """TX recém-vista (< 60s) → retorna (None, None) para evitar re-fetch."""
        m = _patch_monitor(db_conn, monkeypatch)
        m._TX_CACHE_TS['0xcached'] = time.time() - 5  # 5s atrás
        tx, receipt = m._get_tx_and_receipt_safely('0xcached')
        assert tx is None
        assert receipt is None

    def test_uncached_tx_attempts_fetch(self, db_conn, monkeypatch):
        """TX nova → tenta buscar via web3 (mockado)."""
        m = _patch_monitor(db_conn, monkeypatch)
        m._TX_CACHE_TS.pop('0xnew_uncached', None)

        # web3 mockado retorna None (falha silenciosa)
        m.web3 = mock.MagicMock()
        m.web3.eth.get_transaction.return_value = None
        m.web3.eth.get_transaction_receipt.return_value = None

        tx, receipt = m._get_tx_and_receipt_safely('0xnew_uncached')
        # Após chamada, TX deve estar no cache
        assert '0xnew_uncached' in m._TX_CACHE_TS


# ==============================================================================
# 6. Graceful degradation — stats retornam defaults em DB vazio
# ==============================================================================

class TestGracefulDegradation:

    def test_today_stats_returns_zero_on_empty_db(self, db_conn, monkeypatch):
        """_today_stats não deve lançar exceção com DB vazio."""
        m = _patch_monitor(db_conn, monkeypatch)
        trades, pnl = m._today_stats(999999)
        assert trades == 0
        assert pnl == 0.0

    def test_today_wins_returns_zero_on_empty_db(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        result = m._today_wins(999999)
        assert result == 0

    def test_today_streak_returns_zero_on_empty_db(self, db_conn, monkeypatch):
        m = _patch_monitor(db_conn, monkeypatch)
        result = m._today_streak(999999)
        assert result == 0

    def test_monitor_resilience_on_db_error(self, db_conn, monkeypatch):
        """Se cursor falhar, funções de stats devem retornar default (não crashar worker)."""
        m = _patch_monitor(db_conn, monkeypatch)
        bad_cursor = mock.MagicMock()
        bad_cursor.execute.side_effect = Exception('DB error simulado')
        monkeypatch.setattr(m, 'cursor', bad_cursor)

        # Nenhuma dessas deve lançar exceção
        trades, pnl = m._today_stats(123)
        wins = m._today_wins(123)
        streak = m._today_streak(123)

        assert trades == 0
        assert pnl == 0.0
        assert wins == 0
        assert streak == 0
