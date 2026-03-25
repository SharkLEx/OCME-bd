"""
webdex_ai_image.py — bdZinho MATRIX 3.0 Image Pipeline
Epic MATRIX-3 | Story MATRIX-3.4

Geração de cards visuais branded do protocolo WEbdEX via PIL puro.
Zero custo, zero APIs externas. Pronto para Discord, Instagram, Twitter/X.

Cards disponíveis:
  gerar_card_ciclo(digest)       → card 1200×675 resultado ciclo 21h
  gerar_card_milestone(tvl)      → card TVL milestone (conquista)
  gerar_card_destaque(kv_pairs)  → card genérico com métricas custom
  gerar_card_holder(n_holders)   → card de novo(s) holder(s)

Saída:
  - Arquivo PNG em bytes (io.BytesIO)
  - Opcionalmente posta no Discord como arquivo + embed

Design tokens WEbdEX:
  BG      #0A0A0A  fundo escuro
  ACCENT  #FB0491  pink
  SUCCESS #00FFB2  verde teal
  RED     #D90048  vermelho
  GOLD    #FFC832  ouro
"""
from __future__ import annotations

import io
import logging
import math
import os
import threading
import time
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Design tokens ──────────────────────────────────────────────────────────────
_BG       = (10,   10,  10)     # #0A0A0A
_BG2      = (20,   20,  25)     # fundo levemente azulado
_ACCENT   = (251,   4, 145)     # #FB0491 pink
_SUCCESS  = (  0, 255, 178)     # #00FFB2
_RED      = (217,   0,  72)     # #D90048
_GOLD     = (255, 200,  50)     # #FFC832
_WHITE    = (255, 255, 255)
_GRAY     = (130, 130, 150)
_DARK_SEP = ( 40,  40,  50)     # separador

# Card 16:9 → perfeito para Discord embed, Twitter header, YouTube thumb
_W = 1200
_H =  675

# bdZinho image (mascote)
_BDZINHO_PATH = os.getenv("BDZINHO_IMAGE_PATH", "/app/bdzinho.jpg")
_bdzinho_cache: Optional[Image.Image] = None
_bdzinho_lock  = threading.Lock()


# ── Font helpers ───────────────────────────────────────────────────────────────

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Carrega fonte. Tenta DejaVu/Liberation/fallback."""
    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/app/fonts/NotoSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/app/fonts/NotoSans-Regular.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── bdZinho mascote ────────────────────────────────────────────────────────────

def _load_bdzinho(target_h: int = 200) -> Optional[Image.Image]:
    """Carrega e redimensiona o mascote bdZinho."""
    global _bdzinho_cache
    with _bdzinho_lock:
        if _bdzinho_cache is not None:
            pass
        elif os.path.exists(_BDZINHO_PATH):
            try:
                img = Image.open(_BDZINHO_PATH).convert("RGBA")
                # Recorta circular
                size = min(img.width, img.height)
                img = img.crop(((img.width - size) // 2, (img.height - size) // 2,
                                (img.width + size) // 2, (img.height + size) // 2))
                _bdzinho_cache = img
            except Exception as e:
                logger.debug("[image] load_bdzinho falhou: %s", e)
                return None
        else:
            return None

        ratio = target_h / _bdzinho_cache.height
        w = int(_bdzinho_cache.width * ratio)
        return _bdzinho_cache.resize((w, target_h), Image.LANCZOS)


# ── Primitivas de desenho ─────────────────────────────────────────────────────

def _draw_gradient_bg(img: Image.Image) -> None:
    """Fundo com gradiente vertical sutil."""
    draw = ImageDraw.Draw(img)
    for y in range(_H):
        t = y / _H
        r = int(_BG[0] + (_BG2[0] - _BG[0]) * t)
        g = int(_BG[1] + (_BG2[1] - _BG[1]) * t)
        b = int(_BG[2] + (_BG2[2] - _BG[2]) * t)
        draw.line([(0, y), (_W, y)], fill=(r, g, b))


def _draw_accent_bar(draw: ImageDraw.Draw, y: int, h: int = 4, color=_ACCENT) -> None:
    """Barra de acento horizontal."""
    draw.rectangle([(0, y), (_W, y + h)], fill=color)


def _draw_glows(draw: ImageDraw.Draw) -> None:
    """Glow sutil nos cantos para profundidade."""
    for i in range(30):
        alpha = int(40 * (1 - i / 30))
        col = (*_ACCENT[:3], alpha)
        # top-left glow
        draw.ellipse([(-50 + i, -50 + i, 150 - i, 150 - i)], outline=(*_ACCENT, alpha), width=1)


def _text_center(draw: ImageDraw.Draw, x_center: int, y: int,
                 text: str, font, color=_WHITE) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((x_center - w // 2, y), text, font=font, fill=color)


def _metric_block(draw: ImageDraw.Draw, x: int, y: int, w: int,
                  label: str, value: str, value_color=_SUCCESS,
                  font_label=None, font_value=None) -> None:
    """Bloco de métrica: label pequeno + value grande."""
    if font_label is None:
        font_label = _font(20)
    if font_value is None:
        font_value = _font(42, bold=True)

    # Fundo do bloco
    draw.rectangle([(x, y), (x + w, y + 90)], fill=(25, 25, 32), outline=_DARK_SEP, width=1)

    # Label
    label_bbox = draw.textbbox((0, 0), label, font=font_label)
    lw = label_bbox[2] - label_bbox[0]
    draw.text((x + w // 2 - lw // 2, y + 10), label, font=font_label, fill=_GRAY)

    # Value
    val_bbox = draw.textbbox((0, 0), value, font=font_value)
    vw = val_bbox[2] - val_bbox[0]
    draw.text((x + w // 2 - vw // 2, y + 38), value, font=font_value, fill=value_color)


# ── Gerador principal: card ciclo 21h ────────────────────────────────────────

def gerar_card_ciclo(digest: Optional[dict] = None) -> io.BytesIO:
    """
    Card 1200×675 com resultado do ciclo 21h.
    Se digest=None, tenta buscar o mais recente automaticamente.
    """
    if digest is None:
        try:
            from webdex_ai_digest import get_recent_digests
            from webdex_db import conn as _dbc, DB_LOCK
            digs = get_recent_digests(_dbc, DB_LOCK, days=1)
            digest = digs[-1] if digs else {}
        except Exception:
            digest = {}

    traders  = digest.get("traders", 0)
    trades   = digest.get("trades", 0)
    wr_pct   = float(digest.get("wr_pct", 0.0))
    pnl_usd  = float(digest.get("pnl_usd", 0.0))
    tvl_usd  = float(digest.get("tvl_usd", 0.0))
    fee_bd   = float(digest.get("fee_bd", 0.0))
    date_str = digest.get("date", "hoje")

    img  = Image.new("RGB", (_W, _H), _BG)
    _draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)

    # ── Barras de acento top/bottom ──────────────────────────────────────────
    _draw_accent_bar(draw, 0, h=5, color=_ACCENT)
    _draw_accent_bar(draw, _H - 5, h=5, color=_ACCENT)

    # ── Linha vertical accent esquerda ──────────────────────────────────────
    draw.rectangle([(0, 5), (4, _H - 5)], fill=_ACCENT)

    # ── Logo / marca ─────────────────────────────────────────────────────────
    font_logo   = _font(28, bold=True)
    font_sub    = _font(18)
    font_date   = _font(16)
    font_big    = _font(52, bold=True)
    font_label  = _font(19)
    font_value  = _font(40, bold=True)
    font_footer = _font(15)

    draw.text((28, 18), "WEbdEX Protocol", font=font_logo, fill=_ACCENT)
    draw.text((28, 52), "DeFi Automated Trading · Polygon", font=font_sub, fill=_GRAY)
    draw.text((_W - 180, 28), f"Ciclo {date_str}", font=font_date, fill=_GRAY)

    # ── Separador ────────────────────────────────────────────────────────────
    _draw_accent_bar(draw, 82, h=1, color=_DARK_SEP)

    # ── P&L destaque central ─────────────────────────────────────────────────
    pnl_color = _SUCCESS if pnl_usd >= 0 else _RED
    pnl_sign  = "+" if pnl_usd >= 0 else ""
    pnl_text  = f"{pnl_sign}${pnl_usd:,.2f}"

    draw.text((28, 100), "P&L do Ciclo", font=font_label, fill=_GRAY)
    draw.text((28, 128), pnl_text, font=font_big, fill=pnl_color)

    # ── WinRate badge ─────────────────────────────────────────────────────────
    wr_text  = f"{wr_pct:.1f}%"
    wr_color = _SUCCESS if wr_pct >= 70 else (_GOLD if wr_pct >= 60 else _RED)
    # Caixa WR
    draw.rectangle([(28, 200), (200, 255)], fill=(0, 80, 60), outline=_SUCCESS, width=1)
    draw.text((40, 208), "WinRate", font=_font(15), fill=_SUCCESS)
    draw.text((40 + 72, 204), wr_text, font=_font(28, bold=True), fill=wr_color)

    # ── Métricas em bloco (linha inferior) ───────────────────────────────────
    gap   = 12
    bw    = (_W - 28 * 2 - gap * 3) // 4  # 4 blocos com gap
    by    = 290

    metrics = [
        ("TRADERS",    f"{traders:,}",           _WHITE),
        ("TRADES",     f"{trades:,}",             _WHITE),
        ("TVL",        f"${tvl_usd/1_000:.1f}K" if tvl_usd < 1_000_000
                       else f"${tvl_usd/1_000_000:.2f}M", _SUCCESS),
        ("FEE BD",     f"{fee_bd:.2f}",           _GOLD),
    ]

    for i, (lbl, val, col) in enumerate(metrics):
        bx = 28 + i * (bw + gap)
        _metric_block(draw, bx, by, bw, lbl, val, col,
                      font_label=font_label, font_value=font_value)

    # ── bdZinho mascote ───────────────────────────────────────────────────────
    bdzinho = _load_bdzinho(target_h=180)
    if bdzinho:
        # Cria máscara circular
        mask = Image.new("L", bdzinho.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([0, 0, bdzinho.width, bdzinho.height], fill=255)
        # Borda accent
        bx = _W - bdzinho.width - 28
        by_img = 95
        # Círculo de fundo
        draw.ellipse(
            [bx - 6, by_img - 6, bx + bdzinho.width + 6, by_img + bdzinho.height + 6],
            outline=_ACCENT, width=3,
        )
        img.paste(bdzinho, (bx, by_img), mask.convert("L") if bdzinho.mode == "RGBA" else None)

    # ── Linha extra: trades/traders ratio ────────────────────────────────────
    avg_trades = trades // traders if traders else 0
    insight_y = 400
    draw.text((28, insight_y),
              f"Média: {avg_trades} trades/trader · Lag: 0 blocos · Polygon",
              font=font_date, fill=_GRAY)

    # ── Separador footer ─────────────────────────────────────────────────────
    _draw_accent_bar(draw, _H - 45, h=1, color=_DARK_SEP)

    # ── Footer ────────────────────────────────────────────────────────────────
    draw.text((28, _H - 33),
              "webdex.protocol  ·  dados on-chain · Polygon Mainnet  ·  bdZinho MATRIX 3.0",
              font=font_footer, fill=_GRAY)

    # Watermark accent
    draw.text((_W - 100, _H - 33), "#WEbdEX", font=font_footer, fill=_ACCENT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ── Card Milestone ────────────────────────────────────────────────────────────

def gerar_card_milestone(tvl_usd: float, label: str = "") -> io.BytesIO:
    """Card de conquista de TVL milestone. 1200×675."""
    img  = Image.new("RGB", (_W, _H), _BG)
    _draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)

    _draw_accent_bar(draw, 0,      h=6, color=_GOLD)
    _draw_accent_bar(draw, _H - 6, h=6, color=_GOLD)
    draw.rectangle([(0, 6), (4, _H - 6)], fill=_GOLD)

    font_title   = _font(32, bold=True)
    font_big     = _font(80, bold=True)
    font_sub     = _font(24)
    font_footer  = _font(16)

    # Estrelas decorativas
    for sx, sy in [(80, 80), (200, 45), (350, 90), (_W-100, 70), (_W-220, 50)]:
        draw.text((sx, sy), "✦", font=_font(22), fill=(*_GOLD, 180))

    draw.text((28, 30), "WEbdEX Protocol", font=font_title, fill=_GOLD)
    draw.text((28, 75), "MILESTONE ATINGIDO", font=_font(20), fill=_GRAY)

    _draw_accent_bar(draw, 110, h=1, color=_DARK_SEP)

    # Valor principal
    if tvl_usd >= 1_000_000:
        tvl_text = f"${tvl_usd/1_000_000:.2f}M"
    elif tvl_usd >= 1_000:
        tvl_text = f"${tvl_usd/1_000:.0f}K"
    else:
        tvl_text = f"${tvl_usd:,.0f}"

    _text_center(draw, _W // 2, 140, "Total Value Locked", _font(26), _GRAY)
    _text_center(draw, _W // 2, 200, tvl_text, _font(100, bold=True), _GOLD)

    if label:
        _text_center(draw, _W // 2, 320, label, _font(28), _WHITE)

    _text_center(draw, _W // 2, 380,
                 "Construído pela comunidade. Verificado on-chain.",
                 _font(20), _GRAY)

    # bdZinho
    bdzinho = _load_bdzinho(target_h=160)
    if bdzinho:
        bx = _W - bdzinho.width - 28
        by_img = _H - bdzinho.height - 55
        mask = Image.new("L", bdzinho.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, bdzinho.width, bdzinho.height], fill=255)
        draw.ellipse([bx-4, by_img-4, bx+bdzinho.width+4, by_img+bdzinho.height+4],
                     outline=_GOLD, width=2)
        img.paste(bdzinho, (bx, by_img),
                  mask.convert("L") if bdzinho.mode == "RGBA" else None)

    _draw_accent_bar(draw, _H - 40, h=1, color=_DARK_SEP)
    draw.text((28, _H - 28), "webdex.protocol · Polygon Mainnet · bdZinho MATRIX 3.0",
              font=font_footer, fill=_GRAY)
    draw.text((_W - 100, _H - 28), "#WEbdEX", font=font_footer, fill=_GOLD)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ── Card Destaque genérico ────────────────────────────────────────────────────

def gerar_card_destaque(
    titulo: str,
    metricas: list[tuple[str, str, tuple]],  # [(label, value, color), ...]
    subtitulo: str = "",
) -> io.BytesIO:
    """
    Card genérico 1200×675 com título + lista de métricas.
    Útil para posts customizados.
    """
    img  = Image.new("RGB", (_W, _H), _BG)
    _draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)

    _draw_accent_bar(draw, 0,      h=5, color=_ACCENT)
    _draw_accent_bar(draw, _H - 5, h=5, color=_ACCENT)
    draw.rectangle([(0, 5), (4, _H - 5)], fill=_ACCENT)

    draw.text((28, 20), "WEbdEX Protocol", font=_font(26, bold=True), fill=_ACCENT)

    _draw_accent_bar(draw, 68, h=1, color=_DARK_SEP)

    draw.text((28, 80), titulo, font=_font(44, bold=True), fill=_WHITE)
    if subtitulo:
        draw.text((28, 140), subtitulo, font=_font(22), fill=_GRAY)

    start_y = 185 if subtitulo else 155
    gap = 12
    bw  = (_W - 56 - gap * (len(metricas) - 1)) // max(len(metricas), 1)

    for i, (lbl, val, col) in enumerate(metricas[:5]):
        bx = 28 + i * (bw + gap)
        _metric_block(draw, bx, start_y, bw, lbl, val, col)

    bdzinho = _load_bdzinho(target_h=150)
    if bdzinho and len(metricas) <= 3:
        bx = _W - bdzinho.width - 28
        by_img = 80
        mask = Image.new("L", bdzinho.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, bdzinho.width, bdzinho.height], fill=255)
        draw.ellipse([bx-4, by_img-4, bx+bdzinho.width+4, by_img+bdzinho.height+4],
                     outline=_ACCENT, width=2)
        img.paste(bdzinho, (bx, by_img),
                  mask.convert("L") if bdzinho.mode == "RGBA" else None)

    _draw_accent_bar(draw, _H - 38, h=1, color=_DARK_SEP)
    draw.text((28, _H - 26), "webdex.protocol · Polygon Mainnet · bdZinho MATRIX 3.0",
              font=_font(14), fill=_GRAY)
    draw.text((_W - 100, _H - 26), "#WEbdEX", font=_font(14), fill=_ACCENT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ── Card Novo Holder ──────────────────────────────────────────────────────────

def gerar_card_holder(n_holders: int, total_holders: int = 0) -> io.BytesIO:
    """Card de celebração de novo(s) holder(s)."""
    label = f"{'NOVOS HOLDERS' if n_holders > 1 else 'NOVO HOLDER'}!"
    sub = f"A comunidade WEbdEX cresce.\nTotal ativo: {total_holders} holders" if total_holders else ""

    metricas = [
        ("NOVOS",   str(n_holders),   _SUCCESS),
        ("TOTAL",   str(total_holders) if total_holders else "—", _WHITE),
        ("REDE",    "Polygon",         _ACCENT),
    ]
    return gerar_card_destaque(label, metricas, sub)


# ── Post para Discord ─────────────────────────────────────────────────────────

def post_card_discord(
    webhook_url: str,
    image_buf: io.BytesIO,
    filename: str = "webdex_card.png",
    title: str = "",
    description: str = "",
    color: int = 0xFB0491,
) -> bool:
    """
    Posta card PNG no Discord via webhook como upload de arquivo + embed.
    Retorna True em sucesso.
    """
    if not webhook_url:
        logger.warning("[image] webhook_url vazio — descartando post")
        return False

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "image": {"url": f"attachment://{filename}"},
        "footer": {"text": "WEbdEX Protocol · bdZinho MATRIX 3.0"},
    }

    image_buf.seek(0)
    for attempt in range(3):
        try:
            resp = requests.post(
                webhook_url,
                data={"payload_json": __import__("json").dumps({"embeds": [embed]})},
                files={"file": (filename, image_buf, "image/png")},
                timeout=30,
            )
            if resp.status_code in (200, 204):
                logger.info("[image] Card postado: %s", title)
                return True
            if resp.status_code == 429:
                time.sleep(float(resp.json().get("retry_after", 2.0)) + 0.2)
                image_buf.seek(0)
                continue
            logger.warning("[image] Discord %s: %s", resp.status_code, resp.text[:120])
            return False
        except Exception as e:
            logger.warning("[image] Tentativa %d/3 falhou: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2)
                image_buf.seek(0)
    return False


# ── Salva em arquivo local ────────────────────────────────────────────────────

def salvar_card(image_buf: io.BytesIO, path: str) -> bool:
    """Salva PNG em disco. Útil para inspecionar cards gerados."""
    try:
        image_buf.seek(0)
        with open(path, "wb") as f:
            f.write(image_buf.read())
        logger.info("[image] Card salvo: %s", path)
        return True
    except Exception as e:
        logger.warning("[image] salvar_card falhou: %s", e)
        return False


# ── CLI rápido para teste ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ciclo"

    if cmd == "ciclo":
        buf = gerar_card_ciclo()
        salvar_card(buf, "/tmp/card_ciclo.png")
        print("✅ /tmp/card_ciclo.png")

    elif cmd == "milestone":
        tvl = float(sys.argv[2]) if len(sys.argv) > 2 else 2_220_000
        buf = gerar_card_milestone(tvl, "Comunidade em crescimento!")
        salvar_card(buf, "/tmp/card_milestone.png")
        print("✅ /tmp/card_milestone.png")

    elif cmd == "destaque":
        metricas = [
            ("WinRate",  "74.5%",  (0, 255, 178)),
            ("P&L",      "+$14.2K", (0, 255, 178)),
            ("TVL",      "$2.2M",   (255, 200, 50)),
            ("Traders",  "328",     (255, 255, 255)),
        ]
        buf = gerar_card_destaque("Performance WEbdEX", metricas, "Ciclo 24/03/2026")
        salvar_card(buf, "/tmp/card_destaque.png")
        print("✅ /tmp/card_destaque.png")
