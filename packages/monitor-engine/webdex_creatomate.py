"""
webdex_creatomate.py — Geração de vídeos branded via Creatomate API

Casos de uso:
  render_relatorio_21h(pnl, trades, wins, gas, data)
      → gera vídeo "Relatório Visual 21h" com dados do protocolo
      → faz post do vídeo no canal #relatório-diário (Discord)

Configuração (.env):
  CREATOMATE_API_KEY       — API Key (Settings → API Keys no dashboard Creatomate)
  CREATOMATE_TEMPLATE_21H  — ID do template "Relatório 21h" no Creatomate

Pré-requisito no Creatomate Dashboard:
  Crie um template com os seguintes elementos nomeados:
    • "pnl_text"      — Texto do P&L líquido  (ex: "+$123.45")
    • "trades_text"   — Número de trades       (ex: "42 trades")
    • "winrate_text"  — WinRate em %           (ex: "71%")
    • "gas_text"      — Gás total              (ex: "$8.20")
    • "data_text"     — Data do relatório      (ex: "16/03/2026")
    • "status_color"  — Cor dinâmica (hex)     (#00FF88 = verde, #FF4444 = vermelho)

Fluxo:
  1. POST /v1/renders → obtém render ID (status: planned)
  2. Poll GET /v1/renders/{id} a cada 5s → aguarda status "succeeded"
  3. Posta URL do vídeo no Discord via webhook embed
"""
from __future__ import annotations

import os
import time
import logging

import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Configuração via env
# ─────────────────────────────────────────────────────────────
_API_KEY       = os.getenv("CREATOMATE_API_KEY", "").strip()
_TEMPLATE_21H  = os.getenv("CREATOMATE_TEMPLATE_21H", "").strip()
_WEBHOOK_RELATORIO = os.getenv("DISCORD_WEBHOOK_RELATORIO", "").strip()

_BASE_URL      = "https://api.creatomate.com/v1"
_POLL_INTERVAL = 6      # segundos entre polls
_POLL_TIMEOUT  = 300    # 5 min máximo de espera

if not _API_KEY:
    logger.warning("[creatomate] CREATOMATE_API_KEY não configurada — vídeos desativados")
if not _TEMPLATE_21H:
    logger.warning("[creatomate] CREATOMATE_TEMPLATE_21H não configurada — vídeos desativados")

# ─────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────
def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type":  "application/json",
    }


def _create_render(template_id: str, modifications: dict) -> str | None:
    """Envia render request → retorna render ID ou None em caso de erro."""
    payload = {
        "template_id":   template_id,
        "modifications": modifications,
    }
    try:
        resp = requests.post(
            f"{_BASE_URL}/renders",
            headers=_headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # A API pode retornar lista ou objeto único
        if isinstance(data, list):
            return data[0].get("id")
        return data.get("id")
    except Exception as e:
        logger.error("[creatomate] Falha ao criar render: %s", e)
        return None


def _poll_render(render_id: str) -> str | None:
    """Faz polling até status=succeeded → retorna URL do vídeo ou None."""
    deadline = time.time() + _POLL_TIMEOUT
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{_BASE_URL}/renders/{render_id}",
                headers=_headers(),
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")
            if status == "succeeded":
                return data.get("url")
            if status in ("failed", "deleted"):
                logger.error("[creatomate] Render %s falhou: status=%s", render_id, status)
                return None
            logger.debug("[creatomate] Render %s status=%s — aguardando...", render_id, status)
        except Exception as e:
            logger.error("[creatomate] Erro ao consultar render %s: %s", render_id, e)
        time.sleep(_POLL_INTERVAL)

    logger.error("[creatomate] Timeout aguardando render %s (%ds)", render_id, _POLL_TIMEOUT)
    return None


def _post_discord_video(video_url: str, title: str, description: str, color: int) -> bool:
    """Posta embed com vídeo no canal #relatório-diário."""
    if not _WEBHOOK_RELATORIO:
        logger.warning("[creatomate] DISCORD_WEBHOOK_RELATORIO não configurada — vídeo não postado")
        return False

    payload = {
        "embeds": [
            {
                "title":       title,
                "description": description,
                "color":       color,
                "video":       {"url": video_url},
                "footer":      {"text": "WEbdEX Protocol · Relatório Visual"},
            }
        ]
    }
    try:
        resp = requests.post(
            _WEBHOOK_RELATORIO,
            json=payload,
            timeout=15,
        )
        if resp.status_code in (200, 204):
            logger.info("[creatomate] Vídeo postado no Discord: %s", video_url)
            return True
        logger.error("[creatomate] Discord webhook retornou %s: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.error("[creatomate] Falha ao postar vídeo no Discord: %s", e)
        return False

# ─────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────
def render_relatorio_21h(
    pnl:    float,
    trades: int,
    wins:   int,
    gas:    float,
    data:   str,          # "YYYY-MM-DD"
) -> bool:
    """
    Gera vídeo "Relatório Visual 21h" via Creatomate e posta no Discord.

    Args:
        pnl:    Lucro/Prejuízo líquido em USD (ex: 123.45 ou -45.20)
        trades: Total de trades no ciclo
        wins:   Trades positivos (para WinRate)
        gas:    Gás total gasto em USD
        data:   Data no formato "YYYY-MM-DD"

    Returns:
        True se vídeo gerado e postado com sucesso, False caso contrário.
    """
    if not _API_KEY or not _TEMPLATE_21H:
        logger.debug("[creatomate] render_relatorio_21h ignorado — variáveis de env ausentes")
        return False

    winrate = (wins / trades * 100) if trades > 0 else 0.0
    pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
    color_hex = "#00FF88" if pnl >= 0 else "#FF4444"
    emoji = "🟢" if pnl >= 0 else "🔴"

    # Data formatada como DD/MM/YYYY para exibição
    try:
        from datetime import datetime
        dt = datetime.strptime(data, "%Y-%m-%d")
        data_fmt = dt.strftime("%d/%m/%Y")
    except ValueError:
        data_fmt = data

    modifications = {
        "pnl_text":     pnl_str,
        "trades_text":  f"{trades} trades",
        "winrate_text": f"{winrate:.0f}%",
        "gas_text":     f"${gas:.2f}",
        "data_text":    data_fmt,
        "status_color": color_hex,
    }

    logger.info("[creatomate] Iniciando render relatório 21h — data=%s pnl=%s", data, pnl_str)

    render_id = _create_render(_TEMPLATE_21H, modifications)
    if not render_id:
        return False

    logger.info("[creatomate] Render criado id=%s — aguardando processamento...", render_id)
    video_url = _poll_render(render_id)
    if not video_url:
        return False

    title       = f"{emoji} Relatório 21h — WEbdEX"
    description = (
        f"**P&L Líquido:** `{pnl_str}`\n"
        f"**Trades:** `{trades}` · **WinRate:** `{winrate:.0f}%`\n"
        f"**Gás Total:** `${gas:.2f}`\n"
        f"**Data:** {data_fmt}"
    )
    discord_color = 0x00FF88 if pnl >= 0 else 0xFF4444

    return _post_discord_video(video_url, title, description, discord_color)
