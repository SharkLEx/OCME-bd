#!/bin/bash
# vault-backup.sh — Backup do vault Obsidian para git + Cloudflare R2
#
# Deploy no VPS: scp bin/vault-backup.sh root@76.13.100.67:/opt/scripts/vault-backup.sh
# Permissao: chmod +x /opt/scripts/vault-backup.sh
# Cron (3h da manha, horario UTC): 0 3 * * * /opt/scripts/vault-backup.sh >> /var/log/vault-backup.log 2>&1
#
# Dependencias:
#   - git configurado no VPS com acesso ao repo webdex-vault-backup
#   - gh CLI ou deploy key SSH para push ao GitHub
#   - rclone (opcional) para sync com Cloudflare R2
#
# Configuracao inicial no VPS (uma vez):
#   git clone git@github.com:SharkLEx/webdex-vault-backup.git /opt/vault-backup-git
#   cd /opt/vault-backup-git && git config user.email "devops@webdex.app"
#   cd /opt/vault-backup-git && git config user.name "WEbdEX Backup Bot"

set -euo pipefail

# ─── CONFIG ────────────────────────────────────────────────────────────────────

VAULT_PATH="/opt/vault"
BACKUP_REPO="/opt/vault-backup-git"
LOG_FILE="/var/log/vault-backup.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
DATE_TAG=$(date '+%Y-%m-%d %H:%M')

# ─── FUNCOES ───────────────────────────────────────────────────────────────────

log() {
  echo "[${TIMESTAMP}] $*" | tee -a "$LOG_FILE"
}

die() {
  log "ERROR: $*"
  exit 1
}

# ─── PRE-CHECKS ────────────────────────────────────────────────────────────────

log "=== vault-backup.sh iniciando ==="

[[ -d "$VAULT_PATH" ]] || die "Vault nao encontrado em $VAULT_PATH"
[[ -d "$BACKUP_REPO" ]] || die "Repo de backup nao encontrado em $BACKUP_REPO — execute: git clone git@github.com:SharkLEx/webdex-vault-backup.git $BACKUP_REPO"
[[ -d "$BACKUP_REPO/.git" ]] || die "$BACKUP_REPO nao e um repositorio git"

# ─── STEP 1: SINCRONIZAR VAULT → BACKUP REPO ──────────────────────────────────

log "Sincronizando vault para $BACKUP_REPO ..."

# Copiar apenas arquivos .md (ignorar .obsidian, plugins, cache)
rsync -av --delete \
  --include="*/" \
  --include="*.md" \
  --exclude="*" \
  "$VAULT_PATH/" "$BACKUP_REPO/" \
  --log-file="$LOG_FILE" \
  2>&1 | tail -5

log "Sync rsync concluido"

# ─── STEP 2: GIT COMMIT + PUSH ─────────────────────────────────────────────────

cd "$BACKUP_REPO"

# Verificar se ha mudancas antes de commitar
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  log "Nenhuma mudanca detectada no vault — backup git pulado"
else
  log "Mudancas detectadas, commitando..."

  git add -A

  CHANGED_COUNT=$(git status --short | wc -l | tr -d ' ')
  git commit -m "backup: ${DATE_TAG} (${CHANGED_COUNT} arquivos)" \
    || log "WARN: git commit falhou (possivel conflito) — continuando"

  log "Fazendo push para origin/main ..."
  git push origin main \
    && log "Git push concluido com sucesso" \
    || log "WARN: git push falhou — verificar credenciais SSH/deploy key"
fi

# ─── STEP 3: BACKUP PARA CLOUDFLARE R2 (OPCIONAL) ────────────────────────────

if command -v rclone &> /dev/null; then
  # Verificar se o remote r2 esta configurado
  if rclone listremotes 2>/dev/null | grep -q "^r2:"; then
    log "rclone encontrado com remote r2 — iniciando sync para R2 ..."

    rclone sync "$VAULT_PATH" r2:webdex-vault-backup/ \
      --include="*.md" \
      --log-file="$LOG_FILE" \
      --log-level INFO \
      2>&1

    log "rclone sync R2 concluido"
  else
    log "rclone encontrado mas remote 'r2' nao configurado — sync R2 pulado"
    log "Para configurar: rclone config (adicionar remote tipo 's3' com provider 'Cloudflare')"
  fi
else
  log "rclone nao instalado — backup R2 pulado (apenas git ativo)"
  log "Para instalar rclone: curl https://rclone.org/install.sh | sudo bash"
fi

# ─── STEP 4: RELATORIO FINAL ──────────────────────────────────────────────────

NOTE_COUNT=$(find "$VAULT_PATH" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
REPO_SIZE=$(du -sh "$BACKUP_REPO" 2>/dev/null | cut -f1)

log "=== Backup concluido: ${NOTE_COUNT} notas, repo ${REPO_SIZE} ==="
log ""
