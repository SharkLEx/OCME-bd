#!/bin/bash
# ==============================================================================
# fix_ai_model.sh — Corrige OPENAI_MODEL no VPS sem deploy completo
# Troca anthropic/claude-haiku-4.5 → anthropic/claude-haiku-4-5 (traço, não ponto)
# ==============================================================================

set -euo pipefail

VPS_USER="root"
VPS_HOST="76.13.100.67"
VPS_TARGET="${VPS_USER}@${VPS_HOST}"
SSH_KEY="${HOME}/.ssh/ocme_vps_key"
SSH_OPTS="-i ${SSH_KEY} -o StrictHostKeyChecking=no -o ConnectTimeout=15"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'
BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }

_ssh() { ssh $SSH_OPTS "$VPS_TARGET" "$@"; }

ENV_PATH="/opt/ocme-monitor/packages/monitor-engine/.env"

echo ""
echo -e "${BOLD}${BLUE}▶ Corrigindo OPENAI_MODEL no VPS...${NC}"

# 1. Mostra modelo atual
info "Modelo atual:"
_ssh "grep 'OPENAI_MODEL' $ENV_PATH || echo '(não definido — usando default do código)'"

# 2. Aplica o fix (ponto → traço no claude-haiku-4.5)
_ssh "sed -i 's|anthropic/claude-haiku-4\.5|anthropic/claude-haiku-4-5|g' $ENV_PATH"
_ssh "grep 'OPENAI_MODEL' $ENV_PATH && echo '' || true"

success "Modelo corrigido: anthropic/claude-haiku-4-5"

# 3. Se não tinha OPENAI_MODEL, adiciona
_ssh "grep -q 'OPENAI_MODEL' $ENV_PATH || echo 'OPENAI_MODEL=anthropic/claude-haiku-4-5' >> $ENV_PATH"

# 4. Reinicia o container
echo ""
echo -e "${BOLD}${BLUE}▶ Reiniciando container...${NC}"
_ssh "cd /opt/ocme-monitor/packages/monitor-engine && docker compose restart && echo '✅ Container reiniciado'"

# 5. Aguarda e verifica log
info "Aguardando inicialização (10s)..."
sleep 10

echo ""
echo -e "${BOLD}${BLUE}▶ Últimas linhas do log:${NC}"
_ssh "docker logs ocme-monitor --tail 20 2>&1 || docker compose -f /opt/ocme-monitor/packages/monitor-engine/docker-compose.yml logs --tail 20 2>&1 || true"

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║  ✅  Fix aplicado! Teste a IA no Telegram agora.        ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
