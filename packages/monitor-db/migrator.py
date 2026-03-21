"""
monitor-db · Migrator
=====================
Aplica migrations SQL numeradas de forma idempotente.

Uso:
    from monitor_db.migrator import Migrator
    m = Migrator("path/to/db.sqlite")
    m.migrate()          # aplica apenas migrations pendentes
    print(m.status())    # dict com versão atual e pendentes
"""

from __future__ import annotations

import os
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Colunas opcionais que podem não existir em DBs antigos → aplicar via ALTER TABLE
_OPTIONAL_COLUMNS: List[Tuple[str, str, str]] = [
    # (tabela, coluna, definição SQL)
    ("operacoes", "ambiente",      "TEXT DEFAULT 'UNKNOWN'"),
    ("operacoes", "fee",           "REAL DEFAULT 0.0"),
    ("operacoes", "strategy_addr", "TEXT DEFAULT ''"),
    ("operacoes", "bot_id",        "TEXT DEFAULT ''"),
    ("operacoes", "gas_protocol",  "REAL DEFAULT 0.0"),
    ("operacoes", "gas_pol",       "REAL DEFAULT 0"),
    ("users",     "sub_filter",    "TEXT"),
    ("users",     "last_seen_ts",  "REAL"),
    ("users",     "username",      "TEXT"),
    ("users",     "capital_hint",  "REAL"),
    ("users",     "created_at",    "TEXT"),
    ("users",     "updated_at",    "TEXT"),
    ("fl_snapshots", "total_usd",  "REAL DEFAULT 0"),
    ("institutional_snapshots", "created_at", "TEXT"),
    ("institutional_snapshots", "env_json",   "TEXT"),
    ("institutional_snapshots", "token_json", "TEXT"),
]


class Migrator:
    """Gerencia migrations versionadas para o DB do OCME."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    # ── conexão ──────────────────────────────────────────────────────────────
    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── versão atual ─────────────────────────────────────────────────────────
    def _ensure_version_table(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _schema_version (
                version    INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)
        conn.commit()

    def current_version(self) -> int:
        conn = self._get_conn()
        self._ensure_version_table(conn)
        row = conn.execute(
            "SELECT MAX(version) FROM _schema_version"
        ).fetchone()
        return int(row[0] or 0)

    # ── migrations disponíveis ────────────────────────────────────────────────
    def available_migrations(self) -> List[Tuple[int, Path]]:
        """Retorna [(versão, path)] ordenado, baseado em arquivos 00N_*.sql."""
        result = []
        for p in sorted(MIGRATIONS_DIR.glob("*.sql")):
            try:
                version = int(p.stem.split("_")[0])
                result.append((version, p))
            except ValueError:
                continue
        return result

    def pending_migrations(self) -> List[Tuple[int, Path]]:
        cur = self.current_version()
        return [(v, p) for v, p in self.available_migrations() if v > cur]

    # ── aplicar migrations ────────────────────────────────────────────────────
    def _apply_optional_columns(self, conn: sqlite3.Connection):
        """Garante colunas opcionais em tabelas existentes (ALTER TABLE seguro)."""
        for table, col, coldef in _OPTIONAL_COLUMNS:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coldef}")
                logger.info("[migrator] ALTER TABLE %s ADD COLUMN %s", table, col)
            except sqlite3.OperationalError:
                pass  # coluna já existe — ok

    def migrate(self) -> int:
        """
        Aplica todas as migrations pendentes.
        Retorna número de migrations aplicadas.
        """
        conn = self._get_conn()
        self._ensure_version_table(conn)
        self._apply_optional_columns(conn)

        pending = self.pending_migrations()
        if not pending:
            logger.info("[migrator] DB up-to-date (version %d)", self.current_version())
            return 0

        applied = 0
        for version, path in pending:
            sql = path.read_text(encoding="utf-8")
            logger.info("[migrator] Aplicando migration %03d: %s", version, path.name)
            try:
                # Executa cada statement separadamente (executescript não suporta params)
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    if stmt and not stmt.startswith("--"):
                        conn.execute(stmt)
                conn.execute(
                    "INSERT OR REPLACE INTO _schema_version (version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit()
                applied += 1
                logger.info("[migrator] ✅ Migration %03d aplicada.", version)
            except Exception as e:
                conn.rollback()
                logger.error("[migrator] ❌ Falha na migration %03d: %s", version, e)
                raise RuntimeError(f"Migration {version} falhou: {e}") from e

        return applied

    # ── status ────────────────────────────────────────────────────────────────
    def status(self) -> dict:
        cur = self.current_version()
        available = self.available_migrations()
        pending = self.pending_migrations()
        return {
            "db_path": self.db_path,
            "current_version": cur,
            "available": len(available),
            "pending": len(pending),
            "pending_versions": [v for v, _ in pending],
            "up_to_date": len(pending) == 0,
        }
