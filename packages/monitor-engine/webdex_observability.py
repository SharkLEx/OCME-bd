"""webdex_observability.py — Servidor HTTP de Observability para OCME Engine.

Expõe dois endpoints (stdlib puro — sem dependências externas):
  GET /metrics  → formato Prometheus text/plain
  GET /health   → JSON { status, vigia, db, rpc }

Story 7.7 — @devops

Métricas disponíveis:
  vigia_blocks_processed_total  — blocos processados desde o início
  vigia_ops_total               — operações detectadas (trades + transfers)
  vigia_lag_blocks              — lag atual (head - last_processed)
  sentinela_alerts_total        — alertas disparados pela sentinela

Uso:
    from webdex_observability import ObservabilityServer

    srv = ObservabilityServer(port=9090, db_path="webdex_v5_final.db")
    srv.start()  # daemon thread — não bloqueia

    # Atualizar métricas via HEALTH dict (compatível com webdex_monitor.py):
    srv.update_from_health(HEALTH)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

logger = logging.getLogger("webdex_observability")

# ── Registro global de métricas ───────────────────────────────────────────────

class _MetricsRegistry:
    """Thread-safe store de métricas Prometheus-ready."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {
            "vigia_blocks_processed_total": 0,
            "vigia_ops_total": 0,
            "sentinela_alerts_total": 0,
        }
        self._gauges: Dict[str, float] = {
            "vigia_lag_blocks": 0.0,
            "vigia_loops_total": 0.0,
            "vigia_rpc_errors_total": 0.0,
            "vigia_capture_rate": 100.0,
        }
        self._started_at: float = time.time()
        self._last_health_ts: float = 0.0  # timestamp da última atualização do vigia

    def update(self, health: Dict[str, Any]):
        """Atualiza métricas a partir do dict HEALTH do monitor (webdex_monitor.py)."""
        with self._lock:
            # Suporta chaves do HEALTH dict do webdex_monitor.py
            self._counters["vigia_blocks_processed_total"] = int(
                health.get("blocks_processed", 0)
            )
            self._counters["vigia_ops_total"] = int(
                health.get("ops_total", 0) or
                health.get("logs_trade", 0) + health.get("logs_transfer", 0)
            )
            self._gauges["vigia_lag_blocks"] = float(
                health.get("lag_blocks", 0)
            )
            self._gauges["vigia_loops_total"] = float(
                health.get("vigia_loops", 0)
            )
            self._gauges["vigia_rpc_errors_total"] = float(
                health.get("rpc_errors", 0) or health.get("rpc_errors_total", 0)
            )
            self._gauges["vigia_capture_rate"] = float(
                health.get("capture_rate", 100.0)
            )
            # Timestamp: usa last_fetch_ok_ts (webdex) ou updated_at (modular)
            self._last_health_ts = float(
                health.get("updated_at", 0) or
                health.get("last_fetch_ok_ts", 0) or
                time.time()
            )

    def increment_alert(self):
        with self._lock:
            self._counters["sentinela_alerts_total"] += 1

    def to_prometheus(self) -> str:
        """Serializa no formato texto do Prometheus (text/plain; version=0.0.4)."""
        lines = []
        with self._lock:
            # Counters
            lines.append("# HELP vigia_blocks_processed_total Blocos processados pelo Vigia desde o início")
            lines.append("# TYPE vigia_blocks_processed_total counter")
            lines.append(f'vigia_blocks_processed_total {self._counters["vigia_blocks_processed_total"]}')

            lines.append("# HELP vigia_ops_total Operações detectadas (trades + transfers)")
            lines.append("# TYPE vigia_ops_total counter")
            lines.append(f'vigia_ops_total {self._counters["vigia_ops_total"]}')

            lines.append("# HELP sentinela_alerts_total Alertas disparados pela Sentinela")
            lines.append("# TYPE sentinela_alerts_total counter")
            lines.append(f'sentinela_alerts_total {self._counters["sentinela_alerts_total"]}')

            # Gauges
            lines.append("# HELP vigia_lag_blocks Lag atual entre head da chain e último bloco processado")
            lines.append("# TYPE vigia_lag_blocks gauge")
            lines.append(f'vigia_lag_blocks {self._gauges["vigia_lag_blocks"]:.0f}')

            lines.append("# HELP vigia_loops_total Número de loops do Vigia executados")
            lines.append("# TYPE vigia_loops_total gauge")
            lines.append(f'vigia_loops_total {self._gauges["vigia_loops_total"]:.0f}')

            lines.append("# HELP vigia_rpc_errors_total Total de erros RPC acumulados")
            lines.append("# TYPE vigia_rpc_errors_total gauge")
            lines.append(f'vigia_rpc_errors_total {self._gauges["vigia_rpc_errors_total"]:.0f}')

            lines.append("# HELP vigia_capture_rate Taxa de captura de blocos (0-100%)")
            lines.append("# TYPE vigia_capture_rate gauge")
            lines.append(f'vigia_capture_rate {self._gauges["vigia_capture_rate"]:.2f}')

            # Uptime
            uptime = time.time() - self._started_at
            lines.append("# HELP vigia_uptime_seconds Tempo de uptime do processo em segundos")
            lines.append("# TYPE vigia_uptime_seconds gauge")
            lines.append(f'vigia_uptime_seconds {uptime:.0f}')

        return "\n".join(lines) + "\n"


# Instância global singleton
_registry = _MetricsRegistry()


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class _ObsHandler(BaseHTTPRequestHandler):
    """Handler HTTP para /metrics e /health."""

    # Referências injetadas pela fábrica
    _db_path: str = ""
    _health_ref: Optional[Dict] = None

    def _live_health(self) -> Optional[Dict]:
        """Retorna o HEALTH dict vivo: health_ref ou sys.modules['webdex_monitor'].HEALTH."""
        if self._health_ref is not None:
            return self._health_ref
        import sys
        wm = sys.modules.get("webdex_monitor")
        if wm and hasattr(wm, "HEALTH"):
            return wm.HEALTH  # type: ignore
        return None

    def do_GET(self):  # noqa: N802
        if self.path == "/metrics":
            self._handle_metrics()
        elif self.path.startswith("/health"):
            self._handle_health()
        elif self.path.startswith("/digests"):
            self._handle_digests()
        else:
            self._send(404, "application/json",
                       json.dumps({"error": "Not Found", "path": self.path}))

    def _handle_digests(self):
        """Retorna últimos 7 digests como JSON."""
        try:
            import urllib.parse as _up
            qs = _up.parse_qs(_up.urlparse(self.path).query)
            days = int(qs.get("days", ["7"])[0])
            from webdex_ai_digest import get_recent_digests
            from webdex_db import DB_LOCK, conn
            digests = get_recent_digests(conn, DB_LOCK, days=min(days, 30))
            body = json.dumps({"digests": digests, "count": len(digests)})
            self._send(200, "application/json", body)
        except Exception as e:
            self._send(500, "application/json", json.dumps({"error": str(e)}))

    def _handle_metrics(self):
        # Sincroniza métricas do HEALTH vivo (via health_ref ou sys.modules)
        h = self._live_health()
        if h:
            try:
                _registry.update(h)
            except Exception:
                pass
        body = _registry.to_prometheus()
        self._send(200, "text/plain; version=0.0.4; charset=utf-8", body)

    def _handle_health(self):
        status = self._build_health_payload()
        code = 200 if status["status"] == "ok" else 503
        self._send(code, "application/json", json.dumps(status))

    def _build_health_payload(self) -> Dict:
        # Vigia — lê HEALTH dict via live_health() (health_ref ou sys.modules)
        # Fallback: se vigia legado nao atualiza last_fetch_ok_ts,
        # verifica atividade recente no DB (workers modernos = protocolo ok)
        vigia_ok = False
        try:
            h = self._live_health() or {}
            last_updated = float(
                _registry._last_health_ts or
                h.get("last_vigia_ts", 0) or
                h.get("last_fetch_ok_ts", 0) or
                h.get("updated_at", 0)
            )
            if last_updated == 0:
                # Vigia legado inativo: checar workers modernos via DB
                try:
                    c = sqlite3.connect(self._db_path, timeout=3)
                    row = c.execute(
                        "SELECT MAX(ts) FROM protocol_ops "
                        "WHERE ts >= datetime(now, -30 minutes)"
                    ).fetchone()
                    c.close()
                    if row and row[0]:
                        last_updated = time.time()  # dados frescos = workers ativos
                except Exception:
                    pass
            vigia_ok = last_updated > 0 and (time.time() - last_updated) < 300  # 5 min
        except Exception:
            pass

        # DB
        db_ok = False
        try:
            c = sqlite3.connect(self._db_path, timeout=3)
            c.execute("SELECT 1")
            c.close()
            db_ok = True
        except Exception:
            pass

        # RPC (não testa conexão real — apenas verifica config)
        rpc_ok = bool(os.environ.get("RPC_URL", ""))

        overall = "ok" if (vigia_ok and db_ok) else "degraded"

        return {
            "status": overall,
            "vigia": "ok" if vigia_ok else "not_running",
            "db": "ok" if db_ok else "error",
            "rpc": "configured" if rpc_ok else "not_configured",
            "uptime_seconds": round(time.time() - _registry._started_at),
            "ts": time.time(),
        }

    def _send(self, code: int, content_type: str, body: str):
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt, *args):  # silencia logs de acesso no stdout
        logger.debug("[obs] %s", fmt % args)


# ── Servidor principal ────────────────────────────────────────────────────────

class ObservabilityServer:
    """Servidor de observability — expõe /metrics e /health em thread daemon."""

    def __init__(
        self,
        port: int = 9090,
        db_path: str = "",
        health_ref: Optional[Dict] = None,
    ):
        self._port = port or int(os.environ.get("METRICS_PORT", 9090))
        self._db_path = db_path
        self._health_ref = health_ref  # referência ao dict HEALTH do monitor
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, daemon: bool = True):
        """Inicia o servidor HTTP em thread background."""
        db_path = self._db_path
        health_ref = self._health_ref

        def handler_factory(*args, **kwargs):
            h = _ObsHandler(*args, **kwargs)
            h._db_path = db_path
            h._health_ref = health_ref
            return h

        try:
            self._server = HTTPServer(("0.0.0.0", self._port), handler_factory)
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                name="observability-server",
                daemon=daemon,
            )
            self._thread.start()
            logger.info(
                "📊 Observability server em http://0.0.0.0:%d  (/metrics, /health)",
                self._port,
            )
        except OSError as exc:
            logger.warning("Observability server não iniciado (porta %d): %s", self._port, exc)

    def stop(self, timeout: float = 3.0):
        if self._server:
            self._server.shutdown()
            if self._thread:
                self._thread.join(timeout=timeout)

    def update_from_health(self, health: Dict):
        """Atualiza métricas a partir do dict HEALTH do monitor (thread-safe)."""
        _registry.update(health)

    def increment_alert(self):
        """Incrementa contador de alertas da sentinela."""
        _registry.increment_alert()

    @property
    def port(self) -> int:
        return self._port


# ── Acesso direto ao registry (para testes e integração) ─────────────────────

def get_registry() -> _MetricsRegistry:
    return _registry
