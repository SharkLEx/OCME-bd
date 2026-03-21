"""
rollback_ai_memory.py — Story 12.1: Rollback da migração IA
Restaura o backup do SQLite e opcionalmente limpa o PostgreSQL.

Uso:
    python rollback_ai_memory.py <backup_path> [--clear-pg]

    backup_path: caminho do arquivo .bak criado pelo migrate_ai_memory.py
    --clear-pg:  também deleta os dados migrados do PostgreSQL
"""
from __future__ import annotations

import os
import sys
import shutil
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rollback_ai_memory")

DB_PATH = os.environ.get("OCME_DB_PATH", os.environ.get("DB_PATH", "webdex_v5_final.db"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def run():
    if len(sys.argv) < 2:
        logger.error("Uso: python rollback_ai_memory.py <backup_path> [--clear-pg]")
        sys.exit(1)

    backup_path = sys.argv[1]
    clear_pg = "--clear-pg" in sys.argv

    if not os.path.exists(backup_path):
        logger.error("Backup não encontrado: %s", backup_path)
        sys.exit(1)

    # ── 1. Restaurar SQLite ──────────────────────────────────────────────────
    shutil.copy2(backup_path, DB_PATH)
    logger.info("✅ SQLite restaurado de %s → %s", backup_path, DB_PATH)

    # ── 2. Limpar PostgreSQL (opcional) ──────────────────────────────────────
    if clear_pg:
        if not DATABASE_URL:
            logger.warning("DATABASE_URL não configurada — PostgreSQL não limpo")
        else:
            try:
                import psycopg2
                pg_conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
                with pg_conn.cursor() as cur:
                    cur.execute("DELETE FROM ai_conversations WHERE platform = 'telegram'")
                    deleted = cur.rowcount
                pg_conn.commit()
                pg_conn.close()
                logger.info("✅ PostgreSQL limpo: %d registros deletados", deleted)
            except Exception as e:
                logger.error("❌ Falha ao limpar PostgreSQL: %s", e)

    logger.info("Rollback concluído. Reiniciar o container após verificar o banco.")


if __name__ == "__main__":
    run()
