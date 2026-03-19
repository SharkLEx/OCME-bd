"""
creatomate_worker.py — WEbdEX Protocol
Geração automática de vídeo CICLO 21h via Creatomate API.

Story 11.1 | Epic 11 — Automação de Conteúdo
"""

import os
import time
import logging
import urllib.request
import urllib.error
import json
from typing import Optional

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("CREATOMATE_API_KEY", "")
_TEMPLATE_CICLO_ID = os.environ.get("CREATOMATE_TEMPLATE_21H", "")
_API_BASE = "https://api.creatomate.com/v1"
_POLL_INTERVAL = 3   # segundos entre checks de status
_POLL_TIMEOUT  = 90  # segundos máximo aguardando render


def _request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """Faz requisição HTTP simples sem dependências externas."""
    url = f"{_API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _download_bytes(url: str) -> bytes:
    """Faz download do vídeo gerado retornando bytes."""
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def gerar_video_ciclo(dados: dict) -> Optional[bytes]:
    """
    Gera vídeo do ciclo 21h via Creatomate e retorna bytes do MP4.

    Args:
        dados: dict com chaves:
            - profit (float): P&L do ciclo em USDC
            - ops_count (int): número de operações
            - tvl_total (float): TVL total em USDC
            - data_str (str, opcional): data formatada — padrão hoje BRT

    Returns:
        bytes do vídeo MP4, ou None se falhar (graceful degradation).
    """
    if not _API_KEY:
        logger.warning("[creatomate] CREATOMATE_API_KEY não configurada — vídeo ignorado")
        return None
    if not _TEMPLATE_CICLO_ID:
        logger.warning("[creatomate] CREATOMATE_TEMPLATE_21H não configurada — vídeo ignorado")
        return None

    profit    = dados.get("profit", 0.0)
    ops_count = dados.get("ops_count", 0)
    tvl_total = dados.get("tvl_total", 0.0)
    data_str  = dados.get("data_str", time.strftime("%d.%m.%Y"))

    pnl_sinal = "+" if profit >= 0 else ""
    pnl_valor = f"{abs(profit):,.0f}"
    pnl_cor   = "#00FFB2" if profit >= 0 else "#FF4455"
    tvl_m     = f"{tvl_total / 1_000_000:.2f}"

    payload = {
        "template_id": _TEMPLATE_CICLO_ID,
        "modifications": {
            "data":       data_str,
            "pnl_sinal":  pnl_sinal,
            "pnl_valor":  pnl_valor,
            "pnl_cor":    pnl_cor,
            "ops_count":  str(ops_count),
            "tvl_milhoes": tvl_m,
        },
    }

    try:
        logger.info("[creatomate] Iniciando render do ciclo 21h...")
        render = _request("POST", "/renders", payload)

        render_id = render[0]["id"] if isinstance(render, list) else render.get("id")
        if not render_id:
            logger.error("[creatomate] ERRO: resposta sem render_id — %s", render)
            return None

        # Poll até render completar
        elapsed = 0
        while elapsed < _POLL_TIMEOUT:
            time.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

            status_resp = _request("GET", f"/renders/{render_id}")
            status = status_resp.get("status", "")

            if status == "succeeded":
                video_url = status_resp.get("url")
                if not video_url:
                    logger.error("[creatomate] ERRO: render succeeded mas sem URL")
                    return None
                logger.info("[creatomate] Render concluído em %ds — baixando vídeo...", elapsed)
                video_bytes = _download_bytes(video_url)
                logger.info("[creatomate] Vídeo gerado: %d KB", len(video_bytes) // 1024)
                return video_bytes

            elif status == "failed":
                logger.error("[creatomate] ERRO: render falhou — %s", status_resp.get("error_message", "sem detalhes"))
                return None

            logger.debug("[creatomate] status=%s elapsed=%ds", status, elapsed)

        logger.error("[creatomate] ERRO: timeout após %ds aguardando render %s", _POLL_TIMEOUT, render_id)
        return None

    except urllib.error.HTTPError as e:
        logger.error("[creatomate] ERRO HTTP %d: %s", e.code, e.read().decode())
        return None
    except Exception as e:
        logger.error("[creatomate] ERRO inesperado: %s", e)
        return None
