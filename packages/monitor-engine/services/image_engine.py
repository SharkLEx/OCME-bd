"""
webdex_image_engine.py — bdZinho Image Engine v1.1

Motor unificado de processamento de imagens para o bdZinho.
3 capacidades, provider chain com Replicate para fidelidade máxima ao personagem.

Capacidades:
  gerar_imagem()       — texto → PNG via Replicate SDXL img2img | FLUX.1-schnell | Gemini
  melhorar_imagem()    — PNG → PNG melhorado via PIL (sharpen + upscale 2x, GRÁTIS)
  analisar_imagem_ocr() — PNG → texto via GLM-OCR (HF, 3.75M downloads)

Provider chain (personagem):
  GERAR char: Replicate SDXL img2img → FLUX.1-schnell → None
  GERAR other: FLUX.1-schnell → Gemini OpenRouter → None
  MELHORAR: PIL puro (sem API) → None
  EXTRAIR: HF (GLM-OCR / zai-org) → None

Licença modelo:
  FLUX.1-schnell: Apache 2.0 (uso comercial permitido)
  SDXL via Replicate: uso comercial permitido (créditos pré-pagos)
  GLM-OCR: MIT (uso comercial permitido)

Story: 20.1 — Epic 20 bdZinho Image Intelligence
"""
from __future__ import annotations

import base64
import io
import logging
import os
import threading
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

# HuggingFace Inference API
_HF_TOKEN    = os.getenv('HF_TOKEN', '')
_HF_API_BASE = 'https://router.huggingface.co/hf-inference/models'

# Modelos HF
_HF_FLUX_MODEL    = 'black-forest-labs/FLUX.1-schnell'   # text-to-image, Apache 2.0
_HF_IMG2IMG_MODEL = 'stabilityai/stable-diffusion-xl-refiner-1.0'  # img2img, personagem
_HF_OCR_MODEL     = 'zai-org/GLM-OCR'                    # image-to-text, MIT

# Referência visual do bdZinho para img2img
_BDZINHO_REF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bdzinho_reference.png')

# Replicate — img2img com referência (melhor fidelidade ao personagem)
_REPLICATE_TOKEN = os.getenv('REPLICATE_API_TOKEN', '')
_REPLICATE_POLL_TIMEOUT  = 120   # segundos máx aguardando prediction
_REPLICATE_POLL_INTERVAL = 3     # segundos entre polls

# Fallback Gemini (reutiliza config existente)
_AI_BASE_URL    = os.getenv('AI_BASE_URL', 'https://openrouter.ai/api/v1')
_AI_API_KEY     = os.getenv('OPENROUTER_API_KEY') or os.getenv('AI_API_KEY', '')
_IMAGE_GEN_MODEL = os.getenv('IMAGE_GEN_MODEL', 'google/gemini-2.5-flash-image')

# Limites
_IMG_MAX_BYTES  = 4 * 1024 * 1024   # 4 MB — limite HF Inference API
_PROMPT_MAX     = 400               # chars — anti-injection
_HF_TIMEOUT     = 90                # segundos — FLUX leva ~15-30s no free tier
_OCR_TIMEOUT    = 30

# Cooldowns por capacidade (segundos)
ENGINE_GERAR_COOLDOWN_S    = 30
ENGINE_MELHORAR_COOLDOWN_S = 5
ENGINE_ANALISAR_COOLDOWN_S = 10

# img2img config
_IMG2IMG_TIMEOUT  = 120
_IMG2IMG_STRENGTH = 0.45   # 45% mudança — mantém DNA do personagem, aplica contexto

# ── Rate Limiting ──────────────────────────────────────────────────────────────

_rate_lock:  threading.Lock = threading.Lock()
_rate_cache: dict[tuple[int, str], float] = {}

_COOLDOWNS: dict[str, int] = {
    'gerar':    ENGINE_GERAR_COOLDOWN_S,
    'melhorar': ENGINE_MELHORAR_COOLDOWN_S,
    'analisar': ENGINE_ANALISAR_COOLDOWN_S,
}


def check_cooldown(user_id: int, cap: str) -> float:
    """
    Verifica cooldown de uma capacidade para um usuário.
    Retorna 0.0 se liberado, ou segundos restantes se em cooldown.
    Efeito colateral: registra o timestamp atual se liberado.
    """
    key = (user_id, cap)
    now = time.time()
    limit = _COOLDOWNS.get(cap, 30)
    with _rate_lock:
        last = _rate_cache.get(key, 0.0)
        remaining = limit - (now - last)
        if remaining > 0:
            return remaining
        _rate_cache[key] = now
        return 0.0


# ── SCDS Prompt Builder (DNA bdZinho) ────────────────────────────────────────

_BDZINHO_DNA = (
    'bdZinho 3D chibi robot mascot, '
    'perfectly round oval head: large deep hot pink face circle fills the entire front of the round head, '
    'narrow light blush pink border ring around the hot pink face circle, '
    'two tall sharp white devil horns growing straight up from top of round head, hot pink band at horn bases, '
    'two small black oval eyes and a gentle smile directly on the hot pink face circle, '
    'round light blush pink tubby barrel-shaped body, '
    'hot pink square rounded badge with white "bd" text on chest belly, '
    'hot pink joint rings at neck elbows and waist, '
    'light blush pink short chunky arms and short stubby legs with round flat feet, '
    'smooth matte 3D render, all-pink monochromatic pastel palette, chibi toy proportions'
)
_DEFAULT_BG = 'pure black background, subtle hot pink bokeh glow behind character'
_TECH_BG    = 'pure black background, subtle blue holographic blockchain grid, hot pink rim light'

_CONTEXT_KEYWORDS: dict[str, str] = {
    'lucro':     'celebrating with arms raised, golden particles, dark background',
    'ganho':     'thumbs up, happy expression, golden light particles',
    'alerta':    'all-pink body variant, concerned expression, dark red vignette',
    'risco':     'all-pink body variant, cautious pose, warning orange glow',
    'blockchain':'one hand levitating glowing blue blockchain orb, expert pose',
    'defi':      'surrounded by floating crypto coins, neon blue glow',
    'relatorio': 'holding holographic tablet with charts, analytical pose',
    'dica':      'index finger pointing up with glowing lightbulb, idea pose',
    'trading':   'cool sunglasses, leather jacket, confident pose, holding coins',
}


def _build_scds_prompt(raw: str) -> str:
    """Enriquece prompt com DNA do bdZinho. Seguro contra injection (trim + sanitize)."""
    safe = raw[:_PROMPT_MAX].replace('\n', ' ').strip()
    low  = safe.lower()

    overlay = next(
        (v for k, v in _CONTEXT_KEYWORDS.items() if k in low),
        'friendly pointing gesture, warm expression',
    )
    wants_char = any(w in low for w in ('bdzinho', 'bot', 'mascote', 'personagem', 'robot'))

    if wants_char:
        return (
            f'{_BDZINHO_DNA}, {overlay}, {safe}, '
            f'{_DEFAULT_BG}, ultra HD, sharp 3D render, cinematic quality, '
            'WEbdEX DeFi mascot, 16:9'
        )
    return (
        f'{safe}, WEbdEX DeFi aesthetic, featuring {_BDZINHO_DNA}, {overlay}, '
        f'{_TECH_BG}, neon pink and blue accents, ultra HD, cinematic, 16:9'
    )


# ── Provider: HF FLUX.1-schnell ───────────────────────────────────────────────

def _gerar_via_flux(prompt: str) -> Optional[bytes]:
    """
    Gera imagem via FLUX.1-schnell na HuggingFace Inference API.
    Modelo Apache 2.0 — uso comercial permitido.
    Custo: ~$0.003/imagem no free tier (incluso $0.10/mês).
    Retorna bytes PNG ou None em falha.
    """
    if not _HF_TOKEN:
        logger.debug('[image_engine] HF_TOKEN ausente — skip FLUX')
        return None

    scds = _build_scds_prompt(prompt)
    logger.info('[image_engine][FLUX] Gerando | prompt=%s...', scds[:60])

    try:
        resp = requests.post(
            f'{_HF_API_BASE}/{_HF_FLUX_MODEL}',
            headers={'Authorization': f'Bearer {_HF_TOKEN}'},
            json={
                'inputs': scds,
                'parameters': {
                    'width': 1024,
                    'height': 576,
                    'num_inference_steps': 4,  # schnell: 1-4 steps suficientes
                    'guidance_scale': 0.0,     # schnell é distilled, não usa CFG
                },
            },
            timeout=_HF_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        logger.warning('[image_engine][FLUX] Timeout (%ds)', _HF_TIMEOUT)
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning('[image_engine][FLUX] Erro de rede: %s', exc)
        return None

    if resp.status_code == 200 and resp.content:
        ct = resp.headers.get('Content-Type', '')
        if 'image' in ct or len(resp.content) > 1000:
            logger.info('[image_engine][FLUX] Sucesso | %d bytes', len(resp.content))
            return resp.content

    if resp.status_code == 503:
        logger.warning('[image_engine][FLUX] Modelo carregando (503) — tente em 30s')
    elif resp.status_code == 402:
        logger.warning('[image_engine][FLUX] Free tier esgotado (402)')
    else:
        logger.warning('[image_engine][FLUX] HTTP %d: %s', resp.status_code, resp.text[:120])

    return None


# ── Provider: SDXL img2img com referência do bdZinho ─────────────────────────

def _gerar_via_img2img(prompt: str) -> Optional[bytes]:
    """
    Gera variação do bdZinho usando SDXL Refiner + imagem de referência.
    Máxima fidelidade ao personagem: dome, chifres, face pink, badge bd.
    strength=0.45 → mantém identidade, aplica contexto do prompt.
    Retorna bytes PNG ou None em falha.
    """
    if not _HF_TOKEN:
        logger.debug('[image_engine] HF_TOKEN ausente — skip img2img')
        return None

    if not os.path.exists(_BDZINHO_REF_PATH):
        logger.warning('[image_engine][img2img] Referência ausente: %s', _BDZINHO_REF_PATH)
        return None

    # Carregar e redimensionar referência (max 768px para economizar bandwidth)
    try:
        from PIL import Image as PILImage  # type: ignore[import]
        with PILImage.open(_BDZINHO_REF_PATH) as ref_img:
            ref_img = ref_img.convert('RGB')
            ref_img.thumbnail((768, 768))
            buf = io.BytesIO()
            ref_img.save(buf, format='JPEG', quality=85)
            ref_bytes = buf.getvalue()
    except ImportError:
        with open(_BDZINHO_REF_PATH, 'rb') as f:
            ref_bytes = f.read()
    except Exception as exc:
        logger.warning('[image_engine][img2img] Erro ao carregar referência: %s', exc)
        return None

    ref_b64 = base64.b64encode(ref_bytes).decode('utf-8')
    scds = _build_scds_prompt(prompt)
    logger.info('[image_engine][img2img] Gerando | prompt=%s...', scds[:60])

    try:
        resp = requests.post(
            f'{_HF_API_BASE}/{_HF_IMG2IMG_MODEL}',
            headers={'Authorization': f'Bearer {_HF_TOKEN}'},
            json={
                'inputs': ref_b64,
                'parameters': {
                    'prompt': scds,
                    'strength': _IMG2IMG_STRENGTH,
                    'guidance_scale': 7.5,
                    'num_inference_steps': 20,
                },
            },
            timeout=_IMG2IMG_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        logger.warning('[image_engine][img2img] Timeout (%ds)', _IMG2IMG_TIMEOUT)
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning('[image_engine][img2img] Erro de rede: %s', exc)
        return None

    if resp.status_code == 200 and resp.content:
        ct = resp.headers.get('Content-Type', '')
        if 'image' in ct or len(resp.content) > 1000:
            logger.info('[image_engine][img2img] Sucesso | %d bytes', len(resp.content))
            return resp.content

    if resp.status_code == 503:
        logger.warning('[image_engine][img2img] Modelo carregando (503) — tente em 30s')
    elif resp.status_code == 422:
        logger.warning('[image_engine][img2img] Parâmetros inválidos (422): %s', resp.text[:200])
    else:
        logger.warning('[image_engine][img2img] HTTP %d: %s', resp.status_code, resp.text[:120])
    return None


# ── Provider: Replicate SDXL img2img (personagem — referência visual) ────────

def _gerar_via_replicate(prompt: str) -> Optional[bytes]:
    """
    Gera imagem via Replicate SDXL img2img usando bdzinho_reference.png.
    Usa a imagem de referência para máxima fidelidade ao personagem bdZinho.
    Replicate é assíncrono — cria prediction e faz poll até concluir.
    Custo: ~$0.008/imagem (cobrado dos créditos pré-pagos).
    Retorna bytes PNG ou None em falha.
    """
    if not _REPLICATE_TOKEN:
        logger.debug('[image_engine] REPLICATE_API_TOKEN ausente — skip Replicate')
        return None

    if not os.path.exists(_BDZINHO_REF_PATH):
        logger.warning('[image_engine][Replicate] Referência ausente: %s', _BDZINHO_REF_PATH)
        return None

    # Carregar referência como data URI (Replicate aceita base64 inline)
    try:
        with open(_BDZINHO_REF_PATH, 'rb') as f:
            ref_bytes = f.read()
        ref_b64 = base64.b64encode(ref_bytes).decode('utf-8')
        ref_data_uri = f'data:image/png;base64,{ref_b64}'
    except Exception as exc:
        logger.warning('[image_engine][Replicate] Erro ao carregar referência: %s', exc)
        return None

    scds = _build_scds_prompt(prompt)
    logger.info('[image_engine][Replicate] Gerando | prompt=%s...', scds[:60])

    headers = {
        'Authorization': f'Token {_REPLICATE_TOKEN}',
        'Content-Type': 'application/json',
        'Prefer': 'wait',   # Replicate: aguarda até 60s antes de retornar async
    }

    # Criar prediction via SDXL (latest version — img2img quando image= fornecido)
    try:
        resp = requests.post(
            'https://api.replicate.com/v1/models/stability-ai/sdxl/predictions',
            headers=headers,
            json={
                'input': {
                    'prompt': scds,
                    'image': ref_data_uri,
                    'prompt_strength': 0.55,   # 55% divergência — mantém DNA, aplica contexto
                    'num_inference_steps': 25,
                    'refine': 'expert_ensemble_refiner',
                    'high_noise_frac': 0.8,
                    'negative_prompt': (
                        'human face, realistic photo, nsfw, ugly, blurry, '
                        'deformed, bad anatomy, text, watermark'
                    ),
                }
            },
            timeout=90,
        )
    except requests.exceptions.Timeout:
        logger.warning('[image_engine][Replicate] Timeout ao criar prediction')
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning('[image_engine][Replicate] Erro de rede ao criar prediction: %s', exc)
        return None

    if resp.status_code not in (200, 201):
        logger.warning('[image_engine][Replicate] HTTP %d: %s', resp.status_code, resp.text[:200])
        return None

    data = resp.json()

    # Prefer: wait — se sucesso imediato, output já vem na resposta
    if data.get('status') == 'succeeded':
        output = data.get('output')
        if output:
            img_url = output[0] if isinstance(output, list) else output
            try:
                img_resp = requests.get(img_url, timeout=30)
                if img_resp.status_code == 200 and img_resp.content:
                    logger.info('[image_engine][Replicate] Sucesso imediato | %d bytes', len(img_resp.content))
                    return img_resp.content
            except requests.exceptions.RequestException as exc:
                logger.warning('[image_engine][Replicate] Erro ao baixar imagem: %s', exc)
                return None

    prediction_id = data.get('id')
    if not prediction_id:
        logger.warning('[image_engine][Replicate] Sem prediction ID na resposta')
        return None

    poll_url = data.get('urls', {}).get('get', f'https://api.replicate.com/v1/predictions/{prediction_id}')
    poll_headers = {'Authorization': f'Token {_REPLICATE_TOKEN}'}

    # Poll até concluir
    deadline = time.time() + _REPLICATE_POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(_REPLICATE_POLL_INTERVAL)
        try:
            poll_resp = requests.get(poll_url, headers=poll_headers, timeout=10)
        except requests.exceptions.RequestException as exc:
            logger.warning('[image_engine][Replicate] Erro ao verificar prediction: %s', exc)
            return None

        if poll_resp.status_code != 200:
            logger.warning('[image_engine][Replicate] Poll HTTP %d', poll_resp.status_code)
            return None

        poll_data = poll_resp.json()
        status = poll_data.get('status')

        if status == 'succeeded':
            output = poll_data.get('output')
            if not output:
                logger.warning('[image_engine][Replicate] Sem output na resposta')
                return None
            img_url = output[0] if isinstance(output, list) else output
            try:
                img_resp = requests.get(img_url, timeout=30)
                if img_resp.status_code == 200 and img_resp.content:
                    logger.info('[image_engine][Replicate] Sucesso | %d bytes', len(img_resp.content))
                    return img_resp.content
            except requests.exceptions.RequestException as exc:
                logger.warning('[image_engine][Replicate] Erro ao baixar imagem: %s', exc)
            return None

        if status in ('failed', 'canceled'):
            error = poll_data.get('error', 'unknown')
            logger.warning('[image_engine][Replicate] Prediction %s: %s', status, error)
            return None

        logger.debug('[image_engine][Replicate] status=%s — aguardando...', status)

    logger.warning('[image_engine][Replicate] Timeout aguardando prediction (%ds)', _REPLICATE_POLL_TIMEOUT)
    return None


# ── Provider: Gemini via OpenRouter (fallback) ────────────────────────────────

def _gerar_via_gemini(prompt: str) -> Optional[bytes]:
    """
    Fallback: Gemini 2.5 Flash Image via OpenRouter.
    Reutiliza a lógica de webdex_ai_image_gen (evita duplicação).
    """
    try:
        from webdex_ai_image_gen import generate_image  # type: ignore[import]
        return generate_image(prompt)
    except ImportError:
        logger.debug('[image_engine] webdex_ai_image_gen indisponível')
        return None
    except Exception as exc:
        logger.warning('[image_engine][Gemini] Erro inesperado: %s', exc)
        return None


# ── Provider: GLM-OCR via HF ──────────────────────────────────────────────────

def _extrair_via_glm_ocr(image_bytes: bytes) -> Optional[str]:
    """
    Extrai texto de imagem via zai-org/GLM-OCR (HuggingFace).
    Modelo MIT — uso comercial permitido. 3.75M downloads.
    Suporta: OCR, tabelas, fórmulas, diagramas, handwriting.
    Retorna texto extraído ou None em falha.
    """
    if not _HF_TOKEN:
        logger.debug('[image_engine] HF_TOKEN ausente — OCR indisponível')
        return None

    logger.info('[image_engine][OCR] Analisando imagem | %d bytes', len(image_bytes))

    try:
        resp = requests.post(
            f'{_HF_API_BASE}/{_HF_OCR_MODEL}',
            headers={
                'Authorization': f'Bearer {_HF_TOKEN}',
                'Content-Type': 'application/octet-stream',
            },
            data=image_bytes,
            timeout=_OCR_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        logger.warning('[image_engine][OCR] Timeout (%ds)', _OCR_TIMEOUT)
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning('[image_engine][OCR] Erro de rede: %s', exc)
        return None

    if resp.status_code != 200:
        if resp.status_code == 503:
            logger.warning('[image_engine][OCR] Modelo carregando (503) — tente em 20s')
        else:
            logger.warning('[image_engine][OCR] HTTP %d: %s', resp.status_code, resp.text[:120])
        return None

    try:
        data = resp.json()
        # GLM-OCR retorna: [{"generated_text": "..."}, ...]
        if isinstance(data, list) and data:
            text = data[0].get('generated_text', '')
            if text:
                logger.info('[image_engine][OCR] Sucesso | %d chars extraídos', len(text))
                return text.strip()
        # Formato alternativo: {"generated_text": "..."}
        if isinstance(data, dict):
            text = data.get('generated_text', '')
            if text:
                return text.strip()
        logger.warning('[image_engine][OCR] Resposta sem texto: %s', str(data)[:100])
        return None
    except Exception as exc:
        logger.warning('[image_engine][OCR] Falha ao parsear resposta: %s', exc)
        return None


# ── PIL Enhancement ────────────────────────────────────────────────────────────

def _melhorar_via_pil(image_bytes: bytes) -> Optional[bytes]:
    """
    Melhora imagem via PIL puro — zero custo, zero API.
    Pipeline: UnsharpMask → Color enhance → Upscale 2x LANCZOS.
    """
    try:
        from PIL import Image, ImageFilter, ImageEnhance  # type: ignore[import]
    except ImportError:
        logger.warning('[image_engine][PIL] Pillow não instalado — melhorar indisponível')
        return None

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        orig_w, orig_h = img.size

        # Passo 1: UnsharpMask — realça bordas sem artefatos
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

        # Passo 2: Realce de cor suave (+10%)
        img = ImageEnhance.Color(img).enhance(1.1)

        # Passo 3: Upscale 2x com LANCZOS (máxima qualidade)
        img = img.resize((orig_w * 2, orig_h * 2), Image.LANCZOS)

        out = io.BytesIO()
        img.save(out, format='PNG', optimize=True)
        result = out.getvalue()
        logger.info(
            '[image_engine][PIL] Sucesso | %dx%d → %dx%d | %d bytes',
            orig_w, orig_h, orig_w * 2, orig_h * 2, len(result),
        )
        return result

    except Exception as exc:
        logger.warning('[image_engine][PIL] Erro: %s', exc)
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def gerar_imagem(prompt: str, user_id: int = 0) -> Optional[bytes]:
    """
    Gera imagem a partir de texto com DNA do bdZinho.

    Provider chain (personagem/bot/mascote):
      1. Replicate SDXL img2img — máxima fidelidade (usa referência visual)
      2. FLUX.1-schnell (HF)    — fallback rápido
    Provider chain (outros):
      1. FLUX.1-schnell (HF)
      2. Gemini OpenRouter (fallback)

    Args:
        prompt:  Descrição da imagem (até 400 chars, sanitizado internamente)
        user_id: ID do usuário Telegram para rate limiting (0 = sem limite)

    Returns:
        bytes PNG/JPEG ou None em caso de falha total
    """
    if user_id:
        remaining = check_cooldown(user_id, 'gerar')
        if remaining > 0:
            logger.debug('[image_engine] gerar bloqueado por cooldown: %.0fs', remaining)
            return None

    low = prompt.lower()
    wants_char = any(w in low for w in ('bdzinho', 'bot', 'mascote', 'personagem', 'robot', 'mascot'))

    if wants_char:
        # Provider 1: Replicate SDXL img2img — melhor fidelidade ao personagem
        result = _gerar_via_replicate(prompt)
        if result:
            return result
        logger.info('[image_engine] Replicate falhou — tentando FLUX')

        # Provider 2: FLUX.1-schnell (fallback)
        result = _gerar_via_flux(prompt)
        if result:
            return result
    else:
        # Provider 1: FLUX.1-schnell
        result = _gerar_via_flux(prompt)
        if result:
            return result

        # Provider 2: Gemini fallback para não-personagem
        result = _gerar_via_gemini(prompt)
        if result:
            return result

    logger.warning('[image_engine] Todos os providers de geração falharam')
    return None


def melhorar_imagem(image_bytes: bytes) -> Optional[bytes]:
    """
    Melhora qualidade de imagem: unsharp mask + upscale 2x via PIL.
    Zero custo, zero API externa — roda localmente.

    Args:
        image_bytes: Bytes da imagem original (PNG/JPEG/WebP)

    Returns:
        bytes PNG melhorado ou None em caso de falha
    """
    if not image_bytes:
        return None

    if len(image_bytes) > _IMG_MAX_BYTES:
        logger.warning(
            '[image_engine] Imagem muito grande para melhorar: %d bytes (máx %d)',
            len(image_bytes), _IMG_MAX_BYTES,
        )
        return None

    return _melhorar_via_pil(image_bytes)


def analisar_imagem_ocr(image_bytes: bytes) -> Optional[str]:
    """
    Extrai texto de uma imagem via GLM-OCR (HuggingFace).
    Suporta: texto impresso, manuscrito, tabelas, fórmulas.

    Args:
        image_bytes: Bytes da imagem (PNG/JPEG/WebP, máx 4MB)

    Returns:
        Texto extraído como string, ou None em caso de falha
    """
    if not image_bytes:
        return None

    if len(image_bytes) > _IMG_MAX_BYTES:
        logger.warning(
            '[image_engine] Imagem muito grande para OCR: %d bytes (máx %d)',
            len(image_bytes), _IMG_MAX_BYTES,
        )
        return None

    return _extrair_via_glm_ocr(image_bytes)


# ── Health Check ───────────────────────────────────────────────────────────────

def engine_status() -> dict[str, bool | str]:
    """
    Retorna status dos providers do engine.
    Útil para /admin health check.
    """
    try:
        from PIL import Image  # type: ignore[import]
        pil_ok = True
    except ImportError:
        pil_ok = False

    return {
        'flux_available':   bool(_HF_TOKEN),
        'ocr_available':    bool(_HF_TOKEN),
        'pil_available':    pil_ok,
        'gemini_available': bool(_AI_API_KEY),
        'hf_token_set':     bool(_HF_TOKEN),
        'flux_model':       _HF_FLUX_MODEL,
        'ocr_model':        _HF_OCR_MODEL,
    }
