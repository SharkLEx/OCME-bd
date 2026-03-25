"""
webdex_ai_cycle_visual.py — bdZinho Visual Expressão Pós-Ciclo

Após cada ciclo 21h, gera UMA imagem do bdZinho com a expressão adequada
e posta no Discord (#relatório-diário). Representa emocionalmente o resultado.

Expressões:
  CELEBRANDO  → ciclo positivo (p_bruto >= 0)
  PROFISSIONAL → ciclo negativo (p_bruto < 0)
  NEUTRO       → sem trades (p_total == 0)
"""
from __future__ import annotations

import logging
import os
import time
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# ── Deps ───────────────────────────────────────────────────────────────────────
try:
    from webdex_ai_image_gen import generate_image
    _IMG_GEN_AVAILABLE = True
except ImportError:
    _IMG_GEN_AVAILABLE = False
    generate_image = None  # type: ignore

try:
    import requests as _requests
    _HTTP_AVAILABLE = True
except ImportError:
    _HTTP_AVAILABLE = False

# ── Config ─────────────────────────────────────────────────────────────────────
_CYCLE_VISUAL_ENABLED = os.environ.get("CYCLE_VISUAL_ENABLED", "true").lower() == "true"
_WEBHOOK_RELATORIO    = os.environ.get("DISCORD_WEBHOOK_RELATORIO", "")

# ── Prompts de expressão (usa Design Bible DNA) ────────────────────────────────
_PROMPT_CELEBRANDO = (
    "bdZinho robot mascot 3D render, cream white body, hot pink face (#FF2D78), "
    "two white pointed horns, 'bd' badge on chest, "
    "CELEBRATING — both arms raised high in victory, confetti and golden particles floating, "
    "big joyful smile, dynamic pose, dark wine background #1A0010 with warm golden glow, "
    "vinyl toy style, Funko proportions, cinematic lighting, ultra HD, WEbdEX DeFi mascot"
)

_PROMPT_PROFISSIONAL = (
    "bdZinho robot mascot 3D render, cream white body, hot pink face (#FF2D78), "
    "two white pointed horns, 'bd' badge on chest, "
    "PROFESSIONAL — arms crossed confidently, calm determined expression, "
    "slight analytical tilt of head, dark wine background #1A0010 with cool blue accent, "
    "vinyl toy style, Funko proportions, cinematic lighting, ultra HD, WEbdEX DeFi mascot"
)

_PROMPT_NEUTRO = (
    "bdZinho robot mascot 3D render, cream white body, hot pink face (#FF2D78), "
    "two white pointed horns, 'bd' badge on chest, "
    "WAITING — one hand raised in friendly wave, curious expression, "
    "dark wine background #1A0010, vinyl toy style, Funko proportions, cinematic, ultra HD"
)


def _choose_prompt(p_bruto: float, p_total: int) -> tuple[str, str]:
    """Retorna (prompt, label_expressao) baseado nos dados do ciclo."""
    if p_total == 0:
        return _PROMPT_NEUTRO, "neutro"
    if p_bruto >= 0:
        return _PROMPT_CELEBRANDO, "celebrando"
    return _PROMPT_PROFISSIONAL, "profissional"


def _build_caption(p_bruto: float, p_wr: float, p_traders: int, hoje: str) -> str:
    """Legenda do Discord para a imagem do bdZinho."""
    emoji = "🟢" if p_bruto >= 0 else "🔴"
    result = f"+${p_bruto:.2f}" if p_bruto >= 0 else f"-${abs(p_bruto):.2f}"
    mood = "Ciclo positivo! 🎉" if p_bruto >= 0 else "Ciclo encerrado. Analisando..."

    return (
        f"{emoji} **{mood}**\n"
        f"📅 {hoje}  |  💰 {result}  |  🎯 WR {p_wr:.0f}%  |  👥 {p_traders} traders"
    )


def post_cycle_bdzinho(cycle_data: dict) -> None:
    """
    Gera imagem do bdZinho com expressão do ciclo e posta no Discord.
    Executa em thread daemon — fail-open, não bloqueia nada.

    cycle_data keys: hoje, p_bruto, p_wr, p_traders, p_total
    """
    if not _CYCLE_VISUAL_ENABLED:
        return
    if not _IMG_GEN_AVAILABLE or not _HTTP_AVAILABLE:
        logger.info("[cycle_visual] Módulos indisponíveis — skip")
        return
    if not _WEBHOOK_RELATORIO:
        logger.info("[cycle_visual] DISCORD_WEBHOOK_RELATORIO não configurado — skip")
        return

    def _run():
        try:
            p_bruto   = float(cycle_data.get("p_bruto", 0))
            p_wr      = float(cycle_data.get("p_wr", 0))
            p_traders = int(cycle_data.get("p_traders", 0))
            p_total   = int(cycle_data.get("p_total", 0))
            hoje      = str(cycle_data.get("hoje", ""))

            prompt, expressao = _choose_prompt(p_bruto, p_total)
            logger.info("[cycle_visual] Gerando bdZinho expressão=%s para ciclo %s", expressao, hoje)

            # Gerar imagem
            img_bytes = generate_image(prompt)  # type: ignore
            if not img_bytes:
                logger.warning("[cycle_visual] Geração de imagem falhou — skip")
                return

            # Legenda Discord
            caption = _build_caption(p_bruto, p_wr, p_traders, hoje)

            # Postar no Discord via webhook (multipart/form-data)
            files = {
                "file": (f"bdzinho_{hoje}.png", img_bytes, "image/png"),
                "payload_json": (
                    None,
                    f'{{"content": "{caption}"}}',
                    "application/json",
                ),
            }
            resp = _requests.post(_WEBHOOK_RELATORIO, files=files, timeout=30)
            if resp.status_code in (200, 204):
                logger.info("[cycle_visual] bdZinho postado no Discord — expressão=%s", expressao)
            else:
                logger.warning("[cycle_visual] Discord webhook retornou %s", resp.status_code)

        except Exception as e:
            logger.error("[cycle_visual] Erro: %s", e)

    threading.Thread(target=_run, daemon=True).start()


logger.info("[cycle_visual] bdZinho Cycle Visual carregado — enabled=%s", _CYCLE_VISUAL_ENABLED)
