"""monitor-ai/ai_engine.py — Motor de IA Contextual do OCME.

v2: classify_intent integrado, memória persistente em SQLite, modelo atualizado.

Chama OpenAI / OpenRouter com contexto on-chain real do usuário.
Governança preservada: ai_global_enabled, ai_admin_only, ai_mode.

Standalone: sem dependência do monolito webdex_*.py.

Uso:
    from ai_engine import AIEngine

    engine = AIEngine(db_path="webdex_v5_final.db")
    reply = engine.answer(
        user_text="Quanto ganhei hoje?",
        wallet="0xabc...",
        chat_id=123456,
        period="24h",
    )
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from typing import Dict, List, Optional

import requests

from context_builder import ContextBuilder

logger = logging.getLogger("monitor-ai.ai_engine")

# Modelo padrão: claude-3.5-haiku — melhor custo-benefício para pt-BR financeiro
_DEFAULT_MODEL = "anthropic/claude-haiku-4-5"
_MEMORY_MAX = 12          # mensagens na memória deslizante
_MEMORY_TTL_HOURS = 24    # memória persiste 24h no SQLite


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _pretty_ai_text(s: str) -> str:
    """Converte markdown genérico em texto amigável para Telegram."""
    if not s:
        return ""
    s = s.replace("\r\n", "\n")
    try:
        import re as _re
        s = _re.sub(r"(\*\*|\*|`|^#{1,6}\s*)", "", s, flags=_re.M)
    except Exception:
        s = s.replace("**", "").replace("*", "").replace("`", "")
    s = re.sub(r"^\s*[-–•]\s+", "• ", s, flags=re.M)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


class AIEngine:
    """Motor de IA Contextual — injeta dados on-chain no system prompt.

    Governança (lida do DB):
        - ai_global_enabled: "1" / "0"
        - ai_admin_only:     "1" / "0"
        - ai_mode:           "full" / "restricted"

    Melhorias v2:
        - classify_intent() agora direciona o contexto antes de cada chamada
        - Memória persistente em SQLite (tabela ai_memory) — sobrevive a restarts
        - Modelo padrão: anthropic/claude-3-5-haiku-20241022
        - TVL e dados de liquidez dinâmicos via context_builder
    """

    def __init__(
        self,
        db_path: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._db_path = db_path
        self._ctx_builder = ContextBuilder(db_path)
        self._api_key = api_key or _env("OPENROUTER_API_KEY") or _env("OPENAI_API_KEY", "")
        self._base_url = base_url or _env("AI_BASE_URL", "https://openrouter.ai/api/v1")
        self._model = model or _env("OPENAI_MODEL", _DEFAULT_MODEL)

        if not self._api_key:
            logger.warning("[ai_engine] Nenhuma API key configurada — IA desabilitada")

        self._ensure_memory_table()

    # ── Schema ────────────────────────────────────────────────────────────
    def _ensure_memory_table(self):
        """Cria tabela ai_memory se não existir."""
        try:
            c = sqlite3.connect(self._db_path)
            c.execute("""
                CREATE TABLE IF NOT EXISTS ai_memory (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id    TEXT NOT NULL,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_ai_memory_chat ON ai_memory(chat_id, created_at)")
            c.commit()
            c.close()
        except Exception as e:
            logger.warning("[ai_engine] Não foi possível criar tabela ai_memory: %s", e)

    # ── Governança ────────────────────────────────────────────────────────
    def _get_config(self, key: str, default: str = "") -> str:
        try:
            c = sqlite3.connect(self._db_path)
            row = c.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
            c.close()
            return str(row[0]) if row else default
        except Exception:
            return default

    def is_enabled(self) -> bool:
        return self._get_config("ai_global_enabled", "1") == "1" and bool(self._api_key)

    def is_admin_only(self) -> bool:
        return self._get_config("ai_admin_only", "0") == "1"

    def _is_admin(self, chat_id: int) -> bool:
        try:
            c = sqlite3.connect(self._db_path)
            row = c.execute("SELECT 1 FROM users WHERE chat_id=? AND admin=1", (str(chat_id),)).fetchone()
            c.close()
            return row is not None
        except Exception:
            return False

    def _get_wallet(self, chat_id: int) -> Optional[str]:
        try:
            c = sqlite3.connect(self._db_path)
            row = c.execute(
                "SELECT wallet FROM users WHERE chat_id=? AND wallet<>'' AND wallet IS NOT NULL",
                (str(chat_id),)
            ).fetchone()
            c.close()
            return row[0] if row else None
        except Exception:
            return None

    # ── Memória persistente (SQLite) ──────────────────────────────────────
    def mem_add(self, chat_id: int, role: str, text: str):
        """Adiciona mensagem à memória persistente."""
        try:
            c = sqlite3.connect(self._db_path)
            c.execute(
                "INSERT INTO ai_memory (chat_id, role, content) VALUES (?, ?, ?)",
                (str(chat_id), role, text)
            )
            # Mantém apenas as últimas _MEMORY_MAX mensagens por chat
            c.execute("""
                DELETE FROM ai_memory WHERE id IN (
                    SELECT id FROM ai_memory WHERE chat_id=?
                    ORDER BY created_at DESC LIMIT -1 OFFSET ?
                )
            """, (str(chat_id), _MEMORY_MAX))
            c.commit()
            c.close()
        except Exception as e:
            logger.debug("[ai_engine] mem_add error: %s", e)

    def mem_get(self, chat_id: int) -> List[Dict]:
        """Recupera histórico recente do chat (últimas 24h, máx _MEMORY_MAX msgs)."""
        try:
            c = sqlite3.connect(self._db_path)
            cutoff = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(time.time() - _MEMORY_TTL_HOURS * 3600)
            )
            rows = c.execute("""
                SELECT role, content FROM ai_memory
                WHERE chat_id=? AND created_at >= ?
                ORDER BY created_at ASC LIMIT ?
            """, (str(chat_id), cutoff, _MEMORY_MAX)).fetchall()
            c.close()
            return [{"role": r[0], "content": r[1]} for r in rows]
        except Exception:
            return []

    def mem_clear(self, chat_id: int):
        """Limpa histórico do chat."""
        try:
            c = sqlite3.connect(self._db_path)
            c.execute("DELETE FROM ai_memory WHERE chat_id=?", (str(chat_id),))
            c.commit()
            c.close()
        except Exception as e:
            logger.debug("[ai_engine] mem_clear error: %s", e)

    # ── API call ──────────────────────────────────────────────────────────
    def _call_api(self, messages: List[Dict], timeout: int = 30) -> str:
        if not self._api_key:
            return "❌ IA não configurada — defina OPENROUTER_API_KEY ou OPENAI_API_KEY no .env"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter" in self._base_url.lower():
            headers["HTTP-Referer"] = "https://ocme.webdex.io"
            headers["X-Title"] = "OCME Intelligence"

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": 800,
            "temperature": 0.65,
        }

        try:
            resp = requests.post(
                f"{self._base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"]).strip()
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else "?"
            logger.error("[ai_engine] HTTP %s: %s", status, exc)
            if status == 401:
                return "🔒 API key inválida ou expirada. Configure OPENROUTER_API_KEY no .env"
            if status == 429:
                return "⏳ Rate limit da API. Tente novamente em alguns instantes."
            return f"❌ Erro de API ({status})"
        except requests.exceptions.Timeout:
            return "⏳ Timeout na API — tente novamente"
        except Exception as exc:
            logger.error("[ai_engine] call_api: %s", exc)
            return "❌ Erro ao conectar à IA — tente novamente"

    # ── Intent classification ─────────────────────────────────────────────
    def classify_intent(self, text: str) -> str:
        """Classifica intenção da pergunta para direcionar contexto correto."""
        t = text.lower().strip()
        checks = [
            (["resultado", "lucro", "perda", "ganho", "rendimento", "profit", "loss", "líquido", "ganhei", "perdi"], "resultado"),
            (["capital", "saldo", "quanto tenho", "patrimônio", "balance", "meu dinheiro"], "capital"),
            (["ciclo", "inatividade", "último trade", "frequência", "parado", "inativo"], "ciclo"),
            (["gas", "gás", "custo", "taxa", "fee", "pol", "gwei", "quanto paguei de gas"], "gas"),
            (["execução", "trade", "transação", "on-chain", "openposition", "operação"], "openposition"),
            (["ranking", "melhor", "pior", "top", "dashboard", "subconta"], "dashboard"),
            (["liquidez", "supply", "lp", "tvl", "pool", "lp-usd", "lp-usdt"], "liquidez"),
            (["tríade", "risco", "responsabilidade", "retorno", "vale a pena", "tríade"], "triade"),
            (["como funciona", "o que é", "me explica", "aprend", "educação", "ensina"], "educacao"),
            (["governança", "protocolo", "webdex", "token bd", "bd token"], "governance"),
        ]
        for keywords, intent in checks:
            if any(k in t for k in keywords):
                return intent
        return "general"

    # ── Main entry point ──────────────────────────────────────────────────
    def answer(
        self,
        user_text: str,
        chat_id: Optional[int] = None,
        wallet: Optional[str] = None,
        period: str = "24h",
        is_admin: bool = False,
        pretty: bool = True,
    ) -> str:
        """Processa pergunta do usuário e retorna resposta contextualizada.

        v2: classify_intent() direciona o contexto antes da chamada à API.

        Args:
            user_text: Texto enviado pelo usuário
            chat_id:   ID Telegram (para memória persistente e governança)
            wallet:    Endereço 0x (sobrescreve lookup por chat_id)
            period:    Período de análise (24h, 7d, 30d, ciclo)
            is_admin:  Override de permissão admin
            pretty:    Aplicar _pretty_ai_text() no resultado

        Returns:
            str com resposta da IA
        """
        if not self.is_enabled():
            return "🤖 IA desabilitada no momento."

        if self.is_admin_only() and not is_admin:
            if chat_id and not self._is_admin(chat_id):
                return "🔒 Acesso à IA restrito a administradores."

        # 1. Classifica intent ANTES de construir o contexto
        intent = self.classify_intent(user_text)
        logger.debug("[ai_engine] intent=%s user=%s", intent, chat_id)

        # 2. Resolve wallet
        effective_wallet = wallet
        if not effective_wallet and chat_id:
            effective_wallet = self._get_wallet(chat_id)

        # 3. Constrói contexto direcionado pelo intent
        ctx = self._ctx_builder.build(
            wallet=effective_wallet,
            period=period,
            intent=intent,
        )
        system_prompt = self._ctx_builder.to_system_prompt(ctx)

        # 4. Monta histórico persistente
        history = self.mem_get(chat_id) if chat_id else []
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-8:])
        messages.append({"role": "user", "content": user_text})

        # 5. Chama API
        reply = self._call_api(messages)

        # 6. Persiste na memória SQLite
        if chat_id and reply and not reply.startswith("❌"):
            self.mem_add(chat_id, "user", user_text)
            self.mem_add(chat_id, "assistant", reply)

        return _pretty_ai_text(reply) if pretty else reply
