#!/bin/bash
# ==============================================================================
# copy_db_to_vps.sh — Copia o banco de dados SQLite para o VPS
#
# USO (rode na sua máquina local):
#   bash deploy/copy_db_to_vps.sh SEU_USUARIO@SEU_IP_VPS
#
# Exemplo:
#   bash deploy/copy_db_to_vps.sh root@192.168.1.100
# ==============================================================================

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }

VPS_TARGET="${1:-}"

if [[ -z "$VPS_TARGET" ]]; then
    echo "Uso: bash $0 usuario@ip_vps"
    echo "Exemplo: bash $0 root@192.168.1.100"
    exit 1
fi

# Encontra o DB local
DB_LOCAL="packages/monitor-engine/webdex_v5_final.db"
if [[ ! -f "$DB_LOCAL" ]]; then
    DB_LOCAL="webdex_v5_final.db"
fi
if [[ ! -f "$DB_LOCAL" ]]; then
    echo "DB não encontrado. Verifique o caminho."
    exit 1
fi

DB_SIZE=$(du -sh "$DB_LOCAL" | cut -f1)
info "DB local: $DB_LOCAL ($DB_SIZE)"

# Para o container no VPS antes de copiar
warn "Parando o bot no VPS para cópia segura..."
ssh "$VPS_TARGET" "cd /opt/ocme-monitor/packages/monitor-engine && docker compose stop monitor 2>/dev/null || true"

# Copia o DB
info "Copiando DB para o VPS..."
scp "$DB_LOCAL" "${VPS_TARGET}:/opt/ocme-data/webdex_v5_final.db"
success "DB copiado!"

# Reinicia o container
info "Reiniciando o bot..."
ssh "$VPS_TARGET" "cd /opt/ocme-monitor/packages/monitor-engine && docker compose start monitor"

success "Pronto! Bot reiniciado com o DB de produção."
info "Verifique: ssh $VPS_TARGET 'curl -s http://localhost:9090/health'"
