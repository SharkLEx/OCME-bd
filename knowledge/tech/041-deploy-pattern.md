---
type: knowledge
id: "041"
title: "Deploy Pattern OCME — Do Código ao VPS em Produção"
layer: L5-tech
tags: [tech, deploy, vps, docker, ssh, scp, producao, devops, pipeline]
links: ["040-tech-stack-ocme", "042-error-patterns", "038-fluxo-dev"]
---

# 041 — Deploy Pattern OCME

> **Ideia central:** O OCME deploy no VPS segue um padrão específico: SCP para /tmp → docker cp para container → restart. Nunca push direto para o container. Sempre verificar health após restart.

---

## Acesso ao VPS

```bash
# SSH
ssh user@76.13.100.67

# Containers ativos
docker ps
# → ocme-monitor       (web3 6.x, porta 9090)
# → orchestrator-discord (web3 7.x)
```

---

## Padrão de Deploy Completo

### Passo 1: Preparar arquivos localmente

```bash
# Na máquina de dev (Windows/WSL)
cd "C:\Users\Alex\ALex Gonzaga bd\packages\monitor-engine"

# Verificar que não há erros de sintaxe
python -m py_compile webdex_monitor.py
python -m py_compile webdex_ai.py
# ... etc
```

### Passo 2: SCP para /tmp no VPS

```bash
# Copiar apenas os arquivos modificados (mais rápido)
scp webdex_ai.py user@76.13.100.67:/tmp/
scp webdex_ai_proactive.py user@76.13.100.67:/tmp/
scp webdex_workers.py user@76.13.100.67:/tmp/

# Ou copiar pasta inteira (mais seguro para mudanças grandes)
scp -r packages/monitor-engine/ user@76.13.100.67:/tmp/monitor-engine/
```

### Passo 3: Docker cp para dentro do container

```bash
# SSH no VPS
ssh user@76.13.100.67

# Copiar arquivo específico
docker cp /tmp/webdex_ai.py ocme-monitor:/app/webdex_ai.py

# Ou copiar pasta (quando muitos arquivos mudaram)
docker cp /tmp/monitor-engine/. ocme-monitor:/app/
```

### Passo 4: Restart do container

```bash
docker restart ocme-monitor

# Aguardar ~10s para subir
sleep 10
```

### Passo 5: Health check

```bash
# Verificar se container está healthy
docker ps | grep ocme-monitor
# Status deve ser "Up X seconds" (não "Restarting")

# Verificar health endpoint
curl http://localhost:9090/health
# Esperado: {"status": "ok", ...}

# Verificar logs para erros de startup
docker logs ocme-monitor --tail=50
```

---

## Deploy do Nightly Trainer

O trainer roda como cron job no container às 00h:

```bash
# Verificar se o cron está configurado
docker exec ocme-monitor crontab -l
# → 0 0 * * * python /app/webdex_ai_trainer.py

# Rodar manualmente (para testar)
docker exec ocme-monitor python /app/webdex_ai_trainer.py

# Ver logs do último run
docker exec ocme-monitor cat /tmp/trainer_last_run.log
```

---

## Deploy de Variáveis de Ambiente

```bash
# Ver .env atual no container
docker exec ocme-monitor cat /app/.env

# Atualizar .env
scp .env user@76.13.100.67:/tmp/.env
ssh user@76.13.100.67 "docker cp /tmp/.env ocme-monitor:/app/.env"
ssh user@76.13.100.67 "docker restart ocme-monitor"
```

---

## Rollback Rápido

```bash
# Se o deploy quebrou algo, restaurar backup
docker exec ocme-monitor ls /app/backups/
# → webdex_ai.py.bak
# → webdex_monitor.py.bak

# Restaurar backup
docker exec ocme-monitor cp /app/backups/webdex_ai.py.bak /app/webdex_ai.py
docker restart ocme-monitor
```

**Boa prática:** Sempre fazer backup do arquivo antes de sobrescrever:

```bash
docker exec ocme-monitor cp /app/webdex_ai.py /app/backups/webdex_ai.py.bak
```

---

## Checklist de Deploy

```
Antes do deploy:
  [ ] Arquivos testados localmente (sem erro de sintaxe)
  [ ] Soft imports verificados (try/except em módulos opcionais)
  [ ] .env com todas as variáveis necessárias
  [ ] Backup do arquivo atual no container

Durante o deploy:
  [ ] SCP → /tmp/ (não direto no container)
  [ ] docker cp para o container
  [ ] docker restart

Após o deploy:
  [ ] docker ps (container subiu sem loop)
  [ ] curl :9090/health (endpoint respondendo)
  [ ] docker logs --tail=50 (sem errors críticos)
  [ ] Testar um comando no Telegram bot
```

---

## Problemas Comuns no Deploy

| Problema | Sintoma | Solução |
|---------|---------|---------|
| Container em loop | `Restarting (1)` no docker ps | `docker logs` para ver erro, corrigir + redeploy |
| Import error | `ModuleNotFoundError` nos logs | Verificar soft import, instalar dependência |
| .env incompleto | `KeyError` ou auth fail | Verificar todas as vars no .env |
| Porta não responde | `curl :9090/health` timeout | Container não subiu, ver logs |
| DB connection | `psycopg2.OperationalError` | Verificar DATABASE_URL no .env |

---

## Deploy do orchestrator-discord

Mesmo padrão, container diferente:

```bash
docker cp /tmp/arquivo.py orchestrator-discord:/app/arquivo.py
docker restart orchestrator-discord
# Health check diferente (sem endpoint HTTP, ver logs)
docker logs orchestrator-discord --tail=20
```

---

## Links

← [[040-tech-stack-ocme]] — A stack que está sendo deployada
← [[038-fluxo-dev]] — O fluxo de desenvolvimento que precede o deploy
→ [[042-error-patterns]] — O que pode dar errado em produção
