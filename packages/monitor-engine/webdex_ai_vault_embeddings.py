"""
webdex_ai_vault_embeddings.py — Busca Semântica no Vault bdZinho

Story 23.1 — Epic 23: bdZinho Vault Intelligence

Gera e persiste embeddings das notas Obsidian usando sentence-transformers
(nomic-ai/nomic-embed-text-v1.5). Busca semântica via cosine similarity local.
Fallback gracioso para fulltext quando o modelo não estiver disponível.

Tabelas SQLite:
  vault_embeddings       — note_id, note_path, content_hash, embedding_blob, updated_at
  vault_queries_noresult — query, timestamp, top_score (para mapear lacunas de conhecimento)

Configuração (env vars):
  VAULT_LOCAL_PATH    — caminho do vault (default: /app/vault)
  EMBEDDING_MODEL     — modelo sentence-transformers (default: nomic-ai/nomic-embed-text-v1.5)
  EMBEDDING_FALLBACK  — modelo fallback menor (default: all-MiniLM-L6-v2)
  SIMILARITY_THRESHOLD — threshold mínimo de confiança (default: 0.65)
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
_VAULT_PATH       = Path(os.getenv("VAULT_LOCAL_PATH", "/app/vault"))
_EMBEDDING_MODEL  = os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
_FALLBACK_MODEL   = os.getenv("EMBEDDING_FALLBACK", "all-MiniLM-L6-v2")
_THRESHOLD        = float(os.getenv("SIMILARITY_THRESHOLD", "0.65"))
_DB_PATH          = os.getenv("DB_PATH") or os.getenv("WEbdEX_DB_PATH") or "webdex_v5_final.db"

# ─────────────────────────────────────────────────────────────────────────────
# SQLite — thread-local connections (mesmo padrão de webdex_db.py)
# ─────────────────────────────────────────────────────────────────────────────
_thread_local = threading.local()
_DB_WRITE_LOCK = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    """Retorna conexão thread-local para o DB, criando se necessário."""
    if not hasattr(_thread_local, "emb_conn") or _thread_local.emb_conn is None:
        c = sqlite3.connect(_DB_PATH, check_same_thread=False)
        c.execute("PRAGMA journal_mode=WAL")
        c.row_factory = sqlite3.Row
        _thread_local.emb_conn = c
    return _thread_local.emb_conn


# ─────────────────────────────────────────────────────────────────────────────
# DDL — criação de tabelas
# ─────────────────────────────────────────────────────────────────────────────
_DDL_VAULT_EMBEDDINGS = """
CREATE TABLE IF NOT EXISTS vault_embeddings (
    note_id        TEXT PRIMARY KEY,
    note_path      TEXT NOT NULL,
    content_hash   TEXT NOT NULL,
    embedding_blob TEXT NOT NULL,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_DDL_VAULT_QUERIES_NORESULT = """
CREATE TABLE IF NOT EXISTS vault_queries_noresult (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    query      TEXT NOT NULL,
    timestamp  TEXT NOT NULL DEFAULT (datetime('now')),
    top_score  REAL NOT NULL DEFAULT 0.0
);
"""


def _ensure_tables() -> None:
    """Cria tabelas se não existirem. Idempotente."""
    c = _get_conn()
    with _DB_WRITE_LOCK:
        c.execute(_DDL_VAULT_EMBEDDINGS)
        c.execute(_DDL_VAULT_QUERIES_NORESULT)
        c.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Modelo sentence-transformers (soft-load — graceful degradation)
# ─────────────────────────────────────────────────────────────────────────────
_model = None
_model_lock = threading.Lock()
_MODEL_AVAILABLE = False


def _load_model() -> bool:
    """
    Carrega o modelo sentence-transformers de forma lazy e thread-safe.
    Tenta o modelo principal; se falhar, tenta o fallback menor.
    Retorna True se modelo carregado com sucesso, False caso contrário.
    """
    global _model, _MODEL_AVAILABLE

    with _model_lock:
        if _model is not None:
            return True
        if _MODEL_AVAILABLE is False and _model is None:
            # Evitar re-tentativa desnecessária — só tenta uma vez por processo
            pass

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        with _model_lock:
            if _model is None:
                try:
                    logger.info("[vault-emb] Carregando modelo: %s", _EMBEDDING_MODEL)
                    _model = SentenceTransformer(_EMBEDDING_MODEL, trust_remote_code=True)
                    _MODEL_AVAILABLE = True
                    logger.info("[vault-emb] Modelo carregado: %s", _EMBEDDING_MODEL)
                except Exception as e:
                    logger.warning(
                        "[vault-emb] Falha ao carregar %s: %s — tentando fallback %s",
                        _EMBEDDING_MODEL, e, _FALLBACK_MODEL,
                    )
                    try:
                        _model = SentenceTransformer(_FALLBACK_MODEL)
                        _MODEL_AVAILABLE = True
                        logger.info("[vault-emb] Fallback model carregado: %s", _FALLBACK_MODEL)
                    except Exception as e2:
                        logger.error("[vault-emb] Fallback também falhou: %s", e2)
                        _MODEL_AVAILABLE = False
        return _MODEL_AVAILABLE
    except ImportError:
        logger.warning(
            "[vault-emb] sentence-transformers não instalado — "
            "busca semântica indisponível, usando fulltext como fallback."
        )
        return False


def is_embeddings_available() -> bool:
    """Verifica se embeddings estão disponíveis sem tentar carregar o modelo."""
    return _MODEL_AVAILABLE


# ─────────────────────────────────────────────────────────────────────────────
# Cosine Similarity — Python puro, sem numpy
# ─────────────────────────────────────────────────────────────────────────────

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Calcula cosine similarity entre dois vetores.
    Implementação pura em Python — sem dependências externas.
    Retorna float entre -1.0 e 1.0 (1.0 = idêntico, 0.0 = ortogonal).
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot   = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    return dot / (mag_a * mag_b)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de conteúdo
# ─────────────────────────────────────────────────────────────────────────────

def _content_hash(text: str) -> str:
    """SHA-256 do conteúdo da nota para detectar mudanças."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _note_id(note_path: Path) -> str:
    """ID estável para a nota baseado no path relativo ao vault."""
    try:
        rel = note_path.relative_to(_VAULT_PATH)
    except ValueError:
        rel = note_path
    return str(rel).replace("\\", "/")


def _read_note(note_path: Path) -> str:
    """Lê conteúdo de uma nota .md. Retorna string vazia em caso de erro."""
    try:
        return note_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.debug("[vault-emb] Erro ao ler nota %s: %s", note_path, e)
        return ""


def _embed_text(text: str) -> list[float]:
    """
    Gera embedding para um texto via sentence-transformers.
    Retorna lista de floats. Levanta RuntimeError se modelo indisponível.
    """
    if not _load_model():
        raise RuntimeError("Modelo de embeddings indisponível")
    # Prefixo recomendado pelo nomic-embed-text-v1.5 para search_document
    prefixed = f"search_document: {text}" if "nomic" in (_EMBEDDING_MODEL + "").lower() else text
    vec = _model.encode(prefixed, normalize_embeddings=True)
    return vec.tolist()


def _embed_query(query: str) -> list[float]:
    """
    Gera embedding para uma query de busca.
    Usa prefixo search_query (nomic recomenda distinguir doc vs query).
    """
    if not _load_model():
        raise RuntimeError("Modelo de embeddings indisponível")
    prefixed = f"search_query: {query}" if "nomic" in (_EMBEDDING_MODEL + "").lower() else query
    vec = _model.encode(prefixed, normalize_embeddings=True)
    return vec.tolist()


# ─────────────────────────────────────────────────────────────────────────────
# Persistência de embeddings
# ─────────────────────────────────────────────────────────────────────────────

def _save_embedding(note_path: Path, text: str, embedding: list[float]) -> None:
    """Persiste embedding no SQLite (upsert por note_id)."""
    nid   = _note_id(note_path)
    chash = _content_hash(text)
    blob  = json.dumps(embedding)
    now   = datetime.now(tz=timezone.utc).isoformat()

    c = _get_conn()
    with _DB_WRITE_LOCK:
        c.execute(
            """
            INSERT INTO vault_embeddings (note_id, note_path, content_hash, embedding_blob, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(note_id) DO UPDATE SET
                note_path      = excluded.note_path,
                content_hash   = excluded.content_hash,
                embedding_blob = excluded.embedding_blob,
                updated_at     = excluded.updated_at
            """,
            (nid, str(note_path), chash, blob, now),
        )
        c.commit()


def _get_stored_hash(note_path: Path) -> Optional[str]:
    """Retorna content_hash armazenado para a nota, ou None se não existir."""
    c = _get_conn()
    row = c.execute(
        "SELECT content_hash FROM vault_embeddings WHERE note_id = ?",
        (_note_id(note_path),),
    ).fetchone()
    return row["content_hash"] if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Log de queries sem resultado
# ─────────────────────────────────────────────────────────────────────────────

def _log_noresult(query: str, top_score: float) -> None:
    """Registra query que não atingiu o threshold de confiança."""
    c = _get_conn()
    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        with _DB_WRITE_LOCK:
            c.execute(
                "INSERT INTO vault_queries_noresult (query, timestamp, top_score) VALUES (?, ?, ?)",
                (query, now, top_score),
            )
            c.commit()
    except Exception as e:
        logger.debug("[vault-emb] Erro ao logar noresult: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# API Pública
# ─────────────────────────────────────────────────────────────────────────────

def generate_embeddings(notes_dir: Optional[Path] = None, force: bool = False) -> dict:
    """
    Processa todas as notas .md do vault e salva embeddings no SQLite.
    Incremental: só re-embeds notas cujo hash de conteúdo mudou.

    Args:
        notes_dir: diretório raiz do vault (default: _VAULT_PATH)
        force:     se True, re-embeds todas as notas independente de hash

    Returns:
        dict com estatísticas: {'processed': N, 'skipped': N, 'errors': N}
    """
    _ensure_tables()

    if not _load_model():
        logger.warning("[vault-emb] generate_embeddings: modelo indisponível — abortando")
        return {"processed": 0, "skipped": 0, "errors": 0, "available": False}

    root = notes_dir or _VAULT_PATH
    if not root.exists():
        logger.warning("[vault-emb] Vault não encontrado em %s", root)
        return {"processed": 0, "skipped": 0, "errors": 0, "available": False}

    notes = list(root.rglob("*.md"))
    stats = {"processed": 0, "skipped": 0, "errors": 0, "available": True}

    for note_path in notes:
        try:
            text = _read_note(note_path)
            if not text.strip():
                stats["skipped"] += 1
                continue

            stored_hash = _get_stored_hash(note_path)
            current_hash = _content_hash(text)

            if not force and stored_hash == current_hash:
                stats["skipped"] += 1
                continue

            embedding = _embed_text(text)
            _save_embedding(note_path, text, embedding)
            stats["processed"] += 1

        except Exception as e:
            logger.error("[vault-emb] Erro ao embedar %s: %s", note_path, e)
            stats["errors"] += 1

    logger.info(
        "[vault-emb] generate_embeddings concluído: %d processadas, %d puladas, %d erros",
        stats["processed"], stats["skipped"], stats["errors"],
    )
    return stats


def semantic_search(query: str, top_k: int = 3) -> list[dict]:
    """
    Busca semântica no vault por cosine similarity.

    Args:
        query:  texto da pergunta do usuário
        top_k:  número máximo de resultados a retornar

    Returns:
        Lista de dicts com chaves: note_path, note_id, score, content, low_confidence
        Retorna lista vazia se modelo indisponível (não levanta exceção — graceful).

    Comportamento de threshold:
        - score >= _THRESHOLD: resultado normal
        - score < _THRESHOLD:  resultado com flag low_confidence=True
        - query é logada em vault_queries_noresult se max score < _THRESHOLD
    """
    _ensure_tables()

    if not _load_model():
        logger.debug("[vault-emb] semantic_search: modelo indisponível — retornando []")
        return []

    c = _get_conn()
    rows = c.execute(
        "SELECT note_id, note_path, embedding_blob FROM vault_embeddings"
    ).fetchall()

    if not rows:
        logger.debug("[vault-emb] Nenhum embedding no banco — rode generate_embeddings() primeiro")
        return []

    try:
        query_vec = _embed_query(query)
    except Exception as e:
        logger.warning("[vault-emb] Erro ao embedar query: %s", e)
        return []

    scored: list[tuple[float, str, str]] = []  # (score, note_id, note_path)
    for row in rows:
        try:
            doc_vec = json.loads(row["embedding_blob"])
            score   = cosine_similarity(query_vec, doc_vec)
            scored.append((score, row["note_id"], row["note_path"]))
        except Exception:
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    if not top:
        return []

    max_score = top[0][0]
    if max_score < _THRESHOLD:
        _log_noresult(query, max_score)

    results: list[dict] = []
    for score, note_id, note_path_str in top:
        content = _read_note(Path(note_path_str))
        results.append({
            "note_id":        note_id,
            "note_path":      note_path_str,
            "score":          round(score, 4),
            "content":        content,
            "low_confidence": score < _THRESHOLD,
        })

    return results


def rebuild_changed_notes(notes_dir: Optional[Path] = None) -> dict:
    """
    Re-embeds apenas as notas cujo conteúdo mudou desde o último embed.
    Alias semântico de generate_embeddings(force=False).
    Usado pelo nightly worker.
    """
    return generate_embeddings(notes_dir=notes_dir, force=False)


# ─────────────────────────────────────────────────────────────────────────────
# Nightly Worker — registrado no webdex_main.py
# ─────────────────────────────────────────────────────────────────────────────
_WORKER_POLL_INTERVAL_S = 300   # checa a cada 5 minutos
_WORKER_RUN_HOUR_UTC    = 4     # janela de execução: 3h–7h UTC


def vault_embeddings_worker() -> None:
    """
    Worker nightly registrado no _THREAD_REGISTRY do webdex_main.py.
    Roda uma vez por dia (janela 3h–7h UTC) re-embeddando notas modificadas.
    Graceful: se modelo indisponível, dorme e retenta na próxima janela.
    """
    logger.info("[vault-emb] Worker iniciado — aguardando janela noturna (3h–7h UTC).")

    # Boot delay para evitar concorrência no startup
    time.sleep(90)

    last_run_date: Optional[str] = None

    while True:
        try:
            now_utc = datetime.now(tz=timezone.utc)
            today   = now_utc.strftime("%Y-%m-%d")
            in_window = 3 <= now_utc.hour < 7

            if in_window and last_run_date != today:
                logger.info("[vault-emb] Janela noturna — iniciando rebuild incremental (%s)", today)
                try:
                    stats = rebuild_changed_notes()
                    last_run_date = today
                    logger.info("[vault-emb] Rebuild concluído: %s", stats)
                except Exception as e:
                    logger.error("[vault-emb] Erro no rebuild: %s", e)

        except Exception as e:
            logger.error("[vault-emb] Erro no worker loop: %s", e)

        time.sleep(_WORKER_POLL_INTERVAL_S)
