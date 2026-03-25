"""
webdex_ai_knowledge.py — bdZinho MATRIX 3.0 Knowledge Base
Epic MATRIX-3 | Story MATRIX-3.1

Base de conhecimento persistente do bdZinho em PostgreSQL.
Alimentada por agentes LMAS (Smith, Morpheus, Analyst, bdPro) via treino noturno.
Injetada no system prompt do bdZinho em cada conversa.

Categorias de conhecimento:
  protocol_patterns — padrões de operação do protocolo (séries de wins/loss, ciclos)
  user_insights     — perfis e comportamentos recorrentes dos usuários
  faq_knowledge     — perguntas frequentes com respostas refinadas
  smith_findings    — análises críticas e alertas (Agent Smith precision)
  daily_insights    — insights do ciclo 21h (performance, tendências)
  content_templates — templates de copy, posts, mensagens para o protocolo
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# ── Pool de conexão ────────────────────────────────────────────────────────────
_pool = None
_pool_lock = threading.Lock()

_CATEGORIES = frozenset({
    "protocol_patterns",
    "user_insights",
    "faq_knowledge",
    "smith_findings",
    "daily_insights",
    "content_templates",
})

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bdz_knowledge (
    id          BIGSERIAL PRIMARY KEY,
    category    TEXT    NOT NULL,
    topic       TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    source      TEXT    DEFAULT 'auto',
    confidence  REAL    DEFAULT 1.0,
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

_CREATE_INDEXES_SQL = [
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_bdz_knowledge_topic ON bdz_knowledge(category, topic);",
    "CREATE INDEX IF NOT EXISTS idx_bdz_knowledge_cat ON bdz_knowledge(category, active, updated_at DESC);",
]


# ── Connection pool ────────────────────────────────────────────────────────────

def _init_pool() -> bool:
    global _pool
    if _pool is not None:
        return True
    with _pool_lock:
        if _pool is not None:
            return True
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            logger.warning("[knowledge] DATABASE_URL não configurada — módulo inativo")
            return False
        try:
            import psycopg2.pool
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=3, dsn=db_url, connect_timeout=5
            )
            logger.info("[knowledge] Pool PostgreSQL inicializado")
            return True
        except Exception as e:
            logger.warning("[knowledge] Falha ao criar pool: %s", e)
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


def _ensure_table() -> bool:
    """Cria tabela e índices se não existirem."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
            for idx_sql in _CREATE_INDEXES_SQL:
                cur.execute(idx_sql)
        conn.commit()
        logger.info("[knowledge] Tabela bdz_knowledge OK")
        return True
    except Exception as e:
        conn.rollback()
        logger.warning("[knowledge] ensure_table falhou: %s", e)
        return False
    finally:
        _put_conn(conn)


# ── API pública ────────────────────────────────────────────────────────────────

def knowledge_upsert(
    category: str,
    topic: str,
    content: str,
    source: str = "auto",
    confidence: float = 1.0,
) -> bool:
    """
    Insere ou atualiza um item de conhecimento (UPSERT por category+topic).
    """
    if category not in _CATEGORIES:
        logger.warning("[knowledge] Categoria inválida: %s", category)
        return False

    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bdz_knowledge (category, topic, content, source, confidence, active, updated_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
                ON CONFLICT (category, topic)
                DO UPDATE SET
                    content    = EXCLUDED.content,
                    source     = EXCLUDED.source,
                    confidence = EXCLUDED.confidence,
                    active     = TRUE,
                    updated_at = NOW()
                """,
                (category, topic, content, source, confidence),
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.warning("[knowledge] upsert falhou (%s/%s): %s", category, topic, e)
        return False
    finally:
        _put_conn(conn)


def knowledge_get(category: Optional[str] = None, limit: int = 60) -> list[dict]:
    """Retorna itens de conhecimento ativos (opcionalmente filtrados por categoria)."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        with conn.cursor() as cur:
            if category:
                cur.execute(
                    """
                    SELECT category, topic, content, source, confidence, updated_at
                    FROM bdz_knowledge
                    WHERE active = TRUE AND category = %s
                    ORDER BY confidence DESC, updated_at DESC
                    LIMIT %s
                    """,
                    (category, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT category, topic, content, source, confidence, updated_at
                    FROM bdz_knowledge
                    WHERE active = TRUE
                    ORDER BY category, confidence DESC, updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
        return [
            {
                "category":   r[0],
                "topic":      r[1],
                "content":    r[2],
                "source":     r[3],
                "confidence": r[4],
                "updated_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("[knowledge] get falhou: %s", e)
        return []
    finally:
        _put_conn(conn)


def knowledge_deactivate(category: str, topic: str) -> bool:
    """Desativa um item (soft delete)."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE bdz_knowledge SET active = FALSE WHERE category = %s AND topic = %s",
                (category, topic),
            )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.warning("[knowledge] deactivate falhou: %s", e)
        return False
    finally:
        _put_conn(conn)


def knowledge_stats() -> dict:
    """Contagem de itens ativos por categoria."""
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT category, COUNT(*) AS total, MAX(updated_at) AS last_update
                FROM bdz_knowledge
                WHERE active = TRUE
                GROUP BY category
                ORDER BY category
                """
            )
            rows = cur.fetchall()
        return {
            r[0]: {
                "total":       r[1],
                "last_update": r[2].isoformat() if r[2] else None,
            }
            for r in rows
        }
    except Exception as e:
        logger.warning("[knowledge] stats falhou: %s", e)
        return {}
    finally:
        _put_conn(conn)


# ── Context builder — injeta no system prompt ─────────────────────────────────

_CATEGORY_LABELS = {
    "protocol_patterns": "PADRÕES DO PROTOCOLO",
    "user_insights":     "PERFIS DE USUÁRIO",
    "faq_knowledge":     "FAQ REFINADO",
    "smith_findings":    "ANÁLISES CRÍTICAS",
    "daily_insights":    "INSIGHTS RECENTES",
    "content_templates": "TEMPLATES DE CONTEÚDO",
}

# Limite de chars por categoria (evita context overflow)
_CAT_CHAR_LIMITS = {
    "protocol_patterns": 1200,
    "user_insights":     800,
    "faq_knowledge":     1500,
    "smith_findings":    1000,
    "daily_insights":    600,
    "content_templates": 1200,
}


def knowledge_build_context(include_categories: Optional[list[str]] = None) -> str:
    """
    Constrói bloco de texto para injeção no system prompt do bdZinho.
    Retorna string vazia se banco vazio ou indisponível.
    """
    cats = include_categories or [
        "protocol_patterns",
        "user_insights",
        "faq_knowledge",
        "smith_findings",
        "daily_insights",
    ]

    items = knowledge_get(limit=120)
    if not items:
        return ""

    by_cat: dict[str, list[dict]] = {}
    for item in items:
        if item["category"] in cats:
            by_cat.setdefault(item["category"], []).append(item)

    if not by_cat:
        return ""

    parts = [
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "INTELIGÊNCIA ACUMULADA (bdZinho MATRIX 3.0):",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for cat in cats:
        cat_items = by_cat.get(cat, [])
        if not cat_items:
            continue

        label = _CATEGORY_LABELS.get(cat, cat.upper())
        parts.append(f"\n{label}:")

        char_budget = _CAT_CHAR_LIMITS.get(cat, 800)
        used = 0
        for item in cat_items:
            line = f"• [{item['topic']}] {item['content']}"
            if used + len(line) > char_budget:
                break
            parts.append(line)
            used += len(line)

    return "\n".join(parts)


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def _bootstrap():
    if _init_pool():
        _ensure_table()


# Executa em background para não bloquear o import se o banco estiver lento
threading.Thread(target=_bootstrap, daemon=True).start()
