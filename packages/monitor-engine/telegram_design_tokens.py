"""
telegram_design_tokens.py — Design System WEbdEX para mensagens Telegram.

Fonte: Manual da Marca WEbdEX (design_tokens.py) + análise das mensagens
existentes do bot OCME_bd (mybdBook, ciclo 21h, operações, SwapBook, token BD).

Tipografia Telegram: HTML bold (<b>), italic (<i>), code (<code>), pre (<pre>).
Parse mode: HTML (padrão do webdex_bot_core.py — telebot parse_mode="HTML").

Uso:
    from telegram_design_tokens import (
        EMOJI, SEP, HDR, format_currency, format_pct, progress_bar,
    )
    msg = HDR.ciclo_21h("21:00")
    msg += SEP.linha
    msg += f"{EMOJI.resultado_win} P&L: {format_currency(1644.0)}"
"""

from __future__ import annotations

# ─── Constantes de Emoji por categoria ───────────────────────────────────────
# Baseadas EXCLUSIVAMENTE nos emojis já presentes nas mensagens do bot.

class _EmojiNS:
    """Namespace de emojis organizados por categoria semântica."""

    # Status e resultado
    resultado_win   = "🟢"   # P&L positivo / ciclo verde
    resultado_loss  = "🔴"   # P&L negativo / ciclo vermelho
    resultado_neu   = "⚪"   # neutro / sem dados

    # Métricas financeiras
    capital         = "💰"   # capital, USDT, saldo
    lucro           = "✅"   # lucros, ganhos
    perda           = "❌"   # perdas, loss
    gas             = "⛽"   # gas consumido
    gas_red         = "🔴"   # valor de gas (POL consumido)
    receita         = "💎"   # receita do protocolo, BD coletado
    banco           = "🏦"   # período de receita
    caixa           = "📦"   # acumulado / supply total

    # Dados e estatísticas
    grafico         = "📊"   # gráfico, trades, dados
    grafico_up      = "📈"   # tendência positiva, operações
    roi             = "📈"   # ROI (alias semântico)
    traders         = "👥"   # contagem de traders
    holders         = "👥"   # contagem de holders (alias)
    carteira        = "💼"   # carteira do usuário
    passe           = "🎟️"   # passe de assinatura

    # Tempo e ciclos
    ciclo_noite     = "🌙"   # relatório 21h (noturno)
    calendario      = "🗓️"   # data do ciclo
    relogio         = "⏰"   # hora, tempo real
    sol             = "☀️"   # good morning / ritual 7h

    # Protocolo e blockchain
    protocolo       = "⚡"   # protocolo ao vivo
    swap            = "🔄"   # SwapBook / swaps
    swap_create     = "🆕"   # novo swap criado
    swap_exec       = "✅"   # swap executado
    link_chain      = "🔗"   # link Polygonscan / on-chain
    polygon         = "🔷"   # rede Polygon
    token_move      = "💎"   # movimentação token WEbdEX
    mint            = "🌱"   # mint de token (from zero address)
    new_wallet      = "👛"   # nova carteira conectada

    # Conquistas e milestones
    trofeu          = "🏆"   # melhor trade, milestone
    medalha_ouro    = "🥇"
    medalha_prata   = "🥈"
    medalha_bronze  = "🥉"
    rank_4          = "4️⃣"
    rank_5          = "5️⃣"
    conquista       = "🎉"   # nova carteira / celebração

    # Alertas e sistema
    alerta          = "⚠️"   # aviso
    critico         = "🚨"   # anomalia crítica
    info            = "💡"   # informação / CTA
    robo            = "🤖"   # OCME_bd, bot, IA
    seta            = "→"    # link / ação (texto simples)
    ok              = "✅"   # confirmação genérica

    # Ranking em lista (top traders)
    MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


EMOJI = _EmojiNS()


# ─── Separadores e divisores ─────────────────────────────────────────────────
# Reproduz fielmente os separadores usados nas mensagens existentes.

class _SepNS:
    """Separadores visuais para mensagens Telegram."""

    # Linha grossa — título de seção principal (ciclo 21h)
    linha   = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Linha fina — subsecção dentro do relatório
    fina    = "─────────────────────────"

    # Árvore de dados — itens dentro de um bloco (├─ └─)
    item    = "  ├─"
    ultimo  = "  └─"

    # Recuo padrão para linhas de detalhe
    recuo   = "  "

    # Linha vazia (espaçamento)
    vazio   = ""


SEP = _SepNS()


# ─── Headers de seção ─────────────────────────────────────────────────────────
# Baseados nos títulos exatos das mensagens existentes.

class _HdrNS:
    """Cabeçalhos de mensagem — retornam strings HTML prontas para envio."""

    @staticmethod
    def ciclo_21h(hora: str = "21:00", label: str = "RELATÓRIO DO CICLO 21H") -> str:
        """Cabeçalho do relatório noturno."""
        return f"{EMOJI.ciclo_noite} <b>{label} — WEbdEX PROTOCOL</b>\n"

    @staticmethod
    def mybdbook(wallet_short: str = "") -> str:
        """Cabeçalho do relatório pessoal mybdBook."""
        linha_carteira = f"Carteira: <code>{wallet_short}</code>\n" if wallet_short else ""
        return f"{EMOJI.grafico} <b>mybdBook — WEbdEX</b>\n{linha_carteira}"

    @staticmethod
    def protocolo_ao_vivo(hora: str = "21:00") -> str:
        """Cabeçalho do relatório de operações ao vivo."""
        return f"{EMOJI.protocolo} <b>PROTOCOLO WEbdEX — AO VIVO · {hora}</b>\n"

    @staticmethod
    def swapbook(hora: str = "21:00") -> str:
        """Cabeçalho do relatório SwapBook."""
        return f"{EMOJI.swap} <b>SWAPBOOK WEbdEX — {hora}</b>\n"

    @staticmethod
    def token_bd() -> str:
        """Cabeçalho do relatório de crescimento do token."""
        return f"{EMOJI.grafico} <b>TOKEN WEbdEX — RELATÓRIO DE CRESCIMENTO</b>\n"

    @staticmethod
    def secao(titulo: str, emoji: str = "") -> str:
        """Cabeçalho genérico de seção dentro de um relatório."""
        pref = f"{emoji}  " if emoji else ""
        return f"\n{pref}<b>{titulo}</b>\n"


HDR = _HdrNS()


# ─── Footer padrão ───────────────────────────────────────────────────────────
# Alinhado com FOOTER_TEXT de design_tokens.py.

FOOTER_TEXT = "WEbdEX Protocol · bdZinho"
BDZINHO_ICON_URL = "https://i.ibb.co/MkcqbvLb/post-149-operador-da-tecnologia-01.jpg"

# CTA OCME_bd — bloco de call-to-action padrão do bot
_OCME_BD_LINK_DEFAULT = "https://t.me/OCME_bd"


def cta_ocme(link: str = _OCME_BD_LINK_DEFAULT) -> str:
    """
    Bloco CTA padrão para mensagens broadcast (ciclo 21h, operações).
    Reproduz o bloco presente no webdex_discord_sync.py, adaptado para HTML Telegram.
    """
    return (
        f"\n{SEP.fina}\n"
        f"{EMOJI.info} <b>Tem o OCME_bd no Telegram?</b>\n"
        f"Quem tem o bot ativo recebe este relatório <b>personalizado por carteira</b>,\n"
        f"análise por trade, alertas de anomalia e acesso total ao fluxo do protocolo.\n"
        f"<b>Informação é poder. Na WEbdEX, ela vem até você.</b>\n\n"
        f"{EMOJI.seta} <a href=\"{link}\">Ativar OCME_bd — Beta Gratuito</a>"
    )


# ─── Formatadores de valores ──────────────────────────────────────────────────

def format_currency(value: float, signed: bool = False, decimals: int = 2) -> str:
    """
    Formata valor monetário em USD.

    Args:
        value:    Valor numérico.
        signed:   Se True, inclui sinal + para positivos (P&L, resultado).
        decimals: Casas decimais (padrão 2; use 4 para médias por trade).

    Exemplos:
        format_currency(1644.0)           → "$1,644.00"
        format_currency(1644.0, signed=True) → "+$1,644.00"
        format_currency(-203.5, signed=True) → "-$203.50"
        format_currency(0.0042, decimals=4)  → "$0.0042"
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "$0.00"

    fmt = f"{{:,.{decimals}f}}"
    abs_str = fmt.format(abs(v))

    if signed:
        return f"+${abs_str}" if v >= 0 else f"-${abs_str}"
    return f"${abs_str}"


def format_pct(value: float, decimals: int = 1, signed: bool = False) -> str:
    """
    Formata percentual.

    Args:
        value:    Valor percentual (ex: 62.3 para 62.3%).
        decimals: Casas decimais (padrão 1).
        signed:   Se True, inclui sinal + para positivos.

    Exemplos:
        format_pct(62.3)              → "62.3%"
        format_pct(0.003, decimals=3) → "0.003%"
        format_pct(-1.2, signed=True) → "-1.2%"
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "0.0%"

    fmt = f"{{:.{decimals}f}}"
    s = fmt.format(abs(v))

    if signed:
        return f"+{s}%" if v >= 0 else f"-{s}%"
    return f"{s}%"


def format_pol(value: float, decimals: int = 4) -> str:
    """
    Formata valor em POL (token nativo Polygon).

    Exemplos:
        format_pol(127.44)    → "127.4400 POL"
        format_pol(0.0032, 6) → "0.003200 POL"
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "0.0000 POL"
    return f"{v:,.{decimals}f} POL"


def format_bd(value: float, decimals: int = 4) -> str:
    """
    Formata valor em BD (token de receita do protocolo).

    Exemplos:
        format_bd(44.882)      → "44.8820 BD"
        format_bd(1247.66)     → "1,247.6600 BD"
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "0.0000 BD"
    return f"{v:,.{decimals}f} BD"


def format_webdex(value: float) -> str:
    """
    Formata supply / quantidade do token WEbdEX.

    Exemplos:
        format_webdex(369369369) → "369,369,369 WEbdEX"
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "0 WEbdEX"
    return f"{v:,.0f} WEbdEX"


def format_int(value: int) -> str:
    """
    Formata inteiro com separador de milhar.

    Exemplos:
        format_int(3994121) → "3,994,121"
        format_int(39813)   → "39,813"
    """
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def format_wallet(address: str) -> str:
    """
    Abrevia endereço de carteira Ethereum para exibição.

    Exemplos:
        format_wallet("0xABCDEF1234567890ABCDEF") → "0xABCD…7890"
    """
    addr = str(address).strip()
    if len(addr) > 12:
        return f"{addr[:6]}…{addr[-4:]}"
    return addr


def format_tx(tx_hash: str) -> str:
    """
    Abrevia hash de transação para exibição inline.

    Exemplos:
        format_tx("0xabc123...def456") → "0xabc1…f456"
    """
    tx = str(tx_hash).strip()
    if len(tx) > 12:
        return f"{tx[:6]}…{tx[-4:]}"
    return tx


def polygonscan_link(tx_hash: str, label: str = "Ver no Polygonscan") -> str:
    """
    Gera link HTML para o Polygonscan.

    Exemplo:
        polygonscan_link("0xabc...") → '<a href="https://polygonscan.com/tx/0xabc...">Ver no Polygonscan</a>'
    """
    return f'<a href="https://polygonscan.com/tx/{tx_hash}">{EMOJI.link_chain} {label}</a>'


# ─── Barra de progresso ───────────────────────────────────────────────────────

def progress_bar(value: float, max_val: float, width: int = 10,
                 fill: str = "█", empty: str = "░") -> str:
    """
    Gera barra de progresso ASCII proporcional ao valor.

    Args:
        value:   Valor atual.
        max_val: Valor máximo para 100%.
        width:   Largura total da barra em blocos (padrão 10).
        fill:    Caractere de preenchimento (padrão "█").
        empty:   Caractere vazio (padrão "░").

    Exemplos:
        progress_bar(8000, 10000)      → "████████░░"
        progress_bar(62.3, 100)        → "██████░░░░"
        progress_bar(14, 14)           → "██████████"
        progress_bar(0, 100)           → "░░░░░░░░░░"
    """
    try:
        v   = float(value)
        mx  = float(max_val)
        if mx <= 0:
            filled = 0
        else:
            ratio  = max(0.0, min(1.0, v / mx))
            filled = round(ratio * width)
    except (TypeError, ValueError, ZeroDivisionError):
        filled = 0

    filled = max(0, min(width, filled))
    return fill * filled + empty * (width - filled)


def winrate_bar(wins: int, total: int, width: int = 10) -> str:
    """
    Barra de win rate com blocos quadrados coloridos.
    Usa 🟩 para wins e 🔴 para losses — padrão da função barra_progresso()
    existente em webdex_bot_core.py.

    Exemplos:
        winrate_bar(6, 10)  → "🟩🟩🟩🟩🟩🟩🔴🔴🔴🔴"
        winrate_bar(10, 10) → "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩"
    """
    if total <= 0:
        return "⬜" * width
    perc = max(0.0, min(1.0, wins / total))
    blocos = round(perc * width)
    blocos = max(0, min(width, blocos))
    return "🟩" * blocos + "🔴" * (width - blocos)


def ops_bar(ops_2h: int, scale: int = 400, width: int = 10) -> str:
    """
    Barra de progresso de operações — escala padrão usada no webdex_discord_sync.py.
    Garante mínimo 1 bloco e máximo width blocos.

    Args:
        ops_2h: Total de operações no período de 2h.
        scale:  Quantas ops equivalem a 1 bloco (padrão 400).
        width:  Largura da barra (padrão 10).

    Exemplos:
        ops_bar(3994121)  → "██████████"  (acima de 4000 ops → barra cheia)
        ops_bar(800)      → "██░░░░░░░░"
    """
    try:
        bars = min(width, max(1, round(int(ops_2h) / scale)))
    except (TypeError, ValueError):
        bars = 1
    return "█" * bars + "░" * (width - bars)


# ─── Constantes de mensagem recorrentes ──────────────────────────────────────
# Textos fixos extraídos das mensagens existentes — nunca inventados.

class _MsgNS:
    """Textos e frases recorrentes nas mensagens do bot OCME_bd."""

    # Estados do protocolo
    protocolo_ativo      = "O protocolo está <b>ativo e monitorando</b> 👁"
    protocolo_aguardando = "<i>Protocolo aguardando próximo ciclo.</i>"
    sem_operacoes        = f"{EMOJI.robo} <b>NENHUMA OPERAÇÃO</b> nas últimas 2h.\n<i>Protocolo aguardando próximo ciclo.</i>"
    sem_swaps            = f"{EMOJI.robo} <b>NENHUM SWAP</b> nas últimas 2h.\n<i>SwapBook aguardando próxima oferta.</i>"

    # Descrição do OCME_bd (protocolo ao vivo)
    ocme_descricao = (
        f"{EMOJI.robo} <b>OCME_bd — Beta Exclusivo</b>\n"
        "O assistente IA do WEbdEX que traz relatórios on-chain,\n"
        "análise de fluxo e dados consolidados na palma da mão.\n"
        "<i>Em breve no portfolio oficial WEbdEX Protocol.</i>"
    )

    # Labels de seção
    label_pnl_traders   = "P&L DOS TRADERS"
    label_gas           = "GÁS CONSUMIDO"
    label_receita       = "RECEITA DO PROTOCOLO"
    label_top5          = "TOP 5 TRADERS (período)"

    # Textos de ROI positivo (mybdBook)
    roi_positivo        = "Capital trabalhando."
    roi_negativo        = "Analisando próxima oportunidade."

    # Rede e fonte
    fonte_onchain       = "Fonte: on-chain · Polygon"
    rede_polygon        = "Polygon Mainnet"

    # Saudação diária
    bom_dia_wagmi       = "Boa sorte nos trades de hoje. Que os ciclos sejam verdes! 🚀"


MSG = _MsgNS()


# ─── Blocos de seção pré-montados ─────────────────────────────────────────────
# Constroem as seções textuais das mensagens complexas.

def bloco_pnl_traders(
    trades: int,
    traders: int,
    wr_pct: float,
    ganhos: float,
    perdas: float,
    lucro: float,
    avg_trade: float,
) -> str:
    """
    Bloco completo de P&L dos Traders (ciclo 21h).
    Reproduz fielmente o formato do relatório existente.

    Exemplo de saída:
        📈  P&L DOS TRADERS (resultado on-chain)
          ├─ 📊 Trades: 39,813  👥 Traders: 19  WR: 62.3%
          ├─ ✅ Lucros: +$2,847.00  ❌ Perdas: -$1,203.00
          └─ 🟢 Resultado: +$1,644.00 USD  (+$0.0413/trade)
    """
    emoji_res = EMOJI.resultado_win if lucro >= 0 else EMOJI.resultado_loss
    s_lucro   = format_currency(lucro, signed=True)
    s_ganhos  = format_currency(ganhos, signed=True)
    s_perdas  = format_currency(perdas, signed=True)
    s_avg     = format_currency(avg_trade, signed=True, decimals=4)

    return (
        f"\n{EMOJI.grafico_up}  <b>{MSG.label_pnl_traders}</b> <i>(resultado on-chain)</i>\n"
        f"{SEP.item} {EMOJI.grafico} Trades: <b>{format_int(trades)}</b>  "
        f"{EMOJI.traders} Traders: <b>{traders}</b>  WR: <b>{format_pct(wr_pct)}</b>\n"
        f"{SEP.item} {EMOJI.lucro} Lucros: <b>{s_ganhos}</b>  {EMOJI.perda} Perdas: <b>{s_perdas}</b>\n"
        f"{SEP.ultimo} {emoji_res} Resultado: <b>{s_lucro} USD</b>  <i>({s_avg}/trade)</i>\n"
    )


def bloco_gas(gas_pol: float, gas_usd: float, trades: int) -> str:
    """
    Bloco de gás consumido (ciclo 21h).

    Exemplo de saída:
        ⛽  GÁS CONSUMIDO
          ├─ 🔴 Total POL: 127.4400 POL  (~$62.71)
          └─ 📊 Média/trade: 0.003200 POL
    """
    avg_gas = (gas_pol / trades) if trades > 0 else 0.0
    return (
        f"\n{EMOJI.gas}  <b>{MSG.label_gas}</b>\n"
        f"{SEP.item} {EMOJI.gas_red} Total POL: <b>{format_pol(gas_pol)}</b>  "
        f"<i>(~{format_currency(gas_usd)})</i>\n"
        f"{SEP.ultimo} {EMOJI.grafico} Média/trade: <b>{format_pol(avg_gas, decimals=6)}</b>\n"
    )


def bloco_receita(bd_periodo: float, bd_acumulado: float) -> str:
    """
    Bloco de receita do protocolo (ciclo 21h).

    Exemplo de saída:
        💎  RECEITA DO PROTOCOLO
          ├─ 🏦 Período:   44.8820 BD
          └─ 📦 Acumulado: 1,247.6600 BD
    """
    return (
        f"\n{EMOJI.receita}  <b>{MSG.label_receita}</b>  <i>(BD/Passe coletado on-chain)</i>\n"
        f"{SEP.item} {EMOJI.banco} Período:   <b>{format_bd(bd_periodo)}</b>\n"
        f"{SEP.ultimo} {EMOJI.caixa} Acumulado: <b>{format_bd(bd_acumulado)}</b>  "
        f"<i>(all-time indexado)</i>\n"
    )


def bloco_top_traders(top_traders: list) -> str:
    """
    Bloco de top 5 traders (ciclo 21h).

    Args:
        top_traders: Lista de tuplas (wallet, lucro, trades, bd_pago, gas).
                     Máximo 5 itens — itens excedentes são ignorados.

    Exemplo de saída:
        🏆  TOP 5 TRADERS (período)
          🥇  `0xABCD…1234`
               🟢 +$210.00  ·  1,203t  ·  💎 12.345 BD
    """
    if not top_traders:
        return ""

    linhas = [f"\n{SEP.linha}\n\n{EMOJI.trofeu}  <b>{MSG.label_top5}</b>\n"]
    for i, entrada in enumerate(top_traders[:5]):
        wallet, lucro, t_trades, bd_pago = entrada[0], entrada[1], entrada[2], entrada[3]
        short_w  = format_wallet(str(wallet))
        emoji_r  = EMOJI.resultado_win if (lucro or 0) >= 0 else EMOJI.resultado_loss
        s_lucro  = format_currency(float(lucro or 0), signed=True)
        medal    = EMOJI.MEDALS[i]
        linhas.append(
            f"  {medal}  <code>{short_w}</code>\n"
            f"       {emoji_r} <b>{s_lucro}</b>  ·  {format_int(t_trades)}t  "
            f"·  {EMOJI.receita} {format_bd(float(bd_pago or 0), decimals=3)}\n"
        )
    return "".join(linhas)


def bloco_mybdbook(
    wallet: str,
    capital_usd: float,
    trades: int,
    subs: int,
    pnl_bruto: float,
    melhor_trade: float,
    roi_pct: float,
) -> str:
    """
    Mensagem completa mybdBook (relatório pessoal do usuário).

    Reproduz a estrutura:
        📊 mybdBook — WEbdEX
        Carteira: 0xABCD...1234
          💰 Capital (USDT0): 15,184.15 USD
          📊 Trades: 1,247 | Subs: 3
          💰 Bruto:   +0.0142 USD
          🏆 Melhor trade: +0.0890 USD
          📈 ROI positivo de +0.003% no ciclo. Capital trabalhando.
    """
    wallet_short = format_wallet(wallet)
    roi_label    = "positivo" if roi_pct >= 0 else "negativo"
    roi_texto    = MSG.roi_positivo if roi_pct >= 0 else MSG.roi_negativo

    return (
        f"{HDR.mybdbook(wallet_short)}\n"
        f"  {EMOJI.capital} Capital (USDT0): <b>{format_currency(capital_usd)} USD</b>\n"
        f"  {EMOJI.grafico} Trades: <b>{format_int(trades)}</b> | Subs: <b>{subs}</b>\n"
        f"  {EMOJI.capital} Bruto:   <b>{format_currency(pnl_bruto, signed=True)}</b>\n"
        f"  {EMOJI.trofeu} Melhor trade: <b>{format_currency(melhor_trade, signed=True)}</b>\n"
        f"  {EMOJI.roi} ROI {roi_label} de "
        f"<b>{format_pct(roi_pct, decimals=3, signed=True)}</b> no ciclo. {roi_texto}"
    )


def bloco_operacoes(total_ops: int, hora: str, ocme_link: str = _OCME_BD_LINK_DEFAULT) -> str:
    """
    Mensagem de relatório de operações ao vivo (2h).

    Reproduz a estrutura do notify_operacoes_horario() do webdex_discord_sync.py.
    """
    if total_ops == 0:
        return (
            f"{HDR.protocolo_ao_vivo(hora)}\n"
            f"{MSG.sem_operacoes}"
        )

    bar = ops_bar(total_ops)
    return (
        f"{HDR.protocolo_ao_vivo(hora)}\n"
        f"{EMOJI.grafico_up} <b>TOTAL DE OPERAÇÕES:</b> <code>{format_int(total_ops)}</code>\n"
        f"<code>{bar} {format_int(total_ops)} ops/2h</code>\n\n"
        f"{SEP.fina}\n"
        f"{MSG.ocme_descricao}\n\n"
        f"{EMOJI.seta} <a href=\"{ocme_link}\">Acessar OCME_bd no Telegram</a>"
    )


def bloco_swapbook(total: int, create: int, execute: int, hora: str) -> str:
    """
    Mensagem do relatório SwapBook (2h).

    Reproduz a estrutura do notify_swaps_horario() do webdex_discord_sync.py.
    """
    if total == 0:
        return f"{HDR.swapbook(hora)}\n{MSG.sem_swaps}"

    bars  = min(10, max(1, total * 2))
    bar   = "█" * bars + "░" * max(0, 10 - bars)
    return (
        f"{HDR.swapbook(hora)}\n"
        f"{EMOJI.grafico} <b>TOTAL DE SWAPS:</b> <code>{total}</code>\n"
        f"{EMOJI.swap_create} <b>CREATE SWAP:</b> <code>{create}</code>\n"
        f"{EMOJI.swap_exec} <b>SWAP EXECUTADO:</b> <code>{execute}</code>\n\n"
        f"<code>{bar} {total} swaps/2h</code>"
    )


def bloco_token_bd(holders: int, supply: float, total_supply: int = 369_369_369) -> str:
    """
    Mensagem do relatório do token WEbdEX (holders / supply).

    Reproduz a estrutura do notify_token_bd() do webdex_discord_sync.py.
    """
    return (
        f"{HDR.token_bd()}\n"
        f"{EMOJI.holders} <b>HOLDERS ATIVOS:</b> <code>{format_int(holders)}</code>\n"
        f"{EMOJI.token_move} <b>EM CIRCULAÇÃO:</b> <code>{format_webdex(supply)}</code>\n"
        f"{EMOJI.caixa} <b>SUPPLY TOTAL:</b> <code>{format_webdex(total_supply)}</code>"
    )
