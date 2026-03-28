"""
webdex_ai_vision.py — bdZinho Vision

bdZinho analisa imagens enviadas pelo usuário — screenshots de dashboard,
gráficos de trading, prints de carteira, charts on-chain.

Fluxo:
  Usuário envia foto → download bytes → Gemini Flash Vision → análise personalizada
  Modelo: google/gemini-2.5-flash (vision) via OpenRouter
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_AI_BASE_URL       = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
_AI_API_KEY        = os.getenv("OPENROUTER_API_KEY") or os.getenv("AI_API_KEY", "")
# Anthropic Vision model — haiku é rápido e suporta imagens
_VISION_MODEL_ANTHROPIC = "claude-haiku-4-5-20251001"
# OpenRouter fallback
_VISION_MODEL_OR  = os.getenv("VISION_MODEL", "google/gemini-2.5-flash")

# Limite de tamanho da imagem para a API (bytes) — 4MB
_IMG_SIZE_LIMIT = 4 * 1024 * 1024

# ── Sistema de análise ─────────────────────────────────────────────────────────
_VISION_SYSTEM = """\
Você é o bdZinho, assistente especialista em DeFi e trading on-chain do protocolo WEbdEX.
O usuário enviou uma imagem para você analisar.

CONTEXTO QUE VOCÊ DEVE IDENTIFICAR AUTOMATICAMENTE:
- Screenshot de dashboard de trading → análise de P&L, win rate, padrões
- Gráfico de preço (chart) → análise técnica simples, tendência, suporte/resistência
- Print de carteira/portfolio → composição, risco, diversificação
- Screenshot de trade executado → entrada, saída, resultado
- Gráfico on-chain (TVL, volume) → interpretação de métricas DeFi
- Qualquer outra imagem → análise contextual relevante para DeFi/trading

REGRAS:
- Seja ESPECÍFICO sobre o que está vendo na imagem
- Conecte com o contexto de DeFi/WEbdEX quando relevante
- Máximo 4-5 parágrafos curtos
- Tom: mentor próximo, direto, expert
- Se não conseguir identificar o tipo de imagem, descreva o que vê e ofereça análise
- Se a imagem não tiver relação com DeFi/trading, mencione isso mas seja útil mesmo assim
- Termine com uma pergunta ou observação acionável

Responda em português.
"""


def _detect_mime(image_bytes: bytes) -> str:
    """Detecta mime type pelos magic bytes."""
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes[:3] == b"GIF":
        return "image/gif"
    return "image/jpeg"


def analyze_image(
    image_bytes: bytes,
    question: str = "",
    profile_context: str = "",
) -> Optional[str]:
    """
    Analisa uma imagem via Claude Vision (Anthropic SDK) com fallback para OpenRouter.

    Args:
        image_bytes:     bytes da imagem (PNG/JPG/WEBP)
        question:        pergunta opcional do usuário sobre a imagem
        profile_context: contexto de perfil do trader (Individual Profile)

    Returns:
        Texto da análise ou None em caso de falha.
    """
    if len(image_bytes) > _IMG_SIZE_LIMIT:
        logger.warning("[vision] Imagem muito grande: %d bytes", len(image_bytes))
        return None

    mime     = _detect_mime(image_bytes)
    b64      = base64.b64encode(image_bytes).decode("utf-8")
    system   = _VISION_SYSTEM
    if profile_context:
        system = f"{_VISION_SYSTEM}\n\nCONTEXTO DO TRADER:\n{profile_context}"
    user_text = question.strip() if question.strip() else "Analise esta imagem para mim."

    # ── Primário: Anthropic SDK (Claude Haiku Vision) ─────────────────────────
    if _ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model=_VISION_MODEL_ANTHROPIC,
                max_tokens=700,
                system=system,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime,
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": user_text},
                        ],
                    }
                ],
            )
            text = msg.content[0].text.strip() if msg.content else ""
            if text:
                logger.debug("[vision] Anthropic Vision OK")
                return text
        except Exception as e:
            logger.warning("[vision] Anthropic Vision falhou, tentando OpenRouter: %s", e)

    # ── Fallback: OpenRouter (Gemini Flash) ───────────────────────────────────
    if not _AI_API_KEY:
        logger.error("[vision] Sem API key disponível (ANTHROPIC nem OPENROUTER)")
        return None

    try:
        import requests
    except ImportError:
        logger.error("[vision] requests não disponível")
        return None

    try:
        resp = requests.post(
            f"{_AI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {_AI_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://webdex.pro",
                "X-Title": "WEbdEX bdZinho Vision",
            },
            json={
                "model": _VISION_MODEL_OR,
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64}"},
                            },
                            {"type": "text", "text": user_text},
                        ],
                    },
                ],
                "max_tokens": 600,
                "temperature": 0.7,
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        return text if text else None

    except Exception as e:
        logger.warning("[vision] OpenRouter fallback falhou: %s", e)
        return None


logger.info("[vision] bdZinho Vision carregado — anthropic=%s | fallback=%s", _VISION_MODEL_ANTHROPIC, _VISION_MODEL_OR)
