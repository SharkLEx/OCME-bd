"""
webdex_ai_image_gen.py — bdZinho Image Generation (Nano Banana / Gemini)
Epic MATRIX-3 | Story MATRIX-3.7

Geração de imagens AI para usuários do Telegram via /criar_imagem.
Usa Google Gemini via OpenRouter (Nano Banana: google/gemini-2.5-flash-image).

Fluxo:
  Usuário digita prompt → SCDS formatting → OpenRouter API → imagem PNG → bot.send_photo

Design Bible: bdZinho_design_bible.md
  Corpo creme/branco, face hot pink (#FF2D78), dois chifres brancos,
  badge "bd" no peito, estilo vinyl toy 3D / Funko, proporções cute.
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

# ── bdZinho Character DNA (Design Bible v1.0) ────────────────────────────────
# Extraído de 13+ renders oficiais — ver bdZinho_design_bible.md
_BDZINHO_DNA = (
    "bdZinho robot mascot, cream white rounded robot body, hot pink face panel (#FF2D78), "
    "two white pointed horns on top of head, white oval eyes with gentle smile, "
    '\'bd\' logo badge on chest in hot pink, articulated joints, rounded boots, '
    "vinyl toy style, Funko-like cute proportions, 3D render, soft pink rim light"
)

# Contextos temáticos para enriquecer o prompt com o DNA do personagem
_CONTEXT_KEYWORDS: dict[str, str] = {
    # Lucro / ganho / positivo
    "lucro":       "celebrating with arms raised, golden particles floating, dark background with warm glow",
    "ganho":       "thumbs up pose, happy expression, golden light particles, dark wine background",
    "win":         "victory pose, arms raised, confetti particles, cinematic dark background",
    "positivo":    "thumbs up, big smile, warm golden accent lighting",
    # Análise / relatório
    "relatorio":   "holding a holographic tablet with DeFi charts, analytical pose, dark blue data overlay",
    "analise":     "holding glowing data screen, professional pose, holographic charts background",
    "dashboard":   "pointing at holographic DeFi dashboard, expert presentation pose",
    # DeFi / blockchain
    "blockchain":  "one hand open levitating glowing blue blockchain orb, expert presentation",
    "defi":        "surrounded by floating crypto coins and blockchain nodes, neon blue glow",
    "token":       "holding two glowing crypto tokens (pink and blue), cool sunglasses, leather jacket",
    "contrato":    "holding glowing cyber padlock with circuit patterns, security pose",
    # Trading
    "trading":     "cool sunglasses, leather jacket, relaxed confident pose, holding coins",
    "trader":      "sunglasses, pointing finger at viewer, confident stance, dark moody background",
    "mercado":     "professional suit, arms crossed, serious but friendly expression",
    # Ideia / dica / insight
    "dica":        "index finger pointing up with glowing lightbulb above, idea pose",
    "insight":     "lightbulb glowing above finger, thoughtful smile, dark background",
    "estrategia":  "pointing at holographic strategy board, professor pose",
    # Alerta / risco
    "alerta":      "all-pink body variant, concerned expression, dark red vignette background",
    "risco":       "all-pink body variant, cautious pose, warning orange glow",
    "drawdown":    "all-pink body variant, worried expression, dark moody atmosphere",
    # Comunidade / social
    "brasil":      "holding Brazilian flag proudly, crimson background",
    "comunidade":  "arms open welcoming gesture, warm background",
}

# Background padrão por contexto geral
_DEFAULT_BG = "deep dark wine background #1A0010, subtle pink bokeh particles"
_TECH_BG    = "deep black background, subtle blue holographic grid, pink rim light"


def _detect_context_overlay(raw: str) -> str:
    """Detecta palavras-chave no prompt e retorna overlay de pose/contexto."""
    low = raw.lower()
    for kw, overlay in _CONTEXT_KEYWORDS.items():
        if kw in low:
            return overlay
    return "friendly pointing gesture, warm expression"


def _build_scds_prompt(raw_prompt: str) -> str:
    """
    Enriquece o prompt do usuário com o DNA completo do personagem bdZinho.
    Retorna prompt SCDS pronto para enviar ao modelo de imagem.

    Se o prompt menciona "bdZinho" ou "bot" → gera o personagem com DNA completo.
    Caso contrário → gera arte WEbdEX com o personagem como elemento secundário.
    """
    safe = raw_prompt[:_PROMPT_MAX_CHARS].replace("\n", " ").strip()
    low  = safe.lower()

    # Detecta se usuário quer o personagem explicitamente ou arte genérica
    wants_character = any(w in low for w in ("bdzinho", "bot", "mascote", "personagem", "robot", "robô"))

    if wants_character or not any(c.isalpha() for c in safe):
        # Modo personagem: DNA completo do bdZinho
        overlay = _detect_context_overlay(safe)
        return (
            f"{_BDZINHO_DNA}, {overlay}, "
            f"{safe}, "
            f"{_DEFAULT_BG}, "
            "ultra HD, sharp 3D render, cinematic quality, WEbdEX DeFi mascot, "
            "professional digital art, 16:9"
        )
    else:
        # Modo arte WEbdEX: personagem ao fundo ou integrado
        overlay = _detect_context_overlay(safe)
        return (
            f"{safe}, "
            f"WEbdEX DeFi protocol aesthetic, featuring {_BDZINHO_DNA}, {overlay}, "
            f"{_TECH_BG}, "
            "neon pink and blue accents, futuristic DeFi art, ultra HD, cinematic, 16:9"
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
