"""
webdex_discord_sync.py — Content Sync: OCME → Discord

Roteamento por canal:
  _WEBHOOK_ONCHAIN   → #webdex-on-chain  (on-chain events, anomalias, milestones, network)
  _WEBHOOK_OPERACOES → #operações        (trades executados pelo protocolo)
  _WEBHOOK_SWAPS     → #swaps            (SwapBook: Create Swap / Swap Tokens)
  _WEBHOOK_RELATORIO → #relatório-diário (ciclo 21h diário)
  _WEBHOOK_GM        → #gm-wagmi         (ritual diário das 7h)
"""
import re
import time
import logging
import threading
import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Webhooks por canal
# ─────────────────────────────────────────────────────────────
_WEBHOOK_ONCHAIN = (
    "https://discord.com/api/webhooks/1482729962258563263/"
    "ku-KJGFzT3nKqUkcS1sYrmzNrNbSt2jLbkzIPKmYs2hoOaRdj65OfkVH6Tqo0eIW2XwQ"
)
_WEBHOOK_OPERACOES = (
    "https://discord.com/api/webhooks/1482918967021539462/"
    "3BUlXTlJXD-IhMy8rBI26Rz5ljadnDxlDv0TFLiIfHCOeL4FOuRET21k2hkvm33kzyqK"
)
_WEBHOOK_SWAPS = (
    "https://discord.com/api/webhooks/1482919384925081601/"
    "UP1GPARFewvvPoXt2vjdz1PAczVuqOa3u68USVSU0zCgDcBASI7oKkbVjyvlSDkKhC4s"
)
_WEBHOOK_RELATORIO = (
    "https://discord.com/api/webhooks/1482919871112019969/"
    "wF5y-kC6FLjxmuxm13OlKzPBn4Bz2GUTJpBIVRPjrHW4mdmLLGPXD5RopWS0cjGMkOTh"
)
_WEBHOOK_GM = (
    "https://discord.com/api/webhooks/1482920003421470757/"
    "2r20C8lUm2V5ScJIEhCGJnF4Q2uswR9EbLx7aNv8mNe0LnJw3gHUHMx8XmXWCwZEdEry"
)

# ─────────────────────────────────────────────────────────────
# Cores padrão
# ─────────────────────────────────────────────────────────────
_COLOR_INFO      = 0x00FFB2   # verde WEbdEX
_COLOR_MILESTONE = 0xFFD700   # dourado
_COLOR_ALERT     = 0xFF6B35   # laranja
_COLOR_CICLO     = 0x38BDF8   # azul
_COLOR_TRADE_WIN = 0x00FF88   # verde trade positivo
_COLOR_TRADE_LOS = 0xFF4444   # vermelho trade negativo
_COLOR_GM        = 0xE91E8C   # rosa WEbdEX


def _telegram_to_discord(text: str) -> str:
    """Converte formatação Telegram HTML/Markdown para Markdown Discord."""
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.DOTALL)
    text = re.sub(r"<i>(.*?)</i>", r"*\1*", text, flags=re.DOTALL)
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.DOTALL)
    text = re.sub(r"<pre>(.*?)</pre>", r"```\n\1\n```", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[━┈]{10,}", "─────────────", text)
    return text[:3900].strip()


def _post_webhook(payload: dict, url: str) -> None:
    """POST com retry automático em caso de rate limit (429)."""
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=8)
            if resp.status_code in (200, 204):
                return
            if resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 1.0)
                time.sleep(float(retry_after) + 0.1)
                continue
            logger.warning("[discord_sync] Webhook %s retornou %s: %s",
                           url[-20:], resp.status_code, resp.text[:200])
            return
        except Exception as e:
            logger.warning("[discord_sync] Erro ao enviar webhook: %s", e)
            return


def _async_post(payload: dict, url: str = _WEBHOOK_ONCHAIN) -> None:
    """Envia webhook assíncrono — não bloqueia o worker chamador."""
    threading.Thread(target=_post_webhook, args=(payload, url), daemon=True).start()


# ─────────────────────────────────────────────────────────────
# API pública — chamada pelos workers
# ─────────────────────────────────────────────────────────────

def notify_milestone(title: str, description: str, env: str = "") -> None:
    """Conquista/milestone do protocolo → #webdex-on-chain."""
    env_label = "🟠 AG_C_bd" if "AG_C" in env else ("🔵 bd_v5" if "bd_v5" in env else "📊 Protocolo")
    _async_post({
        "embeds": [{
            "title": f"🏆 {title}",
            "description": _telegram_to_discord(description),
            "color": _COLOR_MILESTONE,
            "footer": {"text": f"WEbdEX Protocol · {env_label}"},
        }]
    }, url=_WEBHOOK_ONCHAIN)


def notify_ciclo_report(summary: str, env: str = "") -> None:
    """Resumo do ciclo 21h → #relatório-diário."""
    env_label = "🟠 AG_C_bd" if "AG_C" in env else ("🔵 bd_v5" if "bd_v5" in env else "Global")
    _async_post({
        "embeds": [{
            "title": f"📊 Relatório do Ciclo — {env_label}",
            "description": _telegram_to_discord(summary),
            "color": _COLOR_CICLO,
            "footer": {"text": "WEbdEX Protocol · Ciclo 21h BR"},
        }]
    }, url=_WEBHOOK_RELATORIO)


def notify_anomaly(alert_text: str, severity: str = "warning") -> None:
    """Alerta de anomalia → #webdex-on-chain."""
    color = 0xFF0000 if severity == "critical" else _COLOR_ALERT
    icon  = "🚨" if severity == "critical" else "⚠️"
    _async_post({
        "embeds": [{
            "title": f"{icon} Alerta do Protocolo",
            "description": _telegram_to_discord(alert_text),
            "color": color,
            "footer": {"text": "WEbdEX OCME Monitor"},
        }]
    }, url=_WEBHOOK_ONCHAIN)


def notify_info(title: str, message: str) -> None:
    """Notificação genérica informativa → #webdex-on-chain."""
    _async_post({
        "embeds": [{
            "title": title,
            "description": _telegram_to_discord(message),
            "color": _COLOR_INFO,
            "footer": {"text": "WEbdEX Protocol"},
        }]
    }, url=_WEBHOOK_ONCHAIN)


def notify_operacao(
    sub: str,
    valor: float,
    token: str,
    estrategia: str,
    env: str,
    tx_hash: str = "",
    trades_hj: int = 0,
) -> None:
    """Trade executado pelo protocolo → #operações."""
    emoji  = "🟢" if valor >= 0 else "🔴"
    color  = _COLOR_TRADE_WIN if valor >= 0 else _COLOR_TRADE_LOS
    env_lb = "🟠 AG" if "AG_C" in env else "🔵 V5"
    desc   = (
        f"{emoji} **`{sub}`** · {env_lb}\n\n"
        f"💰 Resultado: **`${valor:+.4f}`**\n"
        f"🔄 Estratégia: `{estrategia}` · 🪙 `{token}`\n"
    )
    if trades_hj:
        desc += f"📊 Trades hoje: `{trades_hj}`\n"
    if tx_hash:
        desc += f"\n[🔗 Polygonscan](https://polygonscan.com/tx/{tx_hash})"
    _async_post({
        "embeds": [{
            "title": f"{emoji} Execução Confirmada — WEbdEX",
            "description": desc,
            "color": color,
            "footer": {"text": f"WEbdEX Engine · {env_lb}"},
        }]
    }, url=_WEBHOOK_OPERACOES)


def notify_gm(hoje: str = "") -> None:
    """Ritual diário das 7h → #gm-wagmi."""
    data_str = f" — {hoje}" if hoje else ""
    _async_post({
        "embeds": [{
            "title": f"☀️ Bom dia, WEbdEX{data_str}!",
            "description": (
                "O protocolo está **ativo e monitorando** 👁\n\n"
                "🔵 bd_v5 · 🟠 AG_C_bd · Polygon Mainnet\n\n"
                "> Boa sorte nos trades de hoje. Que os ciclos sejam verdes! 🚀"
            ),
            "color": _COLOR_GM,
            "footer": {"text": "WEbdEX Protocol · OCME Monitor"},
        }]
    }, url=_WEBHOOK_GM)
