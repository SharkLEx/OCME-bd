# ==============================================================================
# monitor_report/dashboard_cache.py — Cache pré-calculado de KPIs
# OCME bd Monitor Engine — Story 7.5
#
# DashboardCache é atualizado pelo Vigia a cada operação.
# Resposta < 500ms garantida — zero RPC no momento do clique.
# ==============================================================================
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger('monitor.report.cache')

_PERIOD_HOURS = {'24h': 24, '7d': 168, '30d': 720}


class DashboardCache:
    '''Cache de KPIs pré-calculados. Thread-safe. TTL configurável.'''

    def __init__(
        self,
        conn: sqlite3.Connection,
        vigia: Any | None = None,
        ttl_seconds: int = 15,
    ):
        self._conn = conn
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._cache: dict[str, dict] = {}  # key=f'{wallet}:{period}' → {data, ts}

        # Subscreve vigia para invalidação automática
        if vigia:
            vigia.on('operation', self._on_operation)

    def get(
        self,
        wallet: str | None = None,
        period: str = '24h',
        env: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        '''Retorna KPIs do cache ou recalcula se expirado.'''
        key = f'{wallet or "__global__"}:{period}:{env or "all"}'

        with self._lock:
            cached = self._cache.get(key)
            if cached and not force_refresh:
                age = time.time() - cached['ts']
                if age < self._ttl:
                    cached['data']['_cache_age_s'] = round(age, 1)
                    return cached['data']

        # Recalcula fora do lock
        data = self._compute(wallet, period, env)
        data['_cache_age_s'] = 0.0
        data['_computed_at'] = datetime.now().strftime('%H:%M:%S')

        with self._lock:
            self._cache[key] = {'data': data, 'ts': time.time()}

        return data

    def invalidate(self, wallet: str | None = None) -> None:
        '''Invalida cache de uma wallet (ou todo o cache se wallet=None).'''
        with self._lock:
            if wallet:
                prefix = f'{wallet}:'
                keys_to_del = [k for k in self._cache if k.startswith(prefix)]
                for k in keys_to_del:
                    del self._cache[k]
            else:
                self._cache.clear()
        logger.debug('Cache invalidado (wallet=%s)', wallet or 'all')

    def _on_operation(self, op: dict) -> None:
        '''Callback do Vigia — invalida cache da wallet afetada.'''
        wallet = (op or {}).get('user_wallet')
        self.invalidate(wallet)

    def _compute(
        self,
        wallet: str | None,
        period: str,
        env: str | None,
    ) -> dict[str, Any]:
        hours = _PERIOD_HOURS.get(period, 24)
        since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')

        env_clause   = 'AND o.ambiente = ?' if env else ''
        wallet_join  = 'JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index' if wallet else ''
        wallet_clause= 'AND LOWER(ow.wallet) = ?' if wallet else ''

        params: list[Any] = [since]
        if wallet:
            params.append(wallet.lower())
        if env:
            params.append(env)

        # KPIs principais
        try:
            row = self._conn.execute(f'''
                SELECT
                    COUNT(*)                       AS trades,
                    COALESCE(SUM(o.valor), 0)      AS profit_gross,
                    COALESCE(SUM(o.gas_usd), 0)    AS gas_total,
                    COALESCE(SUM(o.fee), 0)        AS fee_total,
                    COALESCE(AVG(o.gas_usd), 0)    AS gas_avg,
                    MIN(o.data_hora)               AS first_trade,
                    MAX(o.data_hora)               AS last_trade
                FROM operacoes o
                {wallet_join}
                WHERE o.data_hora >= ?
                  AND o.tipo = 'Trade'
                  {wallet_clause}
                  {env_clause}
            ''', params).fetchone() or (0, 0, 0, 0, 0, None, None)
        except Exception as exc:
            logger.error('_compute query falhou: %s', exc)
            row = (0, 0, 0, 0, 0, None, None)

        trades, gross, gas, fee, gas_avg, first_dt, last_dt = row
        profit_net = float((gross or 0) - (gas or 0) - (fee or 0))

        # Melhor subconta
        best_sub = self._best_subconta(since, wallet, env)

        # Inatividade desde último trade
        inactiv_min = 0.0
        if last_dt:
            try:
                dt = datetime.strptime(last_dt, '%Y-%m-%d %H:%M:%S')
                inactiv_min = (datetime.now() - dt).total_seconds() / 60
            except Exception:
                pass

        # Total de usuários ativos (apenas para global)
        active_wallets = 0
        if not wallet:
            try:
                active_wallets = self._conn.execute(
                    "SELECT COUNT(DISTINCT wallet) FROM op_owner ow "
                    "JOIN operacoes o ON o.hash=ow.hash AND o.log_index=ow.log_index "
                    f"WHERE o.data_hora >= ? AND o.tipo='Trade'",
                    (since,)
                ).fetchone()[0] or 0
            except Exception:
                pass

        return {
            'period':          period,
            'period_hours':    hours,
            'trades':          int(trades or 0),
            'profit_gross':    round(float(gross or 0), 2),
            'profit_net':      round(profit_net, 2),
            'gas_total':       round(float(gas or 0), 4),
            'gas_avg':         round(float(gas_avg or 0), 6),
            'fee_total':       round(float(fee or 0), 2),
            'first_trade_dt':  first_dt,
            'last_trade_dt':   last_dt,
            'inactivity_min':  round(inactiv_min, 1),
            'best_subconta':   best_sub,
            'active_wallets':  active_wallets,
            'env':             env or 'all',
        }

    def _best_subconta(self, since: str, wallet: str | None, env: str | None) -> dict | None:
        wallet_join   = 'JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index' if wallet else ''
        wallet_clause = 'AND LOWER(ow.wallet) = ?' if wallet else ''
        env_clause    = 'AND o.ambiente = ?' if env else ''

        params: list[Any] = [since]
        if wallet:
            params.append(wallet.lower())
        if env:
            params.append(env)

        try:
            row = self._conn.execute(f'''
                SELECT o.sub_conta, SUM(o.valor) as lucro, COUNT(*) as trades
                FROM operacoes o
                {wallet_join}
                WHERE o.data_hora >= ?
                  AND o.tipo = 'Trade'
                  {wallet_clause}
                  {env_clause}
                GROUP BY o.sub_conta
                ORDER BY lucro DESC
                LIMIT 1
            ''', params).fetchone()
        except Exception:
            return None

        if not row:
            return None
        return {'id': row[0], 'profit': round(float(row[1] or 0), 2), 'trades': int(row[2] or 0)}
