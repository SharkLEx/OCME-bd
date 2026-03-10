# ==============================================================================
# Dockerfile — OCME bd Monitor Engine
# Multi-stage: build otimizado + runtime slim
# Story 7.7 — @devops
# ==============================================================================

# ── Stage 1: Build ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Instala dependências de sistema para web3/matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copia dependências instaladas
COPY --from=builder /install /usr/local

# Matplotlib headless (sem display)
ENV MPLBACKEND=Agg

# Diretório de dados persistentes
RUN mkdir -p /app/data && chmod 777 /app/data

# Copia código fonte
COPY config.py .
COPY monitor_cli/ ./monitor_cli/
COPY monitor_core/ ./monitor_core/
COPY monitor_chain/ ./monitor_chain/
COPY monitor_db/ ./monitor_db/
COPY monitor_ai/ ./monitor_ai/
COPY monitor_report/ ./monitor_report/
COPY monitor_bot/ ./monitor_bot/

# Cria __init__.py para todos os pacotes
RUN for pkg in monitor_cli monitor_core monitor_chain monitor_db monitor_ai monitor_report monitor_bot; do \
    touch /app/$pkg/__init__.py; \
    done

# Variáveis de ambiente padrão (override via .env ou docker-compose)
ENV DATA_DIR=/app/data
ENV DB_PATH=/app/data/webdex_v5_final.db
ENV MPLBACKEND=Agg

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import sqlite3; conn = sqlite3.connect('${DB_PATH}'); conn.execute('SELECT 1'); print('OK')" || exit 1

# Entry points
# Bot: python -m monitor_bot.bot
# CLI: python -m monitor_cli
CMD ["python", "-m", "monitor_bot.bot"]
