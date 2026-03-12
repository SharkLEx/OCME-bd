#!/bin/bash
# ==============================================================================
# deploy_now.sh — Deploy OCME Monitor Engine para VPS
# Roda na sua máquina local. Pede senha 1x e faz tudo automaticamente.
# ==============================================================================

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
VPS_USER="root"
VPS_HOST="76.13.100.67"
VPS_TARGET="${VPS_USER}@${VPS_HOST}"
APP_DIR="/opt/ocme-monitor"
DATA_DIR="/opt/ocme-data"
REPO_URL="https://github.com/SharkLEx/OCME-bd.git"
REPO_BRANCH="feat/epic-7-monitor-engine"
SSH_CTRL="/tmp/ocme_ssh_ctrl"

# Cores
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'
BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
step()    { echo -e "\n${BOLD}${BLUE}▶ $*${NC}"; }

# Caminhos locais
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_LOCAL="$REPO_ROOT/packages/monitor-engine/.env"
DB_LOCAL="$REPO_ROOT/packages/monitor-engine/webdex_v5_final.db"
SETUP_SCRIPT="$SCRIPT_DIR/setup_vps.sh"

# Função SSH/SCP usando ControlMaster (senha pedida apenas 1x)
_ssh() { ssh -o ControlPath="$SSH_CTRL" "$VPS_TARGET" "$@"; }
_scp() { scp -o ControlPath="$SSH_CTRL" "$@"; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     OCME bd Monitor Engine — Deploy Automático          ║${NC}"
echo -e "${BOLD}║     VPS: ${VPS_HOST}                                ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Verificar arquivos locais ───────────────────────────────────────────────
step "1/6 — Verificando arquivos locais"
[[ -f "$ENV_LOCAL" ]]    && success ".env encontrado ($ENV_LOCAL)" || { echo -e "${RED}ERRO: .env não encontrado em $ENV_LOCAL${NC}"; exit 1; }
[[ -f "$SETUP_SCRIPT" ]] && success "setup_vps.sh encontrado"      || { echo -e "${RED}ERRO: setup_vps.sh não encontrado${NC}"; exit 1; }
[[ -f "$DB_LOCAL" ]]     && success "DB encontrado ($(du -sh "$DB_LOCAL" | cut -f1))" || warn "DB não encontrado — será criado no VPS"

# ── 2. Conectar ao VPS (pede senha 1x aqui) ────────────────────────────────────
step "2/6 — Conectando ao VPS (digite a senha quando solicitado)"
# Limpar controle anterior se existir
rm -f "$SSH_CTRL"
ssh -M -o ControlPath="$SSH_CTRL" -o ControlPersist=600s \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout=15 \
    "$VPS_TARGET" "echo '✅ Conexão SSH estabelecida — não precisa digitar a senha novamente!'"
success "SSH conectado (sessão válida por 10 min)"

# ── 3. Upload dos arquivos ─────────────────────────────────────────────────────
step "3/6 — Enviando arquivos para o VPS"
_scp -o StrictHostKeyChecking=no "$SETUP_SCRIPT" "${VPS_TARGET}:/root/setup_vps.sh"
success "setup_vps.sh enviado"

_scp -o StrictHostKeyChecking=no "$ENV_LOCAL" "${VPS_TARGET}:/tmp/.env_ocme"
success ".env enviado (credenciais protegidas em /tmp)"

if [[ -f "$DB_LOCAL" ]]; then
    info "Enviando DB ($(du -sh "$DB_LOCAL" | cut -f1)) — pode demorar..."
    _scp -o StrictHostKeyChecking=no "$DB_LOCAL" "${VPS_TARGET}:/tmp/webdex_v5_final.db"
    success "DB enviado"
fi

# ── 4. Executar setup no VPS ───────────────────────────────────────────────────
step "4/6 — Executando setup completo no VPS (pode demorar 3-5 min)"
_ssh bash << 'REMOTE_SETUP'
set -e
chmod +x /root/setup_vps.sh

# Pré-posiciona o .env para o setup encontrar
mkdir -p /opt/ocme-data

# Roda setup (modo não-interativo — .env já está configurado)
export DEBIAN_FRONTEND=noninteractive
bash /root/setup_vps.sh
REMOTE_SETUP
success "Setup concluído!"

# ── 5. Mover .env e DB para os lugares certos ──────────────────────────────────
step "5/6 — Posicionando .env e DB"
_ssh bash << 'REMOTE_FIX'
# .env → pasta do projeto
ENV_DEST="/opt/ocme-monitor/packages/monitor-engine/.env"
if [[ -f /tmp/.env_ocme ]]; then
    cp /tmp/.env_ocme "$ENV_DEST"
    chmod 600 "$ENV_DEST"
    # Ajustar paths para Docker
    sed -i 's|^DB_PATH=.*|DB_PATH=/app/data/webdex_v5_final.db|' "$ENV_DEST"
    sed -i 's|^OCME_DB_PATH=.*|OCME_DB_PATH=/app/data/webdex_v5_final.db|' "$ENV_DEST"
    echo "✅ .env posicionado"
fi

# DB → volume de dados
if [[ -f /tmp/webdex_v5_final.db ]]; then
    cp /tmp/webdex_v5_final.db /opt/ocme-data/webdex_v5_final.db
    echo "✅ DB posicionado ($(du -sh /opt/ocme-data/webdex_v5_final.db | cut -f1))"
fi

# Reinicia com configuração correta
cd /opt/ocme-monitor/packages/monitor-engine
docker compose down 2>/dev/null || true
docker compose up -d
echo "✅ Containers reiniciados com configuração final"
REMOTE_FIX

# ── 6. Health check final ──────────────────────────────────────────────────────
step "6/6 — Verificando health check"
info "Aguardando bot inicializar (45s)..."
sleep 45

HEALTH=$(_ssh "curl -sf http://localhost:9090/health 2>/dev/null || echo 'pending'")
if echo "$HEALTH" | grep -q '"status"'; then
    STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; h=json.load(sys.stdin); print(f\"status={h['status']} | vigia={h['vigia']} | db={h['db']}\")" 2>/dev/null || echo "$HEALTH")
    if echo "$HEALTH" | grep -q '"status": "ok"'; then
        echo -e "${GREEN}✅ $STATUS${NC}"
    else
        echo -e "${YELLOW}⚠️  $STATUS (vigia pode precisar de 1-2 min para ligar)${NC}"
    fi
else
    warn "Health ainda inicializando — verifique em 1 min: curl http://${VPS_HOST}:9090/health"
fi

# Containers status
_ssh "cd /opt/ocme-monitor/packages/monitor-engine && docker compose ps"

# Fechar ControlMaster
ssh -O stop -o ControlPath="$SSH_CTRL" "$VPS_TARGET" 2>/dev/null || true

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║  🚀  Deploy Completo!                                   ║${NC}"
echo -e "${GREEN}${BOLD}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}${BOLD}║  Health:   http://${VPS_HOST}:9090/health         ║${NC}"
echo -e "${GREEN}${BOLD}║  Metrics:  http://${VPS_HOST}:9090/metrics        ║${NC}"
echo -e "${GREEN}${BOLD}║  Logs:     ssh ${VPS_TARGET} docker logs -f ocme-monitor ║${NC}"
echo -e "${GREEN}${BOLD}║  Update:   ssh ${VPS_TARGET} ocme-update          ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
