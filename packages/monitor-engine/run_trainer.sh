#!/bin/bash
# run_trainer.sh — bdZinho MATRIX 3.0 Nightly Trainer
# Executado pelo cron dentro do container ocme-monitor
# Cron: 0 3 * * * (03:00 UTC = 00:00 BRT)

set -e

LOG_FILE="/app/data/trainer_$(date +%Y%m%d).log"

echo "=== bdZinho MATRIX 3.0 Trainer ===" | tee -a "$LOG_FILE"
echo "Data: $(date -u '+%Y-%m-%dT%H:%M:%SZ')" | tee -a "$LOG_FILE"

cd /app

python webdex_ai_trainer.py --days 3 2>&1 | tee -a "$LOG_FILE"

echo "=== Concluído ===" | tee -a "$LOG_FILE"

# Mantém apenas últimos 7 logs
ls -t /app/data/trainer_*.log 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
