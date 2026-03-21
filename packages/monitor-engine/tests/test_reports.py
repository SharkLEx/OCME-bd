"""
test_reports.py — Testes para relatórios e formatação (Story 16.3 AC3)

Nota: reports.py não existe — funções de relatório estão em:
- webdex_db.py: _ciclo_21h_since, _ciclo_21h_label, period_to_hours
- webdex_bot_core.py: formatar_moeda, barra_progresso
- webdex_monitor.py: _profit_emoji, _today_stats, HEALTH

Foco:
- Formato ciclo 21h (data/hora label)
- PnL formatação: positivo/negativo com emoji correto
- Graceful: DB vazio não quebra relatórios
- formatar_moeda: conversão por decimais
"""
from __future__ import annotations

import sys
import time
import unittest.mock as mock
from datetime import datetime, timezone, timedelta

import pytest


def _real_wbc(monkeypatch):
    """Remove o mock de webdex_bot_core e importa o módulo real."""
    monkeypatch.delitem(sys.modules, 'webdex_bot_core', raising=False)
    import webdex_bot_core as _wbc
    # O .env real tem IDs diferentes — normaliza para testes
    monkeypatch.setattr(_wbc, 'ADMIN_USER_IDS', [123456789])
    return _wbc


def _patch_db(db_conn, monkeypatch):
    import webdex_db
    monkeypatch.setattr(webdex_db, 'conn', db_conn)
    monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
    return webdex_db


def _patch_monitor(db_conn, monkeypatch):
    import webdex_monitor
    import webdex_db
    monkeypatch.setattr(webdex_db, 'conn', db_conn)
    monkeypatch.setattr(webdex_db, 'cursor', db_conn.cursor())
    monkeypatch.setattr(webdex_monitor, 'conn', db_conn)
    monkeypatch.setattr(webdex_monitor, 'cursor', db_conn.cursor())
    return webdex_monitor


# ==============================================================================
# 1. Ciclo 21h — formato de data/hora
# ==============================================================================

class TestCiclo21hFormat:

    def test_ciclo_label_is_string(self, db_conn, monkeypatch):
        """_ciclo_21h_label retorna string (não crasha)."""
        wdb = _patch_db(db_conn, monkeypatch)
        label = wdb._ciclo_21h_label()
        assert isinstance(label, str)

    def test_ciclo_since_is_string(self, db_conn, monkeypatch):
        """_ciclo_21h_since retorna string não vazia."""
        wdb = _patch_db(db_conn, monkeypatch)
        since = wdb._ciclo_21h_since()
        assert isinstance(since, str)
        assert len(since) > 0

    def test_ciclo_label_contains_hour_info(self, db_conn, monkeypatch):
        """Label do ciclo contém referência de hora (21h ou timestamp)."""
        wdb = _patch_db(db_conn, monkeypatch)
        label = wdb._ciclo_21h_label()
        # Label deve conter algum indicador de tempo
        assert any(c.isdigit() for c in label), f'Label sem dígito: {label}'


# ==============================================================================
# 2. PnL — formatação positivo/negativo
# ==============================================================================

class TestPnlFormatting:

    def test_profit_emoji_positive_large(self, db_conn, monkeypatch):
        """Lucro >= 10 → 💰 (money bag)."""
        m = _patch_monitor(db_conn, monkeypatch)
        assert m._profit_emoji(10.0) == '💰'
        assert m._profit_emoji(50.0) == '💰'

    def test_profit_emoji_positive_small(self, db_conn, monkeypatch):
        """Lucro 0..9.99 → 🟢."""
        m = _patch_monitor(db_conn, monkeypatch)
        assert m._profit_emoji(0.0) == '🟢'
        assert m._profit_emoji(5.5) == '🟢'
        assert m._profit_emoji(9.99) == '🟢'

    def test_profit_emoji_small_loss(self, db_conn, monkeypatch):
        """Perda -0.01..-2.0 → 🔴."""
        m = _patch_monitor(db_conn, monkeypatch)
        assert m._profit_emoji(-0.01) == '🔴'
        assert m._profit_emoji(-2.0) == '🔴'

    def test_profit_emoji_large_loss(self, db_conn, monkeypatch):
        """Perda < -2 → 🚨 (alarme)."""
        m = _patch_monitor(db_conn, monkeypatch)
        assert m._profit_emoji(-2.01) == '🚨'
        assert m._profit_emoji(-100.0) == '🚨'

    def test_profit_emoji_zero_is_green(self, db_conn, monkeypatch):
        """Zero é resultado neutro → 🟢."""
        m = _patch_monitor(db_conn, monkeypatch)
        assert m._profit_emoji(0) == '🟢'


# ==============================================================================
# 3. Relatórios sem dados — graceful degradation
# ==============================================================================

class TestEmptyHistoryGraceful:

    def test_today_stats_empty_db_no_crash(self, db_conn, monkeypatch):
        """_today_stats com DB vazio não crasha, retorna (0, 0.0)."""
        m = _patch_monitor(db_conn, monkeypatch)
        try:
            trades, pnl = m._today_stats(99999)
        except Exception as e:
            pytest.fail(f'_today_stats lançou exceção com DB vazio: {e}')
        assert trades == 0
        assert pnl == 0.0

    def test_today_wins_empty_db_no_crash(self, db_conn, monkeypatch):
        """_today_wins com DB vazio retorna 0."""
        m = _patch_monitor(db_conn, monkeypatch)
        result = m._today_wins(99999)
        assert result == 0

    def test_today_streak_empty_db_no_crash(self, db_conn, monkeypatch):
        """_today_streak com DB vazio retorna 0."""
        m = _patch_monitor(db_conn, monkeypatch)
        result = m._today_streak(99999)
        assert result == 0

    def test_health_dict_accessible_always(self, db_conn, monkeypatch):
        """HEALTH dict sempre acessível (não None)."""
        m = _patch_monitor(db_conn, monkeypatch)
        assert m.HEALTH is not None
        assert isinstance(m.HEALTH, dict)


# ==============================================================================
# 4. formatar_moeda — conversão por decimais
# ==============================================================================

class TestFormatarMoeda:

    def test_formatar_moeda_usdt_6_decimals(self, monkeypatch):
        """USDT com 6 decimais: 1000000 → 1.0."""
        wbc = _real_wbc(monkeypatch)
        result = wbc.formatar_moeda(1_000_000, 6)
        assert abs(result - 1.0) < 1e-6

    def test_formatar_moeda_18_decimals(self, monkeypatch):
        """Token com 18 decimais: 1e18 → 1.0."""
        wbc = _real_wbc(monkeypatch)
        result = wbc.formatar_moeda(10**18, 18)
        assert abs(result - 1.0) < 1e-6

    def test_formatar_moeda_zero_returns_zero(self, monkeypatch):
        """0 wei → 0.0."""
        wbc = _real_wbc(monkeypatch)
        result = wbc.formatar_moeda(0, 18)
        assert result == 0.0

    def test_formatar_moeda_invalid_returns_zero(self, monkeypatch):
        """Valor inválido (None/string) → 0.0 sem crash."""
        wbc = _real_wbc(monkeypatch)
        try:
            result = wbc.formatar_moeda(None, 18)
        except Exception as e:
            pytest.fail(f'formatar_moeda não deveria crashar com None: {e}')
        assert result == 0.0


# ==============================================================================
# 5. period_to_hours — conversão período → horas
# ==============================================================================

class TestPeriodConversion:

    def test_24h_returns_24(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.period_to_hours('24h') == 24

    def test_7d_returns_168(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.period_to_hours('7d') == 168

    def test_30d_returns_720(self, db_conn, monkeypatch):
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.period_to_hours('30d') == 720

    def test_unknown_period_returns_24(self, db_conn, monkeypatch):
        """Período desconhecido → default 24h."""
        wdb = _patch_db(db_conn, monkeypatch)
        assert wdb.period_to_hours('abc') == 24
