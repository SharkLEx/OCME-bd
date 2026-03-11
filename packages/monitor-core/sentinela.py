"""monitor-core/sentinela.py — Sentinela de Alertas do OCME Engine.

Escuta eventos do Vigia e dispara alertas para:
    - Gas alto (> threshold em USD)
    - GWEI alto (> threshold)
    - Inatividade prolongada (sem ops por > N minutos)
    - RPC errors acumulados

Uso:
    from vigia import Vigia
    from sentinela import Sentinela

    vigia = Vigia(...)
    sentinela = Sentinela(
        vigia=vigia,
        db_path="webdex_v5_final.db",
        on_alert=lambda alert: print(alert),
    )
    vigia.start()
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("monitor-core.sentinela")


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


class Sentinela:
    """Observador de saúde e alertas do OCME Engine.

    Alertas emitidos via on_alert callback:
        {
            "tipo": "gas_alto" | "gwei_alto" | "inatividade" | "rpc_error",
            "mensagem": str,
            "dados": dict,
            "ts": float,
        }
    """

    def __init__(
        self,
        vigia,                          # instância de Vigia
        db_path: str,
        on_alert: Optional[Callable[[Dict], None]] = None,
        # thresholds (env > constructor > default)
        gas_usd_threshold: Optional[float] = None,
        gwei_threshold: Optional[int] = None,
        inactivity_minutes: Optional[int] = None,
        rpc_error_threshold: Optional[int] = None,
    ):
        self._vigia = vigia
        self._db_path = db_path
        self._on_alert = on_alert or (lambda a: logger.warning("[sentinela] %s", a["mensagem"]))

        self._gas_usd_threshold = gas_usd_threshold or _env_float("SENTINELA_GAS_USD_MAX", 2.0)
        self._gwei_threshold = gwei_threshold or _env_int("SENTINELA_GWEI_MAX", 1000)
        self._inactivity_minutes = inactivity_minutes or _env_int("SENTINELA_INACTIVITY_MINUTES", 30)
        self._rpc_error_threshold = rpc_error_threshold or _env_int("SENTINELA_RPC_ERRORS_MAX", 5)

        self._last_op_ts: float = time.time()
        self._last_inactivity_alert_ts: float = 0.0
        self._inactivity_alert_cooldown = 300.0  # max 1 alerta de inatividade a cada 5min

        # Conecta aos eventos do vigia
        vigia.on("operation", self._on_operation)
        vigia.on("progress", self._on_progress)
        vigia.on("error", self._on_error)

    # ── Handlers ─────────────────────────────────────────────────────────
    def _on_operation(self, op: Dict):
        self._last_op_ts = time.time()

        # Gas alto
        gas_usd = float(op.get("gas_usd", 0))
        if gas_usd > self._gas_usd_threshold:
            self._fire_alert("gas_alto", {
                "gas_usd": gas_usd,
                "tx_hash": op.get("tx_hash", ""),
                "sub_conta": op.get("sub_conta", ""),
                "bloco": op.get("bloco", 0),
            })

    def _on_progress(self, progress: Dict):
        """Verificação de inatividade a cada ciclo."""
        now = time.time()
        inactivity_secs = now - self._last_op_ts
        inactivity_min = inactivity_secs / 60

        if inactivity_min >= self._inactivity_minutes:
            # só dispara alerta 1x por cooldown
            if (now - self._last_inactivity_alert_ts) >= self._inactivity_alert_cooldown:
                self._last_inactivity_alert_ts = now
                tx_count_recent = self._count_recent_ops(hours=1)
                self._fire_alert("inatividade", {
                    "minutos": round(inactivity_min, 1),
                    "last_block": progress.get("last_block", 0),
                    "tx_count": tx_count_recent,
                })
                self._persist_inactivity_stat(
                    end_block=progress.get("last_block", 0),
                    minutes=inactivity_min,
                    tx_count=tx_count_recent,
                )

    def _on_error(self, error_str: str):
        rpc_errors = self._vigia.health.get("rpc_errors", 0)
        if rpc_errors > 0 and rpc_errors % self._rpc_error_threshold == 0:
            self._fire_alert("rpc_error", {
                "rpc_errors_total": rpc_errors,
                "last_error": error_str[:200],
            })

    # ── Alert dispatch ────────────────────────────────────────────────────
    def _fire_alert(self, tipo: str, dados: Dict):
        msgs = {
            "gas_alto": (
                f"⛽ Gas alto detectado: ${dados.get('gas_usd', 0):.4f} USD "
                f"(threshold: ${self._gas_usd_threshold:.2f})"
            ),
            "gwei_alto": f"⚡ GWEI alto: {dados.get('gwei', 0)} (threshold: {self._gwei_threshold})",
            "inatividade": (
                f"😴 Inatividade: {dados.get('minutos', 0):.1f} min sem operações "
                f"(threshold: {self._inactivity_minutes} min)"
            ),
            "rpc_error": (
                f"🔴 RPC errors acumulados: {dados.get('rpc_errors_total', 0)} "
                f"| último: {dados.get('last_error', '')[:80]}"
            ),
        }
        mensagem = msgs.get(tipo, f"⚠️ Alerta: {tipo}")
        alert = {
            "tipo": tipo,
            "mensagem": mensagem,
            "dados": dados,
            "ts": time.time(),
        }
        logger.warning("[sentinela] %s", mensagem)
        try:
            self._on_alert(alert)
        except Exception as exc:
            logger.error("sentinela on_alert callback error: %s", exc)

    # ── DB helpers ────────────────────────────────────────────────────────
    def _count_recent_ops(self, hours: int = 1) -> int:
        try:
            c = sqlite3.connect(self._db_path)
            row = c.execute(
                "SELECT COUNT(*) FROM operacoes "
                "WHERE tipo='Trade' AND data_hora >= datetime('now', ?)",
                (f"-{hours} hours",)
            ).fetchone()
            c.close()
            return int(row[0] or 0) if row else 0
        except Exception:
            return 0

    def _persist_inactivity_stat(self, end_block: int, minutes: float, tx_count: int):
        """Persiste em inactivity_stats para histórico de alertas."""
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c = sqlite3.connect(self._db_path)
            c.execute(
                "INSERT OR IGNORE INTO inactivity_stats "
                "(end_block, minutes, tx_count, note, created_at) "
                "VALUES (?,?,?,?,?)",
                (end_block, round(minutes, 2), tx_count,
                 f"sentinela: {minutes:.1f} min sem ops", now_str)
            )
            c.commit()
            c.close()
        except Exception:
            pass
