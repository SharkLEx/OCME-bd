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
import textwrap
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Design tokens WEbdEX ────────────────────────────────────────────────────
_BG         = (0,   0,   0)        # preto
_ACCENT     = (251, 4,   145)      # #FB0491 — pink
_SUCCESS    = (0,   255, 178)      # #00FFB2
_ERROR      = (255, 68,  85)       # #FF4455
_MUTED      = (100, 100, 100)      # cinza
_WHITE      = (255, 255, 255)

_W, _H      = 1080, 1920           # 9:16 vertical

_WEBHOOK    = os.getenv("DISCORD_WEBHOOK_RELATORIO", "").strip()

# ── Font helpers ─────────────────────────────────────────────────────────────
def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Tenta carregar uma fonte do sistema; fallback para default do PIL."""
    candidates_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]
    candidates_regular = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    ]
    for path in (candidates_bold if bold else candidates_regular):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ── Render principal ─────────────────────────────────────────────────────────
def render_imagem(
    pnl:      float,
    trades:   int,
    wins:     int,
    traders:  int,
    tvl_usd:  float,
    bd:       float,
    data:     str,    # "YYYY-MM-DD"
) -> bytes | None:
    """
    Gera imagem 1080×1920 do relatório 21h.
    Retorna bytes PNG ou None em caso de erro.
    """
    try:
        img  = Image.new("RGB", (_W, _H), color=_BG)
        draw = ImageDraw.Draw(img)

        winrate = (wins / trades * 100) if trades > 0 else 0.0
        positivo = pnl >= 0
        cor_resultado = _SUCCESS if positivo else _ERROR
        emoji_pnl = "▲" if positivo else "▼"
        pnl_str   = f"{'+' if positivo else ''}{pnl:,.2f} USD"
        wr_str    = f"{winrate:.1f}%"

        try:
            data_fmt = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            data_fmt = data

        # ── Linha accent no topo ──────────────────────────────────────────
        draw.rectangle([(0, 0), (_W, 12)], fill=_ACCENT)

        # ── Header: WEBDEX PROTOCOL ───────────────────────────────────────
        y = 80
        f_title = _font(52, bold=True)
        draw.text((_W // 2, y), "WEbdEX Protocol", font=f_title,
                  fill=_ACCENT, anchor="mm")

        y += 64
        f_sub = _font(32)
        draw.text((_W // 2, y), "RELATÓRIO CICLO 21H", font=f_sub,
                  fill=_MUTED, anchor="mm")

        y += 40
        draw.text((_W // 2, y), data_fmt, font=f_sub,
                  fill=_MUTED, anchor="mm")

        # ── Divisor ───────────────────────────────────────────────────────
        y += 70
        draw.rectangle([(80, y), (_W - 80, y + 2)], fill=_ACCENT)

        # ── P&L principal ─────────────────────────────────────────────────
        y += 100
        f_emoji = _font(80, bold=True)
        draw.text((_W // 2, y), emoji_pnl, font=f_emoji,
                  fill=cor_resultado, anchor="mm")

        y += 110
        f_pnl = _font(96, bold=True)
        draw.text((_W // 2, y), pnl_str, font=f_pnl,
                  fill=cor_resultado, anchor="mm")

        y += 70
        draw.text((_W // 2, y), "P&L Bruto do Ciclo", font=f_sub,
                  fill=_MUTED, anchor="mm")

        # ── Divisor fino ──────────────────────────────────────────────────
        y += 80
        draw.rectangle([(200, y), (_W - 200, y + 1)], fill=_MUTED)

        # ── Stats: WinRate + Trades ───────────────────────────────────────
        y += 80
        f_stat_val = _font(72, bold=True)
        f_stat_lbl = _font(30)

        cx_left  = _W // 4
        cx_right = 3 * _W // 4

        # WinRate
        draw.text((cx_left, y), wr_str, font=f_stat_val,
                  fill=_SUCCESS, anchor="mm")
        draw.text((cx_left, y + 80), "WinRate", font=f_stat_lbl,
                  fill=_MUTED, anchor="mm")

        # Trades
        draw.text((cx_right, y), f"{trades:,}", font=f_stat_val,
                  fill=_WHITE, anchor="mm")
        draw.text((cx_right, y + 80), "Trades", font=f_stat_lbl,
                  fill=_MUTED, anchor="mm")

        # ── Stats: Traders + TVL ──────────────────────────────────────────
        y += 200
        draw.text((cx_left, y), f"{traders}", font=f_stat_val,
                  fill=_WHITE, anchor="mm")
        draw.text((cx_left, y + 80), "Traders", font=f_stat_lbl,
                  fill=_MUTED, anchor="mm")

        tvl_fmt = f"${tvl_usd/1_000_000:.2f}M" if tvl_usd >= 1_000_000 else f"${tvl_usd:,.0f}"
        draw.text((cx_right, y), tvl_fmt, font=f_stat_val,
                  fill=_ACCENT, anchor="mm")
        draw.text((cx_right, y + 80), "TVL", font=f_stat_lbl,
                  fill=_MUTED, anchor="mm")

        # ── Divisor ───────────────────────────────────────────────────────
        y += 180
        draw.rectangle([(80, y), (_W - 80, y + 2)], fill=_ACCENT)

        # ── BD coletado ───────────────────────────────────────────────────
        y += 80
        f_bd = _font(52, bold=True)
        draw.text((_W // 2, y), f"{bd:.4f} BD", font=f_bd,
                  fill=_ACCENT, anchor="mm")
        draw.text((_W // 2, y + 64), "Coletado pelo Protocolo", font=f_stat_lbl,
                  fill=_MUTED, anchor="mm")

        # ── Barra WinRate visual ──────────────────────────────────────────
        y += 160
        bar_x0, bar_x1 = 80, _W - 80
        bar_w = bar_x1 - bar_x0
        bar_h = 24
        draw.rectangle([(bar_x0, y), (bar_x1, y + bar_h)], fill=_MUTED)
        fill_w = int(bar_w * min(winrate / 100, 1.0))
        if fill_w > 0:
            draw.rectangle([(bar_x0, y), (bar_x0 + fill_w, y + bar_h)],
                           fill=_SUCCESS)

        draw.text((bar_x0, y + bar_h + 16), f"WR {winrate:.1f}%  ·  {wins:,} wins / {trades:,} trades",
                  font=f_stat_lbl, fill=_MUTED)

        # ── Linha accent no rodapé ─────────────────────────────────────────
        draw.rectangle([(0, _H - 12), (_W, _H)], fill=_ACCENT)

        # ── Rodapé ────────────────────────────────────────────────────────
        f_footer = _font(28)
        draw.text((_W // 2, _H - 50), "webdex.finance  ·  Ciclo 21h BRT",
                  font=f_footer, fill=_MUTED, anchor="mm")

        # ── Exportar bytes ────────────────────────────────────────────────
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    except Exception as e:
        logger.error("[pil_render] Erro ao gerar imagem: %s", e)
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
                f"**TVL:** `${tvl_usd:,.0f}`\n"
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
