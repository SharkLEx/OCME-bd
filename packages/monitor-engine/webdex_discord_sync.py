"""
webdex_discord_sync.py — Content Sync: OCME → Discord

Envia notificações importantes para o canal Discord via webhook.
Adaptação de tom: remove Markdown Telegram, usa Markdown Discord.
Chamado pelos workers do OCME (milestone, ciclo 21h, anomalia).
"""
import re
import time
import logging
import threading
import requests

logger = logging.getLogger(__name__)

_WEBHOOK_URL = (
    "https://discord.com/api/webhooks/1482729962258563263/"
    "ku-KJGFzT3nKqUkcS1sYrmzNrNbSt2jLbkzIPKmYs2hoOaRdj65OfkVH6Tqo0eIW2XwQ"
)

_COLOR_INFO      = 0x00FFB2   # verde WEbdEX
_COLOR_MILESTONE = 0xFFD700   # dourado
_COLOR_ALERT     = 0xFF6B35   # laranja
_COLOR_CICLO     = 0x38BDF8   # azul


def _telegram_to_discord(text: str) -> str:
    """Converte formatação Telegram HTML/Markdown para Markdown Discord."""
    # Remove tags HTML do Telegram
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.DOTALL)
    text = re.sub(r"<i>(.*?)</i>", r"*\1*", text, flags=re.DOTALL)
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.DOTALL)
    text = re.sub(r"<pre>(.*?)</pre>", r"```\n\1\n```", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)  # remove demais tags
    # Remove separadores estilo Telegram (━━━)
    text = re.sub(r"[━┈]{10,}", "─────────────", text)
    # Limita tamanho (Discord embed description: 4096 chars)
    return text[:3900].strip()


def _post_webhook(payload: dict) -> None:
    """POST com retry automático em caso de rate limit (429)."""
    for attempt in range(3):
        try:
            resp = requests.post(_WEBHOOK_URL, json=payload, timeout=8)
            if resp.status_code in (200, 204):
                return
            if resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 1.0)
                time.sleep(float(retry_after) + 0.1)
                continue
            logger.warning(f"[discord_sync] Webhook retornou {resp.status_code}: {resp.text[:200]}")
            return
        except Exception as e:
            logger.warning(f"[discord_sync] Erro ao enviar webhook: {e}")
            return


def _async_post(payload: dict) -> None:
    threading.Thread(target=_post_webhook, args=(payload,), daemon=True).start()


# ─────────────────────────────────────────────────────────────
# API pública — chamada pelos workers
# ─────────────────────────────────────────────────────────────

def notify_milestone(title: str, description: str, env: str = "") -> None:
    """Notifica conquista/milestone do protocolo."""
    env_label = "🟠 AG_C_bd" if "AG_C" in env else ("🔵 bd_v5" if "bd_v5" in env else "📊 Protocolo")
    _async_post({
        "embeds": [{
            "title": f"🏆 {title}",
            "description": _telegram_to_discord(description),
            "color": _COLOR_MILESTONE,
            "footer": {"text": f"WEbdEX Protocol · {env_label}"},
        }]
    })


def notify_ciclo_report(summary: str, env: str = "") -> None:
    """Envia resumo do ciclo 21h."""
    env_label = "🟠 AG_C_bd" if "AG_C" in env else ("🔵 bd_v5" if "bd_v5" in env else "Global")
    _async_post({
        "embeds": [{
            "title": f"📊 Relatório do Ciclo — {env_label}",
            "description": _telegram_to_discord(summary),
            "color": _COLOR_CICLO,
            "footer": {"text": "WEbdEX Protocol · Ciclo 21h BR"},
        }]
    })


def notify_anomaly(alert_text: str, severity: str = "warning") -> None:
    """Envia alerta de anomalia."""
    color = 0xFF0000 if severity == "critical" else _COLOR_ALERT
    icon = "🚨" if severity == "critical" else "⚠️"
    _async_post({
        "embeds": [{
            "title": f"{icon} Alerta do Protocolo",
            "description": _telegram_to_discord(alert_text),
            "color": color,
            "footer": {"text": "WEbdEX OCME Monitor"},
        }]
    })


def notify_info(title: str, message: str) -> None:
    """Notificação genérica informativa."""
    _async_post({
        "embeds": [{
            "title": title,
            "description": _telegram_to_discord(message),
            "color": _COLOR_INFO,
            "footer": {"text": "WEbdEX Protocol"},
        }]
    })
