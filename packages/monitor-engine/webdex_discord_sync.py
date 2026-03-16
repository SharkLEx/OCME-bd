"""
webdex_discord_sync.py — Content Sync: OCME → Discord

Roteamento por canal (categoria ⚡ PROTOCOLO AO VIVO):
  _WEBHOOK_ONCHAIN    → #webdex-on-chain  (on-chain events, anomalias, network)
  _WEBHOOK_TOKEN_BD   → #token-bd         (relatório 2h holders/supply)
  _WEBHOOK_CONQUISTAS → #conquistas       (milestones, novas carteiras)
  _WEBHOOK_OPERACOES  → #operações        (nova carteira conectada ao protocolo)
  _WEBHOOK_SWAPS      → #swaps            (SwapBook: Create Swap / Swap Tokens)
  _WEBHOOK_RELATORIO  → #relatório-diário (ciclo 21h diário)
  _WEBHOOK_GM         → #gm-wagmi         (ritual diário das 7h)
"""
import os
import re
import time
import logging
import threading
import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Webhooks por canal — lidos de variáveis de ambiente
# ─────────────────────────────────────────────────────────────
_WEBHOOK_ONCHAIN    = os.getenv("DISCORD_WEBHOOK_ONCHAIN", "").strip()
_WEBHOOK_OPERACOES  = os.getenv("DISCORD_WEBHOOK_OPERACOES", "").strip()
_WEBHOOK_SWAPS      = os.getenv("DISCORD_WEBHOOK_SWAPS", "").strip()
_WEBHOOK_RELATORIO  = os.getenv("DISCORD_WEBHOOK_RELATORIO", "").strip()
_WEBHOOK_GM         = os.getenv("DISCORD_WEBHOOK_GM", "").strip()
_WEBHOOK_TOKEN_BD   = os.getenv("DISCORD_WEBHOOK_TOKEN_BD", "").strip()
_WEBHOOK_CONQUISTAS = os.getenv("DISCORD_WEBHOOK_CONQUISTAS", "").strip()

# Validação de startup — falha rápido se algum webhook não configurado
_REQUIRED_WEBHOOKS = {
    "DISCORD_WEBHOOK_ONCHAIN":    _WEBHOOK_ONCHAIN,
    "DISCORD_WEBHOOK_OPERACOES":  _WEBHOOK_OPERACOES,
    "DISCORD_WEBHOOK_SWAPS":      _WEBHOOK_SWAPS,
    "DISCORD_WEBHOOK_RELATORIO":  _WEBHOOK_RELATORIO,
    "DISCORD_WEBHOOK_GM":         _WEBHOOK_GM,
    "DISCORD_WEBHOOK_TOKEN_BD":   _WEBHOOK_TOKEN_BD,
    "DISCORD_WEBHOOK_CONQUISTAS": _WEBHOOK_CONQUISTAS,
}
_missing = [k for k, v in _REQUIRED_WEBHOOKS.items() if not v]
if _missing:
    logger.warning("[discord_sync] Webhooks não configurados no .env: %s", ", ".join(_missing))

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

# ─────────────────────────────────────────────────────────────
# Contadores em memória — pulso curado do #webdex-on-chain
# ─────────────────────────────────────────────────────────────
_pulse_lock  = threading.Lock()
_pulse_stats: dict = {
    "swaps_exec":   0,  # Swap Tokens executados
    "webdex_moves": 0,  # Transfers WEbdEX relevantes (>= 100k)
    "new_holders":  0,  # Novos holders WEbdEX
    "new_wallets":  0,  # Novas carteiras conectadas ao protocolo
}


def inc_pulse_stat(key: str) -> None:
    """Incrementa contador do pulso curado (thread-safe)."""
    with _pulse_lock:
        if key in _pulse_stats:
            _pulse_stats[key] += 1


def get_pulse_stats_and_reset() -> dict:
    """Retorna contadores do período e zera para próximo ciclo."""
    with _pulse_lock:
        stats = dict(_pulse_stats)
        for k in _pulse_stats:
            _pulse_stats[k] = 0
    return stats


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
    """Conquista/milestone do protocolo → #conquistas."""
    _async_post({
        "embeds": [{
            "title": f"🏆 {title}",
            "description": _telegram_to_discord(description),
            "color": _COLOR_MILESTONE,
            "footer": {"text": "WEbdEX Protocol"},
        }]
    }, url=_WEBHOOK_CONQUISTAS)


def notify_token_bd(holders: int, supply: float, msg: str = "") -> None:
    """Relatório periódico do token BD → #token-bd."""
    desc = (
        f"👥 **HOLDERS ATIVOS:** `{holders:,}`\n"
        f"💎 **EM CIRCULAÇÃO:** `{supply:,.0f} WEbdEX`\n"
        f"📦 **SUPPLY TOTAL:** `369,369,369 WEbdEX`\n"
    )
    if msg:
        desc += f"\n─────────────────────\n{_telegram_to_discord(msg)}"
    _async_post({
        "embeds": [{
            "title": "📊 TOKEN WEbdEX — RELATÓRIO DE CRESCIMENTO",
            "description": desc,
            "color": 0x6C3FE8,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol · Relatório automático a cada 2h · Polygon"},
        }]
    }, url=_WEBHOOK_TOKEN_BD)


def notify_webdex_transfer(
    from_addr: str,
    to_addr: str,
    amount: str,
    tx_hash: str = "",
    is_new_holder: bool = False,
) -> None:
    """QUALQUER movimentação do token WEbdEX → #token-bd (ao vivo)."""
    short_from = f"{from_addr[:6]}…{from_addr[-4:]}"
    short_to   = f"{to_addr[:6]}…{to_addr[-4:]}"
    ZERO = "0x0000000000000000000000000000000000000000"

    if from_addr.lower() == ZERO:
        tipo, icone, cor = "MINT", "🌱", 0x00FF88
    elif to_addr.lower() == ZERO:
        tipo, icone, cor = "BURN", "🔥", 0xFF4444
    else:
        tipo, icone, cor = "TRANSFER", "💎", 0xFFD700

    new_holder_line = "\n\n🎊 **⚡ NOVO HOLDER CONFIRMADO! ⚡**\n**A FAMÍLIA WEbdEX CRESCEU!**" if is_new_holder else ""
    poly_link = f"\n\n[🔗 Ver no Polygonscan](https://polygonscan.com/tx/{tx_hash})" if tx_hash else ""

    desc = (
        f"**{icone} TIPO:** `{tipo}`\n"
        f"**📤 DE:** `{short_from}`\n"
        f"**📥 PARA:** `{short_to}`\n"
        f"**💰 VALOR:** `{amount} WEbdEX`"
        f"{new_holder_line}"
        f"{poly_link}"
    )

    _async_post({
        "embeds": [{
            "title": f"{icone} MOVIMENTO DETECTADO — TOKEN WEbdEX",
            "description": desc,
            "color": cor,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol · A Cereja do Bolo · Polygon"},
        }]
    }, url=_WEBHOOK_TOKEN_BD)


_OCME_BD_LINK = "https://t.me/OCME_bd"
_BDZINHO_IMG  = "https://i.ibb.co/MkcqbvLb/post-149-operador-da-tecnologia-01.jpg"


def notify_operacoes_horario(total: int, by_env: dict, hora_str: str) -> None:
    """Relatório 2h de operações → #operações."""
    if total == 0:
        desc  = "🔇 **NENHUMA OPERAÇÃO** nas últimas 2h.\n*Protocolo aguardando próximo ciclo.*"
        color = 0x555555
    else:
        bars  = min(10, max(1, round(total / 400)))
        bar   = "█" * bars + "░" * (10 - bars)
        desc  = (
            f"**📈 TOTAL DE OPERAÇÕES:** `{total:,}`\n"
            f"`{bar}` `{total:,} ops/2h`\n\n"
            f"─────────────────────────\n"
            f"🤖 **OCME_bd — Beta Exclusivo**\n"
            f"O assistente IA do WEbdEX que traz relatórios on-chain,\n"
            f"análise de fluxo e dados consolidados na palma da mão.\n"
            f"*Em breve no portfolio oficial WEbdEX Protocol.*\n\n"
            f"[→ Acessar OCME_bd no Telegram]({_OCME_BD_LINK})"
        )
        color = 0xFF6B35
    _async_post({
        "embeds": [{
            "title": f"⚡ PROTOCOLO WEbdEX — AO VIVO · {hora_str}",
            "description": desc,
            "color": color,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol · Relatório 2h · Polygon"},
        }]
    }, url=_WEBHOOK_OPERACOES)


def notify_swaps_horario(total: int, create: int, execute: int, hora_str: str) -> None:
    """Relatório 2h de swaps → #swaps."""
    if total == 0:
        desc  = "🔇 **NENHUM SWAP** nas últimas 2h.\n*SwapBook aguardando próxima oferta.*"
        color = 0x555555
    else:
        bars  = min(10, max(1, total * 2))
        bar   = "█" * bars + "░" * max(0, 10 - bars)
        desc  = (
            f"**📊 TOTAL DE SWAPS:** `{total}`\n\n"
            f"🆕 **CREATE SWAP:** `{create}`\n"
            f"✅ **SWAP EXECUTADO:** `{execute}`\n\n"
            f"`{bar}` `{total} swaps/2h`"
        )
        color = 0x38BDF8
    _async_post({
        "embeds": [{
            "title": f"🔄 SWAPBOOK WEbdEX — {hora_str}",
            "description": desc,
            "color": color,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol · SwapBook · Relatório 2h · Polygon"},
        }]
    }, url=_WEBHOOK_SWAPS)


def notify_onchain_event(
    title: str,
    description: str,
    color: int = 0x00FFB2,
    tx_hash: str = "",
) -> None:
    """Evento curado ao vivo → #webdex-on-chain (pulso do protocolo)."""
    poly = f"\n[🔗 Polygonscan](https://polygonscan.com/tx/{tx_hash})" if tx_hash else ""
    _async_post({
        "embeds": [{
            "title": title,
            "description": description + poly,
            "color": color,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol · Polygon · Ao Vivo"},
        }]
    }, url=_WEBHOOK_ONCHAIN)


def notify_onchain_heartbeat(
    ops_2h: int,
    hora_str: str,
    swaps: int = 0,
    webdex_moves: int = 0,
    new_holders: int = 0,
    new_wallets: int = 0,
    pnl: float = 0.0,
) -> None:
    """Heartbeat 2h consolidado → #webdex-on-chain."""
    bars = min(10, max(1, round(ops_2h / 400)))
    bar  = "█" * bars + "░" * (10 - bars)

    lines = []
    if swaps > 0:
        lines.append(f"🔄 **Swaps executados:** `{swaps}`")
    if webdex_moves > 0:
        lines.append(f"💎 **Movimentos WEbdEX:** `{webdex_moves}`")
    if new_holders > 0:
        lines.append(f"🆕 **Novos holders:** `{new_holders}`")
    if new_wallets > 0:
        lines.append(f"👛 **Novas carteiras:** `{new_wallets}`")
    if pnl != 0.0:
        sign = "+" if pnl >= 0 else ""
        emoji_pnl = "🟢" if pnl >= 0 else "🔴"
        lines.append(f"{emoji_pnl} **P&L do ciclo:** `{sign}${pnl:.2f}`")

    activity = "\n".join(lines) if lines else "*Protocolo estável — aguardando próximos eventos.*"

    _async_post({
        "embeds": [{
            "title": f"📡 WEbdEX PROTOCOL — PULSO 2H · {hora_str}",
            "description": (
                f"**O OCME monitora a blockchain Polygon em tempo real.**\n\n"
                f"⚡ **OPERAÇÕES (2h):** `{ops_2h:,}`\n"
                f"`{bar}`\n\n"
                f"─────────────────────────\n"
                f"{activity}\n\n"
                f"🔗 Polygon Mainnet · `{hora_str}`"
            ),
            "color": 0x00FFB2,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol · OCME Monitor · Ao vivo"},
        }]
    }, url=_WEBHOOK_ONCHAIN)


def notify_nova_carteira(endereco: str, total_holders: int) -> None:
    """Nova carteira conectada ao protocolo → #conquistas."""
    short = f"{endereco[:6]}…{endereco[-4:]}" if len(endereco) > 12 else endereco
    _async_post({
        "embeds": [{
            "title": "🎉 Nova Carteira Conectada!",
            "description": (
                f"🔗 **`{short}`** abriu posição no protocolo\n\n"
                f"👥 Total de holders: **`{total_holders}`**"
            ),
            "color": _COLOR_MILESTONE,
            "footer": {"text": "WEbdEX Protocol · OCME"},
        }]
    }, url=_WEBHOOK_CONQUISTAS)


def notify_ciclo_report(
    summary: str,
    env: str = "",
    liq: float = 0.0,
    trades: int = 0,
    wins: int = 0,
    gas: float = 0.0,
) -> None:
    """Resumo do ciclo 21h → #relatório-diário."""
    if trades > 0:
        emoji  = "🟢" if liq >= 0 else "🔴"
        color  = _COLOR_TRADE_WIN if liq >= 0 else _COLOR_TRADE_LOS
        wr_pct = (wins / trades * 100) if trades > 0 else 0.0
        filled = round(wr_pct / 10)
        wr_bar = "█" * filled + "░" * (10 - filled)
        desc = (
            f"{emoji} **P&L líquido:** `${liq:+.2f}`\n"
            f"⛽ **Gás total:** `${gas:.2f}`\n"
            f"📊 **Trades:** `{trades}` · **Wins:** `{wins}`\n"
            f"🎯 **WinRate:** `{wr_pct:.0f}%`\n"
            f"`{wr_bar}`"
        )
    else:
        color = _COLOR_CICLO
        desc  = _telegram_to_discord(summary)

    ocme_block = (
        f"\n\n─────────────────────────\n"
        f"💡 **Tem o OCME_bd no Telegram?**\n"
        f"Quem tem o bot ativo recebe este relatório **personalizado por carteira**,\n"
        f"análise por trade, alertas de anomalia e acesso total ao fluxo do protocolo.\n"
        f"**Informação é poder. Na WEbdEX, ela vem até você.**\n\n"
        f"[→ Ativar OCME_bd — Beta Gratuito]({_OCME_BD_LINK})"
    )
    _async_post({
        "embeds": [{
            "title": "🌙 RELATÓRIO DO CICLO 21H — WEbdEX PROTOCOL",
            "description": desc + ocme_block,
            "color": color,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol · Ciclo 21h BR · Polygon"},
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
    emoji = "🟢" if valor >= 0 else "🔴"
    color = _COLOR_TRADE_WIN if valor >= 0 else _COLOR_TRADE_LOS
    desc  = (
        f"{emoji} **`{sub}`**\n\n"
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
            "footer": {"text": "WEbdEX Protocol · OCME"},
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
                "WEbdEX · Polygon Mainnet\n\n"
                "> Boa sorte nos trades de hoje. Que os ciclos sejam verdes! 🚀"
            ),
            "color": _COLOR_GM,
            "footer": {"text": "WEbdEX Protocol · OCME Monitor"},
        }]
    }, url=_WEBHOOK_GM)
