"""
webdex_ai_proactive.py — bdZinho Proactive Mode
bdZinho ataca primeiro — envia mensagens proativas personalizadas baseadas no
perfil individual do trader + dados do ciclo 21h.

Triggers:
  post_cycle_nudge  → após ciclo 21h: insight personalizado p/ traders ativos com perfil
  inactivity_nudge  → traders inativos >3 dias com ciclos recentes positivos

Rate limit: 1 mensagem proativa por user por 24h (cooldown 24h via config table)
            + rate limit granular por feature 'proactive' via webdex_ai (Story 23.2)
Config key: proactive_{chat_id}_last_ts (epoch inteiro)
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Individual Profile dependency ────────────────────────────────────────────
try:
    from webdex_ai_user_profile import profile_build_context, profile_list_active, profile_get
    _PROFILE_ENABLED = True
except ImportError:
    _PROFILE_ENABLED = False
    profile_build_context = None  # type: ignore
    profile_list_active = None    # type: ignore
    profile_get = None            # type: ignore

# ── Bot + DB ───────────────────────────────────────────────────────────────────
try:
    from webdex_bot_core import send_html
    from webdex_db import get_config, set_config, DB_LOCK, conn, cursor
    _BOT_ENABLED = True
except ImportError:
    _BOT_ENABLED = False

# ── Rate limit granular por feature (Story 23.2) — soft import ───────────────
try:
    from webdex_ai import (
        _check_rate_limit as _ai_check_rate_limit,
        _increment_rate_limit as _ai_increment_rate_limit,
    )
    _GRANULAR_RATE_LIMIT_ENABLED = True
except ImportError:
    _ai_check_rate_limit = None       # type: ignore
    _ai_increment_rate_limit = None   # type: ignore
    _GRANULAR_RATE_LIMIT_ENABLED = False

# ── LLM (OpenRouter) ──────────────────────────────────────────────────────────
try:
    import requests as _requests
    _AI_BASE_URL = "https://openrouter.ai/api/v1"
    _AI_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    _AI_MODEL = os.environ.get("PROACTIVE_MODEL", "deepseek/deepseek-chat")
    _LLM_ENABLED = bool(_AI_KEY)
except ImportError:
    _requests = None  # type: ignore
    _LLM_ENABLED = False

# ── Config ─────────────────────────────────────────────────────────────────────
_PROACTIVE_ENABLED = os.environ.get("PROACTIVE_MODE_ENABLED", "true").lower() == "true"
_COOLDOWN_S = int(os.environ.get("PROACTIVE_COOLDOWN_H", "24")) * 3600
_MAX_USERS_PER_CYCLE = int(os.environ.get("PROACTIVE_MAX_USERS", "15"))


# ── Rate limiter ──────────────────────────────────────────────────────────────

def _can_send(chat_id: int) -> bool:
    """True se o usuário não recebeu mensagem proativa nas últimas 24h."""
    if not _BOT_ENABLED:
        return False
    try:
        val = get_config(f"proactive_{chat_id}_last_ts", "0")
        last_ts = int(val)
        return (time.time() - last_ts) >= _COOLDOWN_S
    except (ValueError, TypeError):
        return True


def _mark_sent(chat_id: int) -> None:
    try:
        set_config(f"proactive_{chat_id}_last_ts", str(int(time.time())))
    except Exception as e:
        logger.warning("[proactive] mark_sent falhou (chat_id=%s): %s", chat_id, e)


# ── LLM: gerar insight personalizado ─────────────────────────────────────────

_SYSTEM_PROMPT = """\
Você é o bdZinho, assistente especialista em DeFi e trading on-chain do protocolo WEbdEX.
Você conhece este trader há tempo e vai enviar uma mensagem PROATIVA e PERSONALIZADA
baseada no perfil dele + dados do ciclo de hoje.

REGRAS:
- Máximo 3 linhas (60-120 palavras no total)
- Comece diretamente com o insight — sem "Olá", sem "Oi"
- Use 1-2 emojis estratégicos (não exagere)
- Referencie algo ESPECÍFICO do perfil do trader
- Conecte com os dados do ciclo de hoje quando relevante
- Tom: próximo, direto, como um mentor que acompanha de perto
- Termine com 1 pergunta ou provocação curta para engajar

Responda APENAS com o texto da mensagem. Nada mais.
"""


def _call_llm(profile_ctx: str, cycle_summary: str) -> Optional[str]:
    if not _LLM_ENABLED or _requests is None:
        return None
    try:
        user_content = (
            f"PERFIL DO TRADER:\n{profile_ctx}\n\n"
            f"DADOS DO CICLO DE HOJE:\n{cycle_summary}\n\n"
            "Gere a mensagem proativa personalizada:"
        )
        resp = _requests.post(
            f"{_AI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {_AI_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://webdex.pro",
                "X-Title": "WEbdEX bdZinho",
            },
            json={
                "model": _AI_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": 200,
                "temperature": 0.82,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        return text if text else None
    except Exception as e:
        logger.warning("[proactive] LLM call falhou: %s", e)
        return None


# ── Cycle summary builder ─────────────────────────────────────────────────────

def _build_cycle_summary(cycle_data: dict) -> str:
    """Constrói texto resumido do ciclo 21h para o LLM."""
    hoje = cycle_data.get("hoje", "hoje")
    tvl = cycle_data.get("tvl_usd", 0)
    p_wr = cycle_data.get("p_wr", 0.0)
    p_bruto = cycle_data.get("p_bruto", 0.0)
    p_traders = cycle_data.get("p_traders", 0)
    p_total = cycle_data.get("p_total", 0)
    p_bd = cycle_data.get("p_bd", 0.0)

    result_str = f"+${p_bruto:.2f}" if p_bruto >= 0 else f"-${abs(p_bruto):.2f}"
    wr_str = f"{p_wr:.1f}%"

    return (
        f"Data: {hoje}\n"
        f"Liquidez do protocolo: ${tvl:,.0f} USD\n"
        f"Resultado bruto do ciclo: {result_str}\n"
        f"Win Rate: {wr_str}\n"
        f"Traders ativos: {p_traders}\n"
        f"Total de trades: {p_total:,}\n"
        f"BD coletado: {p_bd:.4f} BD"
    )


# ── Fallback message (sem LLM) ────────────────────────────────────────────────

def _fallback_message(profile: dict, cycle_data: dict) -> str:
    """Mensagem genérica quando LLM não está disponível."""
    p_bruto = cycle_data.get("p_bruto", 0.0)
    p_wr = cycle_data.get("p_wr", 0.0)
    lvl = profile.get("experience_level", "unknown")
    emoji = "🟢" if p_bruto >= 0 else "🔴"

    result_str = f"+${p_bruto:.2f}" if p_bruto >= 0 else f"-${abs(p_bruto):.2f}"

    if lvl == "iniciante":
        tip = "Cada ciclo é aprendizado. Acompanhe seu dashboard."
    elif lvl == "avancado":
        tip = "Ciclo encerrado. Hora de revisar sua alocação."
    else:
        tip = "Protocolo fechou o ciclo. Como está seu posicionamento?"

    return (
        f"{emoji} <b>Ciclo encerrado:</b> {result_str} · WR {p_wr:.0f}%\n"
        f"{tip}\n"
        f"Alguma dúvida sobre o resultado? Me pergunta 👇"
    )


# ── Core: post_cycle_nudge ────────────────────────────────────────────────────

def post_cycle_nudge(cycle_data: dict) -> None:
    """
    Dispara mensagens proativas personalizadas após o ciclo 21h.
    Executa em thread daemon — não bloqueia o workers loop.

    cycle_data keys: hoje, tvl_usd, p_wr, p_bruto, p_traders, p_total, p_bd
    """
    if not _PROACTIVE_ENABLED:
        logger.info("[proactive] Modo proativo desativado (PROACTIVE_MODE_ENABLED=false)")
        return
    if not _PROFILE_ENABLED or not _BOT_ENABLED:
        logger.info("[proactive] Módulos de perfil ou bot indisponíveis — skip proactive")
        return

    def _run():
        try:
            # 1. Buscar usuários ativos nos últimos 3 dias COM perfil
            active_ids: list[int] = profile_list_active(days=3)  # type: ignore
            if not active_ids:
                logger.info("[proactive] Nenhum usuário ativo com perfil — skip")
                return

            # 2. Filtrar apenas quem pode receber (rate limit 24h)
            eligible = [uid for uid in active_ids if _can_send(uid)]
            if not eligible:
                logger.info("[proactive] Todos os usuários já receberam proativo hoje — skip")
                return

            # Limitar para não explodir API
            eligible = eligible[:_MAX_USERS_PER_CYCLE]

            cycle_summary = _build_cycle_summary(cycle_data)
            sent = 0
            failed = 0

            for chat_id in eligible:
                try:
                    profile = profile_get(chat_id)  # type: ignore
                    if not profile:
                        continue

                    # Só envia se perfil tem dados úteis
                    has_data = (
                        profile.get("summary")
                        or profile.get("experience_level", "unknown") != "unknown"
                        or profile.get("facts")
                    )
                    if not has_data:
                        continue

                    # Gerar contexto de perfil para o LLM
                    profile_ctx = profile_build_context(chat_id)  # type: ignore
                    if not profile_ctx:
                        continue

                    # Gerar mensagem via LLM (com fallback)
                    msg = _call_llm(profile_ctx, cycle_summary)
                    if not msg:
                        msg = _fallback_message(profile, cycle_data)

                    # Story 23.2 — verificar rate limit granular antes de enviar
                    if _GRANULAR_RATE_LIMIT_ENABLED:
                        _allowed, _, _ = _ai_check_rate_limit(chat_id, 'proactive')
                        if not _allowed:
                            logger.debug(
                                "[proactive] Rate limit granular atingido para chat_id=%s — skip",
                                chat_id,
                            )
                            continue
                        _ai_increment_rate_limit(chat_id, 'proactive')

                    # Enviar via Telegram
                    send_html(chat_id, msg)
                    _mark_sent(chat_id)
                    sent += 1

                    # Pequena pausa para não sobrecarregar API + Telegram
                    time.sleep(1.2)

                except Exception as e:
                    logger.warning("[proactive] Falha ao enviar para chat_id=%s: %s", chat_id, e)
                    failed += 1

            logger.info(
                "[proactive] post_cycle_nudge: %d/%d enviados (falhas: %d)",
                sent, len(eligible), failed
            )

        except Exception as e:
            logger.error("[proactive] post_cycle_nudge erro: %s", e)

    threading.Thread(target=_run, daemon=True).start()


# ── Proactive Mode: módulo pronto ─────────────────────────────────────────────
logger.info(
    "[proactive] carregado — perfil=%s bot=%s llm=%s enabled=%s",
    _PROFILE_ENABLED, _BOT_ENABLED, _LLM_ENABLED, _PROACTIVE_ENABLED
)
