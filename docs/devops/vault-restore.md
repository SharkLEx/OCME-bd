---
type: guide
title: "Vault Obsidian — Procedimento de Restore"
tags:
  - devops
  - backup
  - vault
  - obsidian
  - restore
created: "2026-03-28"
owner: "@devops"
---

# Vault Obsidian — Procedimento de Restore

> **Objetivo:** Recuperar notas Obsidian perdidas ou corrompidas a partir dos backups git (GitHub) ou R2 (Cloudflare).

---

## Arquitetura de Backup

| Camada | Destino | Frequência | Responsável |
|--------|---------|-----------|-------------|
| Git | `github.com/SharkLEx/webdex-vault-backup` (privado) | Diário às 03:00 UTC | `vault-backup.sh` via cron |
| Objeto | Cloudflare R2 `webdex-vault-backup/` | Diário às 03:00 UTC | rclone (se configurado) |
| Local | `/opt/vault/` no VPS | Contínuo (vault ativo) | Obsidian sync / Docker volume |

---

## Setup Inicial (fazer uma vez)

### 1. Criar repositório de backup no GitHub

```bash
gh repo create SharkLEx/webdex-vault-backup --private --description "Backup vault Obsidian WEbdEX"
```

### 2. Configurar deploy key no VPS (sem senha para cron funcionar)

```bash
# No VPS
ssh-keygen -t ed25519 -C "vault-backup@vps" -f ~/.ssh/vault_backup_key -N ""
cat ~/.ssh/vault_backup_key.pub
```

Copiar a chave pública e adicionar no GitHub:
- Ir em `https://github.com/SharkLEx/webdex-vault-backup/settings/keys`
- Clicar em **Add deploy key**
- Titulo: `VPS vault-backup`
- Colar a chave pública
- Marcar **Allow write access**

### 3. Configurar SSH no VPS para usar deploy key

```bash
# No VPS — adicionar ao ~/.ssh/config
cat >> ~/.ssh/config << 'EOF'
Host github-vault-backup
  HostName github.com
  User git
  IdentityFile ~/.ssh/vault_backup_key
  IdentitiesOnly yes
EOF
```

### 4. Clonar o repositório de backup no VPS

```bash
git clone git@github-vault-backup:SharkLEx/webdex-vault-backup.git /opt/vault-backup-git
cd /opt/vault-backup-git
git config user.email "devops@webdex.app"
git config user.name "WEbdEX Backup Bot"
```

### 5. Fazer deploy do script de backup

```bash
# Na máquina local — copiar o script para o VPS
scp -i ~/.ssh/ocme_vps_key bin/vault-backup.sh root@76.13.100.67:/opt/scripts/vault-backup.sh
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 "chmod +x /opt/scripts/vault-backup.sh"
```

### 6. Configurar o cron job

```bash
# No VPS — abrir crontab
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 "crontab -e"

# Adicionar a linha:
0 3 * * * /opt/scripts/vault-backup.sh >> /var/log/vault-backup.log 2>&1
```

Verificar que o cron foi salvo:

```bash
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 "crontab -l | grep vault"
```

### 7. Testar o backup manualmente (primeiro run)

```bash
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 "/opt/scripts/vault-backup.sh"
tail -f /var/log/vault-backup.log
```

---

## Setup Cloudflare R2 (opcional — 10GB gratuito)

### Criar bucket R2

1. Acessar `https://dash.cloudflare.com` → R2 Object Storage
2. Criar bucket: `webdex-vault-backup`
3. Gerar API token: **Manage R2 API Tokens** → **Create API Token**
   - Permissões: **Object Read & Write**
   - Copiar **Access Key ID** e **Secret Access Key**
   - Copiar o **endpoint** (formato: `https://{account_id}.r2.cloudflarestorage.com`)

### Configurar rclone no VPS

```bash
# Instalar rclone
curl https://rclone.org/install.sh | sudo bash

# Configurar remote R2
rclone config create r2 s3 \
  provider Cloudflare \
  access_key_id SEU_ACCESS_KEY_ID \
  secret_access_key SEU_SECRET_ACCESS_KEY \
  endpoint https://SEU_ACCOUNT_ID.r2.cloudflarestorage.com \
  no_check_bucket true

# Testar
rclone ls r2:webdex-vault-backup/
```

---

## Cenário 1: Restaurar uma nota específica (do git)

**Quando usar:** Uma nota foi deletada acidentalmente ou corrompida.

```bash
# 1. Conectar ao VPS
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67

# 2. Ir ao repo de backup
cd /opt/vault-backup-git

# 3. Buscar a nota por nome (ex: nota sobre DAI)
git log --oneline --all -- "*dai*"
git log --oneline --all -- "knowledge/webdex/*.md"

# 4. Ver conteúdo da nota na versão mais recente do backup
git show HEAD:knowledge/webdex/056-dai-integration.md

# 5. Restaurar a nota para o vault ativo
git checkout HEAD -- knowledge/webdex/056-dai-integration.md
cp knowledge/webdex/056-dai-integration.md /opt/vault/knowledge/webdex/056-dai-integration.md

# 6. Verificar
ls -la /opt/vault/knowledge/webdex/056-dai-integration.md
head -20 /opt/vault/knowledge/webdex/056-dai-integration.md
```

---

## Cenário 2: Restaurar todas as notas (restore completo do git)

**Quando usar:** O vault inteiro foi corrompido ou deletado.

```bash
# 1. Conectar ao VPS
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67

# 2. Fazer backup do vault atual (mesmo corrompido — para referência)
cp -r /opt/vault /opt/vault-broken-$(date +%Y%m%d-%H%M%S) 2>/dev/null || true

# 3. Ir ao repo de backup e garantir que está atualizado
cd /opt/vault-backup-git
git pull origin main

# 4. Copiar todas as notas do backup para o vault ativo
rsync -av --include="*/" --include="*.md" --exclude="*" \
  /opt/vault-backup-git/ /opt/vault/

# 5. Contar notas restauradas
find /opt/vault -name "*.md" | wc -l

# 6. Verificar uma nota crítica (ex: MOC principal)
head -5 /opt/vault/MOC-Blockchain-Intelligence.md
```

---

## Cenário 3: Restaurar versão anterior de uma nota (git history)

**Quando usar:** Uma nota foi modificada mas a versão antiga era melhor.

```bash
# 1. No VPS, no repo de backup
cd /opt/vault-backup-git

# 2. Ver histórico de uma nota específica
git log --oneline -- knowledge/webdex/015-market-intelligence-Q1Q2-2026.md

# Exemplo de output:
# a3f2c19 backup: 2026-03-28 03:00 (2 arquivos)
# b1e4d82 backup: 2026-03-27 03:00 (0 arquivos)
# c9a1f05 backup: 2026-03-26 03:00 (5 arquivos)

# 3. Ver conteúdo em uma versão específica
git show b1e4d82:knowledge/webdex/015-market-intelligence-Q1Q2-2026.md | head -30

# 4. Restaurar a versão anterior
git checkout b1e4d82 -- knowledge/webdex/015-market-intelligence-Q1Q2-2026.md
cp knowledge/webdex/015-market-intelligence-Q1Q2-2026.md \
   /opt/vault/knowledge/webdex/015-market-intelligence-Q1Q2-2026.md

# 5. Reverter o checkout no backup (para não bagunçar o repo)
git checkout HEAD -- knowledge/webdex/015-market-intelligence-Q1Q2-2026.md
```

---

## Cenário 4: Restaurar do Cloudflare R2 (se rclone configurado)

**Quando usar:** Git não tem a versão necessária ou como segunda fonte.

```bash
# 1. No VPS — listar arquivos disponíveis no R2
rclone ls r2:webdex-vault-backup/ | head -20

# 2. Baixar uma nota específica do R2
rclone copy r2:webdex-vault-backup/knowledge/webdex/056-dai-integration.md \
  /opt/vault/knowledge/webdex/

# 3. Restore completo do R2 (sobrescreve vault ativo)
rclone sync r2:webdex-vault-backup/ /opt/vault/ --include="*.md"

# 4. Verificar contagem
find /opt/vault -name "*.md" | wc -l
```

---

## Teste de Restore (validação do procedimento)

Execute este teste após o setup inicial para confirmar que o backup funciona:

```bash
# 1. Conectar ao VPS
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67

# 2. Criar nota de teste no vault
echo "# Nota de Teste Backup\n\nCriada em: $(date)\nPropósito: validar restore" \
  > /opt/vault/test-backup-validation.md

# 3. Rodar o backup manualmente
/opt/scripts/vault-backup.sh

# 4. Verificar que a nota chegou ao GitHub
# (abrir https://github.com/SharkLEx/webdex-vault-backup no browser)
# ou via CLI:
cd /opt/vault-backup-git && git log --oneline -3

# 5. Deletar a nota do vault ativo (simular perda)
rm /opt/vault/test-backup-validation.md
ls /opt/vault/test-backup-validation.md 2>/dev/null || echo "Nota deletada com sucesso"

# 6. Restaurar do backup git
cd /opt/vault-backup-git
git checkout HEAD -- test-backup-validation.md
cp test-backup-validation.md /opt/vault/test-backup-validation.md

# 7. Verificar que o conteúdo está correto
cat /opt/vault/test-backup-validation.md

# 8. Limpar a nota de teste
rm /opt/vault/test-backup-validation.md
cd /opt/vault-backup-git && git rm test-backup-validation.md
git commit -m "chore: remover nota de teste de validação"
git push origin main

echo "Teste de restore CONCLUIDO — backup funcional"
```

---

## Monitoramento

### Verificar último backup

```bash
# No VPS
tail -50 /var/log/vault-backup.log

# Ver último commit no repo de backup
cd /opt/vault-backup-git && git log --oneline -5

# Contar notas no vault ativo vs backup
echo "Vault ativo:"; find /opt/vault -name "*.md" | wc -l
echo "Backup git:"; find /opt/vault-backup-git -name "*.md" | wc -l
```

### Verificar cron ativo

```bash
# No VPS
crontab -l | grep vault
# Deve retornar: 0 3 * * * /opt/scripts/vault-backup.sh >> /var/log/vault-backup.log 2>&1
```

### Alertas (opcional — via Telegram)

Adicionar no final de `vault-backup.sh` para notificar falhas:

```bash
# Adicionar ao vault-backup.sh (seção final)
if [ $? -ne 0 ]; then
  curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d "chat_id=${OWNER_CHAT_ID}" \
    -d "text=⚠️ vault-backup.sh FALHOU em $(date '+%Y-%m-%d %H:%M')" > /dev/null
fi
```

---

## Notas Importantes

- O cron roda às **03:00 UTC** (00:00 horário de Brasília) para não interferir com uso ativo
- O backup git inclui **apenas arquivos `.md`** — plugins, temas e configurações do Obsidian não são incluídos intencionalmente
- Se nenhuma nota mudou desde o último backup, o commit git é pulado automaticamente
- O vault ativo no VPS está em `/opt/vault/` (host) e também acessível via Docker volume nos containers
- O repo de backup `webdex-vault-backup` deve ser **privado** pois contém conhecimento estratégico
