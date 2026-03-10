# ==============================================================================
# monitor_db/migrator.py — Migrations versionadas e idempotentes
# OCME bd Monitor Engine — Story 7.3
# ==============================================================================
from __future__ import annotations

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger('monitor.db.migrator')

MIGRATIONS_DIR = Path(__file__).parent / 'migrations'

MIGRATION_FILES = [
    (1, '001_initial_schema.sql'),
    (2, '002_add_capital_tables.sql'),
    (3, '003_add_monitoring_tables.sql'),
]


def _ensure_version_table(conn: sqlite3.Connection) -> None:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS _schema_version (
            version   INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    ''')
    conn.commit()


def _get_current_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute('SELECT MAX(version) FROM _schema_version').fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def migrate(conn: sqlite3.Connection) -> int:
    '''Aplica migrations pendentes. Retorna número de migrations aplicadas.'''
    _ensure_version_table(conn)
    current = _get_current_version(conn)
    pending = [(v, f) for v, f in MIGRATION_FILES if v > current]

    if not pending:
        logger.debug('DB já está na versão mais recente (v%d)', current)
        return 0

    applied = 0
    for version, filename in pending:
        filepath = MIGRATIONS_DIR / filename
        if not filepath.exists():
            logger.error('Migration não encontrada: %s', filepath)
            raise FileNotFoundError(f'Migration file not found: {filepath}')

        sql = filepath.read_text(encoding='utf-8')
        try:
            conn.executescript(sql)
            conn.execute(
                'INSERT INTO _schema_version (version, applied_at) VALUES (?, datetime("now"))',
                (version,)
            )
            conn.commit()
            logger.info('Migration v%d aplicada: %s', version, filename)
            applied += 1
        except Exception as exc:
            logger.error('Falha na migration v%d (%s): %s', version, filename, exc)
            raise

    return applied


def get_version(conn: sqlite3.Connection) -> int:
    '''Retorna versão atual do schema.'''
    _ensure_version_table(conn)
    return _get_current_version(conn)
