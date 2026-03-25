"""
webdex_local_animate.py — Animações bdZinho via PIL puro (zero custo).

Substitui webdex_discord_animate.py (Replicate ~$0.20/clip) com geração
local de GIF animado.  API 100% idêntica — drop-in replacement.

Técnica:
  - 24 frames a 80 ms/frame (~1.9 s loop) como GIF animado
  - Ken Burns: zoom suave 1.0 → 1.15 + pan lateral leve
  - Efeitos por evento: confetti, sparkles, coins, wave, pulse
  - Overlay branded: logotipo + texto do evento + borda accent

Requerimentos: Pillow (já instalado no container ocme-monitor)
"""
from __future__ import annotations

import atexit
import hashlib
import io
import json
import logging
import math
import os
import random
import tempfile
import threading
import time
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Design tokens WEbdEX ────────────────────────────────────────────────────
_BG      = (0,   0,   0)
_ACCENT  = (251,   4, 145)   # #FB0491 pink
_SUCCESS = (0,   255, 178)   # #00FFB2
_ERROR   = (255,  68,  85)   # #FF4455
_GOLD    = (255, 200,  50)
_WHITE   = (255, 255, 255)

# Dimensões do GIF
_GIF_W   = 600
_GIF_H   = 600
_FRAMES  = 24
_DELAY   = 80   # ms por frame

# URL e path local do bdZinho mascote
_BDZINHO_URL  = os.getenv(
    "BDZINHO_IMAGE_URL",
    "https://i.ibb.co/MkcqbvLb/post-149-operador-da-tecnologia-01.jpg",
)
_BDZINHO_PATH = os.getenv("BDZINHO_IMAGE_PATH", "")

# Cache da imagem (carregada uma vez, reutilizada em todos os eventos)
_bdzinho_cache: Optional[Image.Image] = None
_bdzinho_lock  = threading.Lock()

# Rate control (reutiliza mesma lógica do módulo Replicate)
_MAX_CLIPS_PER_DAY = 20   # custo zero — limite mais alto
_clips_today: dict = {"date": "", "count": 0}
_clips_lock = threading.Lock()

# Threads ativas
_active_anims: list[threading.Thread] = []
_active_anims_lock = threading.Lock()


# ── Font helper ──────────────────────────────────────────────────────────────
def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Carrega fonte do sistema ou fallback para default."""
    candidates_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]
    candidates_reg = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in (candidates_bold if bold else candidates_reg):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default(size=size)


# ── Configuração por evento ──────────────────────────────────────────────────
_EVENT_CFG: dict[str, dict] = {
    "new_holder": {
        "color": _SUCCESS, "effect": "confetti",
        "label": "NOVO HOLDER", "emoji": "🎉",
    },
    "milestone": {
        "color": _ACCENT, "effect": "sparkles",
        "label": "MILESTONE", "emoji": "🏆",
    },
    "gm": {
        "color": _GOLD, "effect": "wave",
        "label": "GM WEbdEX", "emoji": "🌅",
    },
    "trade_win": {
        "color": _SUCCESS, "effect": "coins",
        "label": "TRADE WIN", "emoji": "💚",
    },
    "relatorio_win": {
        "color": _SUCCESS, "effect": "confetti",
        "label": "CICLO POSITIVO", "emoji": "🟢",
    },
    "relatorio_loss": {
        "color": _ERROR, "effect": "pulse",
        "label": "CICLO NEGATIVO", "emoji": "🔴",
    },
}
_DEFAULT_CFG = _EVENT_CFG["milestone"]


# ── Carregamento do bdZinho ──────────────────────────────────────────────────
def _load_bdzinho() -> Optional[Image.Image]:
    """Carrega o bdZinho com fallback progressivo (local → URL → logo → placeholder)."""
    global _bdzinho_cache

    with _bdzinho_lock:
        if _bdzinho_cache is not None:
            return _bdzinho_cache

        img = _try_load_local() or _try_load_url() or _try_load_logo() or _make_placeholder()
        if img:
            _bdzinho_cache = img.resize((_GIF_W, _GIF_H), Image.LANCZOS).convert("RGBA")
            logger.info("[local_animate] bdZinho carregado (%dx%d).",
                        _bdzinho_cache.width, _bdzinho_cache.height)
        return _bdzinho_cache


def _try_load_local() -> Optional[Image.Image]:
    path = _BDZINHO_PATH
    if not path:
        # Tenta encontrar no mesmo diretório do módulo
        base = os.path.dirname(os.path.abspath(__file__))
        for name in ("bdzinho.jpg", "bdzinho.png", "webdex_logo.jpeg", "webdex_logo.jpg"):
            p = os.path.join(base, name)
            if os.path.exists(p):
                path = p
                break
    if path and os.path.exists(path):
        try:
            return Image.open(path).convert("RGBA")
        except Exception as e:
            logger.debug("[local_animate] load_local %s: %s", path, e)
    return None


def _try_load_url() -> Optional[Image.Image]:
    if not _BDZINHO_URL:
        return None
    try:
        r = requests.get(_BDZINHO_URL, timeout=15)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception as e:
        logger.debug("[local_animate] load_url: %s", e)
    return None


def _try_load_logo() -> Optional[Image.Image]:
    base = os.path.dirname(os.path.abspath(__file__))
    for name in ("webdex_logo.jpeg", "webdex_logo.jpg", "webdex_logo.png"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            try:
                return Image.open(p).convert("RGBA")
            except Exception:
                pass
    return None


def _make_placeholder() -> Image.Image:
    """Gera placeholder circular com as cores WEbdEX caso nenhuma imagem seja encontrada."""
    img  = Image.new("RGBA", (_GIF_W, _GIF_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy, r = _GIF_W // 2, _GIF_H // 2, _GIF_W // 2 - 20
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(30, 30, 30, 255), outline=_ACCENT, width=8)
    f = _font(120, bold=True)
    draw.text((cx - 70, cy - 70), "BD", font=f, fill=_ACCENT)
    return img


# ── Gerador de frames ────────────────────────────────────────────────────────
def _ken_burns_crop(img: Image.Image, frame: int, total: int) -> Image.Image:
    """
    Aplica efeito Ken Burns: zoom de 1.0 → 1.15 + pan diagonal suave.
    Retorna imagem RGB _GIF_W×_GIF_H.
    """
    W, H = img.width, img.height
    t    = frame / max(total - 1, 1)   # 0.0 → 1.0

    # Zoom: começa normal, cresce suavemente
    zoom  = 1.0 + 0.15 * t

    # Pan: drift leve do canto superior-esquerdo para o centro
    px = int(W * 0.04 * t)   # deslocamento x máx 4%
    py = int(H * 0.03 * t)   # deslocamento y máx 3%

    crop_w = int(W / zoom)
    crop_h = int(H / zoom)
    x0 = max(0, px)
    y0 = max(0, py)
    x1 = min(W, x0 + crop_w)
    y1 = min(H, y0 + crop_h)

    cropped = img.crop((x0, y0, x1, y1))
    return cropped.resize((_GIF_W, _GIF_H), Image.LANCZOS).convert("RGB")


def _draw_effect(draw: ImageDraw.ImageDraw, frame: int, effect: str,
                 color: tuple, rng: random.Random) -> None:
    """Desenha partículas/efeito sobre o frame (in-place)."""
    if effect == "confetti":
        _effect_confetti(draw, frame, rng)
    elif effect == "sparkles":
        _effect_sparkles(draw, frame, color, rng)
    elif effect == "coins":
        _effect_coins(draw, frame, rng)
    elif effect == "wave":
        _effect_wave(draw, frame, color)
    elif effect == "pulse":
        _effect_pulse(draw, frame, color)


def _effect_confetti(draw: ImageDraw.ImageDraw, frame: int,
                     rng: random.Random) -> None:
    colors = [_ACCENT, _SUCCESS, _GOLD, _WHITE, (100, 200, 255)]
    for i in range(30):
        rng.seed(i * 997 + frame * 13)
        x  = rng.randint(0, _GIF_W)
        y  = (rng.randint(0, _GIF_H) + frame * 14 * (i % 3 + 1)) % _GIF_H
        sz = rng.randint(4, 10)
        c  = colors[i % len(colors)]
        rot = (frame * 15 + i * 37) % 360
        # Rects rotacionados simulados como ellipses levemente achatados
        draw.ellipse([(x, y), (x + sz, y + sz // 2)], fill=c)


def _effect_sparkles(draw: ImageDraw.ImageDraw, frame: int,
                     color: tuple, rng: random.Random) -> None:
    for i in range(20):
        rng.seed(i * 1031 + 7)
        x   = rng.randint(30, _GIF_W - 30)
        y   = rng.randint(30, _GIF_H - 30)
        # Alpha piscante por frame
        phase = math.sin((frame / _FRAMES) * 2 * math.pi + i * 0.5)
        if phase > 0.3:
            sz = int(3 + 6 * phase)
            draw.ellipse([(x - sz, y - sz), (x + sz, y + sz)], fill=color)
            # Cruz de brilho
            draw.line([(x - sz * 2, y), (x + sz * 2, y)], fill=color, width=1)
            draw.line([(x, y - sz * 2), (x, y + sz * 2)], fill=color, width=1)


def _effect_coins(draw: ImageDraw.ImageDraw, frame: int,
                  rng: random.Random) -> None:
    for i in range(15):
        rng.seed(i * 853)
        x  = rng.randint(20, _GIF_W - 20)
        y0 = rng.randint(-_GIF_H // 2, 0)
        speed = rng.randint(8, 20)
        y  = (y0 + frame * speed) % (_GIF_H + 40)
        r  = rng.randint(6, 12)
        draw.ellipse([(x - r, y - r), (x + r, y + r)],
                     fill=_GOLD, outline=_SUCCESS, width=1)
        draw.text((x - r + 3, y - r + 2), "$", font=_font(r), fill=_BG)


def _effect_wave(draw: ImageDraw.ImageDraw, frame: int, color: tuple) -> None:
    """Onda horizontal suave na parte inferior."""
    phase = (frame / _FRAMES) * 2 * math.pi
    y_base = _GIF_H - 80
    pts = []
    for x in range(0, _GIF_W, 3):
        y = int(y_base + 30 * math.sin(x / 60 + phase))
        pts.append((x, y))
    # Borda suave — draw linha poly
    if len(pts) >= 2:
        draw.line(pts, fill=color, width=3)
    # Segunda onda defasada
    pts2 = []
    for x in range(0, _GIF_W, 3):
        y = int(y_base + 20 * math.sin(x / 50 + phase + 1.0))
        pts2.append((x, y))
    if len(pts2) >= 2:
        draw.line(pts2, fill=(*color[:3],), width=2)


def _effect_pulse(draw: ImageDraw.ImageDraw, frame: int, color: tuple) -> None:
    """Pulso radial crescente da borda — usado em relatorio_loss."""
    cx, cy = _GIF_W // 2, _GIF_H // 2
    # 3 anéis com fases distintas
    for offset in range(3):
        phase = ((frame + offset * (_FRAMES // 3)) % _FRAMES) / _FRAMES
        r = int(phase * math.sqrt(cx**2 + cy**2))
        if r > 0:
            alpha_factor = max(0, 1.0 - phase)
            fill = tuple(int(c * alpha_factor * 0.6) for c in color)
            draw.ellipse(
                [(cx - r, cy - r), (cx + r, cy + r)],
                outline=color, width=max(1, int(3 * alpha_factor)),
            )


# ── Overlay branded ──────────────────────────────────────────────────────────
def _draw_overlay(base: Image.Image, label: str, color: tuple) -> Image.Image:
    """
    Adiciona sobre o frame RGB:
    - Gradiente alpha na borda inferior (escurece para legibilidade)
    - Barra accent superior (6px)
    - Barra accent inferior (6px)
    - Texto WEbdEX + label do evento
    """
    out  = base.convert("RGBA")
    ovl  = Image.new("RGBA", (_GIF_W, _GIF_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ovl)

    # Gradiente inferior: faixa de 180px escurecida para texto
    for y in range(_GIF_H - 180, _GIF_H):
        alpha = int(180 * (y - (_GIF_H - 180)) / 180)
        draw.rectangle([(0, y), (_GIF_W, y + 1)], fill=(0, 0, 0, alpha))

    # Barra accent top
    draw.rectangle([(0, 0), (_GIF_W, 6)], fill=(*color, 220))
    # Barra accent bottom
    draw.rectangle([(0, _GIF_H - 6), (_GIF_W, _GIF_H)], fill=(*color, 220))

    out = Image.alpha_composite(out, ovl)
    draw2 = ImageDraw.Draw(out)

    # Logo texto "WEbdEX" topo-esquerdo
    f_logo  = _font(22, bold=True)
    draw2.text((12, 10), "WEbdEX", font=f_logo, fill=(*color, 230))

    # Label do evento no rodapé centralizado
    f_lbl  = _font(32, bold=True)
    tw     = _measure_text(draw2, label, f_lbl)
    tx     = (_GIF_W - tw) // 2
    # Sombra
    draw2.text((tx + 1, _GIF_H - 54 + 1), label, font=f_lbl, fill=(0, 0, 0, 200))
    draw2.text((tx, _GIF_H - 54),          label, font=f_lbl, fill=(*color, 255))

    return out.convert("RGB")


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]
    except Exception:
        return len(text) * font.size // 2


# ── Gerador do GIF ───────────────────────────────────────────────────────────
def generate_gif(event: str) -> Optional[bytes]:
    """
    Gera GIF animado para o evento.
    Retorna bytes do GIF ou None em caso de erro.
    """
    cfg  = _EVENT_CFG.get(event, _DEFAULT_CFG)
    base = _load_bdzinho()
    if base is None:
        logger.error("[local_animate] Não foi possível carregar imagem base.")
        return None

    effect = cfg["effect"]
    color  = cfg["color"]
    label  = cfg["label"]

    # RNG determinístico por evento (mesmas partículas em cada loop)
    seed_hash = int(hashlib.md5(event.encode()).hexdigest()[:8], 16)
    rng       = random.Random(seed_hash)

    frames: list[Image.Image] = []
    for i in range(_FRAMES):
        # 1. Ken Burns
        frame_rgb = _ken_burns_crop(base, i, _FRAMES)

        # 2. Efeitos de partículas
        draw = ImageDraw.Draw(frame_rgb)
        _draw_effect(draw, i, effect, color, random.Random(seed_hash + i))

        # 3. Overlay branded
        frame_final = _draw_overlay(frame_rgb, label, color)

        # 4. Quantizar para paleta GIF (256 cores)
        frames.append(
            frame_final.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
        )

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=_DELAY,
        loop=0,
        optimize=True,
    )
    size_kb = len(buf.getvalue()) / 1024
    logger.info("[local_animate] GIF gerado: %s — %.0f KB, %d frames.",
                event, size_kb, _FRAMES)
    return buf.getvalue()


# ── Post Discord ─────────────────────────────────────────────────────────────
def _post_gif(gif_bytes: bytes, webhook_url: str, title: str,
              description: str, color: int) -> bool:
    """Posta GIF no Discord via webhook com embed."""
    payload_json = {
        "embeds": [{
            "title":       title,
            "description": description,
            "color":       color,
            "footer":      {"text": "WEbdEX Protocol · bdZinho"},
        }],
    }
    try:
        resp = requests.post(
            webhook_url,
            data={"payload_json": json.dumps(payload_json)},
            files={"file": ("bdzinho.gif", gif_bytes, "image/gif")},
            timeout=30,
        )
        if resp.status_code not in (200, 204):
            logger.warning("[local_animate] Webhook %s: %s",
                           resp.status_code, resp.text[:120])
            return False
        logger.info("[local_animate] GIF postado inline → %s", title)
        return True
    except Exception as e:
        logger.warning("[local_animate] Erro ao postar no Discord: %s", e)
        return False


# ── Rate control ─────────────────────────────────────────────────────────────
def _reserve_slot() -> bool:
    with _clips_lock:
        today = time.strftime("%Y-%m-%d")
        if _clips_today["date"] != today:
            _clips_today["date"]  = today
            _clips_today["count"] = 0
        if _clips_today["count"] >= _MAX_CLIPS_PER_DAY:
            logger.info("[local_animate] Limite diário (%d) atingido.", _MAX_CLIPS_PER_DAY)
            return False
        _clips_today["count"] += 1
        return True


def _release_slot() -> None:
    with _clips_lock:
        if _clips_today["count"] > 0:
            _clips_today["count"] -= 1


# ── Shutdown gracioso ────────────────────────────────────────────────────────
def _cleanup_on_exit() -> None:
    with _active_anims_lock:
        threads = list(_active_anims)
    for t in threads:
        t.join(timeout=30)


atexit.register(_cleanup_on_exit)


# ── API pública (drop-in de webdex_discord_animate.py) ───────────────────────
def animate_and_post(
    event:       str,
    webhook_url: str,
    title:       str = "",
    description: str = "",
    color:       int = 0x00FFB2,
) -> None:
    """
    Gera GIF animado do bdZinho localmente e posta no Discord.
    Assíncrono — não bloqueia o worker chamador.

    Args:
        event:       "new_holder" | "milestone" | "gm" | "trade_win"
                     | "relatorio_win" | "relatorio_loss"
        webhook_url: URL do webhook Discord
        title:       Título do embed
        description: Texto do embed
        color:       Cor do embed (int hex)
    """
    if not webhook_url:
        logger.warning("[local_animate] webhook_url ausente — skipping.")
        return

    if not _reserve_slot():
        return

    def _run() -> None:
        slot_ok = False
        try:
            gif_bytes = generate_gif(event)
            if not gif_bytes:
                return

            ok = _post_gif(gif_bytes, webhook_url, title, description, color)
            if ok:
                slot_ok = True
            else:
                logger.warning("[local_animate] GIF gerado mas não postado (evento=%s).", event)
        except Exception as e:
            logger.warning("[local_animate] Erro inesperado (evento=%s): %s", event, e)
        finally:
            if not slot_ok:
                _release_slot()
            current = threading.current_thread()
            with _active_anims_lock:
                try:
                    _active_anims.remove(current)
                except ValueError:
                    pass

    t = threading.Thread(target=_run, name=f"local_anim_{event}")
    with _active_anims_lock:
        _active_anims.append(t)
    t.start()
