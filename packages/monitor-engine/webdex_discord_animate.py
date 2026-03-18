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

import atexit
import json
import os
import random
import sys
import tempfile
import time
import threading
import logging
import requests

# Tenta importar design_tokens do orchestrator (quando disponível no mesmo PYTHONPATH)
# Fallback: constantes locais para manter o monitor-engine autônomo
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator", "discord"))
    from design_tokens import SUCCESS, WARNING, PINK_LIGHT  # noqa: F401
    sys.path.pop(0)
except ImportError:
    SUCCESS    = 0x00FFB2
    WARNING    = 0xFF8800
    PINK_LIGHT = 0xFB0491

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────────────────────
_REPLICATE_TOKEN = os.getenv("REPLICATE_TOKEN", "")
if not _REPLICATE_TOKEN:
    logger.error("[animate] REPLICATE_TOKEN não configurado — animações desativadas.")

# URL pública do bdZinho — mascote oficial WEbdEX
_BDZINHO_URL = os.getenv(
    "BDZINHO_IMAGE_URL",
    "https://i.ibb.co/MkcqbvLb/post-149-operador-da-tecnologia-01.jpg",
)

_MODEL_OWNER  = "minimax"
_MODEL_NAME   = "video-01"
_POLL_TIMEOUT = 300   # segundos máx para esperar o vídeo (minimax ~2-3min)
_POLL_SLEEP   = 6     # intervalo entre polls

# Controle de gasto — não ultrapassar $8 dos $10 disponíveis
_MAX_CLIPS_PER_DAY = 5   # no máximo 5 clips por dia (~$1/dia)
_clips_today: dict = {"date": "", "count": 0}
_clips_lock = threading.Lock()  # protege _clips_today contra race condition

# Rastreamento de threads ativas — permite cleanup gracioso no shutdown
_active_anims: list[threading.Thread] = []
_active_anims_lock = threading.Lock()

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
    "relatorio_win": [
        "Cute cartoon mascot celebrating end of day, holding green profit chart, "
        "confetti rain, victorious fist pump, moonlit night background",
        "Cute colorful cartoon mascot doing victory dance, green coins raining down, "
        "crypto charts glowing green, arms raised in celebration, starry night sky",
        "Cute cartoon character surfing on a giant green upward arrow, sparkles and stars, "
        "triumphant confident expression, moonlit cityscape background",
        "Cute cartoon mascot popping champagne bottle with green sparkles exploding, "
        "golden trophy glowing beside it, happy dance, moonlit rooftop scene",
    ],
    "relatorio_loss": [
        "Cute cartoon mascot in thoughtful pose, looking at chart, "
        "determined face, night sky background, resilient energy",
        "Cute cartoon character sitting cross-legged, contemplating a red chart, "
        "focused and determined expression, calm night sky, ready to come back stronger",
        "Cute cartoon mascot meditating in zen pose, peaceful stars around, "
        "soft moonlight, calm acceptance, glowing aura of resilience",
    ],
}


# ─────────────────────────────────────────────────────────────
# Shutdown gracioso — aguarda threads ativas (evita temp file leak)
# ─────────────────────────────────────────────────────────────

def _cleanup_on_exit() -> None:
    """Aguarda animações ativas terminarem no shutdown (máx 30s total).

    Threads não são daemon — Python aguardaria infinitamente sem este timeout.
    Isso garante que finally blocks em _post_video sempre executam.
    """
    with _active_anims_lock:
        threads = list(_active_anims)
    for t in threads:
        t.join(timeout=30)


atexit.register(_cleanup_on_exit)


# ─────────────────────────────────────────────────────────────
# Rate control — TOCTOU-safe (check + reserve em operação atômica)
# ─────────────────────────────────────────────────────────────

def _reserve_slot() -> bool:
    """Verifica budget E reserva slot atomicamente — previne TOCTOU race.

    Sem esta atomicidade, múltiplas threads podem passar o check simultaneamente
    e gerar N clips ao invés de 1, esgotando créditos Replicate em bursts.

    Retorna True se slot foi reservado com sucesso.
    DEVE ser pareado com _release_slot() se a geração/postagem falhar.
    """
    with _clips_lock:
        today = time.strftime("%Y-%m-%d")
        if _clips_today["date"] != today:
            _clips_today["date"]  = today
            _clips_today["count"] = 0
        if _clips_today["count"] >= _MAX_CLIPS_PER_DAY:
            logger.info("[animate] Limite diário de %d clips atingido.", _MAX_CLIPS_PER_DAY)
            return False
        _clips_today["count"] += 1
        logger.info("[animate] Slot reservado. Clips hoje: %d/%d",
                    _clips_today["count"], _MAX_CLIPS_PER_DAY)
        return True


def _release_slot() -> None:
    """Devolve slot reservado quando geração ou postagem falha.

    Garante que falhas transientes (Replicate down, Discord offline)
    não desperdiçam o budget diário.
    """
    with _clips_lock:
        if _clips_today["count"] > 0:
            _clips_today["count"] -= 1
            logger.info("[animate] Slot liberado (falha). Clips hoje: %d/%d",
                        _clips_today["count"], _MAX_CLIPS_PER_DAY)


# ─────────────────────────────────────────────────────────────
# Replicate API
# ─────────────────────────────────────────────────────────────

def _start_prediction(prompt: str) -> str | None:
    """Inicia prediction no Replicate. Retorna prediction ID.

    Implementa retry com backoff para erros transientes (429, 502, 503).
    """
    for attempt in range(3):
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
            if r.status_code in (429, 502, 503) and attempt < 2:
                wait = float(r.json().get("retry_after", 5.0)) if r.status_code == 429 else 5.0
                logger.warning("[animate] Replicate %s — retry em %.0fs (tentativa %d/3)",
                               r.status_code, wait, attempt + 1)
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            pred_id = data.get("id")
            logger.info("[animate] Prediction iniciada: %s", pred_id)
            return pred_id
        except Exception as e:
            logger.warning("[animate] Tentativa %d/3 falhou ao iniciar prediction: %s",
                           attempt + 1, e)
            if attempt < 2:
                time.sleep(3)
    return None


def _cancel_prediction(pred_id: str) -> None:
    """Cancela prediction no Replicate para evitar cobrança de clips não utilizados."""
    try:
        requests.post(
            f"https://api.replicate.com/v1/predictions/{pred_id}/cancel",
            headers={"Authorization": f"Bearer {_REPLICATE_TOKEN}"},
            timeout=10,
        )
        logger.info("[animate] Prediction %s cancelada (sem cobrança).", pred_id)
    except Exception as e:
        logger.warning("[animate] Falha ao cancelar prediction %s: %s", pred_id, e)


def _poll_prediction(pred_id: str) -> str | None:
    """Aguarda prediction concluir. Retorna URL do vídeo ou None.

    Em caso de timeout, cancela a prediction no Replicate para evitar
    cobranças de clips que nunca serão utilizados.
    """
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

    logger.warning(
        "[animate] Prediction %s: timeout após %ds — cancelando para evitar cobrança...",
        pred_id, _POLL_TIMEOUT,
    )
    _cancel_prediction(pred_id)
    return None


# ─────────────────────────────────────────────────────────────
# Post Discord
# ─────────────────────────────────────────────────────────────

def _post_video(video_url: str, webhook_url: str, title: str,
                description: str, color: int = 0x00FFB2) -> bool:
    """Posta clip animado no Discord via webhook — upload direto como arquivo.

    Retorna True em sucesso, False em qualquer falha.
    O chamador usa o retorno para decidir se libera o slot de rate limit.
    """
    tmp_path: str = ""
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
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload_json)},
                files={"file": ("bdzinho.mp4", f, "video/mp4")},
                timeout=60,
            )

        if resp.status_code not in (200, 204):
            logger.warning("[animate] Webhook %s: %s", resp.status_code, resp.text[:120])
            return False
        logger.info("[animate] Clip postado inline → %s", title)
        return True
    except Exception as e:
        logger.warning("[animate] Erro ao postar no Discord: %s", e)
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────
# API pública — chamada pelos workers
# ─────────────────────────────────────────────────────────────

def animate_and_post(
    event: str,
    webhook_url: str,
    title: str = "",
    description: str = "",
    color: int = SUCCESS,
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
    if not _REPLICATE_TOKEN:
        return

    if not _reserve_slot():
        return

    def _run() -> None:
        # slot_ok=True indica que o slot foi usado com sucesso e não deve ser liberado
        slot_ok = False
        try:
            _p = _PROMPTS.get(event, _PROMPTS["milestone"])
            prompt = random.choice(_p) if isinstance(_p, list) else _p

            pred_id = _start_prediction(prompt)
            if not pred_id:
                return  # slot liberado no finally

            video_url = _poll_prediction(pred_id)
            if not video_url:
                return  # slot liberado no finally

            success = _post_video(video_url, webhook_url, title, description, color)
            if success:
                slot_ok = True
            else:
                logger.warning("[animate] Clip gerado mas não postado (evento=%s) — slot liberado.",
                               event)
        except Exception as e:
            logger.warning("[animate] Erro inesperado em _run (evento=%s): %s", event, e)
        finally:
            if not slot_ok:
                _release_slot()
            # Remove da lista de threads ativas para cleanup no shutdown
            current = threading.current_thread()
            with _active_anims_lock:
                try:
                    _active_anims.remove(current)
                except ValueError:
                    pass

    # Threads não-daemon — garante que finally blocks executam no shutdown
    # _cleanup_on_exit() faz join com timeout de 30s para não bloquear indefinidamente
    t = threading.Thread(target=_run, name=f"animate_{event}")
    with _active_anims_lock:
        _active_anims.append(t)
    t.start()
