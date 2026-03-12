#!/bin/bash
# ==============================================================================
# setup_vps.sh — OCME bd Monitor Engine — Setup Completo VPS
# Ubuntu 20.04 | Docker | OCME WEbdEX Bot
#
# USO:
#   1. Suba este arquivo para o VPS:
#        scp deploy/setup_vps.sh user@SEU_IP_VPS:~/
#   2. Execute no VPS:
#        chmod +x setup_vps.sh && sudo bash setup_vps.sh
# ==============================================================================

set -euo pipefail

# ── Cores ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERRO]${NC} $*"; exit 1; }
step()    { echo -e "\n${BOLD}${BLUE}▶ $*${NC}"; }

# ── Config ────────────────────────────────────────────────────────────────────
REPO_URL="https://github.com/SharkLEx/OCME-bd.git"
REPO_BRANCH="feat/epic-7-monitor-engine"
APP_DIR="/opt/ocme-monitor"
DATA_DIR="/opt/ocme-data"
BACKUP_DIR="/opt/ocme-backups"
SERVICE_USER="ocme"

# ==============================================================================
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     OCME bd Monitor Engine — Deploy VPS                 ║${NC}"
echo -e "${BOLD}║     Ubuntu 20.04 + Docker                               ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Checar root ───────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    error "Execute com sudo: sudo bash $0"
fi

# ── 1. Atualizar sistema ───────────────────────────────────────────────────────
step "1/8 — Atualizando sistema"
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    curl wget git ca-certificates gnupg lsb-release \
    ufw fail2ban unattended-upgrades htop ncdu
success "Sistema atualizado"

# ── 2. Instalar Docker ─────────────────────────────────────────────────────────
step "2/8 — Instalando Docker"
if command -v docker &>/dev/null; then
    DOCKER_VER=$(docker --version)
    warn "Docker já instalado: $DOCKER_VER"
else
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" \
        | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    success "Docker instalado: $(docker --version)"
fi

# Docker Compose v2 (plugin)
if ! docker compose version &>/dev/null; then
    apt-get install -y -qq docker-compose-plugin
fi
success "Docker Compose: $(docker compose version)"

# ── 3. Criar usuário e diretórios ──────────────────────────────────────────────
step "3/8 — Criando usuário e diretórios"
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/bash -m -d /home/$SERVICE_USER $SERVICE_USER
    usermod -aG docker $SERVICE_USER
    success "Usuário '$SERVICE_USER' criado"
else
    warn "Usuário '$SERVICE_USER' já existe"
    usermod -aG docker $SERVICE_USER
fi

mkdir -p "$APP_DIR" "$DATA_DIR" "$BACKUP_DIR"
chown -R $SERVICE_USER:$SERVICE_USER "$APP_DIR" "$DATA_DIR" "$BACKUP_DIR"
chmod 750 "$APP_DIR" "$DATA_DIR"
chmod 750 "$BACKUP_DIR"
success "Diretórios criados: $APP_DIR, $DATA_DIR, $BACKUP_DIR"

# ── 4. Clonar repositório ──────────────────────────────────────────────────────
step "4/8 — Clonando repositório"
if [[ -d "$APP_DIR/.git" ]]; then
    warn "Repositório já existe — fazendo pull"
    cd "$APP_DIR"
    sudo -u $SERVICE_USER git fetch origin
    sudo -u $SERVICE_USER git checkout "$REPO_BRANCH"
    sudo -u $SERVICE_USER git pull origin "$REPO_BRANCH"
else
    sudo -u $SERVICE_USER git clone \
        --branch "$REPO_BRANCH" \
        --depth 1 \
        "$REPO_URL" "$APP_DIR"
fi
success "Código clonado em $APP_DIR"

# ── 5. Configurar .env ─────────────────────────────────────────────────────────
step "5/8 — Configurando .env"
ENV_TARGET="$APP_DIR/packages/monitor-engine/.env"

if [[ -f "$ENV_TARGET" ]]; then
    warn ".env já existe em $ENV_TARGET"
    warn "Se precisar atualizar: nano $ENV_TARGET"
else
    # Cria .env a partir do exemplo
    cp "$APP_DIR/packages/monitor-engine/.env.example" "$ENV_TARGET"
    chown $SERVICE_USER:$SERVICE_USER "$ENV_TARGET"
    chmod 600 "$ENV_TARGET"

    echo ""
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ⚠️  AÇÃO NECESSÁRIA: Configure o .env                  ║${NC}"
    echo -e "${YELLOW}╠══════════════════════════════════════════════════════════╣${NC}"
    echo -e "${YELLOW}║  nano $ENV_TARGET${NC}"
    echo -e "${YELLOW}║                                                          ║${NC}"
    echo -e "${YELLOW}║  Variáveis obrigatórias:                                 ║${NC}"
    echo -e "${YELLOW}║  • TELEGRAM_TOKEN=seu_token_aqui                        ║${NC}"
    echo -e "${YELLOW}║  • RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/... ║${NC}"
    echo -e "${YELLOW}║  • WALLET_ADDRESS=0x...                                 ║${NC}"
    echo -e "${YELLOW}║  • ADMIN_USER_IDS=seu_chat_id                           ║${NC}"
    echo -e "${YELLOW}║  • OWNER_CHAT_ID=seu_chat_id                            ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    read -rp "Pressione ENTER após configurar o .env (ou CTRL+C para configurar agora)..."
fi

# Ajusta DB_PATH para volume Docker
sed -i 's|^DB_PATH=.*|DB_PATH=/app/data/webdex_v5_final.db|' "$ENV_TARGET"
sed -i 's|^OCME_DB_PATH=.*|OCME_DB_PATH=/app/data/webdex_v5_final.db|' "$ENV_TARGET"

success ".env configurado"

# ── 6. Migrar DB existente (opcional) ─────────────────────────────────────────
step "6/8 — Migração do DB (opcional)"
LOCAL_DB="/tmp/webdex_v5_final.db"
VOLUME_DB="$DATA_DIR/webdex_v5_final.db"

if [[ -f "$LOCAL_DB" ]]; then
    cp "$LOCAL_DB" "$VOLUME_DB"
    chown $SERVICE_USER:$SERVICE_USER "$VOLUME_DB"
    success "DB migrado de $LOCAL_DB para $VOLUME_DB"
elif [[ -f "$VOLUME_DB" ]]; then
    warn "DB já existe em $VOLUME_DB ($(du -sh $VOLUME_DB | cut -f1))"
else
    info "DB não encontrado — será criado automaticamente na primeira execução"
    info "Para migrar DB existente: scp webdex_v5_final.db root@VPS:/opt/ocme-data/"
fi

# ── 7. Configurar firewall ─────────────────────────────────────────────────────
step "7/8 — Configurando firewall (UFW)"
ufw --force reset > /dev/null 2>&1
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 9090/tcp comment "OCME Observability (metrics/health)"
ufw --force enable
success "Firewall configurado (SSH + porta 9090)"
ufw status numbered

# ── 8. Build e iniciar containers ─────────────────────────────────────────────
step "8/8 — Build e start dos containers"
cd "$APP_DIR/packages/monitor-engine"

# Bind os diretórios de dados para os volumes Docker
# Sobrescreve volume paths via variável de ambiente
export DATA_DIR="$DATA_DIR"
export BACKUP_DIR="$BACKUP_DIR"

info "Fazendo build da imagem (pode demorar 2-5 min na primeira vez)..."
sudo -u $SERVICE_USER docker compose build --no-cache

info "Iniciando containers..."
sudo -u $SERVICE_USER docker compose up -d

success "Containers iniciados!"

# ── Criar systemd service para auto-start ─────────────────────────────────────
cat > /etc/systemd/system/ocme-monitor.service << EOF
[Unit]
Description=OCME bd Monitor Engine
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$SERVICE_USER
WorkingDirectory=$APP_DIR/packages/monitor-engine
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=120
TimeoutStopSec=30
Restart=no

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ocme-monitor.service
success "Systemd service criado e habilitado (auto-start no boot)"

# ── Copiar scripts de manutenção ───────────────────────────────────────────────
cp "$APP_DIR/deploy/update.sh" /usr/local/bin/ocme-update
cp "$APP_DIR/deploy/check.sh"  /usr/local/bin/ocme-check
chmod +x /usr/local/bin/ocme-update /usr/local/bin/ocme-check
success "Scripts instalados: ocme-update, ocme-check"

# ── Resumo final ────────────────────────────────────────────────────────────────
VPS_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅  OCME Monitor Engine — Deploy Completo!             ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Bot:      docker compose logs -f monitor               ║${NC}"
echo -e "${GREEN}║  Health:   http://${VPS_IP}:9090/health                  ║${NC}"
echo -e "${GREEN}║  Metrics:  http://${VPS_IP}:9090/metrics                 ║${NC}"
echo -e "${GREEN}║  Update:   sudo ocme-update                              ║${NC}"
echo -e "${GREEN}║  Status:   ocme-check                                    ║${NC}"
echo -e "${GREEN}║  Logs:     docker logs -f ocme-monitor                   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Status final
sleep 5
echo -e "${BOLD}Status dos containers:${NC}"
cd "$APP_DIR/packages/monitor-engine"
docker compose ps
