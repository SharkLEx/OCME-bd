# ==============================================================================
# monitor_core/sentinela.py — Alertas automáticos proativos
# OCME bd Monitor Engine — Story 7.2
#
# Escuta eventos do Vigia e dispara alertas para:
#   - Inatividade prolongada (sigma histórico + % fallback)
#   - Gas GWEI alto
#   - Saldo de gas POL baixo
#   - Backlog de blocos
# ==============================================================================
from __future__ import annotations

import logging
import sqlite3
import time
import threading
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Any, Callable

from monitor_db.queries import config_get, config_set, ops_last_inactivity_minutes

logger = logging.getLogger('monitor.core.sentinela')


class Sentinela:
    '''Monitora métricas e emite alertas proativos.'''

    def __init__(
        self,
        vigia: Any,              # Vigia instance
        fetcher: Any,            # BlockFetcher
        conn: sqlite3.Connection,
        limite_gwei: float = 1000.0,
        limite_gas_pol: float = 2.0,
        limite_inativ_min: float = 30.0,
        check_interval_s: float = 60.0,
    ):
        self._vigia = vigia
        self._fetcher = fetcher
        self._conn = conn
        self._limite_gwei = limite_gwei
        self._limite_gas_pol = limite_gas_pol
        self._limite_inativ = limite_inativ_min
        self._interval = check_interval_s
        self._running = False
        self._thread: threading.Thread | None = None
        self._alert_callbacks: list[Callable[[str, dict], None]] = []

        # Subscreve eventos do Vigia
        vigia.on('backlog', self._on_backlog)

    def on_alert(self, callback: Callable[[str, dict], None]) -> None:
        '''Registra callback para alertas. Assinatura: callback(tipo, dados)'''
        self._alert_callbacks.append(callback)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name='sentinela')
        self._thread.start()
        logger.info('Sentinela iniciado (interval: %.0fs)', self._interval)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info('Sentinela parado')

    # ── Loop de verificação ───────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            try:
                self._check_gas_gwei()
                self._check_gas_pol()
                self._check_global_inactivity()
            except Exception as exc:
                logger.warning('Sentinela check error: %s', exc)
            time.sleep(self._interval)

    # ── Checks individuais ────────────────────────────────────────────────────

    def _check_gas_gwei(self) -> None:
        try:
            gwei = self._fetcher.get_gas_price_gwei()
            if gwei > self._limite_gwei:
                cooldown_key = 'sentinela_alert_gwei_ts'
                last = float(config_get(self._conn, cooldown_key, '0') or 0)
                if time.time() - last > 1800:  # 30 min cooldown
                    self._fire('gas_gwei_alto', {
                        'gwei': gwei,
                        'limite': self._limite_gwei,
                        'msg': f'⚠️ Gas ALTO: {gwei:.0f} GWEI (limite: {self._limite_gwei:.0f})',
                    })
                    config_set(self._conn, cooldown_key, str(time.time()))
        except Exception as exc:
            logger.debug('check_gas_gwei: %s', exc)

    def _check_gas_pol(self) -> None:
        '''Verifica saldo de gas POL em managers (via DB de usuários ativos).'''
        try:
            rows = self._conn.execute(
                "SELECT DISTINCT wallet FROM users WHERE active=1 AND wallet IS NOT NULL AND wallet != ''"
            ).fetchall()
            for (wallet,) in rows[:10]:  # limita a 10 wallets por ciclo
                bal = self._fetcher.get_pol_balance(wallet)
                if 0 < bal < self._limite_gas_pol:
                    self._fire('gas_pol_baixo', {
                        'wallet': wallet,
                        'balance_pol': bal,
                        'limite': self._limite_gas_pol,
                        'msg': f'⚠️ Gas POL baixo: {bal:.3f} POL (limite: {self._limite_gas_pol})',
                    })
        except Exception as exc:
            logger.debug('check_gas_pol: %s', exc)

    def _check_global_inactivity(self) -> None:
        '''Detecta inatividade global usando sigma histórico.'''
        try:
            since = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            row = self._conn.execute(
                "SELECT MAX(data_hora) FROM operacoes WHERE tipo='Trade' AND data_hora >= ?",
                (since,)
            ).fetchone()
            last_dt_str = row[0] if row and row[0] else None
            if not last_dt_str:
                return

            last_dt = datetime.strptime(last_dt_str, '%Y-%m-%d %H:%M:%S')
            minutes_since = (datetime.now() - last_dt).total_seconds() / 60

            if minutes_since < self._limite_inativ:
                return

            # Sigma histórico
            sigma, msg_extra = self._calc_sigma(minutes_since)

            cooldown_key = 'sentinela_alert_inativ_global_ts'
            last_alert = float(config_get(self._conn, cooldown_key, '0') or 0)
            if time.time() - last_alert < 1800:
                return

            self._fire('inatividade_global', {
                'minutes': minutes_since,
                'limite': self._limite_inativ,
                'sigma': sigma,
                'last_trade': last_dt_str,
                'msg': (
                    f'⏳ INATIVIDADE GLOBAL: {minutes_since:.0f} min sem trades '
                    f'({sigma:.1f}σ acima da média). {msg_extra}'
                ),
            })
            config_set(self._conn, cooldown_key, str(time.time()))

        except Exception as exc:
            logger.debug('check_global_inactivity: %s', exc)

    def _calc_sigma(self, current_minutes: float) -> tuple[float, str]:
        '''Calcula desvio padrão histórico de intervalos entre trades.'''
        try:
            window = int(config_get(self._conn, 'inactivity_hist_window', '120') or 120)
            rows = self._conn.execute('''
                SELECT data_hora FROM operacoes
                WHERE tipo='Trade'
                ORDER BY data_hora DESC
                LIMIT ?
            ''', (window,)).fetchall()

            if len(rows) < 10:
                return 0.0, ''

            dts = [datetime.strptime(r[0], '%Y-%m-%d %H:%M:%S') for r in rows]
            gaps = [(dts[i] - dts[i+1]).total_seconds() / 60 for i in range(len(dts) - 1)]

            avg = mean(gaps)
            std = stdev(gaps) if len(gaps) > 1 else 1.0
            sigma = (current_minutes - avg) / std if std > 0 else 0.0
            return sigma, f'Média histórica: {avg:.0f} min'
        except Exception:
            return 0.0, ''

    def _on_backlog(self, data: dict) -> None:
        lag = (data or {}).get('lag', 0)
        if lag > 50:
            self._fire('backlog_critico', {
                'lag': lag,
                'msg': f'🔴 BACKLOG: {lag} blocos de atraso',
            })

    def _fire(self, tipo: str, dados: dict) -> None:
        logger.info('ALERTA [%s]: %s', tipo, dados.get('msg', ''))
        for cb in self._alert_callbacks:
            try:
                cb(tipo, dados)
            except Exception as exc:
                logger.warning('Alert callback error: %s', exc)
