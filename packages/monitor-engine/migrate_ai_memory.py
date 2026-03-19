"""
migrate_ai_memory.py — Story 12.1: Migração de memória IA do SQLite → PostgreSQL
Executar no VPS ANTES do deploy do novo código.

Uso:
    python migrate_ai_memory.py [--dry-run]

    --dry-run: mostra o que seria migrado sem escrever no PostgreSQL
"""
from __future__ import annotations

import os
import sys
import json
import shutil
import sqlite3
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_ai_memory")

DRY_RUN = "--dry-run" in sys.argv
DB_PATH = os.environ.get("OCME_DB_PATH", os.environ.get("DB_PATH", "webdex_v5_final.db"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def run():
    if not os.path.exists(DB_PATH):
        logger.error("SQLite não encontrado: %s", DB_PATH)
        sys.exit(1)

    if not DATABASE_URL:
        logger.error("DATABASE_URL não configurada")
        sys.exit(1)

    # ── 1. Backup do SQLite ──────────────────────────────────────────────────
    backup_path = DB_PATH + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not DRY_RUN:
        shutil.copy2(DB_PATH, backup_path)
        logger.info("Backup criado: %s", backup_path)
    else:
        logger.info("[DRY-RUN] Backup seria criado em: %s", backup_path)

    # ── 2. Ler dados do SQLite ───────────────────────────────────────────────
    sqlite_conn = sqlite3.connect(DB_PATH)
    try:
        cur = sqlite_conn.cursor()
        cur.execute("SELECT key, value FROM config WHERE key LIKE 'ai_mem_%'")
        rows = cur.fetchall()
    finally:
        sqlite_conn.close()

    logger.info("Encontrados %d registros ai_mem_* no SQLite", len(rows))

    if not rows:
        logger.info("Nada a migrar.")
        return

    # ── 3. Parsear e validar ─────────────────────────────────────────────────
    records = []  # list of (chat_id, role, content)
    for key, value in rows:
        if not value:
            continue
        chat_id = key.replace("ai_mem_", "")
        try:
            chat_id = int(chat_id)
        except ValueError:
            logger.warning("chat_id inválido: %s — ignorando", key)
            continue
        try:
            msgs = json.loads(value)
            if not isinstance(msgs, list):
                continue
            for msg in msgs:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role and content:
                    records.append((chat_id, role, content))
        except json.JSONDecodeError as e:
            logger.warning("JSON inválido para %s: %s — ignorando", key, e)

    logger.info("Total de mensagens a migrar: %d (em %d chats)", len(records), len(rows))

    if DRY_RUN:
        logger.info("[DRY-RUN] Mensagens que seriam inseridas no PostgreSQL:")
        by_chat: dict = {}
        for chat_id, role, content in records:
            by_chat.setdefault(chat_id, []).append(f"  [{role}] {content[:60]}...")
        for chat_id, msgs in by_chat.items():
            logger.info("  chat_id=%s (%d msgs)", chat_id, len(msgs))
        return

    # ── 4. Inserir no PostgreSQL ─────────────────────────────────────────────
    import psycopg2
    pg_conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    inserted = 0
    skipped = 0
    try:
        with pg_conn.cursor() as cur:
            for chat_id, role, content in records:
                try:
                    cur.execute(
                        """INSERT INTO ai_conversations (chat_id, platform, role, content)
                           VALUES (%s, 'telegram', %s, %s)""",
                        (chat_id, role, content)
                    )
                    inserted += 1
                except Exception as e:
                    logger.warning("Falha ao inserir chat_id=%s: %s", chat_id, e)
                    skipped += 1
        pg_conn.commit()
        logger.info("✅ Migração concluída: %d inseridos, %d pulados", inserted, skipped)
    except Exception as e:
        pg_conn.rollback()
        logger.error("❌ Falha na migração: %s — rollback executado", e)
        raise
    finally:
        pg_conn.close()

    logger.info("Backup SQLite disponível em: %s (NÃO deletar)", backup_path)
    logger.info("Para reverter: python rollback_ai_memory.py %s", backup_path)


if __name__ == "__main__":
    run()
