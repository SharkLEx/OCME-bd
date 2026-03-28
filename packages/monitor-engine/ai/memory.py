"""
webdex_ai_memory.py — Long-term Memory Manager para bdZinho
Story 12.1 | Epic 12 — bdZinho Intelligence v3

Gerencia memória de longo prazo do bdZinho via PostgreSQL com cache local (deque).
- Escrita assíncrona (não bloqueia resposta do bot)
- Graceful degradation se PostgreSQL indisponível
- Comando LGPD: delete_all(chat_id)
"""
from __future__ import annotations

import os
import json
import logging
import threading
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

# Tamanho do cache local (contexto imediato para OpenAI)
_CACHE_MAXLEN = 20
# Quantas mensagens carregar do PostgreSQL no cold start
_LOAD_LIMIT = 20

# Pool de conexões thread-safe (inicializado em _init_pool)
_pool = None
_pool_lock = threading.Lock()


def _init_pool() -> bool:
    """Inicializa connection pool psycopg2 (lazy, thread-safe)."""
    global _pool
    if _pool is not None:
        return True
    with _pool_lock:
        if _pool is not None:
            return True
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            logger.warning("[ai_memory] DATABASE_URL não configurada — modo degrade (deque only)")
            return False
        try:
            import psycopg2.pool
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=db_url,
                connect_timeout=5,
            )
            logger.info("[ai_memory] Pool PostgreSQL inicializado")
            return True
        except Exception as e:
            logger.warning("[ai_memory] Falha ao criar pool PostgreSQL: %s — modo degrade", e)
            return False


def _get_conn():
    """Retorna conexão do pool. Retorna None se pool indisponível."""
    if _pool is None and not _init_pool():
        return None
    try:
        return _pool.getconn()
    except Exception as e:
        logger.warning("[ai_memory] Falha ao obter conexão do pool: %s", e)
        return None


def _release_conn(conn) -> None:
    """Devolve conexão ao pool."""
    if _pool and conn:
        try:
            _pool.putconn(conn)
        except Exception:
            pass


class AIMemoryManager:
    """
    Gerencia memória de longo prazo de um usuário específico.

    Uso:
        mgr = AIMemoryManager(chat_id=123456789, platform='telegram')
        mgr.load_context()          # cold start — carrega do PostgreSQL
        mgr.append('user', 'texto')
        context = mgr.get_context() # passa para OpenAI
        mgr.delete_all()            # LGPD
    """

    def __init__(self, chat_id: int, platform: str = 'telegram'):
        self.chat_id = chat_id
        self.platform = platform
        self._cache: deque = deque(maxlen=_CACHE_MAXLEN)
        self._loaded = False

    # ── Carregamento ────────────────────────────────────────────────────────

    def load_context(self, n: int = _LOAD_LIMIT) -> None:
        """
        Carrega últimas N mensagens do PostgreSQL para o cache local.
        Silencioso se PostgreSQL indisponível (graceful degradation AC6).
        """
        conn = _get_conn()
        if conn is None:
            self._loaded = True
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT role, content
                       FROM ai_conversations
                       WHERE chat_id = %s AND platform = %s
                       ORDER BY created_at DESC
                       LIMIT %s""",
                    (self.chat_id, self.platform, n)
                )
                rows = cur.fetchall()
            # Inverter para ordem cronológica (DESC → ASC)
            for role, content in reversed(rows):
                self._cache.append({"role": role, "content": content})
            self._loaded = True
            if rows:
                logger.debug("[ai_memory] Carregadas %d msgs de chat_id=%s do PostgreSQL", len(rows), self.chat_id)
        except Exception as e:
            logger.warning("[ai_memory] Falha ao carregar contexto (chat_id=%s): %s", self.chat_id, e)
            self._loaded = True
        finally:
            _release_conn(conn)

    # ── Escrita ─────────────────────────────────────────────────────────────

    def append(self, role: str, content: str) -> None:
        """
        Adiciona mensagem ao cache local E persiste no PostgreSQL de forma assíncrona.
        Não bloqueia a resposta do bot.
        """
        self._cache.append({"role": role, "content": content})
        # Escrita assíncrona — não bloqueia
        t = threading.Thread(
            target=self._persist,
            args=(role, content),
            daemon=True,
        )
        t.start()

    def _persist(self, role: str, content: str) -> None:
        """Persiste uma mensagem no PostgreSQL (executa em thread separada)."""
        conn = _get_conn()
        if conn is None:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO ai_conversations (chat_id, platform, role, content)
                       VALUES (%s, %s, %s, %s)""",
                    (self.chat_id, self.platform, role, content)
                )
            conn.commit()
        except Exception as e:
            logger.warning("[ai_memory] Falha ao persistir msg (chat_id=%s): %s", self.chat_id, e)
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            _release_conn(conn)

    # ── Leitura ─────────────────────────────────────────────────────────────

    def get_context(self) -> list[dict]:
        """Retorna contexto atual (deque) para passar à OpenAI."""
        if not self._loaded:
            self.load_context()
        return list(self._cache)

    # ── LGPD ────────────────────────────────────────────────────────────────

    def delete_all(self) -> int:
        """
        Deleta TODAS as mensagens do usuário do PostgreSQL e limpa cache.
        Retorna quantidade de registros deletados.
        LGPD compliance — AC5.
        """
        self._cache.clear()
        conn = _get_conn()
        if conn is None:
            logger.warning("[ai_memory] PostgreSQL indisponível — cache limpo mas histórico não deletado")
            return 0
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM ai_conversations WHERE chat_id = %s AND platform = %s",
                    (self.chat_id, self.platform)
                )
                deleted = cur.rowcount
            conn.commit()
            logger.info("[ai_memory] LGPD: %d msgs deletadas para chat_id=%s", deleted, self.chat_id)
            return deleted
        except Exception as e:
            logger.error("[ai_memory] Falha ao deletar histórico (chat_id=%s): %s", self.chat_id, e)
            try:
                conn.rollback()
            except Exception:
                pass
            return 0
        finally:
            _release_conn(conn)


# ── Registry de instâncias por chat_id ──────────────────────────────────────

_managers: dict[int, AIMemoryManager] = {}
_managers_lock = threading.Lock()


def get_manager(chat_id: int, platform: str = 'telegram') -> AIMemoryManager:
    """
    Retorna (ou cria) instância de AIMemoryManager para o chat_id.
    Thread-safe. Carrega contexto do PostgreSQL na primeira chamada.
    """
    with _managers_lock:
        if chat_id not in _managers:
            mgr = AIMemoryManager(chat_id, platform)
            mgr.load_context()
            _managers[chat_id] = mgr
        return _managers[chat_id]


def mem_add_pg(chat_id: int, role: str, content: str, platform: str = 'telegram') -> None:
    """Wrapper compatível com a API antiga de webdex_ai.py."""
    get_manager(chat_id, platform).append(role, content)


def mem_get_pg(chat_id: int, platform: str = 'telegram') -> list[dict]:
    """Wrapper compatível com a API antiga de webdex_ai.py."""
    return get_manager(chat_id, platform).get_context()


def mem_delete_all_pg(chat_id: int, platform: str = 'telegram') -> int:
    """Wrapper para deleção LGPD. Retorna registros deletados."""
    with _managers_lock:
        mgr = _managers.pop(chat_id, None)
    if mgr:
        return mgr.delete_all()
    # Instância não estava em memória — deletar direto do PostgreSQL
    tmp = AIMemoryManager(chat_id, platform)
    return tmp.delete_all()
