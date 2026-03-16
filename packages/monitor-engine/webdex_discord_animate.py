from __future__ import annotations
"""
webdex_discord_animate.py — Animações bdZinho via Replicate

Gera clips do mascote bdZinho (image-to-video) e posta no Discord
em momentos-chave do protocolo. Execução 100% assíncrona.

Modelo: minimax/video-01  (~$0.20/clip, 6s)
Créditos: $10 → ~50 clips disponíveis
Token: configurado via variável de ambiente REPLICATE_TOKEN.

Eventos suportados:
  "new_holder"  → novo holder do token WEbdEX
  "milestone"   → conquista do protocolo
  "gm"          → ritual diário das 7h
  "trade_win"   → ciclo positivo
"""

import os
import time
import threading
import logging
import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────────────────────
_REPLICATE_TOKEN = os.getenv("REPLICATE_TOKEN", "")

# URL pública do bdZinho — mascote oficial WEbdEX
_BDZINHO_URL = os.getenv(
    "BDZINHO_IMAGE_URL",
    "https://i.ibb.co/MkcqbvLb/post-149-operador-da-tecnologia-01.jpg",
)

_MODEL_OWNER  = "minimax"
_MODEL_NAME   = "video-01"
_POLL_TIMEOUT = 120   # segundos máx para esperar o vídeo
_POLL_SLEEP   = 6     # intervalo entre polls

# Controle de gasto — não ultrapassar $8 dos $10 disponíveis
_MAX_CLIPS_PER_DAY = 5   # no máximo 5 clips por dia (~$1/dia)
_clips_today: dict = {"date": "", "count": 0}

# ─────────────────────────────────────────────────────────────
# Prompts por evento
# ─────────────────────────────────────────────────────────────
_PROMPTS: dict[str, str] = {
    "new_holder": (
        "Cute colorful cartoon mascot celebrating with arms raised, "
        "confetti and sparkles, energetic happy dance, loop motion"
    ),
    "milestone": (
        "Cute cartoon mascot holding a trophy, golden confetti falling, "
        "triumphant pose, dynamic celebration"
    ),
    "gm": (
        "Cute cartoon character waving hello in morning light, "
        "warm sunrise colors, gentle cheerful wave animation"
    ),
    "trade_win": (
        "Cute cartoon mascot jumping for joy with fist pump, "
        "green sparkles and coins, victorious celebration"
    ),
    "relatorio_win": (
        "Cute cartoon mascot celebrating end of day, holding green profit chart, "
        "confetti rain, victorious fist pump, moonlit night background"
    ),
    "relatorio_loss": (
        "Cute cartoon mascot in thoughtful pose, looking at chart, "
        "determined face, night sky background, resilient energy"
    ),
}


# ─────────────────────────────────────────────────────────────
# Rate control — evita gastar todos os créditos
# ─────────────────────────────────────────────────────────────

def _can_generate() -> bool:
    """Verifica se ainda há budget para gerar um clip hoje."""
    today = time.strftime("%Y-%m-%d")
    if _clips_today["date"] != today:
        _clips_today["date"]  = today
        _clips_today["count"] = 0
    if _clips_today["count"] >= _MAX_CLIPS_PER_DAY:
        logger.info("[animate] Limite diário de %d clips atingido.", _MAX_CLIPS_PER_DAY)
        return False
    return True


def _mark_generated():
    _clips_today["count"] += 1
    logger.info("[animate] Clips gerados hoje: %d/%d", _clips_today["count"], _MAX_CLIPS_PER_DAY)


# ─────────────────────────────────────────────────────────────
# Replicate API
# ─────────────────────────────────────────────────────────────

def _start_prediction(prompt: str) -> str | None:
    """Inicia prediction no Replicate. Retorna prediction ID."""
    try:
        r = requests.post(
            f"https://api.replicate.com/v1/models/{_MODEL_OWNER}/{_MODEL_NAME}/predictions",
            json={"input": {"prompt": prompt, "first_frame_image": _BDZINHO_URL}},
            headers={
                "Authorization": f"Bearer {_REPLICATE_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        pred_id = data.get("id")
        logger.info("[animate] Prediction iniciada: %s", pred_id)
        return pred_id
    except Exception as e:
        logger.warning("[animate] Erro ao iniciar prediction: %s", e)
        return None


def _poll_prediction(pred_id: str) -> str | None:
    """Aguarda prediction concluir. Retorna URL do vídeo ou None."""
    deadline = time.time() + _POLL_TIMEOUT
    headers  = {"Authorization": f"Bearer {_REPLICATE_TOKEN}"}

    while time.time() < deadline:
        time.sleep(_POLL_SLEEP)
        try:
            r = requests.get(
                f"https://api.replicate.com/v1/predictions/{pred_id}",
                headers=headers,
                timeout=15,
            )
            r.raise_for_status()
            data   = r.json()
            status = data.get("status")

            if status == "succeeded":
                output = data.get("output")
                if isinstance(output, str):
                    return output
                if isinstance(output, list) and output:
                    return output[0]
                logger.warning("[animate] Output inesperado: %s", output)
                return None

            if status in ("failed", "canceled"):
                logger.warning("[animate] Prediction %s: %s | %s",
                               pred_id, status, data.get("error", ""))
                return None

        except Exception as e:
            logger.warning("[animate] Erro ao consultar prediction %s: %s", pred_id, e)

    logger.warning("[animate] Prediction %s: timeout após %ds", pred_id, _POLL_TIMEOUT)
    return None


# ─────────────────────────────────────────────────────────────
# Post Discord
# ─────────────────────────────────────────────────────────────

def _post_video(video_url: str, webhook_url: str, title: str,
                description: str, color: int = 0x00FFB2) -> None:
    """Posta clip animado no Discord via webhook — upload direto como arquivo."""
    import tempfile, os
    try:
        # Baixa o vídeo para arquivo temporário
        dl = requests.get(video_url, timeout=60, stream=True)
        dl.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            for chunk in dl.iter_content(chunk_size=1 << 20):
                tmp.write(chunk)
            tmp_path = tmp.name

        # Faz upload multipart → Discord mostra o vídeo inline (não só link)
        payload_json = {
            "embeds": [{
                "title": title,
                "description": description,
                "color": color,
                "footer": {"text": "WEbdEX Protocol · bdZinho"},
            }],
        }
        import json as _json
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                webhook_url,
                data={"payload_json": _json.dumps(payload_json)},
                files={"file": ("bdzinho.mp4", f, "video/mp4")},
                timeout=60,
            )
        os.unlink(tmp_path)

        if resp.status_code not in (200, 204):
            logger.warning("[animate] Webhook %s: %s", resp.status_code, resp.text[:120])
        else:
            logger.info("[animate] Clip postado inline → %s", title)
    except Exception as e:
        logger.warning("[animate] Erro ao postar no Discord: %s", e)


# ─────────────────────────────────────────────────────────────
# API pública — chamada pelos workers
# ─────────────────────────────────────────────────────────────

def animate_and_post(
    event: str,
    webhook_url: str,
    title: str = "",
    description: str = "",
    color: int = 0x00FFB2,
) -> None:
    """
    Gera clip bdZinho via Replicate e posta no Discord.
    Assíncrono — não bloqueia o worker chamador.

    Args:
        event:       "new_holder" | "milestone" | "gm" | "trade_win"
        webhook_url: URL do webhook Discord de destino
        title:       Título do embed Discord
        description: Texto do embed
        color:       Cor do embed (int hex)
    """
    if not _can_generate():
        return

    def _run():
        prompt = _PROMPTS.get(event, _PROMPTS["milestone"])
        pred_id = _start_prediction(prompt)
        if not pred_id:
            return

        video_url = _poll_prediction(pred_id)
        if video_url:
            _post_video(video_url, webhook_url, title, description, color)
            _mark_generated()
        else:
            logger.warning("[animate] Sem vídeo para evento=%s", event)

    threading.Thread(target=_run, name=f"animate_{event}", daemon=True).start()
