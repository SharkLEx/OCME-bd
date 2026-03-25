"""
webdex_ai_user_profile.py — bdZinho MATRIX 4.0 Individual Memory
Epic MATRIX-4 | Story MATRIX-4.0

Perfil individual de cada trader — memória estruturada que o bdZinho usa para
personalizar CADA resposta com contexto específico do usuário.

Schema: bdz_user_profiles (PostgreSQL)
  chat_id          — identificador do usuário
  experience_level — 'iniciante' | 'intermediario' | 'avancado' | 'unknown'
  facts            — JSONB: fatos estruturados atualizados pelo trainer noturno
  summary          — texto natural injetado no system prompt (gerado pelo trainer)
  last_seen        — última vez que interagiu com o bot
  updated_at       — última atualização do perfil

Uso no brain prompt:
  context = profile_build_context(chat_id)
  → injeta no system prompt do bdZinho

Atualização:
  profile_update(chat_id, facts=..., summary=...) → chamado pelo trainer noturno
  profile_touch(chat_id) → chamado a cada mensagem (atualiza last_seen)
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# ── Connection pool (reusa padrão do projeto) ────────────────────────────────
_pool = None
_pool_lock = threading.Lock()


def _init_pool() -> bool:
    global _pool
    if _pool is not None:
        return True
    with _pool_lock:
        if _pool is not None:
            return True
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            logger.warning("[user_profile] DATABASE_URL não configurada — módulo inativo")
            return False
        try:
            import psycopg2.pool
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=3, dsn=db_url, connect_timeout=5
            )
            logger.info("[user_profile] Pool PostgreSQL inicializado")
            return True
        except Exception as e:
            logger.warning("[user_profile] Falha ao criar pool: %s", e)
            return False


def _get_conn():
    if _pool is None and not _init_pool():
        return None
    try:
        return _pool.getconn()
    except Exception:
        return None


def _put_conn(conn):
    if _pool and conn:
        try:
            _pool.putconn(conn)
        except Exception:
            pass


# ── DDL ──────────────────────────────────────────────────────────────────────

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS bdz_user_profiles (
    chat_id          BIGINT      PRIMARY KEY,
    platform         TEXT        NOT NULL DEFAULT 'telegram',
    experience_level TEXT        NOT NULL DEFAULT 'unknown',
    facts            JSONB       NOT NULL DEFAULT '{}',
    summary          TEXT        NOT NULL DEFAULT '',
    last_seen        TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_CREATE_IDX = (
    "CREATE INDEX IF NOT EXISTS idx_bdz_profiles_updated ON bdz_user_profiles(updated_at DESC);",
)


def _ensure_table() -> bool:
    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_SQL)
            for idx in _CREATE_IDX:
                cur.execute(idx)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.warning("[user_profile] ensure_table falhou: %s", e)
        return False
    finally:
        _put_conn(conn)


# ── Cache em RAM (TTL 10 min) ─────────────────────────────────────────────────
import time as _time

_cache: dict[int, tuple[dict, float]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 600  # 10 minutos


def _cache_get(chat_id: int) -> Optional[dict]:
    with _cache_lock:
        entry = _cache.get(chat_id)
        if entry and (_time.time() - entry[1]) < _CACHE_TTL:
            return entry[0]
    return None


def _cache_set(chat_id: int, profile: dict):
    with _cache_lock:
        _cache[chat_id] = (profile, _time.time())


def _cache_invalidate(chat_id: int):
    with _cache_lock:
        _cache.pop(chat_id, None)


# ── API pública ───────────────────────────────────────────────────────────────

def profile_get(chat_id: int) -> dict:
    """
    Retorna perfil do usuário. Usa cache em RAM (10 min TTL).
    Retorna dict vazio se usuário não tem perfil ainda.
    """
    cached = _cache_get(chat_id)
    if cached is not None:
        return cached

    conn = _get_conn()
    if conn is None:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT experience_level, facts, summary, last_seen, updated_at
                FROM bdz_user_profiles
                WHERE chat_id = %s
                """,
                (chat_id,),
            )
            row = cur.fetchone()
        if not row:
            return {}
        profile = {
            "experience_level": row[0],
            "facts":            row[1] or {},
            "summary":          row[2] or "",
            "last_seen":        row[3].isoformat() if row[3] else None,
            "updated_at":       row[4].isoformat() if row[4] else None,
        }
        _cache_set(chat_id, profile)
        return profile
    except Exception as e:
        logger.warning("[user_profile] get falhou (chat_id=%s): %s", chat_id, e)
        return {}
    finally:
        _put_conn(conn)


def profile_update(
    chat_id: int,
    experience_level: Optional[str] = None,
    facts: Optional[dict] = None,
    summary: Optional[str] = None,
    platform: str = "telegram",
) -> bool:
    """
    Insere ou atualiza o perfil do usuário (UPSERT).
    Chamado pelo trainer noturno com os dados extraídos pelo LLM.
    """
    conn = _get_conn()
    if conn is None:
        return False
    try:
        # Merge de facts com o existente (não sobrescreve tudo)
        facts_json = json.dumps(facts or {})
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bdz_user_profiles
                    (chat_id, platform, experience_level, facts, summary, updated_at)
                VALUES (%s, %s,
                    COALESCE(%s, 'unknown'),
                    %s::jsonb,
                    COALESCE(%s, ''),
                    NOW()
                )
                ON CONFLICT (chat_id) DO UPDATE SET
                    experience_level = COALESCE(EXCLUDED.experience_level, bdz_user_profiles.experience_level),
                    facts            = bdz_user_profiles.facts || EXCLUDED.facts,
                    summary          = CASE WHEN EXCLUDED.summary != '' THEN EXCLUDED.summary
                                            ELSE bdz_user_profiles.summary END,
                    updated_at       = NOW()
                """,
                (chat_id, platform, experience_level, facts_json, summary),
            )
        conn.commit()
        _cache_invalidate(chat_id)
        return True
    except Exception as e:
        conn.rollback()
        logger.warning("[user_profile] update falhou (chat_id=%s): %s", chat_id, e)
        return False
    finally:
        _put_conn(conn)


def profile_touch(chat_id: int) -> None:
    """
    Atualiza last_seen para agora. Assíncrono — não bloqueia.
    Chamado a cada mensagem do usuário.
    """
    def _do():
        conn = _get_conn()
        if conn is None:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bdz_user_profiles (chat_id, last_seen, updated_at)
                    VALUES (%s, NOW(), NOW())
                    ON CONFLICT (chat_id) DO UPDATE SET last_seen = NOW()
                    """,
                    (chat_id,),
                )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            _put_conn(conn)

    threading.Thread(target=_do, daemon=True).start()


def profile_build_context(chat_id: int) -> str:
    """
    Constrói bloco de texto para injeção no system prompt do bdZinho.
    Personaliza a resposta com quem o usuário é e como opera.
    Retorna string vazia se usuário não tem perfil.
    """
    profile = profile_get(chat_id)
    if not profile or (not profile.get("summary") and not profile.get("facts")):
        return ""

    parts = [
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "PERFIL INDIVIDUAL DESTE USUÁRIO (MATRIX 4.0):",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    lvl = profile.get("experience_level", "unknown")
    if lvl != "unknown":
        parts.append(f"Nível: {lvl}")

    summary = profile.get("summary", "").strip()
    if summary:
        parts.append(summary)

    facts = profile.get("facts", {})
    if facts:
        if facts.get("trading_style"):
            parts.append(f"Estilo de operação: {facts['trading_style']}")
        if facts.get("pain_points"):
            pts = ", ".join(facts["pain_points"][:3])
            parts.append(f"Dúvidas recorrentes: {pts}")
        if facts.get("strengths"):
            st = ", ".join(facts["strengths"][:3])
            parts.append(f"Pontos fortes identificados: {st}")

    parts.append(
        "USE este contexto para personalizar a resposta — "
        "trate como se conhecesse este trader há tempos."
    )

    return "\n".join(parts)


def profile_list_active(days: int = 7) -> list[int]:
    """
    Retorna chat_ids de usuários ativos nos últimos N dias.
    Usado pelo trainer noturno para saber quem atualizar.
    """
    conn = _get_conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chat_id FROM bdz_user_profiles
                WHERE last_seen >= NOW() - INTERVAL '%s days'
                ORDER BY last_seen DESC
                LIMIT 100
                """,
                (days,),
            )
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.warning("[user_profile] list_active falhou: %s", e)
        return []
    finally:
        _put_conn(conn)


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def _bootstrap():
    if _init_pool():
        _ensure_table()


threading.Thread(target=_bootstrap, daemon=True).start()
