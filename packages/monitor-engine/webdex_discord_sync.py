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
# Design tokens — Manual da Marca WEbdEX (Sati / Story 9.1)
# ─────────────────────────────────────────────────────────────
try:
    from design_tokens import (
        SUCCESS as _SUCCESS, WARNING as _WARNING, ERROR as _ERROR,
        PINK_LIGHT as _PINK_LIGHT, RED_LIGHT as _RED_LIGHT,
        CHART_BLUE as _CHART_BLUE, DARK as _DARK,
    )
except ImportError:
    _SUCCESS    = 0x00FFB2
    _WARNING    = 0xFF8800
    _ERROR      = 0xFF4455
    _PINK_LIGHT = 0xFB0491
    _RED_LIGHT  = 0xD90048
    _CHART_BLUE = 0x00D4FF
    _DARK       = 0x131313

_COLOR_INFO      = _SUCCESS     # verde WEbdEX — info, P&L positivo
_COLOR_MILESTONE = _PINK_LIGHT  # pink accent — milestones, conquistas
_COLOR_ALERT     = _WARNING     # laranja — atenção, loss
_COLOR_CICLO     = _CHART_BLUE  # azul — ciclos, gráficos
_COLOR_TRADE_WIN = _SUCCESS     # verde — trade positivo
_COLOR_TRADE_LOS = _WARNING     # laranja — trade negativo
_COLOR_GM        = _PINK_LIGHT  # pink — ritual diário GM
_COLOR_TOKEN_BD  = _PINK_LIGHT  # pink — relatório token WEbdEX

_OCME_BD_LINK = os.getenv("OCME_BD_LINK", "https://t.me/OCME_bd")
_BDZINHO_IMG  = os.getenv(
    "BDZINHO_IMAGE_URL",
    "https://i.ibb.co/MkcqbvLb/post-149-operador-da-tecnologia-01.jpg",
)
_TOKEN_TOTAL_SUPPLY = int(os.getenv("TOKEN_TOTAL_SUPPLY", "369369369"))

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
        else:
            logger.warning("[discord_sync] inc_pulse_stat: chave desconhecida '%s'", key)


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
    text = text.strip()
    if len(text) > 3900:
        text = text[:3897] + "…"
    return text


def _safe_webhook_id(url: str) -> str:
    """Retorna identificador seguro do webhook para logs — nunca expõe o token."""
    try:
        parts = url.rstrip("/").split("/")
        # URL formato: .../webhooks/{id}/{token} — usa apenas o ID (posição -2)
        return f"#{parts[-2][-8:]}"
    except Exception:
        return "#unknown"


def _post_webhook(payload: dict, url: str) -> bool:
    """POST com retry automático em caso de rate limit (429) ou timeout.

    Retorna True apenas quando o Discord confirma entrega (200/204).
    False em qualquer falha — permitindo que o caller tome decisão de guard.
    """
    if not url:
        logger.error("[discord_sync] Webhook URL vazia — mensagem descartada.")
        return False
    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code in (200, 204):
                return True
            if resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 2.0)
                time.sleep(float(retry_after) + 0.2)
                continue
            logger.warning("[discord_sync] Webhook %s retornou %s: %s",
                           _safe_webhook_id(url), resp.status_code, resp.text[:200])
            return False
        except Exception as e:
            logger.warning("[discord_sync] Tentativa %d/3 falhou: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(3)
                continue
            logger.error("[discord_sync] Webhook falhou após 3 tentativas: %s",
                         _safe_webhook_id(url))
    return False


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
        f"📦 **SUPPLY TOTAL:** `{_TOKEN_TOTAL_SUPPLY:,} WEbdEX`\n"
    )
    if msg:
        desc += f"\n─────────────────────\n{_telegram_to_discord(msg)}"
    _async_post({
        "embeds": [{
            "title": "📊 TOKEN WEbdEX — RELATÓRIO DE CRESCIMENTO",
            "description": desc,
            "color": _COLOR_TOKEN_BD,
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

    # WEbdEX não tem BURN — apenas MINT (deploy) e TRANSFER
    if from_addr.lower() == ZERO:
        tipo, icone, cor = "MINT", "🌱", _SUCCESS
    else:
        tipo, icone, cor = "TRANSFER", "💎", _CHART_BLUE

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




def notify_operacoes_horario(total: int, by_env: dict, hora_str: str) -> None:
    """Relatório 2h de operações → #operações."""
    if total == 0:
        desc  = "🔇 **NENHUMA OPERAÇÃO** nas últimas 2h.\n*Protocolo aguardando próximo ciclo.*"
        color = _DARK
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
        color = _WARNING
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
        color = _DARK
    else:
        bars  = min(10, max(1, total * 2))
        bar   = "█" * bars + "░" * max(0, 10 - bars)
        desc  = (
            f"**📊 TOTAL DE SWAPS:** `{total}`\n\n"
            f"🆕 **CREATE SWAP:** `{create}`\n"
            f"✅ **SWAP EXECUTADO:** `{execute}`\n\n"
            f"`{bar}` `{total} swaps/2h`"
        )
        color = _CHART_BLUE
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
    color: int = _SUCCESS,
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
            "color": _SUCCESS,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol · OCME Monitor · Ao vivo"},
        }]
    }, url=_WEBHOOK_ONCHAIN)


def notify_nova_carteira(endereco: str, total_holders: int) -> None:
    """Nova carteira conectada ao protocolo → #conquistas."""
    short = f"{endereco[:6]}…{endereco[-4:]}" if len(endereco) > 12 else endereco
    _async_post({
        "embeds": [{
            "title": "🟢 Protocolo em Crescimento",
            "description": (
                f"Nova subconta **`{short}`** entrou no protocolo.\n\n"
                f"👥 **Subcontas ativas:** `{total_holders}`"
            ),
            "color": _SUCCESS,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol · OCME · Polygon"},
        }]
    }, url=_WEBHOOK_CONQUISTAS)


def notify_conquistas_diario(
    total_trades: int,
    win_rate: float,
    pnl_usd: float,
    active_traders: int,
    hoje: str = "",
) -> None:
    """Mini-resumo diário do ciclo 21h → #conquistas (saúde do protocolo)."""
    emoji = "🟢" if pnl_usd >= 0 else "🔴"
    pnl_sign = "+" if pnl_usd >= 0 else ""
    filled = round(win_rate / 10)
    wr_bar = "█" * filled + "░" * (10 - filled)
    _async_post({
        "embeds": [{
            "title": f"⚡ Protocolo · Ciclo Encerrado{(' · ' + hoje) if hoje else ''}",
            "description": (
                f"{emoji} **P&L:** `{pnl_sign}${pnl_usd:,.2f}`\n"
                f"📊 **{total_trades:,} trades** · WinRate `{win_rate:.0f}%`\n"
                f"`{wr_bar}`\n"
                f"👥 **Traders ativos:** `{active_traders}`"
            ),
            "color": _SUCCESS if pnl_usd >= 0 else _ERROR,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol · OCME · Polygon"},
        }]
    }, url=_WEBHOOK_CONQUISTAS)


def notify_protocolo_relatorio(
    hoje: str,
    tvl_usd: float,
    bd_periodo: float,
    p_traders: int,
    p_wr: float,
    p_bruto: float,
    top_traders: list,
    label: str = "Ciclo 21h",
    show_cta: bool = True,
) -> bool:
    """Relatório completo 💎 LUCRO TOTAL DO PROTOCOLO → #relatório-diário (Discord).

    Retorna True se o Discord confirmou entrega (200/204), False caso contrário.
    show_cta=False suprime o bloco de CTA OCME_bd — usar em snapshots intraday.
    """
    emoji  = "🟢" if p_bruto >= 0 else "🔴"
    color  = _SUCCESS if p_bruto >= 0 else _ERROR
    pl_str = f"+${p_bruto:,.2f}" if p_bruto >= 0 else f"-${abs(p_bruto):,.2f}"

    desc = (
        f"🗓️ **{label}**  ·  {hoje}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎  **TVL DO PROTOCOLO**\n"
        f"  └─ 💰 Total: **${tvl_usd:,.0f} USD**\n\n"
        f"📈  **P&L DOS TRADERS**  *(resultado on-chain dos usuários)*\n"
        f"  ├─ 👥 Traders: **{p_traders}**  ·  🎯 WR: **{p_wr:.1f}%**\n"
        f"  └─ {emoji} Resultado bruto: **{pl_str} USD**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎  **RECEITA DO PROTOCOLO**  *(BD/Passe coletado on-chain)*\n"
        f"  └─ 🏦 Período: **{bd_periodo:,.4f} BD**\n"
    )

    # Top 5 traders (omitido em snapshots intraday via top_traders=[])
    if top_traders:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        desc += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n🏆  **TOP 5 TRADERS (período)**\n"
        for i, row in enumerate(top_traders):
            wallet  = str(row[0])
            lucro   = float(row[1] or 0)
            fee     = float(row[2] or 0) if len(row) > 2 else 0.0
            short_w = f"{wallet[:6]}\u2026{wallet[-4:]}" if len(wallet) > 10 else wallet
            lstr    = f"+${lucro:.2f}" if lucro >= 0 else f"-${abs(lucro):.2f}"
            sg = "🟢" if lucro >= 0 else "🔴"
            desc += (
                f"  {medals[i]}  `{short_w}`\n"
                f"       {sg} **{lstr}**  ·  💎 {fee:.3f} BD\n"
            )

    # CTA OCME_bd — apenas no fechamento real (show_cta=True); omitido em intraday
    if show_cta:
        desc += (
            f"\n\n─────────────────────────\n"
            f"💡 **Tem o OCME_bd no Telegram?**\n"
            f"Quem tem o bot ativo recebe este relatório **personalizado por carteira**,\n"
            f"análise por trade, alertas de anomalia e acesso total ao fluxo do protocolo.\n"
            f"**Informação é poder. Na WEbdEX, ela vem até você.**\n\n"
            f"[→ Ativar OCME_bd — Beta Gratuito]({_OCME_BD_LINK})"
        )

    # Síncrono: bloqueia até HTTP confirmar (3 tentativas, timeout 20s cada)
    # Retorna bool para que o caller condicione o guard de deduplicação
    return _post_webhook({
        "embeds": [{
            "title": "\U0001f4a0 RELAT\u00d3RIO DO PROTOCOLO \u2014 WEbdEX",
            "description": desc,
            "color": color,
            "thumbnail": {"url": _BDZINHO_IMG},
            "footer": {"text": "WEbdEX Protocol \u00b7 Ciclo 21h BR \u00b7 Polygon"},
        }]
    }, url=_WEBHOOK_RELATORIO)


def notify_protocolo_relatorio_telegram(
    hoje: str,
    tvl_usd: float,
    bd_periodo: float,
    p_traders: int,
    p_wr: float,
    p_bruto: float,
    top_traders: list,
    label: str = "Ciclo 21h",
) -> str:
    """Versão Telegram HTML do relatório protocolo. Retorna string para broadcast."""
    emoji  = "🟢" if p_bruto >= 0 else "🔴"
    pl_str = f"+${p_bruto:,.2f}" if p_bruto >= 0 else f"-${abs(p_bruto):,.2f}"
    msg = (
        f"🌙 <b>RELATÓRIO DO PROTOCOLO — WEbdEX</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💧 Liquidez LP: <b>${tvl_usd:,.0f} USD</b>\n"
        f"👥 Traders: <b>{p_traders}</b>  ·  WR: <b>{p_wr:.1f}%</b>\n"
        f"{emoji} P&amp;L Bruto: <b>{pl_str} USD</b>\n"
        f"🏦 BD período: <b>{bd_periodo:,.4f} BD</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    if top_traders:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        msg += "\n🏆 <b>TOP 5 TRADERS (período):</b>\n"
        for i, row in enumerate(top_traders):
            wallet  = str(row[0])
            lucro   = float(row[1] or 0)
            fee     = float(row[2] or 0) if len(row) > 2 else 0.0
            short_w = f"{wallet[:6]}\u2026{wallet[-4:]}" if len(wallet) > 10 else wallet
            lstr    = f"+${lucro:.2f}" if lucro >= 0 else f"-${abs(lucro):.2f}"
            msg += (
                f"  {medals[i]} <code>{short_w}</code>\n"
                f"       {lstr}  ·  💎 {fee:.3f} BD\n"
            )
    msg += f"\n🗓️ {hoje}"
    return msg


def notify_protocolo_relatorio_onchain(
    hoje: str,
    tvl_usd: float,
    bd_periodo: float,
    p_traders: int,
    p_wr: float,
    p_bruto: float,
    label: str = "Ciclo 21h",
) -> None:
    """Versão compacta do relatório protocolo → #webdex-on-chain (segundo canal).

    label="Intraday HH:00" para snapshots intraday; "Ciclo 21h" para fechamento.
    Cor reflete resultado real: verde em lucro, vermelho em perda.
    """
    emoji  = "🟢" if p_bruto >= 0 else "🔴"
    color  = _SUCCESS if p_bruto >= 0 else _ERROR
    pl_str = f"+${p_bruto:,.0f}" if p_bruto >= 0 else f"-${abs(p_bruto):,.0f}"
    desc = (
        f"**{hoje}  ·  {p_traders} traders  ·  WR {p_wr:.0f}%**\n"
        f"💎 TVL: `${tvl_usd:,.0f}` USD  ·  💰 BD: `{bd_periodo:,.2f}`\n"
        f"{emoji} P&L Bruto: **{pl_str} USD**"
    )
    _async_post({
        "embeds": [{
            "title": f"📋 {label} — Resumo do Protocolo",
            "description": desc,
            "color": color,
            "footer": {"text": "WEbdEX Protocol · Ciclo 21h BR · Polygon"},
        }]
    }, url=_WEBHOOK_ONCHAIN)


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
    color = _ERROR if severity == "critical" else _COLOR_ALERT
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
