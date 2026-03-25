"""
webdex_ai_vision.py — bdZinho MATRIX 4.2 Vision
Epic MATRIX-4 | Story MATRIX-4.2

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
_AI_BASE_URL  = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
_AI_API_KEY   = os.getenv("OPENROUTER_API_KEY") or os.getenv("AI_API_KEY", "")
_VISION_MODEL = os.getenv("VISION_MODEL", "google/gemini-2.5-flash")

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


def analyze_image(
    image_bytes: bytes,
    question: str = "",
    profile_context: str = "",
) -> Optional[str]:
    """
    Analisa uma imagem via Gemini Flash Vision.

    Args:
        image_bytes:     bytes da imagem (PNG/JPG/WEBP)
        question:        pergunta opcional do usuário sobre a imagem
        profile_context: contexto de perfil do trader (MATRIX 4.0)

    Returns:
        Texto da análise ou None em caso de falha.
    """
    if not _AI_API_KEY:
        logger.error("[vision] OPENROUTER_API_KEY não configurada")
        return None

    if len(image_bytes) > _IMG_SIZE_LIMIT:
        logger.warning("[vision] Imagem muito grande: %d bytes — truncando não é possível", len(image_bytes))
        return None

    try:
        import requests
    except ImportError:
        logger.error("[vision] requests não disponível")
        return None

    # Encode para base64
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Detectar mime type pelos magic bytes
    mime = "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        mime = "image/webp"
    elif image_bytes[:3] == b"GIF":
        mime = "image/gif"

    # Montar system prompt com perfil se disponível
    system = _VISION_SYSTEM
    if profile_context:
        system = f"{_VISION_SYSTEM}\n\nCONTEXTO DO TRADER:\n{profile_context}"

    # Montar user message
    user_text = question.strip() if question.strip() else "Analise esta imagem para mim."

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
                "model": _VISION_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{b64}",
                                },
                            },
                            {
                                "type": "text",
                                "text": user_text,
                            },
                        ],
                    },
                ],
                "max_tokens": 600,
                "temperature": 0.7,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        return text if text else None

    except requests.exceptions.Timeout:
        logger.warning("[vision] Timeout na análise de imagem")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning("[vision] Erro HTTP: %s", e)
        return None
    except (KeyError, IndexError) as e:
        logger.warning("[vision] Formato de resposta inesperado: %s", e)
        return None
    except Exception as e:
        logger.warning("[vision] Erro inesperado: %s", e)
        return None


logger.info("[vision] MATRIX 4.2 Vision carregado — model=%s", _VISION_MODEL)
