#!/bin/bash
# ==============================================================================
# check.sh — Status do OCME Monitor Engine
#
# USO: ocme-check
# ==============================================================================

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
BOLD='\033[1m'; NC='\033[0m'

APP_DIR="/opt/ocme-monitor"

echo -e "\n${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     OCME bd Monitor Engine — Status                     ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}\n"

# Containers
echo -e "${BOLD}📦 Containers:${NC}"
cd "$APP_DIR/packages/monitor-engine" 2>/dev/null && \
    docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" || \
    echo "  (diretório não encontrado)"

# Health endpoint
echo -e "\n${BOLD}🏥 Health Check (localhost:9090/health):${NC}"
if HEALTH=$(curl -sf http://localhost:9090/health 2>/dev/null); then
    STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; h=json.load(sys.stdin); s=h.get('status','?'); v=h.get('vigia','?'); d=h.get('db','?'); r=h.get('rpc','?'); u=h.get('uptime_seconds',0); print(f'  status={s} | vigia={v} | db={d} | rpc={r} | uptime={u}s')" 2>/dev/null || echo "$HEALTH")
    if echo "$HEALTH" | grep -q '"status": "ok"'; then
        echo -e "  ${GREEN}✅ $STATUS${NC}"
    else
        echo -e "  ${YELLOW}⚠️  $STATUS${NC}"
    fi
else
    echo -e "  ${RED}❌ Endpoint não responde (container parado ou inicializando?)${NC}"
fi

# Métricas
echo -e "\n${BOLD}📊 Métricas (localhost:9090/metrics):${NC}"
if METRICS=$(curl -sf http://localhost:9090/metrics 2>/dev/null); then
    echo "$METRICS" | grep -E "^(vigia_blocks|vigia_ops|vigia_lag|vigia_loops|sentinela_alerts|vigia_uptime)" | \
        sed 's/^/  /'
else
    echo -e "  ${RED}❌ Não disponível${NC}"
fi

# DB size
echo -e "\n${BOLD}💾 Banco de dados:${NC}"
DB_PATH="/opt/ocme-data/webdex_v5_final.db"
if [[ -f "$DB_PATH" ]]; then
    echo -e "  ${GREEN}✅ $DB_PATH ($(du -sh "$DB_PATH" | cut -f1))${NC}"
else
    echo -e "  ${YELLOW}⚠️  DB ainda não existe (criado na primeira execução)${NC}"
fi

# Backups
echo -e "\n${BOLD}📂 Backups recentes:${NC}"
BACKUP_DIR="/opt/ocme-backups"
if [[ -d "$BACKUP_DIR" ]]; then
    COUNT=$(find "$BACKUP_DIR" -name "*.db" 2>/dev/null | wc -l)
    LATEST=$(ls -t "$BACKUP_DIR"/*.db 2>/dev/null | head -1)
    if [[ -n "$LATEST" ]]; then
        echo -e "  ${GREEN}$COUNT backup(s) — último: $(basename "$LATEST") ($(du -sh "$LATEST" | cut -f1))${NC}"
    else
        echo -e "  ${YELLOW}Nenhum backup ainda${NC}"
    fi
else
    echo -e "  ${YELLOW}Diretório de backup não existe${NC}"
fi

# Uso de recursos
echo -e "\n${BOLD}⚡ Recursos (container ocme-monitor):${NC}"
docker stats ocme-monitor --no-stream --format \
    "  CPU: {{.CPUPerc}} | MEM: {{.MemUsage}} | NET: {{.NetIO}}" 2>/dev/null || \
    echo -e "  ${RED}Container não está rodando${NC}"

# Últimas linhas de log
echo -e "\n${BOLD}📋 Últimas 10 linhas de log:${NC}"
docker logs ocme-monitor --tail 10 2>/dev/null | sed 's/^/  /' || \
    echo -e "  ${RED}Container não está rodando${NC}"

echo ""
echo -e "${BOLD}Comandos úteis:${NC}"
echo "  docker logs -f ocme-monitor          # logs em tempo real"
echo "  sudo ocme-update                     # atualizar código"
echo "  docker compose restart monitor       # reiniciar bot"
echo "  docker exec -it ocme-monitor bash    # entrar no container"
echo ""
