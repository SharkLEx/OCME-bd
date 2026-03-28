"""
webdex_creatomate.py — Relatório Visual 21h via Creatomate

Template: "Personalized Welcome" (ID: 70a37ffc-ace8-4417-a0c8-2f83e3e6535d)
  Cena 1 — Título animado:  "Name"   → P&L do ciclo
  Cena 1 — Subtítulo:        texto 2  → "N trades · WR%"
  Cena 2 — Destaque:         texto 3  → "Gás $X · DD/MM/YYYY"
  Cena 3 — Branding Creatomate (fixo)

Variáveis de ambiente necessárias:
  CREATOMATE_API_KEY        — API Key do projeto Creatomate
  DISCORD_WEBHOOK_RELATORIO — Webhook do canal #relatório-diário
"""
from __future__ import annotations

import os
import copy
import json
import time
import logging

import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
_API_KEY           = os.getenv("CREATOMATE_API_KEY", "").strip()
_TEMPLATE_ID       = "70a37ffc-ace8-4417-a0c8-2f83e3e6535d"
_WEBHOOK_RELATORIO = os.getenv("DISCORD_WEBHOOK_RELATORIO", "").strip()

_BASE_URL      = "https://api.creatomate.com/v1"
_POLL_INTERVAL = 6
_POLL_TIMEOUT  = 300   # 5 min

# Cache do source do template (evita fetch repetido)
_template_source_cache: dict | None = None

if not _API_KEY:
    logger.warning("[creatomate] CREATOMATE_API_KEY não configurada — vídeos desativados")


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type":  "application/json",
    }


def _fetch_template_source() -> dict | None:
    """Busca source JSON do template (com cache em memória)."""
    global _template_source_cache
    if _template_source_cache:
        return copy.deepcopy(_template_source_cache)
    try:
        r = requests.get(
            f"{_BASE_URL}/templates/{_TEMPLATE_ID}",
            headers=_headers(),
            timeout=15,
        )
        r.raise_for_status()
        src = r.json().get("source")
        if src:
            _template_source_cache = src
            logger.info("[creatomate] Template source carregado e em cache.")
            return copy.deepcopy(src)
        logger.error("[creatomate] Template não tem 'source' no response.")
        return None
    except Exception as e:
        logger.error("[creatomate] Falha ao buscar template: %s", e)
        return None


def _replace_texts_in_source(source: dict, replacements: list[tuple[str, str]]) -> dict:
    """
    Substitui textos no source JSON do template.
    replacements = [(texto_original, texto_novo), ...]
    Percorre recursivamente todos os elementos.
    """
    src = copy.deepcopy(source)

    def _walk(node):
        if isinstance(node, dict):
            if node.get("type") == "text" and "text" in node:
                for old, new in replacements:
                    if node["text"] == old:
                        node["text"] = new
                        break
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(src)
    return src


def _create_render(source: dict) -> str | None:
    """Envia render com source JSON → retorna render ID."""
    try:
        r = requests.post(
            f"{_BASE_URL}/renders",
            headers=_headers(),
            json={"source": source},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data[0].get("id")
        return data.get("id")
    except Exception as e:
        logger.error("[creatomate] Falha ao criar render: %s", e)
        return None


def _poll_render(render_id: str) -> str | None:
    """Polling até status=succeeded → retorna URL do vídeo."""
    deadline = time.time() + _POLL_TIMEOUT
    while time.time() < deadline:
        try:
            r = requests.get(
                f"{_BASE_URL}/renders/{render_id}",
                headers=_headers(),
                timeout=15,
            )
            r.raise_for_status()
            data   = r.json()
            status = data.get("status", "")
            if status == "succeeded":
                return data.get("url")
            if status in ("failed", "deleted"):
                logger.error("[creatomate] Render %s falhou: %s", render_id, data.get("error", ""))
                return None
        except Exception as e:
            logger.error("[creatomate] Erro ao consultar render %s: %s", render_id, e)
        time.sleep(_POLL_INTERVAL)

    logger.error("[creatomate] Timeout render %s (%ds)", render_id, _POLL_TIMEOUT)
    return None


def _post_discord(video_url: str, title: str, description: str, color: int) -> bool:
    """Posta vídeo como embed + link no Discord #relatório-diário."""
    if not _WEBHOOK_RELATORIO:
        logger.warning("[creatomate] DISCORD_WEBHOOK_RELATORIO ausente")
        return False

    # Baixa o vídeo e faz upload multipart (Discord exibe inline)
    try:
        dl = requests.get(video_url, timeout=60, stream=True)
        dl.raise_for_status()
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            for chunk in dl.iter_content(chunk_size=1 << 20):
                tmp.write(chunk)
            tmp_path = tmp.name

        payload_json = json.dumps({
            "embeds": [{
                "title":       title,
                "description": description,
                "color":       color,
                "footer":      {"text": "WEbdEX Protocol · Relatório Visual · Creatomate"},
            }]
        })
        import os as _os
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                _WEBHOOK_RELATORIO,
                data={"payload_json": payload_json},
                files={"file": ("relatorio_21h.mp4", f, "video/mp4")},
                timeout=60,
            )
        _os.unlink(tmp_path)

        if resp.status_code in (200, 204):
            logger.info("[creatomate] Vídeo 21h postado no Discord.")
            return True
        logger.error("[creatomate] Discord %s: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.error("[creatomate] Erro ao postar vídeo: %s", e)
        return False


# ─────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────
def render_relatorio_21h(
    pnl:    float,
    trades: int,
    wins:   int,
    gas:    float,
    data:   str,   # "YYYY-MM-DD"
) -> bool:
    """
    Gera vídeo branded do Relatório 21h via Creatomate e posta no Discord.

    Cena 1 título  → P&L líquido destacado
    Cena 1 subtítulo → trades e WinRate
    Cena 2 destaque → gás total e data
    """
    if not _API_KEY:
        return False

    winrate  = (wins / trades * 100) if trades > 0 else 0.0
    emoji    = "🟢" if pnl >= 0 else "🔴"
    pnl_str  = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"

    try:
        from datetime import datetime
        data_fmt = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        data_fmt = data

    # Textos que serão injetados no template
    texto_titulo    = f"{emoji} {pnl_str}"
    texto_subtitulo = f"{trades} trades  ·  WinRate {winrate:.0f}%"
    texto_destaque  = f"Gás ${gas:.2f}  ·  {data_fmt}"

    source = _fetch_template_source()
    if not source:
        return False

    # Substitui os 3 textos originais do template
    modified = _replace_texts_in_source(source, [
        ("Monitoramento DeFi",                             texto_titulo),
        ("O OCMC_bd",                                      texto_subtitulo),
        ("Let your video automation journey begin today. 🚀", texto_destaque),
    ])

    logger.info("[creatomate] Renderizando relatório 21h — %s pnl=%s", data, pnl_str)

    render_id = _create_render(modified)
    if not render_id:
        return False

    logger.info("[creatomate] Render iniciado id=%s — aguardando...", render_id)
    video_url = _poll_render(render_id)
    if not video_url:
        return False

    title       = f"{emoji} Relatório Visual 21h — WEbdEX"
    description = (
        f"**P&L Líquido:** `{pnl_str}`\n"
        f"**Trades:** `{trades}` · **WinRate:** `{winrate:.0f}%`\n"
        f"**Gás Total:** `${gas:.2f}`\n"
        f"**Data:** {data_fmt}"
    )
    color = 0x00FF88 if pnl >= 0 else 0xFF4444

    return _post_discord(video_url, title, description, color)
