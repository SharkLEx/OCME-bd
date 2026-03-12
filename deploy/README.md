# Deploy OCME Monitor Engine — VPS Ubuntu 20.04

## Pré-requisitos
- VPS Ubuntu 20.04 com acesso SSH root
- Mínimo: 1 vCPU, 1GB RAM, 20GB disco
- Portas: SSH (22) + Observability (9090)

---

## 1. Upload dos scripts para o VPS

Na sua máquina local:

```bash
# Upload do script de setup
scp deploy/setup_vps.sh root@SEU_IP:/root/

# (Opcional) Upload do DB local
scp packages/monitor-engine/webdex_v5_final.db root@SEU_IP:/tmp/
```

---

## 2. Executar setup completo no VPS

```bash
ssh root@SEU_IP
chmod +x setup_vps.sh
sudo bash setup_vps.sh
```

O script faz automaticamente:
- ✅ Atualiza o sistema (apt)
- ✅ Instala Docker + Docker Compose v2
- ✅ Cria usuário `ocme` dedicado
- ✅ Clona o repositório em `/opt/ocme-monitor`
- ✅ Configura `.env` (você preenche as variáveis)
- ✅ Migra o DB se encontrado em `/tmp/webdex_v5_final.db`
- ✅ Configura firewall UFW (SSH + 9090)
- ✅ Faz build da imagem Docker
- ✅ Inicia os containers
- ✅ Cria systemd service para auto-start no boot

---

## 3. Configurar o .env

Durante o setup, você será solicitado a preencher:

```bash
nano /opt/ocme-monitor/packages/monitor-engine/.env
```

Variáveis obrigatórias:

| Variável | Descrição |
|----------|-----------|
| `TELEGRAM_TOKEN` | Token do bot Telegram |
| `RPC_URL` | Alchemy Polygon Mainnet |
| `RPC_CAPITAL` | Alchemy dedicado para capital |
| `WALLET_ADDRESS` | Wallet principal monitorada |
| `ADMIN_USER_IDS` | Chat IDs dos admins (separados por vírgula) |
| `OWNER_CHAT_ID` | Chat ID do dono |
| `OPENAI_API_KEY` | OpenAI API key (para IA contextual) |

---

## 4. Verificar status

```bash
ocme-check
```

Ou manualmente:
```bash
# Containers
cd /opt/ocme-monitor/packages/monitor-engine
docker compose ps

# Logs em tempo real
docker logs -f ocme-monitor

# Health check
curl -s http://localhost:9090/health | python3 -m json.tool

# Métricas Prometheus
curl -s http://localhost:9090/metrics
```

---

## 5. Atualizar após novo deploy

```bash
sudo ocme-update
```

O script faz backup do DB, pull do código, rebuild e restart.

---

## 6. Migrar DB existente (produção local → VPS)

Da sua máquina local:
```bash
bash deploy/copy_db_to_vps.sh root@SEU_IP
```

---

## Arquitetura no VPS

```
/opt/ocme-monitor/          # código (git clone)
/opt/ocme-data/             # DB SQLite (persistente)
/opt/ocme-backups/          # backups diários do DB

Containers Docker:
  ocme-monitor   → bot + vigia + observability (:9090)
  ocme-backup    → backup diário automático do DB

Portas abertas:
  22    → SSH
  9090  → Observability (GET /health, GET /metrics)
```

---

## Comandos do dia a dia

```bash
ocme-check                              # status geral
ocme-update                             # atualizar código
docker logs -f ocme-monitor             # logs em tempo real
docker compose restart monitor          # reiniciar bot
docker exec -it ocme-monitor bash       # entrar no container
```

---

## Troubleshooting

**Bot não responde no Telegram:**
```bash
docker logs ocme-monitor --tail 50
# Checar TELEGRAM_TOKEN no .env
```

**Health retorna `vigia: not_running`:**
```bash
docker logs ocme-monitor | grep "vigia\|HEALTH\|loop"
# Aguardar 1-2 min para o vigia inicializar
```

**Erro de build Docker:**
```bash
cd /opt/ocme-monitor/packages/monitor-engine
docker compose build --no-cache --progress=plain
```

**DB corrompido:**
```bash
# Restaurar do backup
ls /opt/ocme-backups/
cp /opt/ocme-backups/webdex_YYYYMMDD_HHMM.db /opt/ocme-data/webdex_v5_final.db
docker compose restart monitor
```
