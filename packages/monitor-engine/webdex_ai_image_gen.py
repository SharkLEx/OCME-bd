"""
webdex_ai_image_gen.py — bdZinho Image Generation (Nano Banana / Gemini)
Epic MATRIX-3 | Story MATRIX-3.7

Geração de imagens AI para usuários do Telegram via /criar_imagem.
Usa Google Gemini via OpenRouter (Nano Banana: google/gemini-2.5-flash-image).

Fluxo:
  Usuário digita prompt → SCDS formatting → OpenRouter API → imagem PNG → bot.send_photo
"""
from __future__ import annotations

import base64
import io
import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_AI_BASE_URL = os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1")
_AI_API_KEY  = os.getenv("OPENROUTER_API_KEY") or os.getenv("AI_API_KEY", "")
_IMAGE_MODEL = os.getenv("IMAGE_GEN_MODEL", "google/gemini-2.5-flash-image")

# Cooldown por usuário (segundos) — evita flood de geração
IMAGE_GEN_COOLDOWN_S = int(os.getenv("IMAGE_GEN_COOLDOWN_S", "30"))

# Limite de chars no prompt do usuário (anti-injection)
_PROMPT_MAX_CHARS = 400

# ── SCDS Wrapper — Structured Creative Direction System ───────────────────────
_SCDS_SYSTEM = (
    "Você é um especialista em geração de imagens do protocolo WEbdEX DeFi. "
    "Formate o prompt do usuário seguindo o padrão SCDS: "
    "[SUBJECT]: foco principal, [SETTING]: ambiente/contexto, "
    "[STYLE]: estilo visual, futurista, DeFi, neon blue/green, dark background, "
    "[TECHNICAL]: 16:9, ultra HD, professional digital art. "
    "Retorne APENAS o prompt formatado, sem explicações."
)


def _build_scds_prompt(raw_prompt: str) -> str:
    """
    Enriquece o prompt do usuário com identidade visual WEbdEX.
    Retorna prompt SCDS pronto para enviar ao modelo de imagem.
    """
    # Sanitização básica
    safe = raw_prompt[:_PROMPT_MAX_CHARS].replace("\n", " ").strip()

    # Adiciona contexto WEbdEX ao prompt diretamente (sem LLM extra — mais rápido e barato)
    return (
        f"{safe}, "
        "WEbdEX DeFi protocol aesthetic, dark background, neon blue and green accents, "
        "futuristic digital art, ultra HD, professional, 16:9"
    )


# ── API Call ──────────────────────────────────────────────────────────────────

def generate_image(prompt: str) -> Optional[bytes]:
    """
    Gera uma imagem a partir do prompt via OpenRouter (Gemini).
    Retorna os bytes PNG/JPEG ou None em caso de falha.
    """
    if not _AI_API_KEY:
        logger.error("[image_gen] OPENROUTER_API_KEY não configurada")
        return None

    scds_prompt = _build_scds_prompt(prompt)
    logger.info("[image_gen] Gerando imagem | model=%s | prompt=%s...", _IMAGE_MODEL, scds_prompt[:80])

    try:
        resp = requests.post(
            f"{_AI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {_AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": _IMAGE_MODEL,
                "messages": [
                    {"role": "user", "content": scds_prompt}
                ],
                "modalities": ["image", "text"],
                "image_config": {
                    "aspect_ratio": "16:9",
                    "image_size": "1K",
                },
            },
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        logger.warning("[image_gen] Timeout na geração de imagem")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning("[image_gen] Erro HTTP: %s", e)
        return None
    except Exception as e:
        logger.warning("[image_gen] Erro inesperado: %s", e)
        return None

    # Extrai imagem da resposta — pode vir como data URL base64 ou URL direta
    try:
        content = data["choices"][0]["message"]["content"]

        # content pode ser string (URL ou base64 data URL) ou lista de partes
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    url = part["image_url"].get("url", "")
                    return _decode_image_url(url)
            # fallback: verificar se alguma parte tem text com URL
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
                    urls = re.findall(r'https?://\S+\.(?:png|jpg|jpeg|webp)', text)
                    if urls:
                        return _download_image(urls[0])
        elif isinstance(content, str):
            return _decode_image_url(content)

        logger.warning("[image_gen] Formato de resposta inesperado: %s", str(content)[:200])
        return None

    except (KeyError, IndexError, TypeError) as e:
        logger.warning("[image_gen] Falha ao extrair imagem da resposta: %s", e)
        return None


def _decode_image_url(url: str) -> Optional[bytes]:
    """Decodifica data URL base64 ou faz download de URL HTTP."""
    if url.startswith("data:"):
        # data:image/png;base64,AAAA...
        try:
            _, b64 = url.split(",", 1)
            return base64.b64decode(b64)
        except Exception as e:
            logger.warning("[image_gen] Falha ao decodificar base64: %s", e)
            return None
    elif url.startswith("http"):
        return _download_image(url)
    return None


def _download_image(url: str) -> Optional[bytes]:
    """Baixa imagem de uma URL."""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        logger.warning("[image_gen] Falha ao baixar imagem de URL: %s", e)
        return None
