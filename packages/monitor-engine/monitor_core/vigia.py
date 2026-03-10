# ==============================================================================
# monitor_core/vigia.py — Watchdog de blocos com padrão EventEmitter
# OCME bd Monitor Engine — Story 7.2
#
# Eventos emitidos:
#   'operation'  → dict (trade ou transfer processado)
#   'progress'   → {'block': int, 'lag': int, 'ops_count': int}
#   'error'      → {'context': str, 'exc': Exception}
#   'backlog'    → {'lag': int} (quando lag > BACKLOG_WARN_AT)
#   'started'    → None
#   'stopped'    → None
# ==============================================================================
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from typing import Callable, Any

logger = logging.getLogger('monitor.core.vigia')


class Vigia:
    '''Loop de monitoramento de blocos. Thread-safe. Emite eventos.'''

    def __init__(
        self,
        fetcher: Any,           # BlockFetcher
        parser: Any,            # OperationParser
        conn: sqlite3.Connection,
        addresses: list[str],   # endereços a filtrar nos logs
        topics: list[str],      # topics a filtrar
        max_blocks_per_loop: int = 80,
        idle_sleep: float = 1.2,
        busy_sleep: float = 0.25,
        backlog_warn_at: int = 20,
    ):
        self._fetcher = fetcher
        self._parser  = parser
        self._conn    = conn
        self._addresses = addresses
        self._topics    = topics
        self._max_blocks = max_blocks_per_loop
        self._idle_sleep = idle_sleep
        self._busy_sleep = busy_sleep
        self._backlog_warn = backlog_warn_at

        self._running = False
        self._thread: threading.Thread | None = None
        self._last_block: int = 0
        self._ops_total: int = 0
        self._listeners: dict[str, list[Callable]] = {}

    # ── EventEmitter interface ────────────────────────────────────────────────

    def on(self, event: str, callback: Callable) -> None:
        self._listeners.setdefault(event, []).append(callback)

    def off(self, event: str, callback: Callable | None = None) -> None:
        if callback is None:
            self._listeners[event] = []
        else:
            self._listeners[event] = [c for c in self._listeners.get(event, []) if c != callback]

    def _emit(self, event: str, data: Any = None) -> None:
        for cb in self._listeners.get(event, []):
            try:
                cb(data)
            except Exception as exc:
                logger.warning('Listener error (%s): %s', event, exc)

    # ── Controle ──────────────────────────────────────────────────────────────

    def start(self, from_block: int | None = None) -> None:
        if self._running:
            return
        self._running = True
        self._last_block = from_block or self._load_last_block()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='vigia')
        self._thread.start()
        logger.info('Vigia iniciado (bloco inicial: %d)', self._last_block)
        self._emit('started')

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info('Vigia parado (último bloco: %d | ops: %d)', self._last_block, self._ops_total)
        self._emit('stopped')

    def is_running(self) -> bool:
        return self._running and (self._thread is not None) and self._thread.is_alive()

    @property
    def last_block(self) -> int:
        return self._last_block

    @property
    def ops_total(self) -> int:
        return self._ops_total

    # ── Loop principal ────────────────────────────────────────────────────────

    def _loop(self) -> None:
        consecutive_errors = 0
        while self._running:
            try:
                current = self._fetcher.get_latest_block()
                lag = current - self._last_block

                if lag <= 0:
                    time.sleep(self._idle_sleep)
                    continue

                if lag > self._backlog_warn:
                    self._emit('backlog', {'lag': lag})
                    logger.warning('Backlog: %d blocos atrasados', lag)

                to_process = min(lag, self._max_blocks)
                from_b = self._last_block + 1
                to_b   = self._last_block + to_process

                logs = self._fetcher.get_logs(from_b, to_b, self._addresses, self._topics)
                ops  = self._parser.parse(logs)

                for op in ops:
                    self._save_op(op)
                    self._emit('operation', op)
                    self._ops_total += 1

                self._last_block = to_b
                self._save_last_block(to_b)

                self._emit('progress', {
                    'block':     to_b,
                    'lag':       current - to_b,
                    'ops_count': len(ops),
                })

                consecutive_errors = 0
                time.sleep(self._busy_sleep if lag > 1 else self._idle_sleep)

            except KeyboardInterrupt:
                break
            except Exception as exc:
                consecutive_errors += 1
                backoff = min(2 ** consecutive_errors, 60)
                logger.error('Vigia loop error (tentativa %d, backoff %ds): %s', consecutive_errors, backoff, exc)
                self._emit('error', {'context': 'vigia_loop', 'exc': exc})
                time.sleep(backoff)

    # ── Persistência do estado ────────────────────────────────────────────────

    def _load_last_block(self) -> int:
        try:
            row = self._conn.execute(
                "SELECT valor FROM config WHERE chave='vigia_last_block'"
            ).fetchone()
            if row and row[0]:
                return int(row[0])
        except Exception:
            pass
        try:
            return self._fetcher.get_latest_block()
        except Exception:
            return 0

    def _save_last_block(self, block: int) -> None:
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO config (chave, valor) VALUES ('vigia_last_block', ?)",
                (str(block),)
            )
            self._conn.commit()
        except Exception:
            pass

    def _save_op(self, op: dict) -> None:
        '''Persiste operação no DB (idempotente via PRIMARY KEY).'''
        if op.get('type') != 'trade':
            return
        try:
            self._conn.execute('''
                INSERT OR IGNORE INTO operacoes
                  (hash, log_index, data_hora, tipo, valor, gas_usd, token,
                   sub_conta, bloco, ambiente, fee, strategy_addr, bot_id,
                   gas_protocol, old_balance_usd, contract_address)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                op['hash'], op['log_index'], op['timestamp'], 'Trade',
                op['profit_usd'], op['gas_usd'], op['token_sym'],
                op['sub_conta'], op['block'], op['env'],
                op['fee_usd'], op['strategy_addr'], op['bot_id'],
                op['gas_usd'], op['old_balance_usd'], op['contract_address'],
            ))
            if op.get('user_wallet'):
                self._conn.execute('''
                    INSERT OR IGNORE INTO op_owner (hash, log_index, wallet)
                    VALUES (?,?,?)
                ''', (op['hash'], op['log_index'], op['user_wallet'].lower()))
            self._conn.commit()
        except Exception as exc:
            logger.debug('_save_op falhou: %s', exc)
