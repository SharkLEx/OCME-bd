---
type: knowledge
title: "Dev — Deploy Protocol: VPS, Docker e Hotswap"
tags:
  - dev
  - deploy
  - vps
  - docker
  - devops
created: 2026-03-26
source: operator-sensei
---

# Deploy Protocol: VPS, Docker e Hotswap

> Módulo 05 de 10 — Professor: Operator
> Como levar código novo ao VPS sem downtime.

---

## Acesso ao VPS

```bash
# SSH
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67

# Verificar containers rodando
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'

# Logs ao vivo
docker logs orchestrator-discord --tail=20 -f
docker logs ocme-monitor --tail=20 -f
```

---

## Dois Tipos de Deploy

### Tipo 1 — Hotswap (sem rebuild, mais rápido)
Usado quando: arquivo Python puro, sem novas dependências.

```bash
# 1. Copiar arquivo para VPS
scp -i ~/.ssh/ocme_vps_key arquivo.py root@76.13.100.67:/tmp/

# 2. Injetar no container + restart
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 \
  "docker cp /tmp/arquivo.py CONTAINER:/app/arquivo.py && \
   docker restart CONTAINER && echo 'OK'"

# Containers:
# orchestrator-discord  → /app/arquivo.py
# ocme-monitor          → /app/arquivo.py
```

**IMPORTANTE:** O hotswap se perde no próximo `docker compose up --build`. Para persistir, commitar o arquivo E fazer rebuild eventualmente.

### Tipo 2 — Rebuild (com novas dependências)
Usado quando: `requirements.txt` mudou, novo pacote Python, `Dockerfile` alterado.

```bash
# Para ocme-monitor:
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 "
  cd /opt/ocme-monitor/packages/monitor-engine
  git pull origin main
  docker compose build monitor
  docker compose up -d monitor
"

# Para orchestrator-discord:
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 "
  cd /app/orchestrator
  git pull origin main
  docker compose build discord
  docker compose up -d discord
"
```

---

## Localização dos docker-compose.yml

| Container | docker-compose.yml |
|-----------|-------------------|
| `orchestrator-discord` | `/app/orchestrator/docker-compose.yml` |
| `ocme-monitor` | `/opt/ocme-monitor/packages/monitor-engine/docker-compose.yml` |

---

## Variáveis de Ambiente Chave

Nunca hardcodar — sempre usar env vars:

| Var | Container | Uso |
|-----|-----------|-----|
| `DISCORD_BOT_TOKEN` | orchestrator-discord | Token do bot |
| `OPENROUTER_API_KEY` | orchestrator-discord | API de IA |
| `DATABASE_URL` | ambos | PostgreSQL connection string |
| `OCME_DB_PATH` | orchestrator-discord | `/ocme_data/webdex_v5_final.db` |
| `VAULT_PATH` | orchestrator-discord | `/ocme_data/vault` |
| `VAULT_LOCAL_PATH` | ocme-monitor | `/app/data/vault` |
| `DB_PATH` | ocme-monitor | `/app/data/webdex_v5_final.db` |
| `RPC_URL` | ocme-monitor | Alchemy Polygon (key 1) |
| `RPC_CAPITAL` | ocme-monitor | Alchemy Polygon (key 2) |

---

## Volume Compartilhado

```
monitor-engine_monitor_data (Docker named volume)
├── webdex_v5_final.db   ← SQLite principal (4.37M+ rows)
├── vault/               ← Vault Obsidian (59+ notas)
│   ├── knowledge/
│   ├── bdzinho/
│   ├── learned/         ← Notas auto-aprendidas pelo Nexo
│   └── ...
└── backups/             ← Backups diários do SQLite

# Mounts:
# ocme-monitor:          /app/data/ (leitura + escrita)
# orchestrator-discord:  /ocme_data/ (somente leitura)
```

---

## Deploy de Vault Notes

Para adicionar novas notas ao vault em produção:

```bash
# 1. Criar nota localmente em knowledge/
# 2. Copiar para VPS
scp -i ~/.ssh/ocme_vps_key minha-nota.md root@76.13.100.67:/tmp/

# 3. Injetar no volume via ocme-monitor (tem acesso rw)
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 \
  "docker cp /tmp/minha-nota.md ocme-monitor:/app/data/vault/SUBDIR/minha-nota.md"

# 4. vault_reader reindexará automaticamente (cache 60min)
# Para forçar reload imediato:
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 \
  "docker exec orchestrator-discord python3 -c \
  'import vault_reader; vault_reader._index._last_load=0; vault_reader._index.ensure_loaded(); \
   print(vault_reader.vault_status())'"
```

---

## Checklist de Deploy

Antes de fazer deploy em produção:

- [ ] Testado localmente (ou dry-run)
- [ ] Não quebra imports existentes (graceful degradation)
- [ ] Não tem segredos hardcoded
- [ ] Passou Smith review (CRITICAL issues = 0)
- [ ] Commit feito no submodule correto
- [ ] `docker logs CONTAINER --tail=20` mostra "Bot online" após restart

---

## Troubleshooting Comum

```bash
# Container não sobe após restart
docker logs orchestrator-discord --tail=50

# Erro de import Python
docker exec orchestrator-discord python3 -c "import arquivo_novo"

# Verificar variáveis de ambiente
docker exec orchestrator-discord env | grep VAULT

# Ver o que está montado
docker inspect orchestrator-discord --format '{{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}'

# Forçar recreate com novo env
docker compose up -d --force-recreate discord
```
