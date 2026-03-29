# ==============================================================================
# Dockerfile — OCME bd Monitor Engine (WEbdEX)
# Multi-stage: build otimizado + runtime Python 3.12 slim
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

# ── Root Python files (monolito + stubs + novos módulos) ────────────────────────
COPY monitor-engine/*.py ./

# ── Domain namespaces — Epic 7 (Stories 7.1-7.5) ──────────────────────────────
COPY monitor-engine/ai/       ./ai/
COPY monitor-engine/core/     ./core/
COPY monitor-engine/monitors/ ./monitors/
COPY monitor-engine/services/ ./services/
COPY monitor-engine/workers/  ./workers/

# ── Handlers do bot ────────────────────────────────────────────────────────────
COPY monitor-engine/webdex_handlers/ ./webdex_handlers/

# ── Scripts, contratos e migrations ───────────────────────────────────────────
COPY monitor-engine/scripts/    ./scripts/
COPY monitor-engine/contracts/  ./contracts/
COPY monitor-engine/migrations/ ./migrations/

# ── Variáveis de ambiente padrão ──────────────────────────────────────────────
ENV DATA_DIR=/app/data
ENV DB_PATH=/app/data/webdex_v5_final.db
ENV OCME_DB_PATH=/app/data/webdex_v5_final.db

# Health check: /metrics sempre retorna 200 (ao contrário de /health que retorna 503
# enquanto vigia não processar blocos — HTTPError derrubaria o healthcheck no startup)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9090/metrics')" || exit 1

# Entry point
CMD ["python", "webdex_main.py"]
