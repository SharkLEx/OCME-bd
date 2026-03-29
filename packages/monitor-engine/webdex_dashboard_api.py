"""
webdex_dashboard_api.py — Dashboard API read-only do WEbdEX Monitor Engine

Story 13.1 | Epic 13 — Dashboard Externo Next.js + SIWE

Expõe dados do SQLite webdex_monitor.db via REST endpoints autenticados.
Bind: 127.0.0.1:8765 (não exposto publicamente — Nginx ou SSH tunnel para acesso externo)
Auth: header X-Dashboard-Secret (secret configurado via .env)

Endpoints:
    GET /health                           — status da API (sem auth)
    GET /v1/trader/{address}/positions    — posições abertas do trader
    GET /v1/trader/{address}/history      — histórico de operações (últimas 50)
    GET /v1/stats/global                  — TVL, traders ativos, volume 24h

Uso como worker (registrado em workers/registry.py):
    from webdex_dashboard_api import dashboard_api_worker
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "")
_DASHBOARD_PORT   = int(os.getenv("DASHBOARD_PORT", "8765"))
_DASHBOARD_HOST   = os.getenv("DASHBOARD_HOST", "127.0.0.1")
_HISTORY_LIMIT    = 50


# ── FastAPI app ───────────────────────────────────────────────────────────────
def _build_app():
    """Constrói a FastAPI app. Importado lazy para não quebrar startup sem fastapi."""
    try:
        from fastapi import FastAPI, Header, HTTPException, Path
        from fastapi.responses import JSONResponse
    except ImportError as e:
        raise ImportError(f"fastapi não instalado. Instalar com: pip install fastapi uvicorn[standard]. Erro: {e}")

    app = FastAPI(
        title="WEbdEX Dashboard API",
        description="API read-only para o Dashboard OCME (Epic 13)",
        version="1.0.0",
        docs_url=None,   # desabilitar Swagger UI em produção
        redoc_url=None,
    )

    def _auth(x_dashboard_secret: Optional[str]) -> None:
        """Verifica o header X-Dashboard-Secret. Lança HTTP 401 se inválido."""
        if not _DASHBOARD_SECRET:
            raise HTTPException(status_code=500, detail="DASHBOARD_SECRET não configurado no servidor")
        if x_dashboard_secret != _DASHBOARD_SECRET:
            raise HTTPException(status_code=401, detail="Unauthorized")

    def _get_db():
        """Abre conexão SQLite read-only (thread-local para segurança)."""
        import sqlite3
        db_path = os.getenv("DB_PATH", "webdex_v5_final.db")
        conn = sqlite3.connect(
            f"file:{db_path}?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        return conn

    # ── GET /health ──────────────────────────────────────────────────────────

    @app.get("/health")
    def health():
        return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}

    # ── GET /v1/trader/{address}/positions ───────────────────────────────────

    @app.get("/v1/trader/{address}/positions")
    def get_positions(
        address: str = Path(..., description="Endereço da wallet (0x...)"),
        x_dashboard_secret: Optional[str] = Header(None),
    ):
        _auth(x_dashboard_secret)
        if not address.startswith("0x") or len(address) < 10:
            raise HTTPException(status_code=400, detail="Endereço inválido")

        try:
            conn = _get_db()
            rows = conn.execute(
                """SELECT wallet, sub_conta, ambiente, saldo_usdt,
                          last_trade, trade_count, updated_at
                   FROM sub_positions
                   WHERE LOWER(wallet) = LOWER(?)
                   ORDER BY saldo_usdt DESC""",
                (address,),
            ).fetchall()
            conn.close()
        except Exception as e:
            logger.error("[dashboard_api] positions query error (address=%s): %s", address, e)
            raise HTTPException(status_code=500, detail="Erro ao consultar posições")

        return {
            "address": address,
            "positions": [dict(r) for r in rows],
            "count": len(rows),
        }

    # ── GET /v1/trader/{address}/history ─────────────────────────────────────

    @app.get("/v1/trader/{address}/history")
    def get_history(
        address: str = Path(..., description="Endereço da wallet (0x...)"),
        x_dashboard_secret: Optional[str] = Header(None),
        limit: int = _HISTORY_LIMIT,
    ):
        _auth(x_dashboard_secret)
        if not address.startswith("0x") or len(address) < 10:
            raise HTTPException(status_code=400, detail="Endereço inválido")

        limit = min(max(1, limit), 200)  # clamp 1–200

        try:
            conn = _get_db()
            rows = conn.execute(
                """SELECT o.hash, o.log_index, o.data_hora, o.tipo,
                          o.valor, o.gas_usd, o.token, o.sub_conta,
                          o.ambiente, o.fee
                   FROM operacoes o
                   JOIN op_owner oo ON o.hash = oo.hash AND o.log_index = oo.log_index
                   WHERE LOWER(oo.wallet) = LOWER(?)
                   ORDER BY o.data_hora DESC
                   LIMIT ?""",
                (address, limit),
            ).fetchall()
            conn.close()
        except Exception as e:
            logger.error("[dashboard_api] history query error (address=%s): %s", address, e)
            raise HTTPException(status_code=500, detail="Erro ao consultar histórico")

        return {
            "address": address,
            "history": [dict(r) for r in rows],
            "count": len(rows),
        }

    # ── GET /v1/stats/global ─────────────────────────────────────────────────

    @app.get("/v1/stats/global")
    def get_stats_global(x_dashboard_secret: Optional[str] = Header(None)):
        _auth(x_dashboard_secret)

        try:
            conn = _get_db()

            # TVL — último snapshot de capital total
            tvl_row = conn.execute(
                """SELECT capital_total FROM adm_capital_stats
                   ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            tvl = float(tvl_row["capital_total"]) if tvl_row else 0.0

            # Traders ativos — wallets com posição aberta (saldo > 0)
            active_row = conn.execute(
                """SELECT COUNT(DISTINCT wallet) AS cnt
                   FROM sub_positions WHERE saldo_usdt > 0"""
            ).fetchone()
            active_traders = int(active_row["cnt"]) if active_row else 0

            # Volume 24h — soma de valores nas últimas 24h
            since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            vol_row = conn.execute(
                """SELECT COALESCE(SUM(ABS(valor)), 0) AS vol
                   FROM operacoes WHERE data_hora >= ?""",
                (since_24h,),
            ).fetchone()
            volume_24h = float(vol_row["vol"]) if vol_row else 0.0

            # Total de operações 24h
            count_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM operacoes WHERE data_hora >= ?",
                (since_24h,),
            ).fetchone()
            ops_24h = int(count_row["cnt"]) if count_row else 0

            conn.close()

        except Exception as e:
            logger.error("[dashboard_api] stats/global query error: %s", e)
            raise HTTPException(status_code=500, detail="Erro ao consultar stats globais")

        return {
            "tvl_usdt":       tvl,
            "active_traders": active_traders,
            "volume_24h":     volume_24h,
            "ops_24h":        ops_24h,
            "ts":             datetime.now(timezone.utc).isoformat(),
        }

    return app


# ── Worker function (registrado em workers/registry.py) ──────────────────────

def dashboard_api_worker() -> None:
    """
    Worker thread que inicia o servidor FastAPI/uvicorn em 127.0.0.1:8765.
    Graceful degradation: se fastapi/uvicorn não estiver instalado, loga e termina silenciosamente.
    """
    import time as _time

    if not _DASHBOARD_SECRET:
        logger.warning("[dashboard_api] DASHBOARD_SECRET não configurado — API não iniciada.")
        logger.warning("[dashboard_api] Configure DASHBOARD_SECRET no .env para ativar o dashboard.")
        # Sleep forever so watchdog doesn't restart this thread in a tight loop
        while True:
            _time.sleep(3600)

    logger.info("[dashboard_api] Iniciando servidor em %s:%d...", _DASHBOARD_HOST, _DASHBOARD_PORT)

    # Aguarda 10s para que outros workers iniciem primeiro
    _time.sleep(10)

    try:
        import uvicorn
        app = _build_app()
        uvicorn.run(
            app,
            host=_DASHBOARD_HOST,
            port=_DASHBOARD_PORT,
            log_level="warning",
            access_log=False,
        )
    except ImportError:
        logger.warning("[dashboard_api] uvicorn/fastapi não instalados — API não iniciada.")
        logger.warning("[dashboard_api] Instalar: pip install fastapi uvicorn[standard]")
        # Sleep forever so watchdog doesn't restart this thread in a tight loop
        while True:
            _time.sleep(3600)
    except Exception as e:
        logger.error("[dashboard_api] Erro ao iniciar servidor: %s", e)
        # Não lança exceção — o worker morre silenciosamente (watchdog pode reiniciar)
