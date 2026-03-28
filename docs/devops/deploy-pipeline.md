---
type: guide
title: "CI/CD Deploy Pipeline — ocme-monitor"
tags:
  - devops
  - ci-cd
  - github-actions
  - vps
---

# Deploy Pipeline — ocme-monitor

## Como funciona

O workflow `.github/workflows/deploy-monitor.yml` realiza deploy automático do container `ocme-monitor` no VPS toda vez que há um push para `main` com mudanças em `packages/monitor-engine/**`.

### Sequência de steps

```
push → main (packages/monitor-engine/**)
  │
  ▼
1. Checkout repo (fetch-depth=2 para SHA do commit anterior)
  │
  ▼
2. SCP — copia arquivos .py e requirements.txt para
   /opt/ocme-monitor/packages/monitor-engine/
  │
  ▼
3. SSH — tag da imagem atual como rollback anchor
   → docker compose build --no-cache monitor
   → docker compose up -d --force-recreate monitor
  │
  ▼
4. Smoke test — polling a cada 5s por até 60s
   docker inspect --format='{{.State.Health.Status}}' ocme-monitor
   healthy → continua  |  timeout → FAIL
  │
  ├─ healthy ──────────────────────────────────────────────────────┐
  │                                                                │
  └─ falhou ──► 5. Rollback (imagem ocme-monitor:rollback)        │
                                                                   │
                                                           6. Telegram
                                                    ✅ OK  /  ❌ FALHOU
```

### Rollback automático

Antes do build, o pipeline salva a imagem atual com a tag `ocme-monitor:rollback`. Se o smoke test falhar, o step de rollback recria o container a partir dessa tag. O rollback **não** acontece se o build em si falhar (falha de compilação) — apenas se o container subir mas não passar no health check.

---

## Configuração dos Secrets no GitHub

Acesse: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valor | Onde encontrar |
|--------|-------|---------------|
| `VPS_HOST` | `76.13.100.67` | IP do VPS |
| `VPS_USER` | `root` | Usuário SSH |
| `VPS_SSH_KEY` | conteúdo de `~/.ssh/ocme_vps_key` | Chave privada RSA/Ed25519 |
| `VPS_PORT` | `22` | Porta SSH padrão |
| `TELEGRAM_BOT_TOKEN` | `123456:ABC...` | BotFather → token do bot |
| `TELEGRAM_OWNER_CHAT_ID` | `seu_chat_id` | `/getid` no bot ou Telegram API |

### Como copiar a chave SSH

```bash
# No terminal local — exibe o conteúdo da chave privada
cat ~/.ssh/ocme_vps_key
```

Cole **todo** o conteúdo (incluindo as linhas `-----BEGIN...` e `-----END...`) no campo do secret `VPS_SSH_KEY`.

### Verificar se os secrets estão corretos

Após configurar, acione o pipeline manualmente (ver seção abaixo). Se a conexão SSH falhar, o erro aparecerá no step "Build and restart container".

---

## Deploy manual via workflow_dispatch

1. Acesse: **GitHub repo → Actions → Deploy Monitor Engine to VPS**
2. Clique em **Run workflow**
3. Selecione o branch `main`
4. Marque **force_rebuild** se quiser forçar rebuild mesmo sem mudanças de código
5. Clique em **Run workflow**

O pipeline roda exatamente igual ao automático.

---

## Rollback manual

Se o rollback automático não funcionar ou você precisar voltar para uma versão específica:

### Opção 1 — Usar a imagem de rollback no VPS

```bash
ssh root@76.13.100.67
cd /opt/ocme-monitor/packages/monitor-engine

# Ver imagens disponíveis
docker images | grep ocme-monitor

# Recriar container com imagem de rollback
docker tag ocme-monitor:rollback ocme-monitor:current
docker compose up -d --force-recreate monitor
```

### Opção 2 — Fazer revert do commit e novo deploy

```bash
# No repositório local
git revert <commit-sha-do-deploy-quebrado>
git push origin main
# O pipeline dispara automaticamente com o revert
```

### Opção 3 — Deploy manual direto no VPS (sem pipeline)

```bash
ssh root@76.13.100.67
cd /opt/ocme-monitor/packages/monitor-engine

# Copiar arquivos manualmente (do seu terminal local)
# scp -i ~/.ssh/ocme_vps_key packages/monitor-engine/*.py root@76.13.100.67:/opt/ocme-monitor/packages/monitor-engine/

# Rebuild e restart
docker compose build --no-cache monitor
docker compose up -d --force-recreate monitor

# Verificar saúde
docker inspect --format='{{.State.Health.Status}}' ocme-monitor
```

---

## Verificação de saúde

O smoke test usa o healthcheck built-in do container:

```bash
# Checar manualmente no VPS
docker inspect --format='{{.State.Health.Status}}' ocme-monitor
# healthy | unhealthy | starting
```

O container define seu próprio healthcheck no `Dockerfile` ou `docker-compose.yml`. Se o status ficar em `starting` por mais de 60s, o pipeline falha e o rollback é ativado.

---

## Troubleshooting

| Sintoma | Provável causa | Solução |
|---------|---------------|---------|
| Step SCP falha com "permission denied" | Chave SSH incorreta ou usuário errado | Verificar `VPS_SSH_KEY` e `VPS_USER` |
| Build falha com "context deadline exceeded" | VPS lento ou timeout de rede | Aumentar `timeout-minutes` no workflow |
| Smoke test sempre falha | Container unhealthy por variável faltando | Verificar `.env` no VPS, checar `docker logs ocme-monitor` |
| Rollback não encontra imagem | Container nunca tinha rodado antes | Primeiro deploy não tem rollback — erro esperado |
| Telegram não notifica | Secret incorreto ou bot bloqueado | Testar `curl` manualmente com os tokens |

---

## Arquivos do pipeline

| Arquivo | Descrição |
|---------|-----------|
| `.github/workflows/deploy-monitor.yml` | Workflow principal |
| `packages/monitor-engine/docker-compose.yml` | Compose do container (VPS) |
| `docs/devops/deploy-pipeline.md` | Este documento |
