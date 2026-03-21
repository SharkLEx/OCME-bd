# ==============================================================================
# Dockerfile — OCME bd Monitor Engine (WEbdEX)
# Multi-stage: build otimizado + runtime Python 3.12 slim
# Story 7.7 — @devops
# ==============================================================================

# ── Stage 1: Build ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Dependências de sistema para web3 / matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY monitor-engine/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Dependências instaladas no stage build
COPY --from=builder /install /usr/local

# Matplotlib headless + UTF-8
ENV MPLBACKEND=Agg
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUTF8=1

# Diretório de dados persistentes (DB + logs)
RUN mkdir -p /app/data /app/logs && chmod 777 /app/data /app/logs

# ── Monolito WEbdEX (produção atual) ────────────────────────────────────────
COPY monitor-engine/webdex_config.py \
     monitor-engine/webdex_db.py \
     monitor-engine/webdex_chain.py \
     monitor-engine/webdex_monitor.py \
     monitor-engine/webdex_workers.py \
     monitor-engine/webdex_bot_core.py \
     monitor-engine/webdex_main.py \
     monitor-engine/webdex_ai.py \
     monitor-engine/webdex_observability.py \
     monitor-engine/webdex_anomaly.py \
     monitor-engine/webdex_milestones.py \
     monitor-engine/webdex_discord_sync.py \
     monitor-engine/webdex_discord_animate.py \
     monitor-engine/webdex_onchain_notify.py \
     monitor-engine/webdex_swapbook_notify.py \
     monitor-engine/webdex_network_notify.py \
     monitor-engine/webdex_creatomate.py \
     monitor-engine/subscription_worker.py \
     monitor-engine/notification_engine.py \
     monitor-engine/protocol_context.py \
     monitor-engine/webdex_tools.py \
     monitor-engine/creatomate_worker.py \
     monitor-engine/metrics_worker.py \
     monitor-engine/webdex_ai_memory.py \
     ./

# Handlers do bot
COPY monitor-engine/webdex_handlers/ ./webdex_handlers/

# ── Pacotes modulares (Epic 7) ──────────────────────────────────────────────
COPY monitor-cli/   ./monitor_cli/
COPY monitor-db/    ./monitor_db/
COPY monitor-core/  ./monitor_core/
COPY monitor-chain/ ./monitor_chain/
COPY monitor-ai/    ./monitor_ai/
COPY monitor-report/ ./monitor_report/
COPY monitor-bot/   ./monitor_bot/

# ── Variáveis de ambiente padrão ──────────────────────────────────────────────
ENV DATA_DIR=/app/data
ENV DB_PATH=/app/data/webdex_v5_final.db
ENV OCME_DB_PATH=/app/data/webdex_v5_final.db

# Health check: verifica DB SQLite
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/app/data/webdex_v5_final.db').execute('SELECT 1'); print('OK')" || exit 1

# Entry point: monolito WEbdEX (bot + vigia)
CMD ["python", "webdex_main.py"]
