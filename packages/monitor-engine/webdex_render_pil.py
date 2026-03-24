"""
webdex_render_pil.py — Geração de imagem branded do relatório 21h via PIL puro.

Zero dependências externas além de Pillow (já instalado no container).
Design system WEbdEX: fundo preto, accent #FB0491, success #00FFB2.
"""
from __future__ import annotations

import io
import json
import logging
import os
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Design tokens WEbdEX ────────────────────────────────────────────────────
_BG      = (0,   0,   0)        # preto
_ACCENT  = (251, 4,   145)      # #FB0491 — pink
_SUCCESS = (0,   255, 178)      # #00FFB2
_ERROR   = (255, 68,  85)       # #FF4455
_MUTED   = (120, 120, 120)      # cinza médio
_DIM     = (60,  60,  60)       # cinza escuro (linhas finas)
_WHITE   = (255, 255, 255)

_W, _H   = 1080, 1920           # 9:16 vertical

_WEBHOOK = os.getenv("DISCORD_WEBHOOK_RELATORIO", "").strip()

# ── Font helpers ─────────────────────────────────────────────────────────────
def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """load_default(size) funciona no Pillow 10+ sem fontes do sistema."""
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


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    """Largura real do texto (compatível Pillow 9/10/11)."""
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]
    except Exception:
        return draw.textlength(text, font=font)


def _cx(draw, text, font, width=_W) -> int:
    """X centralizado para texto."""
    return (width - _text_w(draw, text, font)) // 2


# ── Blocos de desenho ─────────────────────────────────────────────────────────
def _accent_bar(draw, y, height=14):
    draw.rectangle([(0, y), (_W, y + height)], fill=_ACCENT)


def _h_rule(draw, y, x0=80, x1=_W - 80, color=_ACCENT, thick=2):
    draw.rectangle([(x0, y), (x1, y + thick)], fill=color)


def _stat_block(draw, cx, y, value, label, vfont, lfont, vcol=_WHITE):
    """Bloco value+label centralizado em cx."""
    x = cx - _text_w(draw, value, vfont) // 2
    draw.text((x, y), value, font=vfont, fill=vcol)
    x = cx - _text_w(draw, label, lfont) // 2
    draw.text((x, y + _text_h(vfont) + 16), label, font=lfont, fill=_MUTED)


def _text_h(font) -> int:
    """Altura aproximada de uma linha."""
    try:
        bb = font.getbbox("Ag")
        return bb[3] - bb[1]
    except Exception:
        return font.size


# ── Render principal ──────────────────────────────────────────────────────────
def render_imagem(
    pnl:      float,
    trades:   int,
    wins:     int,
    traders:  int,
    tvl_usd:  float,
    bd:       float,
    data:     str,   # "YYYY-MM-DD"
) -> bytes | None:
    """
    Gera imagem 1080×1920 do relatório 21h.
    Retorna bytes PNG ou None em caso de erro.
    """
    try:
        img  = Image.new("RGB", (_W, _H), color=_BG)
        draw = ImageDraw.Draw(img)

        winrate  = (wins / trades * 100) if trades > 0 else 0.0
        positivo = pnl >= 0
        cor_pnl  = _SUCCESS if positivo else _ERROR
        pnl_sign = "+" if positivo else ""
        pnl_str  = f"{pnl_sign}{pnl:,.2f} USD"
        wr_str   = f"{winrate:.1f}%"
        tvl_fmt  = f"${tvl_usd / 1_000_000:.2f}M" if tvl_usd >= 1_000_000 else f"${tvl_usd:,.0f}"

        try:
            data_fmt = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            data_fmt = data

        # Fontes
        f_brand   = _font(62, bold=True)   # WEbdEX Protocol
        f_sub     = _font(34)              # subtítulo / data
        f_pnl     = _font(100, bold=True)  # valor P&L grande
        f_pnl_lbl = _font(32)             # label P&L
        f_val_lg  = _font(78, bold=True)  # valores stats grandes
        f_val_md  = _font(58, bold=True)  # BD
        f_lbl     = _font(30)             # labels stats
        f_bar_lbl = _font(28)             # texto abaixo da barra
        f_footer  = _font(28)

        y = 0

        # ── Barra accent topo ──────────────────────────────────────────
        _accent_bar(draw, y, 16)
        y += 16

        # ── Header ────────────────────────────────────────────────────
        y += 72
        brand = "WEbdEX Protocol"
        draw.text((_cx(draw, brand, f_brand), y), brand, font=f_brand, fill=_ACCENT)

        y += _text_h(f_brand) + 24
        sub = "RELATORIO CICLO 21H"
        draw.text((_cx(draw, sub, f_sub), y), sub, font=f_sub, fill=_MUTED)

        y += _text_h(f_sub) + 14
        draw.text((_cx(draw, data_fmt, f_sub), y), data_fmt, font=f_sub, fill=_MUTED)

        # ── Divider ───────────────────────────────────────────────────
        y += _text_h(f_sub) + 56
        _h_rule(draw, y)

        # ── P&L ───────────────────────────────────────────────────────
        y += 72
        draw.text((_cx(draw, pnl_str, f_pnl), y), pnl_str, font=f_pnl, fill=cor_pnl)

        y += _text_h(f_pnl) + 20
        lbl = "P&L Bruto do Ciclo"
        draw.text((_cx(draw, lbl, f_pnl_lbl), y), lbl, font=f_pnl_lbl, fill=_MUTED)

        # ── Divider fino ──────────────────────────────────────────────
        y += _text_h(f_pnl_lbl) + 56
        _h_rule(draw, y, x0=200, x1=_W - 200, color=_DIM, thick=1)

        # ── Stats linha 1: WinRate + Trades ───────────────────────────
        y += 64
        cx_l = _W // 4
        cx_r = 3 * _W // 4

        _stat_block(draw, cx_l, y, wr_str,         "WinRate", f_val_lg, f_lbl, vcol=_SUCCESS)
        _stat_block(draw, cx_r, y, f"{trades:,}",  "Trades",  f_val_lg, f_lbl, vcol=_WHITE)

        # ── Divider vertical entre os dois ────────────────────────────
        mid_y1 = y
        mid_y2 = y + _text_h(f_val_lg) + 16 + _text_h(f_lbl)
        draw.rectangle([(_W // 2 - 1, mid_y1), (_W // 2 + 1, mid_y2)], fill=_DIM)

        # ── Stats linha 2: Traders + Liquidez LP ──────────────────────
        y += _text_h(f_val_lg) + _text_h(f_lbl) + 72
        _h_rule(draw, y - 36, x0=200, x1=_W - 200, color=_DIM, thick=1)

        _stat_block(draw, cx_l, y, str(traders),  "Traders",     f_val_lg, f_lbl, vcol=_WHITE)
        _stat_block(draw, cx_r, y, tvl_fmt,       "Liquidez LP", f_val_lg, f_lbl, vcol=_ACCENT)

        mid_y1 = y
        mid_y2 = y + _text_h(f_val_lg) + 16 + _text_h(f_lbl)
        draw.rectangle([(_W // 2 - 1, mid_y1), (_W // 2 + 1, mid_y2)], fill=_DIM)

        # ── Divider ───────────────────────────────────────────────────
        y += _text_h(f_val_lg) + _text_h(f_lbl) + 72
        _h_rule(draw, y)

        # ── BD coletado ───────────────────────────────────────────────
        y += 60
        bd_str = f"{bd:.4f} BD"
        draw.text((_cx(draw, bd_str, f_val_md), y), bd_str, font=f_val_md, fill=_ACCENT)

        y += _text_h(f_val_md) + 18
        lbl_bd = "Coletado pelo Protocolo"
        draw.text((_cx(draw, lbl_bd, f_lbl), y), lbl_bd, font=f_lbl, fill=_MUTED)

        # ── Barra WinRate ─────────────────────────────────────────────
        y += _text_h(f_lbl) + 60
        bx0, bx1 = 80, _W - 80
        bw   = bx1 - bx0
        bh   = 28
        # Fundo
        draw.rectangle([(bx0, y), (bx1, y + bh)], fill=_DIM)
        # Preenchimento
        fill_w = int(bw * min(winrate / 100, 1.0))
        if fill_w > 0:
            # gradiente simples: verde com leve brilho
            draw.rectangle([(bx0, y), (bx0 + fill_w, y + bh)], fill=_SUCCESS)
        # Borda accent
        draw.rectangle([(bx0, y), (bx1, y + bh)], outline=_DIM, width=1)

        y += bh + 16
        bar_txt = f"WR {winrate:.1f}%   {wins:,} wins / {trades:,} trades"
        draw.text((_cx(draw, bar_txt, f_bar_lbl), y), bar_txt, font=f_bar_lbl, fill=_MUTED)

        # ── Barra accent rodapé ───────────────────────────────────────
        _accent_bar(draw, _H - 16, 16)

        # ── Footer ────────────────────────────────────────────────────
        foot = "webdex.finance  |  Ciclo 21h BRT  |  Polygon"
        draw.text((_cx(draw, foot, f_footer), _H - 58), foot, font=f_footer, fill=_MUTED)

        # ── Export PNG ────────────────────────────────────────────────
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    except Exception as e:
        logger.error("[pil_render] Erro ao gerar imagem: %s", e, exc_info=True)
        return None


def post_discord(
    img_bytes: bytes,
    pnl:       float,
    traders:   int,
    trades:    int,
    winrate:   float,
    tvl_usd:   float,
    bd:        float,
    data_fmt:  str,
) -> bool:
    """Posta imagem PNG no Discord via webhook."""
    if not _WEBHOOK:
        logger.warning("[pil_render] DISCORD_WEBHOOK_RELATORIO ausente")
        return False

    positivo = pnl >= 0
    cor      = 0x00FFB2 if positivo else 0xFF4455
    emoji    = "🟢" if positivo else "🔴"
    pnl_str  = f"+${pnl:,.2f}" if positivo else f"-${abs(pnl):,.2f}"

    payload = {
        "embeds": [{
            "title":       f"{emoji} Relatório Ciclo 21h — WEbdEX Protocol",
            "description": (
                f"**P&L Bruto:** `{pnl_str}`\n"
                f"**Traders:** `{traders}` · **Trades:** `{trades:,}`\n"
                f"**WinRate:** `{winrate:.1f}%`\n"
                f"**Liquidez LP:** `${tvl_usd:,.0f}`\n"
                f"**BD Coletado:** `{bd:.4f}`\n"
                f"**Data:** {data_fmt}"
            ),
            "color": cor,
            "footer": {"text": "WEbdEX Protocol · Relatório Visual"},
        }]
    }
    try:
        resp = requests.post(
            _WEBHOOK,
            data={"payload_json": json.dumps(payload)},
            files={"file": ("relatorio_21h.png", img_bytes, "image/png")},
            timeout=30,
        )
        if resp.status_code in (200, 204):
            logger.info("[pil_render] Imagem postada no Discord.")
            return True
        logger.error("[pil_render] Discord %s: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.error("[pil_render] Erro ao postar: %s", e)
        return False


def render_e_postar_relatorio(
    pnl:      float,
    trades:   int,
    wins:     int,
    traders:  int,
    tvl_usd:  float,
    bd:       float,
    data:     str,
) -> bool:
    """API pública: gera imagem PIL e posta no Discord. Sem APIs externas."""
    try:
        data_fmt = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        data_fmt = data

    winrate = (wins / trades * 100) if trades > 0 else 0.0

    img_bytes = render_imagem(
        pnl=pnl, trades=trades, wins=wins,
        traders=traders, tvl_usd=tvl_usd, bd=bd, data=data,
    )
    if not img_bytes:
        return False

    return post_discord(
        img_bytes=img_bytes,
        pnl=pnl, traders=traders, trades=trades,
        winrate=winrate, tvl_usd=tvl_usd, bd=bd, data_fmt=data_fmt,
    )
