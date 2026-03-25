"""
webdex_ai_content.py — bdZinho MATRIX 3.0 Content Engine
Epic MATRIX-3 | Story MATRIX-3.5

Geração de conteúdo de marketing para o protocolo WEbdEX usando:
  - Dados reais do último ciclo 21h (ai_digests)
  - Inteligência acumulada (bdz_knowledge via MATRIX 3.0)
  - LLM via OpenRouter (deepseek ou openai)

Funções públicas:
  gerar_post_discord(style)   → post formatado para Discord
  gerar_post_telegram(style)  → post formatado para Telegram
  gerar_copy_trafego(objetivo)→ copy para anúncio pago
  gerar_relatorio_marketing() → relatório narrativo do ciclo
  gerar_thread_x(style)       → thread Twitter/X com múltiplos tweets
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_AI_BASE_URL   = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
_AI_API_KEY    = os.getenv("OPENROUTER_API_KEY") or os.getenv("AI_API_KEY", "")
_CONTENT_MODEL = os.getenv("CONTENT_MODEL", "deepseek/deepseek-chat")


# ── Carrega contexto ──────────────────────────────────────────────────────────

def _get_protocol_context() -> str:
    """Monta contexto completo do protocolo: último digest + knowledge MATRIX 3.0."""
    parts = []

    # Dados reais do último ciclo 21h
    try:
        from webdex_ai_digest import get_recent_digests
        from webdex_db import conn as _db_conn, DB_LOCK
        digests = get_recent_digests(_db_conn, DB_LOCK, days=2)
        if digests:
            d = digests[-1]  # mais recente
            parts.append(
                f"ÚLTIMO CICLO 21H ({d.get('date', 'hoje')}):\n"
                f"• Traders ativos: {d.get('traders', '?')}\n"
                f"• Trades executados: {d.get('trades', '?')}\n"
                f"• WinRate: {d.get('wr_pct', 0):.1f}%\n"
                f"• P&L total: ${d.get('pnl_usd', 0):,.2f}\n"
                f"• TVL: ${d.get('tvl_usd', 0):,.0f}\n"
                f"• Fee BD coletada: {d.get('fee_bd', 0):.4f} BD\n"
            )
    except Exception as e:
        logger.debug("[content] digest falhou: %s", e)

    # Inteligência MATRIX 3.0
    try:
        from webdex_ai_knowledge import knowledge_build_context
        ctx = knowledge_build_context(include_categories=[
            "protocol_patterns", "daily_insights", "smith_findings"
        ])
        if ctx:
            parts.append(ctx)
    except Exception as e:
        logger.debug("[content] knowledge falhou: %s", e)

    return "\n\n".join(parts) if parts else "(dados não disponíveis)"


# ── LLM call ─────────────────────────────────────────────────────────────────

def _llm(system: str, user: str, max_tokens: int = 800, temperature: float = 0.7) -> Optional[str]:
    if not _AI_API_KEY:
        return None
    try:
        resp = requests.post(
            f"{_AI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {_AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": _CONTENT_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=45,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning("[content] LLM call falhou: %s", e)
        return None


# ── Prompts de persona ────────────────────────────────────────────────────────

_PERSONA_BASE = """
Você é o copywriter oficial do protocolo WEbdEX — um protocolo DeFi de trade automatizado
na blockchain Polygon. Seu público são traders brasileiros que já estão dentro do protocolo
ou ainda estão considerando entrar.

Tom: direto, confiante, técnico sem ser frio, com energia de quem sabe o que está fazendo.
Nunca prometa retorno. Nunca diga "garantia". Foque em dados reais, transparência e processo.
Escreva em PT-BR. Use emojis com moderação — máx 1-2 por linha.
"""

# ── Funções públicas ──────────────────────────────────────────────────────────

def gerar_post_discord(style: str = "ciclo") -> str:
    """
    Gera post para Discord sobre o protocolo.
    style: 'ciclo' (relatório 21h), 'milestone' (conquista), 'educativo', 'engajamento'
    """
    ctx = _get_protocol_context()

    style_guides = {
        "ciclo": (
            "Escreva um post de resultado do ciclo 21h do protocolo WEbdEX para o Discord.\n"
            "Formato: título chamativo → métricas reais → análise em 2-3 linhas → CTA suave.\n"
            "Use os dados reais do contexto. Máx 250 palavras. Markdown Discord (bold = **texto**)."
        ),
        "milestone": (
            "Escreva um post celebrando uma conquista/milestone do protocolo WEbdEX para Discord.\n"
            "Tom: energia, orgulho da comunidade, foco no que foi alcançado.\n"
            "Máx 150 palavras. Use emojis de conquista."
        ),
        "educativo": (
            "Escreva um post educativo sobre como funciona o protocolo WEbdEX para Discord.\n"
            "Foco: como o protocolo gera trades automaticamente e protege o capital.\n"
            "Máx 200 palavras. Tom: didático mas confiante."
        ),
        "engajamento": (
            "Escreva um post de engajamento para a comunidade WEbdEX no Discord.\n"
            "Faça uma pergunta ou observação que incentive a resposta dos membros.\n"
            "Máx 100 palavras. Tom: community-first."
        ),
    }

    guide = style_guides.get(style, style_guides["ciclo"])

    result = _llm(
        _PERSONA_BASE,
        f"{guide}\n\nCONTEXTO DO PROTOCOLO:\n{ctx}",
        max_tokens=600,
        temperature=0.75,
    )
    return result or "⚠️ Falha na geração de conteúdo. Verifique a chave API."


def gerar_post_telegram(style: str = "ciclo") -> str:
    """
    Gera post para Telegram (sem markdown Discord, HTML-safe).
    style: 'ciclo', 'alerta', 'motivacional', 'educativo'
    """
    ctx = _get_protocol_context()

    style_guides = {
        "ciclo": (
            "Escreva um post de resultado do ciclo 21h do WEbdEX para Telegram.\n"
            "Formato: abertura forte → números reais → contexto/análise → fechamento.\n"
            "Sem Markdown. Use emojis. Máx 200 palavras."
        ),
        "alerta": (
            "Escreva um alerta para os usuários do WEbdEX no Telegram.\n"
            "Pode ser sobre: TVL subindo, WinRate acima da média, ciclo especial.\n"
            "Tom: urgência saudável, não alarmista. Máx 100 palavras."
        ),
        "motivacional": (
            "Escreva uma mensagem motivacional para a comunidade WEbdEX no Telegram.\n"
            "Baseada nos dados reais do protocolo. Reforce o processo, não a emoção.\n"
            "Máx 120 palavras."
        ),
        "educativo": (
            "Escreva um post educativo curto sobre o WEbdEX para Telegram.\n"
            "Explique um conceito do protocolo de forma simples (Tríade, WinRate, ciclo, etc).\n"
            "Máx 150 palavras."
        ),
    }

    guide = style_guides.get(style, style_guides["ciclo"])

    result = _llm(
        _PERSONA_BASE,
        f"{guide}\n\nCONTEXTO DO PROTOCOLO:\n{ctx}",
        max_tokens=500,
        temperature=0.72,
    )
    return result or "⚠️ Falha na geração."


def gerar_copy_trafego(objetivo: str = "captacao") -> str:
    """
    Gera copy para tráfego pago (Meta Ads, Google, etc).
    objetivo: 'captacao' (atrair novos), 'retencao' (manter ativos), 'reativacao'
    """
    ctx = _get_protocol_context()

    obj_guides = {
        "captacao": (
            "Escreva 3 variações de copy para anúncio Meta Ads captando novos usuários para o WEbdEX.\n"
            "Cada variação: Headline (máx 40 chars) + Texto principal (máx 90 chars) + CTA.\n"
            "Baseie nos dados reais do protocolo. Proibido: 'garantia', 'certeza de lucro'.\n"
            "Use prova social e dados reais (WinRate%, traders, P&L)."
        ),
        "retencao": (
            "Escreva 2 variações de copy para anúncio reforçando por que usuários WEbdEX devem manter capital ativo.\n"
            "Foco: consistência do processo, WinRate histórico, transparência on-chain.\n"
            "Headline + Texto + CTA. Tom: confiante, não desesperado."
        ),
        "reativacao": (
            "Escreva 2 variações de copy para reativar usuários WEbdEX que pararam de usar o protocolo.\n"
            "Mostre o que eles perderam (dados reais de P&L/ciclos) e convide a voltar.\n"
            "Tom: direto, sem julgamento. CTA claro."
        ),
    }

    guide = obj_guides.get(objetivo, obj_guides["captacao"])

    result = _llm(
        _PERSONA_BASE,
        f"{guide}\n\nCONTEXTO DO PROTOCOLO:\n{ctx}",
        max_tokens=700,
        temperature=0.80,
    )
    return result or "⚠️ Falha na geração de copy."


def gerar_relatorio_marketing() -> str:
    """
    Gera relatório narrativo do ciclo para uso em marketing/redes sociais.
    Versão mais elaborada que pode virar post, thread ou newsletter.
    """
    ctx = _get_protocol_context()

    result = _llm(
        _PERSONA_BASE + "\nVocê também é analista financeiro — combine narrativa + dados.",
        f"""Escreva um relatório narrativo do ciclo WEbdEX para uso em marketing.

Estrutura:
1. HEADLINE: frase de impacto com o número mais relevante do ciclo
2. CONTEXTO: o que aconteceu em 2-3 frases
3. NÚMEROS: métricas reais em bullets
4. ANÁLISE: o que esses números significam (2-3 frases)
5. PERSPECTIVA: o que esperar / o que isso demonstra sobre o protocolo

Tom: jornalístico-financeiro. Máx 300 palavras.

CONTEXTO DO PROTOCOLO:
{ctx}""",
        max_tokens=800,
        temperature=0.65,
    )
    return result or "⚠️ Falha na geração do relatório."


def gerar_thread_x(num_tweets: int = 5) -> str:
    """
    Gera thread para Twitter/X sobre o ciclo WEbdEX.
    Retorna tweets numerados prontos para postar.
    """
    ctx = _get_protocol_context()

    result = _llm(
        _PERSONA_BASE + "\nVocê é especialista em Twitter/X. Posts curtos, impactantes, shareáveis.",
        f"""Escreva uma thread de {num_tweets} tweets sobre o WEbdEX para Twitter/X.

Formato:
[1/N] Tweet de abertura (hook forte — faça querer ler o resto)
[2/N] Dado mais impressionante com contexto
[3/N] Como o protocolo funciona (técnico simples)
[4/N] Prova social / transparência on-chain
[5/N] CTA + onde saber mais

Cada tweet: máx 250 caracteres. Sem Markdown. Emojis OK.
CONTEXTO DO PROTOCOLO:
{ctx}""",
        max_tokens=700,
        temperature=0.78,
    )
    return result or "⚠️ Falha na geração da thread."


def gerar_pacote_ciclo(webhook_discord: str = "") -> dict:
    """
    Gera o pacote completo de conteúdo do ciclo:
      - Card visual PNG (1200×675)
      - Post Discord formatado
      - Post Telegram formatado
      Opcionalmente posta o card no Discord se webhook fornecido.

    Retorna dict com chaves: 'card_buf', 'post_discord', 'post_telegram', 'discord_ok'
    """
    try:
        from webdex_ai_image import gerar_card_ciclo, post_card_discord
        card_buf = gerar_card_ciclo()
        discord_ok = False
        if webhook_discord:
            discord_ok = post_card_discord(
                webhook_discord,
                card_buf,
                filename="webdex_ciclo.png",
                title="📊 Resultado do Ciclo 21h",
                description="Dados on-chain · Polygon Mainnet",
                color=0x00FFB2,
            )
    except Exception as e:
        logger.warning("[content] gerar_card falhou: %s", e)
        card_buf = None
        discord_ok = False

    return {
        "card_buf":      card_buf,
        "post_discord":  gerar_post_discord("ciclo"),
        "post_telegram": gerar_post_telegram("ciclo"),
        "discord_ok":    discord_ok,
    }
