#!/bin/bash
# ==============================================================================
# update.sh — Atualiza o OCME Monitor Engine no VPS
#
# USO: sudo ocme-update
#      ou: sudo bash /opt/ocme-monitor/deploy/update.sh
# ==============================================================================

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }

APP_DIR="/opt/ocme-monitor"
BRANCH="feat/epic-7-monitor-engine"

echo -e "\n${BOLD}${BLUE}▶ OCME Monitor Engine — Update${NC}\n"

cd "$APP_DIR"

# ── 1. Backup do DB antes de atualizar ────────────────────────────────────────
info "Criando backup do DB antes da atualização..."
BACKUP_FILE="/opt/ocme-backups/pre-update-$(date +%Y%m%d_%H%M%S).db"
if docker exec ocme-monitor python -c "import shutil; shutil.copy('/app/data/webdex_v5_final.db', '/tmp/bkp.db')" 2>/dev/null; then
    docker cp ocme-monitor:/tmp/bkp.db "$BACKUP_FILE" 2>/dev/null && \
        success "Backup: $BACKUP_FILE" || warn "Backup falhou (container pode estar parado)"
else
    warn "Container não está rodando — pulando backup"
fi

# ── 2. Pull do código novo ─────────────────────────────────────────────────────
info "Puxando código novo do GitHub..."
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"
success "Código atualizado: $(git log --oneline -1)"

# ── 3. Rebuild e restart ───────────────────────────────────────────────────────
cd "$APP_DIR/packages/monitor-engine"

info "Rebuild da imagem Docker..."
docker compose build

info "Reiniciando containers..."
docker compose up -d --remove-orphans

success "Update concluído!"

# ── 4. Health check pós-update ────────────────────────────────────────────────
echo ""
info "Aguardando bot inicializar (30s)..."
sleep 30

if curl -sf http://localhost:9090/health > /dev/null 2>&1; then
    STATUS=$(curl -s http://localhost:9090/health | python3 -c "import sys,json; h=json.load(sys.stdin); print(f\"status={h['status']} vigia={h['vigia']} db={h['db']}\")" 2>/dev/null || echo "JSON parse error")
    success "Health check: $STATUS"
else
    warn "Health check falhou — verifique os logs: docker logs ocme-monitor --tail 50"
fi

echo ""
docker compose ps
