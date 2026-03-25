from __future__ import annotations
# ==============================================================================
# webdex_handlers/user.py — WEbdEX Monitor Engine (extraído de WEbdEX_V30_24_SPEED_PATCH_FIXED.py)
# Linhas fonte: ~2558-2606 (main_kb, _tg_ai_pretty)
#               + ~2952-2979 (require_auth)
#               + ~4754-7200 (user handlers)
#               + ~7459-7543 (auto_resume_notify, polling helpers)
#               + ~7706-7733 (_KNOWN_BUTTONS)
#               + ~7734-7978 (mybdBook user, inatividade_report)
# ==============================================================================

import os, time, threading, hashlib
import csv
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import math
from statistics import median, stdev as _stdev
import functools

from telebot import types

from webdex_config import (
    logger, Web3, CONTRACTS, TOKENS_TO_WATCH,
    ADDR_USDT0, ADDR_LPLPUSD,
)
from webdex_db import (
    DB_LOCK, cursor, conn, now_br, get_config, set_config,
    period_to_hours, _period_since, _period_label,
    _ciclo_21h_since, _ciclo_21h_label,
    get_last_trade_by_sub, _minutes_since, get_subs_in_period,
    load_trade_times_by_sub, ciclo_stats, consist_score, _percentile, _std,
    _dt_since, get_user_filter_clause, from_s,
    get_user, upsert_user, get_connected_users,
    LIMITE_INATIV_MIN,
    get_known_wallet, mark_known_wallet_registered,
    normalize_txhash,
)
from webdex_chain import (
    web3, web3_for_rpc, get_contracts, obter_preco_pol,
    chain_pol_price, chain_gwei, chain_block, rpc_pool,
)
from webdex_bot_core import (
    bot, send_html, send_support, _send_long, send_logo_photo,
    esc, code, barra_progresso, gerar_grafico,
    _is_admin, is_admin,
)
from webdex_db import ai_can_use, ai_global_enabled, ai_mode, DASH_GRAPH_CACHE
from webdex_config import ai_answer_ptbr
from webdex_monitor import HEALTH, fetch_range

# Image generation (Nano Banana / Gemini via OpenRouter) — soft import
try:
    from webdex_ai_image_gen import generate_image as _img_gen, IMAGE_GEN_COOLDOWN_S
    _IMG_GEN_AVAILABLE = True
except ImportError:
    _img_gen = None  # type: ignore[assignment]
    IMAGE_GEN_COOLDOWN_S = 30
    _IMG_GEN_AVAILABLE = False

# Vision — análise de imagens enviadas pelo usuário — soft import
try:
    from webdex_ai_vision import analyze_image as _vision_analyze
    _VISION_AVAILABLE = True
except ImportError:
    _vision_analyze = None  # type: ignore[assignment]
    _VISION_AVAILABLE = False

# Individual Profile — para enriquecer análise de visão — soft import
try:
    from webdex_ai_user_profile import profile_build_context as _profile_ctx
    _VISION_PROFILE_ENABLED = True
except ImportError:
    _profile_ctx = None  # type: ignore[assignment]
    _VISION_PROFILE_ENABLED = False

# Rate limit dedicado para image gen (separado do _rate_cache geral)
_img_rate_cache: dict[int, float] = {}
_img_rate_lock  = threading.Lock()

# Rate limit para vision (cooldown 10s)
_VISION_COOLDOWN_S = 10
_vision_rate_cache: dict[int, float] = {}
_vision_rate_lock  = threading.Lock()

# ==============================================================================
# TOKENS MAP (para handler IDs com Saldo)
# ==============================================================================
from webdex_config import TOKEN_CONFIG
from decimal import Decimal

TOKENS_MAP = {
    k.lower(): v for k, v in TOKEN_CONFIG.items()
}

# ==============================================================================
# RATE LIMITING — proteção contra spam/flood de comandos
# ==============================================================================
_rate_cache: dict[int, float] = {}
_rate_lock  = threading.Lock()

def _throttle(user_id: int, seconds: float, label: str = "") -> bool:
    """
    Verifica se o usuário pode executar a ação agora.
    Retorna True se BLOQUEADO (ainda no cooldown), False se LIBERADO.
    """
    now = time.time()
    with _rate_lock:
        last = _rate_cache.get(user_id, 0.0)
        if now - last < seconds:
            return True   # bloqueado
        _rate_cache[user_id] = now
        return False      # liberado

# ==============================================================================
# DASH GRAPH CACHE TTL
# ==============================================================================
DASH_GRAPH_TTL = 300  # 5 min

# ==============================================================================
# 🎮 TECLADOS (main_kb, ajuda_kb, kpi_kb, ia_kb)
# ==============================================================================
def main_kb(chat_id=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 Resultados", "🤖 bdZinho")
    kb.row("🌐 Protocolo", "⚙️ Config")
    return kb


def ajuda_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📘 Iniciante", "📗 Intermediário", "📕 Avançado")
    kb.row("ℹ️ KPIs", "⏳ Inatividade")
    kb.row("⬅️ Voltar")
    return kb


def kpi_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🏅 Líquido", "⛽ Gás", "🏆 WinRate")
    kb.row("📐 Expectancy", "📉 Drawdown", "📈 Profit Factor")
    kb.row("🔥 Streaks", "🧯 Outliers")
    kb.row("⬅️ Voltar")
    return kb


def ia_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💬 Perguntar", "📌 OpenPosition")
    kb.row("📈 Dashboard", "🏆 Ranking")
    kb.row("🔙 Menu")
    return kb


def resultado_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📌 Ciclo 21h", "📈 Dashboard PRO")
    kb.row("📍 Posições", "📊 mybdBook")
    kb.row("📈 mybdBook (Gráfico)", "🩺 Saúde")
    kb.row("⬅️ Menu")
    return kb


def bdzinho_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💬 Perguntar", "🎨 Criar Imagem")
    kb.row("📌 Posição Aberta", "🔬 Análise")
    kb.row("⬅️ Menu")
    return kb


def protocolo_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🏆 Ranking Lucro", "🧠 Ranking Consistência")
    kb.row("⏱️ Ranking Ciclo", "🏛️ Comunidade")
    kb.row("📡 Status", "🔔 Alertas")
    kb.row("⛽ Auditoria Gás", "🧬 Ciclo da Subconta")
    kb.row("📜 Ops", "🔍 Buscar Tx")
    kb.row("🔄 Sync OnChain", "🧾 IDs com Saldo")
    kb.row("⬅️ Menu")
    return kb


def config_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🔌 Conectar", "▶️ Ativar", "⏸️ Pausar")
    kb.row("🗓️ Escolher Período", "🎛️ Filtros")
    kb.row("🔎 Wallet Info", "❓ Ajuda")
    kb.row("⏳ Inatividade", "🛠️ ADM")
    kb.row("⬅️ Menu")
    return kb


# ==============================================================================
# 🎨 HELPERS (formatação IA, dashboard)
# ==============================================================================
def _tg_ai_pretty(text: str) -> str:
    """Converte markdown simples (**, ###, -) em texto limpo para Telegram (HTML mode)."""
    import re
    import html as _html
    if not text:
        return ""
    s = str(text)

    # remove fences/backticks
    s = s.replace("```", "").replace("`", "")

    # remove markdown bold/italics markers
    s = s.replace("**", "").replace("__", "")

    # headings like ### Título — strip marker before escaping
    s = re.sub(r"(?m)^\s*#{1,6}\s*", "🔹 ", s)

    # bullets: -, * at start
    s = re.sub(r"(?m)^\s*[-\*]\s+", "• ", s)

    # normalize excessive blank lines
    s = re.sub(r"\n{3,}", "\n\n", s).strip()

    # escape HTML special chars (<, >, &) so parse_mode=HTML doesn't corrupt the text
    s = _html.escape(s)
    return s


# ==============================================================================
# 🛡️ REQUIRE_AUTH DECORATOR
# ==============================================================================
def require_auth(func):
    """Decorator: garante usuário autenticado antes de chamar func(m, u).
    Funciona quando chamado pelo Telegram (1 arg) ou internamente (2 args).
    """
    @functools.wraps(func)
    def wrapper(m, *args, **kwargs):
        u = get_user(m.chat.id)
        if not u or not u.get("wallet"):
            return send_support(m.chat.id, "⚠️ Conecte primeiro em 🔌 Conectar.", reply_markup=main_kb())
        try:
            # Se u já foi passado externamente, usa ele (evita duplo get_user)
            # Caso contrário usa o que buscamos acima
            if args and isinstance(args[0], dict):
                return func(m, *args, **kwargs)
            return func(m, u, *args, **kwargs)
        except Exception as e:
            logger.error("[handler] %s", e)
            try:
                send_support(
                    m.chat.id,
                    "⚠️ Ocorreu um erro ao processar sua solicitação. Tente novamente.",
                    reply_markup=main_kb()
                )
            except Exception:
                pass
            return None
    return wrapper


# ==============================================================================
# 🔁 AUTO RESUME (sem /start após reinício)
# ==============================================================================
def auto_resume_notify():
    try:
        for cid in get_connected_users():
            send_support(
                cid,
                "✅ Bot reiniciado e online.\n\nUse os botões abaixo (não precisa /start).",
                reply_markup=main_kb(),
                disable_web_page_preview=True
            )
            time.sleep(0.05)
    except Exception:
        pass


# ==============================================================================
# ✅ START
# ==============================================================================
@bot.message_handler(commands=["start"])
def start(m):
    # Rate limit: máx 1 /start a cada 3 segundos por usuário
    if _throttle(m.from_user.id, 3.0, "start"):
        return

    if not get_user(m.chat.id):
        upsert_user(m.chat.id)

    # ── Fase B: deep link  /start 0xABC123...
    parts = m.text.split(" ", 1)
    wallet_arg = parts[1].strip() if len(parts) > 1 else None
    if wallet_arg and wallet_arg.startswith("0x") and len(wallet_arg) == 42:
        _auto_connect_wallet(m, wallet_arg)
        return

    u = get_user(m.chat.id)
    if u and u.get("wallet"):
        sf = (u.get("sub_filter") or "").strip() or "Todas"
        send_support(
            m.chat.id,
            f"✅ Você já está conectado.\n\n🎛️ Filtro atual: <b>{esc(sf)}</b>\n🗓️ Período: <b>{esc(u.get('periodo','24h'))}</b>\n\nUse os botões abaixo.",
            reply_markup=main_kb()
        )
    else:
        welcome_caption = (
            "👋 <b>Bem-vindo ao WEbdEX Monitor!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🤖 Motor on-chain DeFi na Polygon.\n"
            "📊 Monitore suas subcontas, trades e capital em tempo real.\n\n"
            "🔌 Clique em <b>Conectar</b> para configurar sua wallet."
        )
        if not send_logo_photo(m.chat.id, welcome_caption, reply_markup=main_kb()):
            send_support(m.chat.id, welcome_caption, reply_markup=main_kb())


def _rpc_skip_kb():
    """Teclado com opção de pular o RPC."""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("⏭️ Pular RPC")
    kb.row("cancelar")
    return kb


def _auto_connect_wallet(m, wallet: str) -> None:
    """Salva a wallet e pede RPC (sempre — para permitir sync histórico).

    Fluxo:
      wallet reconhecida → mostra histórico + pede RPC (pode pular)
      wallet desconhecida → pede RPC (pode pular) → pede env
    """
    chat_id = m.chat.id
    kw = get_known_wallet(wallet)
    if kw and kw["trade_count"] > 0:
        env = kw["env"] or "bd_v5"
        lucro = kw["lucro_total"]
        sinal = "+" if lucro >= 0 else ""
        # Salva wallet + env já detectado; pede RPC antes de finalizar
        upsert_user(chat_id, wallet=wallet.lower(), env=env, pending="ASK_RPC")
        send_support(
            chat_id,
            f"🎉 <b>Wallet reconhecida!</b>\n\n"
            f"Histórico on-chain encontrado:\n"
            f"• Ambiente: <b>{esc(env)}</b>\n"
            f"• Trades: <b>{kw['trade_count']}</b>  "
            f"(✅{kw['wins']} / ❌{kw['losses']})\n"
            f"• Lucro total: <b>{sinal}{lucro:.4f} USDT</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 <b>Passo 2: Envie seu RPC Polygon</b>\n"
            f"(ex: <code>https://polygon-mainnet.g.alchemy.com/v2/SUA_CHAVE</code>)\n\n"
            f"O RPC permite sincronizar operações <b>anteriores</b> à sua conexão.\n"
            f"Não tem RPC? Use <b>⏭️ Pular RPC</b> para continuar assim mesmo.",
            reply_markup=_rpc_skip_kb()
        )
    else:
        # Wallet não conhecida — pede RPC e env manualmente
        upsert_user(chat_id, wallet=wallet.lower(), pending="ASK_RPC")
        send_support(
            chat_id,
            f"✅ Wallet salva: <code>{wallet[:10]}...{wallet[-6:]}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 <b>Passo 2: Envie seu RPC Polygon</b>\n"
            f"(ex: <code>https://polygon-mainnet.g.alchemy.com/v2/SUA_CHAVE</code>)\n\n"
            f"O RPC permite ver operações passadas da sua wallet.\n"
            f"Não tem RPC? Use <b>⏭️ Pular RPC</b>.",
            reply_markup=_rpc_skip_kb()
        )


# ==============================================================================
# ✅ BOTÕES BÁSICOS
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🔌 Conectar")
def btn_conectar(m):
    upsert_user(m.chat.id, pending="ASK_WALLET")
    send_support(
        m.chat.id,
        "🍰 <b>CONFIGURAÇÃO</b>\nPasso 1: Envie sua Wallet (0x...).\n\nDigite <b>cancelar</b> para sair.",
        reply_markup=types.ReplyKeyboardRemove()
    )


@bot.message_handler(func=lambda m: m.text == "▶️ Ativar")
def btn_ativar(m):
    upsert_user(m.chat.id, active=1)
    send_support(m.chat.id, "▶️ Monitoramento <b>ATIVADO</b>.", reply_markup=main_kb())


@bot.message_handler(func=lambda m: m.text == "⏸️ Pausar")
def btn_pausar(m):
    upsert_user(m.chat.id, active=0)
    send_support(m.chat.id, "⏸️ Monitoramento <b>PAUSADO</b>.", reply_markup=main_kb())


# ==============================================================================
# ✅ ESCOLHER PERÍODO
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🗓️ Escolher Período")
def escolher_periodo(m):
    u = get_user(m.chat.id) or {}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("ciclo", "7d", "30d")
    kb.row("⬅️ Voltar")
    upsert_user(m.chat.id, pending="ASK_PERIOD")
    send_support(
        m.chat.id,
        f"🗓️ <b>ESCOLHER PERÍODO</b>\n\nAtual: <b>{esc(_period_label(u.get('periodo','ciclo')))}</b>\nSelecione:",
        reply_markup=kb
    )


# ==============================================================================
# 🎛️ FILTROS
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🎛️ Filtros")
@require_auth
def filtros_menu(m, u):
    hours = period_to_hours(u.get("periodo") or "24h")
    # Subcontas com contagem e PnL no período
    sub_rows = []
    try:
        with DB_LOCK:
            sub_rows = cursor.execute("""
                SELECT o.sub_conta,
                       COUNT(*) as cnt,
                       SUM(CAST(o.valor AS REAL) - CAST(o.gas_usd AS REAL)) as liq
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE LOWER(ow.wallet)=? AND o.tipo='Trade'
                  AND o.data_hora >= datetime('now', ? || ' hours')
                GROUP BY o.sub_conta ORDER BY cnt DESC LIMIT 30
            """, (u["wallet"].lower(), f"-{hours}")).fetchall()
    except Exception:
        sub_rows = []

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Todas", "⬅️ Voltar")
    for sub, cnt, liq in sub_rows:
        kb.row(str(sub))  # botão limpo — sem emoji para não quebrar o handler

    upsert_user(m.chat.id, pending="ASK_FILTER_SUB")
    curr = (u.get("sub_filter") or "").strip() or "Todas"

    sub_lines = "\n".join(
        f"  {'🟢' if (liq or 0) >= 0 else '🔴'} {esc(str(sub))}  "
        f"({cnt} trades  |  {'+'if(liq or 0)>=0 else ''}${(liq or 0):.2f})"
        for sub, cnt, liq in sub_rows
    ) if sub_rows else "  <i>Sem trades no período</i>"

    send_support(
        m.chat.id,
        f"🎛️ <b>FILTROS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Subconta atual: <b>{esc(curr)}</b>\n\n"
        f"Subcontas disponíveis ({esc(u.get('periodo','24h'))}):\n"
        f"{sub_lines}\n\n"
        f"Escolha uma subconta ou <b>Todas</b>:",
        reply_markup=kb
    )


# ==============================================================================
# 🩺 SAÚDE
# ==============================================================================

def _health_score(uptime_h: float, lat_avg: float, cap_rate: float, rpc_errs: int):
    """Calcula Health Score 0-100 com 4 dimensões."""
    # Dimensão 1 — RPC Latência (25pts)
    if   lat_avg < 300:  s_lat = 25
    elif lat_avg < 500:  s_lat = 20
    elif lat_avg < 1000: s_lat = 15
    elif lat_avg < 1500: s_lat = 8
    else:                s_lat = 0

    # Dimensão 2 — Taxa de Captura (30pts)
    if   cap_rate >= 99.5: s_cap = 30
    elif cap_rate >= 99.0: s_cap = 25
    elif cap_rate >= 97.0: s_cap = 18
    elif cap_rate >= 95.0: s_cap = 10
    else:                  s_cap = 0

    # Dimensão 3 — Uptime (25pts)
    if   uptime_h >= 24: s_up = 25
    elif uptime_h >= 12: s_up = 22
    elif uptime_h >= 6:  s_up = 18
    elif uptime_h >= 1:  s_up = 12
    else:                s_up = 5

    # Dimensão 4 — Erros RPC (20pts)
    if   rpc_errs == 0:  s_err = 20
    elif rpc_errs <= 3:  s_err = 16
    elif rpc_errs <= 10: s_err = 10
    elif rpc_errs <= 20: s_err = 5
    else:                s_err = 0

    total = s_lat + s_cap + s_up + s_err
    return total, s_lat, s_cap, s_up, s_err


def _health_score_label(score: int) -> str:
    if score >= 90: return "Excelente 🟢"
    if score >= 75: return "Bom 🟢"
    if score >= 60: return "Regular 🟡"
    if score >= 40: return "Degradado 🟠"
    return "Crítico 🔴"


def _health_build_text():
    uptime_h     = (time.time() - HEALTH["started_at"]) / 3600.0
    last_ok      = HEALTH.get("last_fetch_ok_ts") or 0
    ago          = int(time.time() - last_ok) if last_ok else -1
    cd_until     = int(HEALTH.get("cooldown_until") or 0)
    cd_left      = max(0, cd_until - int(time.time()))
    lag          = f"{ago}s" if ago >= 0 else "-"
    sync_running = int(HEALTH.get("sync_running") or 0)
    sync_last    = str(HEALTH.get("sync_last") or "-")
    tg_last      = float(HEALTH.get("tg_last_ok_ts") or 0)
    tg_ago       = int(time.time() - tg_last) if tg_last else -1
    lat_ms       = float(HEALTH.get("rpc_latency_ms")  or 0)
    lat_avg      = float(HEALTH.get("rpc_latency_avg") or 0)
    rpc_errs     = int(HEALTH.get("rpc_errors_total")  or 0)
    blks_proc    = int(HEALTH.get("blocks_processed")  or 0)
    blks_skip    = int(HEALTH.get("blocks_skipped")    or 0)
    cap_rate     = float(HEALTH.get("capture_rate")    or 100.0)
    evts_lost    = int(HEALTH.get("events_lost_est")   or 0)

    score, s_lat, s_cap, s_up, s_err = _health_score(uptime_h, lat_avg, cap_rate, rpc_errs)
    score_label = _health_score_label(score)

    lines = [
        "🩺 <b>SAÚDE DO BOT — WEbdEX</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🏥 <b>Health Score: {score}/100</b> — {score_label}",
        f"   ├─ RPC Latência:  <b>{s_lat}/25</b>  (avg {lat_avg:.0f}ms)",
        f"   ├─ Captura:       <b>{s_cap}/30</b>  ({cap_rate:.1f}%)",
        f"   ├─ Uptime:        <b>{s_up}/25</b>  ({uptime_h:.1f}h)",
        f"   └─ Erros RPC:     <b>{s_err}/20</b>  ({rpc_errs} erros)",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🧱 Último bloco: <b>{HEALTH.get('last_block_seen', 0):,}</b>",
        f"📉 Lag: <b>{lag}</b> | TG OK: <b>{tg_ago}s</b>",
        f"📦 Blocos proc.: <b>{blks_proc:,}</b> | Pulados: <b>{blks_skip:,}</b>",
        f"⚠️ Eventos perdidos est.: <b>{evts_lost:,}</b>",
        "",
        "📊 <b>Capturas</b>",
        f"  📦 Trades: <b>{HEALTH.get('logs_trade', 0):,}</b>",
        f"  📦 Transfers: <b>{HEALTH.get('logs_transfer', 0):,}</b>",
        "",
        f"🔁 Vigia loops: <b>{HEALTH.get('vigia_loops', 0):,}</b>",
        f"⏳ Cooldown 429: <b>{cd_left}s</b>",
        f"🔄 Sync: <b>{'▶️ rodando' if sync_running == 1 else '✅ ocioso'}</b>",
        f"🧭 Último sync: {code(sync_last)}",
        f"⚠️ Último erro: {code(HEALTH.get('last_error', '') or '-')}",
    ]
    return "\n".join(lines)


def _health_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="health_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="health_close"),
    )
    return kb


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("health_"))
def _health_callback(c):
    bot.answer_callback_query(c.id)
    if c.data == "health_close":
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        return
    try:
        bot.edit_message_text(_health_build_text(), c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_health_kb())
    except Exception:
        pass


@bot.message_handler(func=lambda m: m.text == "🩺 Saúde")
def health(m):
    send_support(m.chat.id, _health_build_text(), reply_markup=_health_kb())


# ==============================================================================
# 🔎 WALLET INFO
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🔎 Wallet Info")
@require_auth
def wallet_info(m, u):
    import json as _jwi
    # Capital do worker (sem chamada on-chain que trava)
    cap_total = 0.0
    try:
        with DB_LOCK:
            _cc = cursor.execute(
                "SELECT total_usd, breakdown_json FROM capital_cache WHERE chat_id=? LIMIT 1",
                (m.chat.id,)
            ).fetchone()
        if _cc:
            _ct  = float(_cc[0] or 0)
            _bdj = _jwi.loads(_cc[1] or "{}")
            _bdj_sum = sum(float(v) for v in _bdj.values() if float(v or 0) > 0)
            cap_total = max(_ct, _bdj_sum)
    except Exception:
        pass

    # TokenPass (balanceOf é rápido — mantém)
    passes_str = "—"
    try:
        _w3g = web3_for_rpc(u.get("rpc") or "")
        c = get_contracts(u["env"], _w3g)
        raw_pass = c["pass"].functions.balanceOf(Web3.to_checksum_address(u["wallet"])).call()
        passes_str = f"{raw_pass / 10**9:.0f}"
    except Exception:
        pass

    sf       = (u.get("sub_filter") or "").strip() or "Todas"
    cap_line = (f"💰  Capital: <b>${cap_total:,.2f} USD</b>\n"
                if cap_total > 0 else "")

    msg = (
        f"💎 <b>WEbdEX V5.6 — DASHBOARD</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🧾  Ambiente:  <b>{esc(u['env'])}</b>\n"
        f"👛  Wallet:    {code(u['wallet'][:10] + '...' + u['wallet'][-6:])}\n"
        f"🎫  Passes:    <b>{passes_str}</b>\n"
        f"{cap_line}"
        f"\n"
        f"🗓️  Período:   <b>{esc(u['periodo'])}</b>\n"
        f"🎛️  Filtro Sub: <b>{esc(sf)}</b>\n"
        f"✅  Monitor:   <b>{'Ativo' if int(u.get('active', 1)) == 1 else 'Pausado'}</b>\n"
        f"⏰  Relatório: <b>21:00</b>\n"
        f"\n"
        f"<i>⚡ WEbdEX · New Digital Economy</i>"
    )
    send_support(m.chat.id, msg, reply_markup=main_kb())


# ==============================================================================
# 🧾 IDs com Saldo
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🧾 IDs com Saldo")
@require_auth
def ids_saldo(m, u):
    bot.send_chat_action(m.chat.id, "typing")
    try:
        w3_user = web3_for_rpc(u.get("rpc"))
        c = get_contracts(u["env"], w3_user)
        mgr = Web3.to_checksum_address(c["addr"]["MANAGER"])
        usr = Web3.to_checksum_address(u["wallet"])

        subs = c["sub"].functions.getSubAccounts(mgr, usr).call()
        msg = f"🧾 <b>SALDOS [{esc(u['env'])}]</b>\n\n"
        has = False

        for s in subs:
            time.sleep(0.15)
            sid = s[0]
            try:
                strats = c["sub"].functions.getStrategies(mgr, usr, sid).call()
            except Exception:
                continue

            line = []
            for st in strats:
                try:
                    bals = c["sub"].functions.getBalances(mgr, usr, sid, st).call()
                except Exception:
                    continue

                for b in bals:
                    addr_t = str(b[1]).lower()
                    if addr_t in TOKENS_MAP:
                        val = Decimal(b[0]) / Decimal(10 ** int(b[2]))
                        if val > Decimal("0.01"):
                            line.append(f"{val:.4f} {TOKENS_MAP[addr_t]['sym']}")

            if line:
                msg += f"• {code(sid)}: " + " | ".join(line) + "\n"
                has = True

        if not has:
            msg += "(Sem saldo)"
        send_support(m.chat.id, msg, reply_markup=main_kb())

    except Exception as e:
        send_support(m.chat.id, f"Erro: {code(e)}", reply_markup=main_kb())


# ==============================================================================
# 📌 Helpers (Dashboard PRO)
# ==============================================================================
def _profit_factor(gains: float, losses_abs: float) -> float:
    """Profit Factor = total_gains / total_losses_abs. Se não houver perdas, retorna ∞."""
    try:
        g = float(gains or 0.0)
        l = float(losses_abs or 0.0)
        if l <= 0:
            return float("inf") if g > 0 else 0.0
        return g / l
    except Exception:
        return 0.0


def _streaks(net_series):
    """Retorna (maior sequência de wins, maior sequência de losses) a partir de uma série de nets."""
    best_w = best_l = 0
    cur_w = cur_l = 0
    for x in net_series or []:
        try:
            v = float(x)
        except Exception:
            v = 0.0
        if v > 0:
            cur_w += 1
            cur_l = 0
        elif v < 0:
            cur_l += 1
            cur_w = 0
        else:
            cur_w = 0
            cur_l = 0
        best_w = max(best_w, cur_w)
        best_l = max(best_l, cur_l)
    return best_w, best_l


def _fmt_inf(v: float) -> str:
    try:
        if v == float("inf"):
            return "∞"
        return f"{float(v):.2f}"
    except Exception:
        return "-"


def _sqn_label(sqn: float) -> str:
    """Sistema de Qualidade de Van Tharp."""
    if sqn >= 5.0:  return "Excepcional 🌟"
    if sqn >= 3.0:  return "Excelente 🟢"
    if sqn >= 2.5:  return "Bom 🟢"
    if sqn >= 2.0:  return "Médio 🟡"
    if sqn >= 1.6:  return "Abaixo da média 🟡"
    return "Fraco 🔴"


def _sharpe_icon(sharpe: float) -> str:
    if sharpe >= 1.5: return "🟢"
    if sharpe >= 0.5: return "🟡"
    return "🔴"


def _sortino_icon(sortino: float) -> str:
    if sortino >= 2.0: return "🟢"
    if sortino >= 1.0: return "🟡"
    return "🔴"


def _max_drawdown(equity: List[float]) -> float:
    if not equity:
        return 0.0
    peak = equity[0]
    mdd = 0.0
    for x in equity:
        if x > peak:
            peak = x
        dd = peak - x
        if dd > mdd:
            mdd = dd
    return float(mdd)


def _query_trades(wallet: str, hours: int, sub_filter: str = "") -> List[Tuple[Any, ...]]:
    """
    Preferência: block_ts (auditável). Fallback: data_hora.
    Retorna: (ts, data_hora, sub_conta, valor, gas_usd)
    """
    dt = (now_br() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    st = int(time.time()) - int(hours) * 3600

    sf = (sub_filter or "").strip()
    sf_clause = ""
    params: List[Any] = [wallet.lower(), st, dt]
    if sf:
        sf_clause = " AND o.sub_conta=? "
        params.append(sf)

    with DB_LOCK:
        rows = cursor.execute(f"""
            SELECT
              COALESCE(obt.block_ts, 0) as ts,
              o.data_hora,
              o.sub_conta,
              o.valor,
              o.gas_usd
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            LEFT JOIN op_blocktime obt ON obt.hash=o.hash AND obt.log_index=o.log_index
            WHERE o.tipo='Trade' AND ow.wallet=?
              AND (
                   (COALESCE(obt.block_ts, 0) >= ?)
                   OR (COALESCE(obt.block_ts, 0)=0 AND o.data_hora >= ?)
              )
              {sf_clause}
            ORDER BY ts ASC, o.data_hora ASC
        """, tuple(params)).fetchall()
    return rows


# ==============================================================================
# 📈 DASHBOARD PRO (V5.6)
# ==============================================================================

def _dashboard_build_text(u):
    """Retorna (texto, nets) ou (None, None) se sem dados."""
    hours = period_to_hours(u.get("periodo") or "24h")
    dt = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    extra_sql, extra_params = get_user_filter_clause(u)

    with DB_LOCK:
        cursor.execute(f"""
            SELECT o.data_hora, o.sub_conta, o.valor, o.gas_usd
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=? {extra_sql}
            ORDER BY o.data_hora ASC
        """, (dt, u["wallet"], *extra_params))
        rows = cursor.fetchall()

    if not rows:
        return None, None

    nets = []
    gross_pos = 0.0
    gross_neg = 0.0
    gas_total = 0.0

    for dh, sub, v, g in rows:
        v = float(v or 0.0)
        g = float(g or 0.0)
        net = v - g
        nets.append((str(dh), str(sub), float(net), float(g)))
        gas_total += g
        if v > 0:
            gross_pos += v
        if v < 0:
            gross_neg += v

    equity = []
    acc = 0.0
    gains = 0.0
    losses_abs = 0.0
    net_series = []

    for dh, sub, net, g in nets:
        acc += net
        equity.append(acc)
        net_series.append(net)
        if net > 0:
            gains += net
        elif net < 0:
            losses_abs += abs(net)

    liq = equity[-1] if equity else 0.0
    mdd = _max_drawdown(equity)

    wins = sum(1 for x in net_series if x > 0)
    total = len(net_series)
    winrate = (wins / total) * 100 if total else 0.0
    expectancy = (sum(net_series) / total) if total else 0.0
    pf = _profit_factor(gains, losses_abs)
    best_w, best_l = _streaks(net_series)

    # Métricas quantitativas avançadas
    std_net      = _stdev(net_series) if total >= 2 else 0.0
    sharpe       = expectancy / std_net if std_net > 0 else 0.0
    sqn          = math.sqrt(total) * sharpe if total >= 5 else 0.0
    recovery     = liq / mdd if mdd > 0 else float("inf")

    # Sortino: usa apenas desvio padrão do downside (só penaliza perdas)
    downside_returns = [x for x in net_series if x < 0]
    downside_dev     = _stdev(downside_returns) if len(downside_returns) >= 2 else 0.0
    sortino          = expectancy / downside_dev if downside_dev > 0 else 0.0

    # VaR 95% — perda máxima esperada em 95% dos trades
    sorted_nets = sorted(net_series)
    var_idx     = max(0, int(len(sorted_nets) * 0.05) - 1)
    var_95      = sorted_nets[var_idx] if sorted_nets else 0.0

    top_gas = sorted(nets, key=lambda x: x[3], reverse=True)[:2]
    worst_net = sorted(nets, key=lambda x: x[2])[:2]

    def _hhmm(dh: str) -> str:
        try:
            s = str(dh)
            return s[11:16] if len(s) >= 16 else s
        except Exception:
            return "-"

    sf = (u.get("sub_filter") or "").strip() or "Todas"
    per = (u.get("periodo") or "24h")

    out = []
    out.append("📈 <b>DASHBOARD PRO — WEbdEX</b>")
    out.append(f"🗓️ <b>Período:</b> {esc(per)}")
    out.append(f"🎛️ <b>Filtro:</b> {esc(sf)}")
    out.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    out.append(f"🏅 <b>LÍQUIDO TOTAL:</b> <b>{liq:+.4f} USD</b>")
    out.append(f"💵 <b>Bruto (+):</b> <b>{gross_pos:+.4f} USD</b>")
    out.append(f"📉 <b>Bruto (−):</b> <b>{gross_neg:.4f} USD</b>")
    out.append(f"⛽ <b>Gás total:</b> <b>-{gas_total:.4f} USD</b>")
    out.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    out.append(f"🏆 <b>WinRate:</b> <b>{winrate:.1f}%</b>")
    out.append(f"📊 <b>Trades:</b> <b>{total}</b>")
    out.append(f"📐 <b>Expectancy:</b> <b>{expectancy:+.4f} USD / trade</b>")
    out.append(f"📉 <b>Max Drawdown:</b> <b>-{mdd:.4f} USD</b>")
    out.append(f"📈 <b>Profit Factor:</b> <b>{_fmt_inf(pf)}</b>")
    out.append(f"🔥 <b>Streaks:</b> W <b>{best_w}</b> | L <b>{best_l}</b>")
    out.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if total >= 5:
        rec_str = "♾️" if recovery == float("inf") else f"{recovery:.1f}x"
        out.append("📊 <b>ANÁLISE QUANTITATIVA</b>")
        out.append(f"🎯 <b>Sharpe Ratio:</b>    <b>{sharpe:.2f}</b> {_sharpe_icon(sharpe)}")
        out.append(f"📐 <b>Sortino Ratio:</b>   <b>{sortino:.2f}</b> {_sortino_icon(sortino)}")
        out.append(f"📉 <b>VaR 95%:</b>         <b>{var_95:+.4f} USD</b>")
        out.append(f"♻️ <b>Recovery Factor:</b>  <b>{rec_str}</b>")
        out.append(f"🔬 <b>SQN:</b>              <b>{sqn:.1f}</b> — {_sqn_label(sqn)}")
        out.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    out.append("🧯 <b>Outliers (eventos fora do padrão)</b>")
    out.append("⛽ <b>Maiores custos de gás:</b>")
    for dh, sub, net, g in top_gas:
        out.append(f"• {esc(sub)} — gás <b>${g:.2f}</b> | net <b>{net:+.2f}</b> | {_hhmm(dh)}")
    out.append("🔻 <b>Piores resultados líquidos:</b>")
    for dh, sub, net, g in worst_net:
        out.append(f"• {esc(sub)} — <b>{net:+.2f} USD</b> | gás <b>${g:.2f}</b> | {_hhmm(dh)}")
    out.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    out.append("🧱 <b>Network:</b> Polygon")
    out.append("🧠 <b>Análise automática WEbdEX</b>")

    return "\n".join(out), nets


def _dashboard_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="dash_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="dash_close"),
    )
    return kb


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("dash_"))
def _dashboard_callback(c):
    bot.answer_callback_query(c.id)
    if c.data == "dash_close":
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        return
    u = get_user(c.from_user.id) or {}
    if not u.get("wallet"):
        return
    txt, _ = _dashboard_build_text(u)
    if txt is None:
        txt = "⚠️ Sem dados para o Dashboard PRO (com o filtro atual)."
    try:
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_dashboard_kb())
    except Exception:
        pass


@bot.message_handler(func=lambda m: (m.text or "").strip() and "Dashboard PRO" in (m.text or ""))
@require_auth
def dashboard(m, u):
    bot.send_chat_action(m.chat.id, "typing")

    txt, nets = _dashboard_build_text(u)
    if txt is None:
        return send_support(m.chat.id, "⚠️ Sem dados para o Dashboard PRO (com o filtro atual).", reply_markup=main_kb())

    send_support(m.chat.id, txt, reply_markup=_dashboard_kb())

    # Envia gráficos informativos (Equity / Gás / Distribuição)
    sf  = (u.get("sub_filter") or "").strip() or "Todas"
    per = (u.get("periodo") or "24h")
    try:
        if nets and len(nets) >= 5:
            _dash_send_graphs(m.chat.id, u, sf, per, nets)
    except Exception as _e:
        logger.debug("[dashboard] graph send failed: %s", _e)


# ==============================================================================
# 📌 Ciclo 21h (com filtro)
# ==============================================================================

def _painel_build_text(u):
    """Retorna texto do Ciclo 21h ou None se sem dados."""
    since = _ciclo_21h_since()
    label = _ciclo_21h_label()
    extra_sql, extra_params = get_user_filter_clause(u)

    with DB_LOCK:
        cursor.execute(f"""
            SELECT o.valor, o.gas_usd, o.sub_conta
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=? {extra_sql}
        """, (since, u["wallet"], *extra_params))
        rows = cursor.fetchall()

    if not rows:
        return None

    bruto = sum(float(r[0]) for r in rows)
    gas   = sum(float(r[1] or 0.0) for r in rows)
    liq   = bruto - gas
    wins  = sum(1 for r in rows if float(r[0]) > 0)
    total = len(rows)
    wr    = wins / total * 100 if total else 0.0
    subs  = len(set(r[2] for r in rows))
    bar   = barra_progresso(wins, total)

    icon = "🟢" if liq >= 0 else "🔴"
    lines = [
        "📌 <b>CICLO 21H — WEbdEX</b>",
        f"🕘 <i>{label}</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 Trades:     <b>{total:,}</b> | Subs: <b>{subs}</b>",
        f"💰 Bruto:      <b>{bruto:+.4f} USD</b>",
        f"⛽ Gás:        <b>{gas:.4f} USD</b>",
        f"{icon} Líquido:    <b>{liq:+.4f} USD</b>",
        "",
        f"🎯 WinRate:    <b>{wr:.1f}%</b>",
        bar,
        f"✅ Wins: <b>{wins}</b> | ❌ Losses: <b>{total - wins}</b>",
    ]
    return "\n".join(lines)


def _painel_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="painel_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="painel_close"),
    )
    return kb


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("painel_"))
def _painel_callback(c):
    bot.answer_callback_query(c.id)
    if c.data == "painel_close":
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        return
    u = get_user(c.from_user.id) or {}
    if not u.get("wallet"):
        return
    since = _ciclo_21h_since()
    txt = _painel_build_text(u) or f"⚠️ Sem dados no ciclo atual.\n🕘 Desde: <b>{since[11:16]} BRT</b>"
    try:
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_painel_kb())
    except Exception:
        pass


@bot.message_handler(func=lambda m: m.text == "📌 Ciclo 21h")
@require_auth
def painel(m, u):
    """Painel do Ciclo 21h — desde as 21:00 BRT de ontem até agora."""
    since = _ciclo_21h_since()
    txt = _painel_build_text(u)
    if txt is None:
        return send_support(m.chat.id,
            f"⚠️ Sem dados no ciclo atual.\n🕘 Desde: <b>{since[11:16]} BRT</b>",
            reply_markup=main_kb())
    send_support(m.chat.id, txt, reply_markup=_painel_kb())


# ==============================================================================
# 📊 Consolidado (24h) — com filtro
# ==============================================================================

def _consolidado_build_text(u):
    """Retorna texto do Consolidado 24h ou None se sem dados."""
    dt = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    extra_sql, extra_params = get_user_filter_clause(u)

    with DB_LOCK:
        cursor.execute(f"""
            SELECT o.valor, o.gas_usd
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=? {extra_sql}
        """, (dt, u["wallet"], *extra_params))
        rows = cursor.fetchall()

    if not rows:
        return None

    faturamento = sum(float(v) for (v, g) in rows if float(v) > 0)
    custos      = sum(float(v) for (v, g) in rows if float(v) < 0)
    gas         = sum(float(g or 0.0) for (v, g) in rows)
    liquido     = faturamento + custos - gas

    wins    = sum(1 for (v, g) in rows if float(v) > 0)
    total   = len(rows)
    winrate = (wins / total) * 100 if total else 0.0
    bar     = barra_progresso(wins, total)

    sf = (u.get("sub_filter") or "").strip() or "Todas"

    lines = [
        "📊 <b>CONSOLIDADO (24h) — WEbdEX</b>",
        f"🎛️ Filtro: <b>{esc(sf)}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"💵 Faturamento: <b>{faturamento:+.6f}</b>",
        f"📉 Custos: <b>{custos:+.6f}</b>",
        f"⛽ Gás: <b>-{gas:.6f}</b>",
        f"🏅 <b>LÍQUIDO: {liquido:+.6f} USD</b>",
        "",
        bar,
        f"🏆 WinRate: <b>{winrate:.1f}%</b>  | trades: <b>{total}</b>",
    ]
    return "\n".join(lines)


def _consolidado_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="consol_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="consol_close"),
    )
    return kb


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("consol_"))
def _consolidado_callback(c):
    bot.answer_callback_query(c.id)
    if c.data == "consol_close":
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        return
    u = get_user(c.from_user.id) or {}
    if not u.get("wallet"):
        return
    txt = _consolidado_build_text(u) or "⚠️ Sem dados nas últimas 24h (com o filtro atual)."
    try:
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_consolidado_kb())
    except Exception:
        pass


@bot.message_handler(func=lambda m: m.text == "📊 Consolidado (24h)")
@require_auth
def consolidado_24h(m, u):
    txt = _consolidado_build_text(u)
    if txt is None:
        return send_support(m.chat.id, "⚠️ Sem dados nas últimas 24h (com o filtro atual).", reply_markup=main_kb())
    send_support(m.chat.id, txt, reply_markup=_consolidado_kb())


# ==============================================================================
# 🏆 Ranking Lucro (por sub_conta)
# ==============================================================================

def _ranking_lucro_build_text(u):
    """Retorna texto do Ranking Lucro ou None se sem dados."""
    periodo = u.get("periodo") or "ciclo"
    dt      = _period_since(periodo)
    lbl     = _period_label(periodo)
    extra_sql, extra_params = get_user_filter_clause(u)

    with DB_LOCK:
        cursor.execute(f"""
            SELECT o.sub_conta, SUM(o.valor) as s_val, SUM(o.gas_usd) as s_gas, COUNT(*)
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=? {extra_sql}
            GROUP BY o.sub_conta
        """, (dt, u["wallet"], *extra_params))
        rows = cursor.fetchall()

    if not rows:
        return None

    rank = []
    for sub, s_val, s_gas, cnt in rows:
        s_val = float(s_val or 0.0)
        s_gas = float(s_gas or 0.0)
        liq = s_val - s_gas
        rank.append((liq, str(sub), int(cnt)))

    rank.sort(key=lambda x: x[0], reverse=True)
    top = rank[:15]

    sf   = (u.get("sub_filter") or "").strip() or "Todas"
    lines = [
        "🏆 <b>RANKING LUCRO — WEbdEX</b>",
        f"🗓️ <i>{esc(lbl)}</i>",
        f"🎛️ Filtro: <b>{esc(sf)}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for i, (liq, sub, cnt) in enumerate(top, start=1):
        med = _medal(i)
        dot = "🟢" if liq >= 0 else "🔴"
        lines.append(f"{med or f'{i:02d})'} {dot} {code(sub)} — <b>${liq:+.4f}</b> | trades {cnt}")

    return "\n".join(lines)


def _ranking_lucro_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="rnklucro_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="rnklucro_close"),
    )
    return kb


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("rnklucro_"))
def _ranking_lucro_callback(c):
    bot.answer_callback_query(c.id)
    if c.data == "rnklucro_close":
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        return
    u = get_user(c.from_user.id) or {}
    if not u.get("wallet"):
        return
    periodo = u.get("periodo") or "ciclo"
    lbl     = _period_label(periodo)
    txt = _ranking_lucro_build_text(u) or f"⚠️ Sem trades para ranquear.\n🗓️ Período: <b>{esc(lbl)}</b>"
    try:
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_ranking_lucro_kb())
    except Exception:
        pass


@bot.message_handler(func=lambda m: m.text == "🏆 Ranking Lucro")
@require_auth
def ranking_lucro(m, u):
    txt = _ranking_lucro_build_text(u)
    if txt is None:
        periodo = u.get("periodo") or "ciclo"
        lbl     = _period_label(periodo)
        return send_support(m.chat.id,
            f"⚠️ Sem trades para ranquear.\n🗓️ Período: <b>{esc(lbl)}</b>",
            reply_markup=main_kb())
    send_support(m.chat.id, txt, reply_markup=_ranking_lucro_kb())


# ==============================================================================
# 🧬 Ciclo da Subconta
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🧬 Ciclo da Subconta")
@require_auth
def ciclo_subconta(m, u):
    hours = period_to_hours(u.get("periodo") or "24h")
    sf = (u.get("sub_filter") or "").strip()

    data = load_trade_times_by_sub(u["wallet"], hours, only_sub=sf)
    if not data:
        return send_support(m.chat.id, "⚠️ Sem trades no período para calcular ciclo (com o filtro atual).", reply_markup=main_kb())

    now = datetime.now()
    lines = [f"🧬 <b>CICLO DA SUBCONTA</b> ({esc(u['periodo'])})"]
    lines.append(f"🎛️ Filtro: <b>{esc(sf) if sf else 'Todas'}</b>")
    lines.append("")

    all_gaps: List[float] = []
    for sub, times in data.items():
        st = ciclo_stats(times)
        all_gaps.extend(st["gaps"])
    all_gaps_sorted = sorted(all_gaps)
    if all_gaps_sorted:
        g_med = float(median(all_gaps_sorted))
        g_p95 = float(_percentile(all_gaps_sorted, 95))
        g_sd = _std(all_gaps_sorted)
        g_score = consist_score(g_med, g_p95)
        lines.append(f"📊 Geral: med <b>{g_med:.1f}m</b> | P95 <b>{g_p95:.1f}m</b> | σ <b>{g_sd:.1f}m</b> | consist <b>{g_score:.0f}</b>/100")
        lines.append("")

    for sub, times in list(data.items())[:25]:
        st = ciclo_stats(times)
        last_trade = st["last_trade"]
        since_last = (now - last_trade).total_seconds()/60.0 if last_trade else 0.0
        score = consist_score(st["med"], st["p95"]) if st["n_gaps"] >= 5 else 0.0

        last_gaps = st["gaps"][-5:] if st["gaps"] else []
        last_gaps_txt = ", ".join(f"{x:.0f}m" for x in last_gaps) if last_gaps else "—"

        lines.append(
            f"• {code(sub)} | gaps <b>{st['n_gaps']}</b> | med <b>{st['med']:.1f}m</b> | "
            f"P95 <b>{st['p95']:.1f}m</b> | σ <b>{st['sd']:.1f}m</b> | "
            f"consist <b>{score:.0f}</b>/100 | ⏳ desde último <b>{since_last:.0f}m</b>"
        )
        lines.append(f"   últimos gaps: {code(last_gaps_txt)}")

    send_support(m.chat.id, "\n".join(lines), reply_markup=main_kb())

    # IA interpreta o padrão de ciclo (async — não bloqueia)
    if all_gaps_sorted and len(all_gaps_sorted) >= 5:
        _g_med_c   = g_med if all_gaps_sorted else 0
        _g_p95_c   = g_p95 if all_gaps_sorted else 0
        _g_sd_c    = g_sd  if all_gaps_sorted else 0
        _g_score_c = g_score if all_gaps_sorted else 0
        _wallet_c  = u.get("wallet", "")
        def _ai_ciclo_task():
            try:
                from webdex_ai import _ai_interpret_cycle
                interp = _ai_interpret_cycle(_g_med_c, _g_p95_c, _g_sd_c, _g_score_c, _wallet_c)
                if interp:
                    send_html(m.chat.id,
                        f"┈┈┈┈┈┈ IA ┈┈┈┈┈┈\n\n🤖 {interp}")
            except Exception:
                pass
        threading.Thread(target=_ai_ciclo_task, daemon=True).start()


# ==============================================================================
# 🏅 RANKING HELPERS — medals, barra, inline period kb
# ==============================================================================
def _medal(pos: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"{pos:02d} ")

def _barra_score(score: float) -> str:
    """Barra visual de 10 blocos para score 0-100."""
    blocos = max(0, min(10, int(round(score / 10))))
    return "█" * blocos + "░" * (10 - blocos)

_RANK_PERIODS = [("24h", "24h"), ("7d", "7d"), ("30d", "30d"), ("ciclo", "Ciclo")]

def _ranking_consist_text(wallet: str, periodo: str) -> str:
    hours = period_to_hours(periodo)
    data  = load_trade_times_by_sub(wallet, hours)
    rows  = []
    for sub, times in data.items():
        st = ciclo_stats(times)
        if st["n_gaps"] < 5:
            continue
        sc = consist_score(st["med"], st["p95"])
        rows.append((sc, st["med"], st["p95"], st["n_gaps"], str(sub)))
    if not rows:
        return None
    rows.sort(key=lambda x: x[0], reverse=True)
    top = rows[:20]
    lines = [
        "🧠 <b>RANKING CONSISTÊNCIA</b>",
        f"🗓️ <i>Período: {esc(periodo)}  ·  {len(rows)} subcontas</i>",
        "<i>Score: quanto maior, mais regular o ciclo</i>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for i, (sc, medg, p95g, ng, sub) in enumerate(top, start=1):
        barra = _barra_score(sc)
        lines.append(f"{_medal(i)}  {code(sub)}")
        lines.append(f"    {barra}  <b>{sc:.0f}</b>/100")
        lines.append(f"    ⏱ med <b>{medg:.1f}m</b>  ·  P95 <b>{p95g:.1f}m</b>  ·  {ng} gaps")
        lines.append("")
    return "\n".join(lines).rstrip()

def _ranking_ciclo_text(wallet: str, periodo: str) -> str:
    hours = period_to_hours(periodo)
    data  = load_trade_times_by_sub(wallet, hours)
    rows  = []
    for sub, times in data.items():
        st = ciclo_stats(times)
        if st["n_gaps"] < 3:
            continue
        rows.append((st["med"], st["p95"], st["n_gaps"], st["sd"], str(sub)))
    if not rows:
        return None
    rows.sort(key=lambda x: x[0])  # menor ciclo = mais rápido = melhor
    top = rows[:20]
    # normalizar para barra: menor med = score 100, maior med = score 0
    meds  = [r[0] for r in top]
    lo, hi = min(meds), max(meds)
    def _norm(v):
        if hi == lo: return 100.0
        return 100.0 - ((v - lo) / (hi - lo) * 100.0)
    lines = [
        "⏱️ <b>RANKING CICLO</b>",
        f"🗓️ <i>Período: {esc(periodo)}  ·  {len(rows)} subcontas</i>",
        "<i>Menor mediana de gap = ciclo mais rápido</i>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for i, (medg, p95g, ng, sd, sub) in enumerate(top, start=1):
        barra = _barra_score(_norm(medg))
        lines.append(f"{_medal(i)}  {code(sub)}")
        lines.append(f"    {barra}")
        lines.append(f"    ⏱ med <b>{medg:.1f}m</b>  ·  P95 <b>{p95g:.1f}m</b>  ·  σ <b>{sd:.1f}m</b>  ·  {ng} gaps")
        lines.append("")
    return "\n".join(lines).rstrip()

def _ranking_period_kb(tipo: str, active: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    row = []
    for val, label in _RANK_PERIODS:
        txt = f"✅ {label}" if val == active else label
        row.append(types.InlineKeyboardButton(txt, callback_data=f"rk:{tipo}:{val}"))
    kb.row(*row)
    return kb


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("rk:"))
def _ranking_cb(c):
    bot.answer_callback_query(c.id)
    try:
        _, tipo, periodo = c.data.split(":")
    except Exception:
        return
    u = get_user(c.from_user.id) or {}
    wallet = u.get("wallet") or ""
    if not wallet:
        return
    if tipo == "consist":
        txt = _ranking_consist_text(wallet, periodo) or f"⚠️ Poucos dados ({periodo})."
        kb  = _ranking_period_kb("consist", periodo)
    elif tipo == "ciclo":
        txt = _ranking_ciclo_text(wallet, periodo) or f"⚠️ Poucos dados ({periodo})."
        kb  = _ranking_period_kb("ciclo", periodo)
    else:
        return
    try:
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass


# ==============================================================================
# 🧠 Ranking Consistência
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🧠 Ranking Consistência")
@require_auth
def ranking_consistencia(m, u):
    bot.send_chat_action(m.chat.id, "typing")
    periodo = u.get("periodo") or "24h"
    txt = _ranking_consist_text(u["wallet"], periodo)
    if not txt:
        return send_support(m.chat.id,
            "⚠️ Poucos dados para ranking (precisa ≥ 5 gaps por subconta).",
            reply_markup=main_kb())
    try:
        bot.send_message(m.chat.id, txt, parse_mode="HTML",
                         reply_markup=_ranking_period_kb("consist", periodo))
    except Exception as e:
        logger.warning("[ranking_consist] send error: %s", e)
        send_html(m.chat.id, txt)


# ==============================================================================
# ⏱️ Ranking Ciclo
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "⏱️ Ranking Ciclo")
@require_auth
def ranking_ciclo(m, u):
    bot.send_chat_action(m.chat.id, "typing")
    periodo = u.get("periodo") or "24h"
    txt = _ranking_ciclo_text(u["wallet"], periodo)
    if not txt:
        return send_support(m.chat.id,
            "⚠️ Poucos dados para ranking (precisa ≥ 3 gaps por subconta).",
            reply_markup=main_kb())
    try:
        bot.send_message(m.chat.id, txt, parse_mode="HTML",
                         reply_markup=_ranking_period_kb("ciclo", periodo))
    except Exception as e:
        logger.warning("[ranking_ciclo] send error: %s", e)
        send_html(m.chat.id, txt)


# ==============================================================================
# 📜 Ops / Auditoria / Alertas / Status / Config
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🔬 Análise")
@require_auth
def analise_temporal(m, u):
    bot.send_chat_action(m.chat.id, "typing")
    wallet = (u.get("wallet") or "").lower().strip()
    if not wallet:
        return send_support(m.chat.id, "⚠️ Configure sua wallet primeiro.", reply_markup=main_kb())
    hours = period_to_hours(u.get("periodo") or "24h")
    dt = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with DB_LOCK:
            rows = cursor.execute("""
                SELECT strftime('%H', o.data_hora) as hr,
                       COUNT(*) as cnt,
                       SUM(o.valor) as s_val,
                       SUM(o.gas_usd) as s_gas
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=?
                GROUP BY hr ORDER BY hr
            """, (dt, wallet)).fetchall()
        if not rows:
            return send_support(m.chat.id, "⚠️ Sem trades no período para análise.", reply_markup=main_kb())

        # Hora mais ativa e mais lucrativa
        best_cnt  = max(rows, key=lambda r: int(r[1] or 0))
        best_liq  = max(rows, key=lambda r: float(r[2] or 0.0) - float(r[3] or 0.0))

        # Dia da semana
        with DB_LOCK:
            dow_rows = cursor.execute("""
                SELECT strftime('%w', o.data_hora) as dw,
                       COUNT(*) as cnt,
                       SUM(o.valor - o.gas_usd) as net
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=?
                GROUP BY dw ORDER BY net DESC
            """, (dt, wallet)).fetchall()
        days_map = {"0":"Dom","1":"Seg","2":"Ter","3":"Qua","4":"Qui","5":"Sex","6":"Sáb"}
        best_day = days_map.get(str(dow_rows[0][0]), "?") if dow_rows else "?"
        best_day_net = float(dow_rows[0][2] or 0.0) if dow_rows else 0.0

        lbl = _period_label(u.get("periodo") or "24h")
        lines = [
            f"🔬 <b>ANÁLISE TEMPORAL — WEbdEX</b>",
            f"🗓️ <i>{esc(lbl)}</i>",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"",
            f"⏰ <b>Hora mais ativa:</b> {best_cnt[0]}h ({best_cnt[1]} trades)",
            f"💰 <b>Hora mais lucrativa:</b> {best_liq[0]}h (${float(best_liq[2] or 0.0)-float(best_liq[3] or 0.0):+.2f})",
            f"📅 <b>Melhor dia:</b> {best_day} (${best_day_net:+.2f})",
            f"",
            f"📊 <b>Trades por hora:</b>",
        ]
        for hr, cnt, s_val, s_gas in rows:
            net = float(s_val or 0.0) - float(s_gas or 0.0)
            dot = "🟢" if net >= 0 else "🔴"
            bar = "█" * min(10, int(cnt))
            lines.append(f"  {hr}h {dot} <code>{bar}</code> {cnt}t ${net:+.2f}")
        lines += ["", "━━━━━━━━━━━━━━━━━━━━"]
        send_support(m.chat.id, "\n".join(lines), reply_markup=main_kb())
    except Exception as e:
        logger.warning("[analise_temporal] %s", e)
        send_support(m.chat.id, "⚠️ Erro ao gerar análise.", reply_markup=main_kb())


def _ops_build_text():
    with DB_LOCK:
        cursor.execute("SELECT data_hora, tipo, sub_conta, valor, token, bloco FROM operacoes ORDER BY bloco DESC LIMIT 12")
        r = cursor.fetchall()
    lines = ["📜 <b>ÚLTIMAS OPS (Global) — WEbdEX</b>", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for dh, tp, sub, val, tk, bl in r:
        lines.append(f"• {esc(tp)} | {code(sub)} | <b>{float(val):+.4f}</b> {esc(tk)} | bloco {code(bl)}")
    return "\n".join(lines)


def _ops_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="ops_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="ops_close"),
    )
    return kb


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("ops_"))
def _ops_callback(c):
    bot.answer_callback_query(c.id)
    if c.data == "ops_close":
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        return
    try:
        bot.edit_message_text(_ops_build_text(), c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_ops_kb())
    except Exception as e:
        logger.warning("[ops_callback] %s", e)


@bot.message_handler(func=lambda m: m.text == "📜 Ops")
def ops(m):
    bot.send_chat_action(m.chat.id, "typing")
    try:
        send_support(m.chat.id, _ops_build_text(), reply_markup=_ops_kb())
    except Exception as e:
        logger.warning("[ops] %s", e)
        send_support(m.chat.id, "⚠️ Erro ao buscar ops.", reply_markup=main_kb())


def _audit_build_text():
    with DB_LOCK:
        cursor.execute("""
            SELECT gas_usd, valor, sub_conta
            FROM operacoes
            WHERE tipo='Trade'
            ORDER BY data_hora DESC LIMIT 100
        """)
        d = cursor.fetchall()
    if not d:
        return None

    tg      = sum(float(x[0] or 0.0) for x in d)
    lb      = sum(float(x[1] or 0.0) for x in d if float(x[1] or 0.0) > 0)
    net_tot = sum(float(x[1] or 0.0) - float(x[0] or 0.0) for x in d)
    cnt     = len(d)
    ef      = (lb / tg) if tg > 0 else 0.0
    gtrade  = tg / cnt if cnt > 0 else 0.0
    gas_pct = (tg / lb * 100) if lb > 0 else 0.0
    gp_icon = "🟢" if gas_pct < 15 else ("🟡" if gas_pct < 30 else "🔴")

    # Agrupamento por subconta
    subs: dict = {}
    for gas, val, sub in d:
        gas = float(gas or 0.0)
        val = float(val or 0.0)
        sub = str(sub or "-")
        if sub not in subs:
            subs[sub] = {"gas": 0.0, "cnt": 0, "net": 0.0}
        subs[sub]["gas"] += gas
        subs[sub]["cnt"] += 1
        subs[sub]["net"] += val - gas

    sub_eff = [
        (s, v["gas"] / v["cnt"], v["net"])
        for s, v in subs.items() if v["cnt"] >= 3
    ]
    sub_eff.sort(key=lambda x: x[1])  # menor gas/trade = mais eficiente

    lines = [
        "⛽ <b>AUDITORIA GÁS — WEbdEX</b>",
        "<i>Últimas 100 operações</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"💸 Gás total:    <b>${tg:.2f}</b>",
        f"💵 Lucro bruto:  <b>${lb:.2f}</b>",
        f"🏅 Líquido:      <b>${net_tot:+.2f}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"💡 Eficiência:   1 Gás = <b>${ef:.2f}</b> Lucro",
        f"📊 Gas/Trade:    <b>${gtrade:.3f}</b> por op.",
        f"{gp_icon} Gas % PnL:    <b>{gas_pct:.1f}%</b>",
    ]

    if sub_eff:
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🏆 <b>Ranking Eficiência (≥3 trades)</b>")
        for i, (sub, gpt, net_sub) in enumerate(sub_eff[:3], start=1):
            medal = ("🥇", "🥈", "🥉")[i - 1]
            lines.append(f"{medal} {esc(sub)} — <b>${gpt:.3f}</b>/trade | net <b>${net_sub:+.2f}</b>")
        if len(sub_eff) > 3:
            worst = sub_eff[-1]
            lines.append(f"🔴 Menos efic.: {esc(worst[0])} — <b>${worst[1]:.3f}</b>/trade")

    return "\n".join(lines)


def _audit_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="audit_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="audit_close"),
    )
    return kb


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("audit_"))
def _audit_callback(c):
    bot.answer_callback_query(c.id)
    if c.data == "audit_close":
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        return
    try:
        txt = _audit_build_text() or "⚠️ Sem dados."
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_audit_kb())
    except Exception as e:
        logger.warning("[audit_callback] %s", e)


@bot.message_handler(func=lambda m: m.text == "⛽ Auditoria Gás")
def audit(m):
    bot.send_chat_action(m.chat.id, "typing")
    try:
        txt = _audit_build_text()
        if txt is None:
            return send_support(m.chat.id, "⚠️ Sem dados.", reply_markup=main_kb())
        send_support(m.chat.id, txt, reply_markup=_audit_kb())
    except Exception as e:
        logger.warning("[audit] %s", e)
        send_support(m.chat.id, "⚠️ Erro na auditoria.", reply_markup=main_kb())


def _alerts_build_text(u):
    """Detecção de degradação + status da rede."""
    wallet = u.get("wallet") or ""
    extra_sql, extra_params = get_user_filter_clause(u)

    dt_7d  = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    dt_30d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    def _stats(since):
        with DB_LOCK:
            cursor.execute(f"""
                SELECT o.valor, o.gas_usd
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=? {extra_sql}
            """, (since, wallet, *extra_params))
            rows = cursor.fetchall()
        if not rows:
            return None
        total = len(rows)
        wins  = sum(1 for v, g in rows if float(v or 0) > 0)
        gas   = sum(float(g or 0) for v, g in rows)
        wr    = wins / total * 100 if total else 0.0
        gpt   = gas / total if total else 0.0
        return {"wr": wr, "gpt": gpt, "total": total}

    s7  = _stats(dt_7d)
    s30 = _stats(dt_30d)

    try:
        gwei = web3.eth.gas_price / 10**9
    except Exception:
        gwei = 0.0

    # Health Score rápido
    uptime_h = (time.time() - HEALTH["started_at"]) / 3600.0
    lat_avg  = float(HEALTH.get("rpc_latency_avg") or 0)
    cap_rate = float(HEALTH.get("capture_rate") or 100.0)
    rpc_errs = int(HEALTH.get("rpc_errors_total") or 0)
    score, *_ = _health_score(uptime_h, lat_avg, cap_rate, rpc_errs)
    score_label = _health_score_label(score)

    lines = [
        "🔔 <b>ALERTAS & DIAGNÓSTICO — WEbdEX</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Bloco 1 — Rede
    gwei_icon = "🟢" if gwei < 50 else ("🟡" if gwei < 150 else "🔴")
    lines += [
        "🌐 <b>Rede Polygon</b>",
        f"  {gwei_icon} Gas: <b>{gwei:.0f} Gwei</b>",
        f"  🏥 Motor: <b>{score}/100</b> — {score_label}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Bloco 2 — Tendências de performance
    lines.append("📊 <b>Tendências de Performance</b>")

    if s7 and s30 and s30["total"] >= 10:
        wr_delta  = s7["wr"]  - s30["wr"]
        gpt_delta = s7["gpt"] - s30["gpt"]

        # Win Rate
        wr_icon = "🟢" if wr_delta >= -5 else ("🟡" if wr_delta >= -10 else "🔴")
        lines.append(
            f"  {wr_icon} Win Rate: <b>{s7['wr']:.1f}%</b> (7d) vs <b>{s30['wr']:.1f}%</b> (30d) "
            f"→ <b>{wr_delta:+.1f}pp</b>"
        )
        if wr_delta < -10:
            lines.append("  ⚠️ <b>ALERTA:</b> Win rate caiu >10pp vs histórico!")

        # Gas/Trade
        gpt_icon = "🟢" if gpt_delta <= 0 else ("🟡" if gpt_delta < 0.02 else "🔴")
        lines.append(
            f"  {gpt_icon} Gas/Trade: <b>${s7['gpt']:.3f}</b> (7d) vs <b>${s30['gpt']:.3f}</b> (30d) "
            f"→ <b>{gpt_delta:+.3f}</b>"
        )
        if gpt_delta > 0.02:
            lines.append("  ⚠️ <b>ALERTA:</b> Custo de gás acelerando!")

        lines.append(f"  📈 Trades: <b>{s7['total']}</b> (7d) | <b>{s30['total']}</b> (30d)")
    elif s7:
        lines.append(f"  📊 Win Rate 7d: <b>{s7['wr']:.1f}%</b> | Gas/Trade: <b>${s7['gpt']:.3f}</b>")
        lines.append("  <i>Histórico 30d insuficiente para comparação (< 10 trades)</i>")
    else:
        lines.append("  <i>Sem dados suficientes no período.</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Bloco 3 — Último erro do motor
    last_err = HEALTH.get("last_error") or "-"
    lines.append(f"⚠️ Último erro motor: {code(str(last_err))}")

    return "\n".join(lines)


def _alerts_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="alerts_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="alerts_close"),
    )
    return kb


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("alerts_"))
def _alerts_callback(c):
    bot.answer_callback_query(c.id)
    if c.data == "alerts_close":
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        return
    u = get_user(c.from_user.id) or {}
    if not u.get("wallet"):
        return
    try:
        bot.edit_message_text(_alerts_build_text(u), c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_alerts_kb())
    except Exception as e:
        logger.warning("[alerts_callback] %s", e)


@bot.message_handler(func=lambda m: m.text == "🔔 Alertas")
@require_auth
def alerts(m, u):
    bot.send_chat_action(m.chat.id, "typing")
    send_support(m.chat.id, _alerts_build_text(u), reply_markup=_alerts_kb())


@bot.message_handler(func=lambda m: m.text == "📡 Status")
def sts(m):
    bot.send_chat_action(m.chat.id, "typing")
    try:
        blk = int(web3.eth.block_number)
    except Exception:
        blk = 0
    send_support(m.chat.id, f"📡 <b>Status</b>\nBloco: <b>{blk}</b>\nRPC Core: <b>OK</b>", reply_markup=main_kb())


@bot.message_handler(func=lambda m: m.text == "⚙️ Config")
def cfg(m):
    bot.send_chat_action(m.chat.id, "typing")
    try:
        u = get_user(m.chat.id) or {}
        sf = (u.get("sub_filter") or "").strip() or "Todas"
        send_support(
            m.chat.id,
            f"⚙️ <b>Config</b>\nWallet: {code((u.get('wallet') or 'N/A'))}\nAmbiente: <b>{esc(u.get('env') or 'N/A')}</b>\nPeríodo: <b>{esc(u.get('periodo') or '24h')}</b>\nFiltro: <b>{esc(sf)}</b>",
            reply_markup=main_kb()
        )
    except Exception as e:
        logger.warning("[cfg] %s", e)
        send_support(m.chat.id, "⚠️ Erro ao carregar config.", reply_markup=main_kb())


@bot.message_handler(func=lambda m: m.text == "❓ Ajuda")
def ajuda(m):
    txt = """❓ <b>AJUDA — WEbdEX</b>

<b>Menu</b>
1) 🔌 Conectar → envie Wallet → RPC → escolha ambiente.
2) ▶️ Ativar → começa a receber notificações de EXECUÇÃO.
3) 🎛️ Filtros → escolher subconta (ou Todas).
4) 📈 Dashboard PRO → painel com KPIs do período.
5) 🧬 Ciclo → tempo entre trades (mediana/P95) e consistência.
6) 🧠 Ranking → lucro / consistência / ciclo.
7) 🗓️ Período → 24h / 7d / 30d.
8) 🔄 Sync OnChain → sync por range (corrige histórico).
9) 🔍 Buscar Tx → consulta no DB (hash).

<b>📈 Dashboard PRO — o que significa</b>
• <b>LÍQUIDO TOTAL</b>: soma dos resultados já descontando gás.
• <b>Bruto (+)</b>: soma dos trades positivos (antes do gás).
• <b>Bruto (−)</b>: soma dos trades negativos (perdas).
• <b>Gás total</b>: custo total de taxas no período.
• <b>WinRate</b>: % de trades positivos.
• <b>Trades</b>: quantidade de operações no período.
• <b>Expectancy</b>: lucro médio por trade (líquido/trades).
• <b>Max Drawdown</b>: maior queda acumulada do período (risco).
• <b>Profit Factor</b>: ganhos / perdas (acima de 1 é saudável).
• <b>Streaks</b>: maior sequência de vitórias (W) e perdas (L).
• <b>Outliers</b>: maiores gases e piores nets (eventos fora do padrão).

<b>Níveis (para leitura)</b>
• Iniciante: foque em Líquido, Gás e Trades.
• Intermediário: adicione WinRate e Expectancy.
• Avançado: monitore Drawdown, Profit Factor, Streaks e Outliers.
"""
    send_support(m.chat.id, txt, reply_markup=ajuda_kb())


# ==============================================================================
# 🧠 IA — WEbdEX Brain
# ==============================================================================
def _brain_style_prefix() -> str:
    return (
        "🧠 WEbdEX Brain — Governança & Auditoria Educativa\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )


def webdex_explain_openposition() -> str:
    return (
        _brain_style_prefix()
        + "📌 <b>OpenPosition (evento)</b>\n\n"
        "No WEbdEX V5, <b>OpenPosition</b> é o evento on-chain que marca uma nova operação registrada pelo protocolo.\n"
        "Ele é a base do nosso <b>Dashboard</b>, <b>Ranking</b> e relatórios (ex.: Relatório 21h).\n\n"
        "🔎 O que você normalmente encontra no Input/Data do OpenPosition:\n"
        "• Identificadores da subconta (quem operou)\n"
        "• Par/rota e parâmetros do trade\n"
        "• Valores (entrada/saída) e métricas de execução\n"
        "• Informações úteis para auditoria (timestamp/bloco/tx)\n\n"
        "✅ Importante (educativo):\n"
        "• <b>Transfer</b> é movimento ERC20 (não é trade).\n"
        "• <b>OpenPosition</b> representa a execução/abertura de uma operação (trade).\n\n"
        "Quer que eu explique um OpenPosition específico? Envie a <b>tx hash</b> ou o trecho do log."
    )


def webdex_explain_dashboard() -> str:
    return (
        _brain_style_prefix()
        + "📈 <b>Dashboard PRO</b>\n\n"
        "O Dashboard PRO consolida as operações do protocolo (baseadas em <b>OpenPosition</b>) e apresenta:\n"
        "• Lucro bruto e lucro líquido (após taxas/gás quando aplicável)\n"
        "• Curva de equity / desempenho no período\n"
        "• Top subcontas e métricas de consistência\n\n"
        "🧭 Como interpretar (bem simples):\n"
        "1) Veja o período selecionado (ex.: 24h)\n"
        "2) Confira se as subcontas estão girando (ciclo)\n"
        "3) Compare lucro vs. custo de gás\n\n"
        "Se você me disser qual seção do Dashboard você está olhando, eu explico linha por linha 🙂"
    )


def webdex_explain_ranking() -> str:
    return (
        _brain_style_prefix()
        + "🏆 <b>Ranking (Lucro / Consistência / Ciclo)</b>\n\n"
        "Rankings no WEbdEX servem para leitura objetiva do comportamento das subcontas:\n"
        "• 💰 <b>Ranking Lucro</b>: quem mais gerou resultado\n"
        "• 🧠 <b>Ranking Consistência</b>: estabilidade (menos oscilações / melhor padrão)\n"
        "• ⏱️ <b>Ranking Ciclo</b>: quem gira mais rápido (mediana menor)\n\n"
        "📌 Dica de governança:\n"
        "Resultado alto com ciclo ruim pode sinalizar picos.\n"
        "Consistência boa com lucro menor pode sinalizar estabilidade.\n\n"
        "Quer que eu explique o ranking que você acabou de gerar? Copia aqui o texto do ranking."
    )


@bot.message_handler(func=lambda m: m.text == "🧠 IA")
def ia_menu(m):
    chat_id = m.chat.id

    if not ai_can_use(chat_id):
        bot.send_message(
            chat_id,
            "🧠 IA da WEbdEX\n\n"
            "🔒 A IA está em modo <b>ADM-only</b> no momento.\n"
            "Isso é uma medida de governança e segurança.\n\n"
            "✅ Você ainda pode usar o bot normalmente (Dashboard/Ranking/Relatórios).",
            reply_markup=main_kb(chat_id),
            parse_mode="HTML"
        )
        return

    g = "ON" if ai_global_enabled() else "OFF"
    mode = "DEV" if ai_mode() == "dev" else "COMUNIDADE"

    bot.send_message(
        chat_id,
        "🤖 <b>bdZinho</b>\n\n"
        f"✅ Status: <b>{g}</b>\n"
        f"🎛️ Modo: <b>{mode}</b>\n\n"
        "Escolha uma opção abaixo 👇",
        reply_markup=bdzinho_kb(),
        parse_mode="HTML"
    )


@bot.message_handler(func=lambda m: m.text == "📊 Resultados")
def btn_resultados(message):
    bot.send_message(message.chat.id, "📊 <b>Resultados</b> — escolha:",
                     parse_mode="HTML", reply_markup=resultado_kb())


@bot.message_handler(func=lambda m: m.text == "🤖 bdZinho")
def btn_bdzinho(message):
    bot.send_message(message.chat.id, "🤖 <b>bdZinho</b> — o que deseja?",
                     parse_mode="HTML", reply_markup=bdzinho_kb())


@bot.message_handler(func=lambda m: m.text == "🌐 Protocolo")
def btn_protocolo(message):
    bot.send_message(message.chat.id, "🌐 <b>Protocolo WEbdEX</b> — explorar:",
                     parse_mode="HTML", reply_markup=protocolo_kb())


@bot.message_handler(func=lambda m: m.text == "⚙️ Config")
def btn_config(message):
    bot.send_message(message.chat.id, "⚙️ <b>Configurações</b>:",
                     parse_mode="HTML", reply_markup=config_kb())


@bot.message_handler(func=lambda m: m.text in ("⬅️ Menu", "🔙 Menu"))
def btn_voltar_menu(message):
    bot.send_message(message.chat.id, "🏠 Menu principal:",
                     parse_mode="HTML", reply_markup=main_kb(message.chat.id))


@bot.message_handler(func=lambda m: m.text == "📌 Posição Aberta")
def btn_posicao_aberta(message):
    chat_id = message.chat.id
    msg = webdex_explain_openposition()
    send_support(chat_id, msg, reply_markup=bdzinho_kb())


@bot.message_handler(func=lambda m: (m.text or "").strip() == "💬 Perguntar")
def ia_ask_btn(m):
    chat_id = m.chat.id
    if not ai_can_use(chat_id):
        bot.send_message(chat_id, "🔒 IA em modo ADM-only no momento.", reply_markup=main_kb(chat_id))
        return
    bot.send_message(
        chat_id,
        "💬 Manda sua pergunta agora.\n\n"
        "Exemplos:\n"
        "• O que é OpenPosition?\n"
        "• Como ler o Dashboard PRO?\n"
        "• O que significa Ranking Lucro?\n",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(m, ia_question)


@bot.message_handler(func=lambda m: (m.text or "").strip() == "📌 OpenPosition")
def ia_explain_openposition_btn(m):
    chat_id = m.chat.id
    msg = webdex_explain_openposition()
    send_support(chat_id, msg, reply_markup=ia_kb())


@bot.message_handler(func=lambda m: (m.text or "").strip() == "📈 Dashboard")
def ia_explain_dashboard_btn(m):
    chat_id = m.chat.id
    msg = webdex_explain_dashboard()
    send_support(chat_id, msg, reply_markup=ia_kb())


@bot.message_handler(func=lambda m: (m.text or "").strip() == "🏆 Ranking")
def ia_explain_ranking_btn(m):
    chat_id = m.chat.id
    msg = webdex_explain_ranking()
    send_support(chat_id, msg, reply_markup=ia_kb())


def ia_question(m):
    chat_id = m.chat.id
    t = (m.text or "").strip()
    if t.lower() in ("/cancelar", "cancelar", "/cancel"):
        bot.send_message(chat_id, "✅ IA cancelada.", reply_markup=bdzinho_kb())
        return

    if not ai_can_use(chat_id):
        bot.send_message(chat_id, "🔒 IA em modo ADM-only no momento.", reply_markup=main_kb(chat_id))
        return

    # Resposta com Brain (OpenAI) + fallback educativo
    try:
        answer = ai_answer_ptbr(t, chat_id=chat_id)
    except Exception as e:
        logger.error("[ia] falhou")
        answer = (
            "⚠️ A IA falhou momentaneamente.\n\n"
            "✅ Isso pode ocorrer por instabilidade externa (rede/timeout).\n"
            "Tente novamente em alguns segundos.\n"
        )

    send_support(chat_id, _tg_ai_pretty(answer), reply_markup=bdzinho_kb())


# Mantém compatibilidade: per-user flag existe no DB (não usado por padrão)
def get_user_ai_enabled(chat_id: int) -> int:
    try:
        with DB_LOCK:
            cur = conn.cursor()
            cur.execute("SELECT ai_enabled FROM users WHERE chat_id=?", (chat_id,))
            row = cur.fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        pass
    return 1


def set_user_ai_enabled(chat_id: int, enabled: int):
    enabled = 1 if enabled else 0
    with DB_LOCK:
        cur = conn.cursor()
        try:
            cur.execute("INSERT OR IGNORE INTO users(chat_id) VALUES(?)", (chat_id,))
        except Exception:
            pass
        try:
            cur.execute("UPDATE users SET ai_enabled=? WHERE chat_id=?", (enabled, chat_id))
            conn.commit()
        except Exception:
            pass


@bot.message_handler(func=lambda m: m.text in ["📘 Iniciante", "📗 Intermediário", "📕 Avançado"])
@require_auth
def ajuda_niveis(m, u):
    lvl = m.text
    if lvl == "📘 Iniciante":
        txt = (
            "📘 <b>AJUDA — Iniciante</b>\n\n"
            "• <b>Líquido</b>: resultado final (lucro - perdas - gás).\n"
            "• <b>Gás</b>: taxa da rede Polygon que pode reduzir o lucro.\n"
            "• <b>WinRate</b>: % de trades positivos.\n"
            "• <b>Trades</b>: quantidade de operações no período.\n\n"
            "Dica: no DeFi, <b>gás</b> e <b>consistência</b> importam tanto quanto o lucro."
        )
    elif lvl == "📗 Intermediário":
        txt = (
            "📗 <b>AJUDA — Intermediário</b>\n\n"
            "• <b>Expectancy</b>: média do resultado por trade (líquido / trades).\n"
            "• <b>Max Drawdown</b>: maior queda acumulada no período (risco).\n"
            "• <b>Profit Factor</b>: ganhos / perdas (quanto maior, melhor).\n"
            "• <b>Streaks</b>: maior sequência de vitórias (W) e perdas (L).\n\n"
            "Use <b>Outliers</b> para encontrar trades fora do padrão (gás alto, net ruim)."
        )
    else:
        txt = (
            "📕 <b>AJUDA — Avançado</b>\n\n"
            "• <b>Expectancy</b> positiva com amostra grande = vantagem estatística.\n"
            "• <b>Drawdown</b> é métrica-chave de risco/psicológico.\n"
            "• <b>Profit Factor</b> > 1.5 costuma indicar sistema saudável.\n"
            "• <b>Outliers</b> ajudam a separar evento externo (rede) de padrão do algoritmo.\n\n"
            "Diretriz WEbdEX: <b>Risco • Responsabilidade • Retorno</b> (ambiente não-custodial)."
        )
    send_support(m.chat.id, txt, reply_markup=ajuda_kb())


# ==============================================================================
# ℹ️ KPI Tooltips (Ajuda interativa)
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "ℹ️ KPIs")
def kpis_menu(m):
    u = get_user(m.chat.id) or {}
    wallet = u.get("wallet") or ""
    periodo = u.get("periodo") or "24h"
    hours = period_to_hours(periodo)

    # Tenta buscar dados reais do periodo
    kpi_data = None
    if wallet:
        try:
            dt = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
            extra_sql, extra_params = get_user_filter_clause(u)
            with DB_LOCK:
                row = cursor.execute(f"""
                    SELECT COUNT(*), COALESCE(SUM(o.valor),0), COALESCE(SUM(o.gas_usd),0),
                           COUNT(CASE WHEN o.valor > 0 THEN 1 END)
                    FROM operacoes o
                    JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                    WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=? {extra_sql}
                """, (dt, wallet, *extra_params)).fetchone()
            if row and row[0]:
                cnt, vol, gas, wins = int(row[0] or 0), float(row[1] or 0), float(row[2] or 0), int(row[3] or 0)
                liq  = vol - gas
                wr   = wins / cnt * 100 if cnt else 0.0
                kpi_data = {"cnt": cnt, "vol": vol, "gas": gas, "liq": liq, "wr": wr, "wins": wins}
        except Exception:
            pass

    if kpi_data:
        liq_icon = "🟢" if kpi_data["liq"] >= 0 else "🔴"
        liq_sign = "+" if kpi_data["liq"] >= 0 else ""
        hdr  = (
            f"📊 <b>KPIs em tempo real — {esc(periodo)}</b>\n"
            f"╼╼╼╼╼╼╼╼╼╼\n"
            f"🏅 Líquido:   {liq_icon} <b>{liq_sign}{kpi_data['liq']:,.4f} USD</b>\n"
            f"⛽ Gás total: <b>{kpi_data['gas']:.4f} USD</b>\n"
            f"🏆 WinRate:  <b>{kpi_data['wr']:.1f}%</b> ({kpi_data['wins']}/{kpi_data['cnt']} trades)\n"
            f"💵 Volume:   <b>{kpi_data['vol']:,.4f} USD</b>\n"
            f"╼╼╼╼╼╼╼╼╼╼\n"
            f"Clique em um KPI para entender o significado:"
        )
    else:
        hdr = "ℹ️ Selecione um KPI para entender o significado:"

    send_support(m.chat.id, hdr, reply_markup=kpi_kb())


@bot.message_handler(func=lambda m: m.text == "⬅️ Voltar")
def voltar_menu(m):
    send_support(m.chat.id, "✅ Menu principal.", reply_markup=main_kb())


_KPI_TEXT = {
    "🏅 Líquido": """🏅 <b>LÍQUIDO TOTAL</b>
Resultado real do período (já descontando gás).

<b>Uso:</b> principal indicador do período.""",
    "⛽ Gás": """⛽ <b>GÁS TOTAL</b>
Custo total de taxas de rede (Polygon) no período.

<b>Uso:</b> mede a fricção; gás alto pode reduzir o líquido.""",
    "🏆 WinRate": """🏆 <b>WINRATE</b>
Percentual de trades positivos.

<b>Uso:</b> consistência, mas não garante lucro sozinho.""",
    "📐 Expectancy": """📐 <b>EXPECTANCY</b>
Lucro médio por trade (líquido / trades).

<b>Uso:</b> se for positivo, tende a crescer no longo prazo.""",
    "📉 Drawdown": """📉 <b>MAX DRAWDOWN</b>
Maior queda acumulada do período.

<b>Uso:</b> mede risco e impacto psicológico.""",
    "📈 Profit Factor": """📈 <b>PROFIT FACTOR</b>
Ganhos / perdas (abs).

<b>Guia:</b> >1 saudável; >2 muito forte.""",
    "🔥 Streaks": """🔥 <b>STREAKS</b>
Maior sequência de vitórias (W) e perdas (L).

<b>Uso:</b> calibra expectativa e gestão de risco.""",
    "🧯 Outliers": """🧯 <b>OUTLIERS</b>
Eventos fora do padrão: maiores gases e piores nets.

<b>Uso:</b> diagnóstico e transparência (rede vs. desempenho).""",
}

for _k in list(_KPI_TEXT.keys()):
    @bot.message_handler(func=lambda m, kk=_k: m.text == kk)
    def _kpi_tip(m, kk=_k):
        send_support(m.chat.id, _KPI_TEXT.get(kk, "—"), reply_markup=kpi_kb())


# ==============================================================================
# 📍 POSIÇÕES ABERTAS
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "📍 Posições")
@require_auth
def posicoes_abertas(m, u):
    """Mostra saldo e atividade por subconta baseado em oldBalance do evento."""
    bot.send_chat_action(m.chat.id, "typing")
    wallet = (u.get("wallet") or "").lower().strip()
    if not wallet:
        return send_support(m.chat.id, "⚠️ Wallet não configurada.", reply_markup=main_kb())

    try:
        with DB_LOCK:
            rows = conn.execute("""
                SELECT sub_conta, ambiente, saldo_usdt, old_balance,
                       trade_count, last_trade, updated_at
                FROM sub_positions
                WHERE LOWER(wallet)=?
                ORDER BY trade_count DESC, saldo_usdt DESC
                LIMIT 30
            """, (wallet,)).fetchall()
    except Exception as _e:
        return send_support(m.chat.id, f"⚠️ Erro ao ler posições: {_e}", reply_markup=main_kb())

    if not rows:
        return send_support(
            m.chat.id,
            "📍 <b>Posições</b>\n\n"
            "Nenhuma subconta rastreada ainda.\n"
            "As posições aparecem aqui após o primeiro trade capturado.",
            reply_markup=main_kb()
        )

    # Agrupa por ambiente
    by_env: dict = {}
    for sub, amb, saldo, old_bal, n_trades, last_t, upd in rows:
        by_env.setdefault(str(amb), []).append(
            (str(sub), float(saldo or 0), float(old_bal or 0), int(n_trades or 0), str(last_t or ""))
        )

    # Capital total do worker (capital_cache) — sem busca on-chain por subconta
    # (busca on-chain por sub era bugada: sem seen_coins, sem LP, calculo errado)
    import json as _jpos
    cap_total_cache = 0.0
    cap_breakdown_cache: dict = {}
    try:
        with DB_LOCK:
            _cc = cursor.execute(
                "SELECT total_usd, breakdown_json FROM capital_cache WHERE chat_id=? LIMIT 1",
                (m.chat.id,)
            ).fetchone()
        if _cc:
            _ct = float(_cc[0] or 0)
            cap_breakdown_cache = __import__('json').loads(_cc[1] or "{}")
            _bdj_sum = sum(float(v) for v in cap_breakdown_cache.values() if float(v or 0) > 0)
            cap_total_cache = max(_ct, _bdj_sum)
    except Exception:
        pass

    out = [
        "📍 <b>POSIÇÕES POR SUBCONTA — WEbdEX</b>",
        f"🔗 Wallet: <code>{esc(wallet[:12])}…</code>",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    total_saldo = 0.0
    for amb, subs in sorted(by_env.items()):
        amb_icon = "🔵" if "v5" in str(amb).lower() else "🟠"
        out.append(f"\n{amb_icon} <b>{esc(amb)}</b>")
        for sub, saldo, old_bal, n, last_t in subs:
            cap_val  = old_bal
            cap_src  = "<i>(ref.)</i>"
            icon     = "🟢" if old_bal > 0 else ("🔴" if old_bal < 0 else "⚪")

            mins = ""
            try:
                diff = (datetime.now() - datetime.strptime(last_t[:19], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60
                if diff < 60:
                    mins = f"  ·  {int(diff)}min atrás"
                elif diff < 1440:
                    mins = f"  ·  {int(diff/60)}h atrás"
                else:
                    mins = f"  ·  {int(diff/1440)}d atrás"
            except Exception:
                pass

            out.append(
                f"  {icon} <b>{esc(str(sub)[:22])}</b>\n"
                f"     💵 <b>${cap_val:,.4f}</b> {cap_src}  ·  Trades: <b>{n}</b>{mins}"
            )
            total_saldo += cap_val

    out.append("\n━━━━━━━━━━━━━━━━━━━━")
    if cap_total_cache > 0:
        _usdt_c = cap_breakdown_cache.get("USDT", cap_breakdown_cache.get("USDT0", 0.0))
        _lp_c   = cap_breakdown_cache.get("LP-USD", cap_breakdown_cache.get("LP-V5", 0.0))
        out.append(f"💼  <b>Capital total (worker):</b> <b>${cap_total_cache:,.2f} USD</b>")
        if _usdt_c > 0 and _lp_c > 0:
            out.append(f"     ├ USDT: <b>${_usdt_c:,.2f}</b>  LP-USD: <b>${_lp_c:,.2f}</b>")
    else:
        out.append(f"💼  Capital: <b>—</b> <i>(worker ainda carregando)</i>")
    out.append("<i>⚡ WEbdEX · New Digital Economy</i>")

    send_support(m.chat.id, "\n".join(out), reply_markup=main_kb())


# ==============================================================================
# 🔍 Buscar Tx
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🔍 Buscar Tx")
def buscar_tx(m):
    upsert_user(m.chat.id, pending="ASK_TX")
    send_support(m.chat.id, "🔍 Envie a <b>txhash</b> (0x...) para buscar no DB.\n\nDigite <b>cancelar</b> para sair.", reply_markup=types.ReplyKeyboardRemove())


def find_tx_in_db(txh: str) -> Optional[Dict[str, Any]]:
    txh = normalize_txhash(txh)
    with DB_LOCK:
        row = cursor.execute("""
            SELECT o.data_hora,o.tipo,o.valor,o.gas_usd,o.token,o.sub_conta,o.bloco, ow.wallet
            FROM operacoes o
            LEFT JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.hash=?
            ORDER BY o.log_index ASC
            LIMIT 1
        """, (txh,)).fetchone()
    if not row:
        return None
    return {
        "data_hora": row[0],
        "tipo": row[1],
        "valor": float(row[2] or 0.0),
        "gas_usd": float(row[3] or 0.0),
        "token": row[4],
        "sub": row[5],
        "bloco": int(row[6] or 0),
        "wallet": (row[7] or "").lower()
    }


# ==============================================================================
# 🔄 Sync OnChain por Range REAL
# ==============================================================================
SYNC_LOCK = threading.Lock()


def _parse_block(s: str) -> Optional[int]:
    s = (s or "").strip().lower()
    if not s:
        return None
    if s == "auto":
        return -1
    try:
        return int(s)
    except Exception:
        return None


def _sync_key(env: str) -> str:
    return f"last_sync_{env}"


def _get_last_sync(env: str) -> int:
    try:
        return int(get_config(_sync_key(env), "0"))
    except Exception:
        return 0


def _set_last_sync(env: str, blk: int):
    set_config(_sync_key(env), str(int(blk)))


def _sync_thread(chat_id: int, env: str, from_blk: int, to_blk: int):
    from webdex_config import MONITOR_SYNC_STEP
    with SYNC_LOCK:
        HEALTH["sync_running"] = 1
        try:
            start_ts = now_br().strftime("%Y-%m-%d %H:%M:%S")
            HEALTH["sync_last"] = f"{env} {from_blk}->{to_blk} @ {start_ts}"
            send_support(
                chat_id,
                (
                    f"🔄 <b>SYNC INICIADO</b>\n"
                    f"Ambiente: <b>{esc(env)}</b>\n"
                    f"Range: <b>{from_blk}</b> → <b>{to_blk}</b>\n\n"
                    f"Isso roda em background."
                ),
                reply_markup=main_kb(),
            )

            step = max(100, int(MONITOR_SYNC_STEP))
            cur = from_blk
            last_msg_at = time.time()

            while cur <= to_blk:
                nxt = min(to_blk, cur + step - 1)
                fetch_range(cur, nxt, env_only=env, include_transfers=False)
                _set_last_sync(env, nxt)

                if time.time() - last_msg_at > 12:
                    pct = (nxt - from_blk) / max(1, (to_blk - from_blk))
                    send_html(chat_id, f"🔄 Sync {esc(env)}: {code(cur)}→{code(nxt)} ({pct*100:.1f}%)")
                    last_msg_at = time.time()

                cur = nxt + 1
                time.sleep(0.10)

            send_support(
                chat_id,
                (
                    f"✅ <b>SYNC CONCLUÍDO</b>\n"
                    f"Ambiente: <b>{esc(env)}</b>\n"
                    f"Até bloco: <b>{to_blk}</b>"
                ),
                reply_markup=main_kb(),
            )
        except Exception as e:
            HEALTH["last_error"] = f"sync: {e}"
            send_support(chat_id, f"⚠️ Sync falhou: {code(e)}", reply_markup=main_kb())
        finally:
            HEALTH["sync_running"] = 0


@bot.message_handler(func=lambda m: m.text == "🔄 Sync OnChain")
@require_auth
def sync_onchain(m, u):
    upsert_user(m.chat.id, pending="ASK_SYNC_FROM")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("auto", "⬅️ Voltar")
    send_support(
        m.chat.id,
        "🔄 <b>SYNC ONCHAIN (Range)</b>\n\n"
        "Env será o seu ambiente atual.\n\n"
        "Passo 1: envie <b>fromBlock</b> (ex: 60000000)\n"
        "ou digite <b>auto</b> (usa último sync salvo / fallback).\n\n"
        "Digite <b>cancelar</b> para sair.",
        reply_markup=kb
    )


# ==============================================================================
# 🏛️ COMUNIDADE WEbdEX — Score Institucional + Ranking Cross-Wallet  (item C)
# ==============================================================================
def _calc_inst_score(winrate_pct: float, profit_factor: float, efficiency: float) -> float:
    pf_s  = min(100.0, profit_factor * 50.0)
    wr_s  = min(100.0, winrate_pct)
    eff_s = min(100.0, efficiency * 20.0)
    return (pf_s * 0.40) + (wr_s * 0.30) + (eff_s * 0.30)


@bot.message_handler(func=lambda m: m.text == "🏛️ Comunidade")
def comunidade(m):
    bot.send_chat_action(m.chat.id, "typing")
    try:
        with DB_LOCK:
            rows = cursor.execute("""
                SELECT u.wallet, u.env,
                       COUNT(*)                                              AS total,
                       SUM(CASE WHEN CAST(o.valor AS REAL)>0 THEN 1 ELSE 0 END)  AS wins,
                       SUM(CAST(o.valor AS REAL))                           AS gross,
                       SUM(CAST(o.gas_usd AS REAL))                         AS gas,
                       SUM(CASE WHEN CAST(o.valor AS REAL)>0 THEN CAST(o.valor AS REAL) ELSE 0 END) AS gross_wins
                FROM users u
                JOIN op_owner ow ON LOWER(ow.wallet)=LOWER(u.wallet)
                JOIN operacoes o  ON o.hash=ow.hash AND o.log_index=ow.log_index
                WHERE o.tipo='Trade' AND u.wallet IS NOT NULL AND TRIM(u.wallet)!=''
                GROUP BY LOWER(u.wallet)
                HAVING total >= 5
                ORDER BY total DESC
            """).fetchall()
    except Exception as e:
        logger.warning("[comunidade] query error: %s", e)
        rows = []

    if not rows:
        return send_support(m.chat.id,
            "⚠️ Sem dados suficientes para o ranking comunitário (mínimo 5 trades por wallet).",
            reply_markup=main_kb())

    ranking = []
    for wallet, env, total, wins, gross, gas, gross_wins in rows:
        gross      = float(gross or 0)
        gas        = float(gas or 0)
        wins       = int(wins or 0)
        gross_wins = float(gross_wins or 0)
        gross_loss = abs(gross - gross_wins)
        liq        = gross - gas
        winrate    = (wins / total * 100) if total > 0 else 0.0
        pf         = min(10.0, gross_wins / gross_loss) if gross_loss > 0.001 else (10.0 if gross_wins > 0 else 0.0)
        efficiency = liq / gas if gas > 0.001 else 0.0
        score      = _calc_inst_score(winrate, pf, efficiency)
        ws = f"{wallet[:6]}…{wallet[-4:]}" if wallet and len(wallet) > 10 else (wallet or "?")
        ranking.append((score, winrate, pf, liq, int(total), ws, env or ""))

    ranking.sort(key=lambda x: x[0], reverse=True)

    # posição do usuário atual
    u = get_user(m.chat.id) or {}
    user_wallet_low = (u.get("wallet") or "").lower()
    user_pos = None
    u_w_low = (get_user(m.chat.id) or {}).get("wallet", "")
    u_w_low = (u_w_low or "").lower()
    if u_w_low:
        for idx, (sc, wr, pf, liq, tot, ws, env) in enumerate(ranking, 1):
            if u_w_low[:6] in ws.lower() or u_w_low[-4:] in ws.lower():
                user_pos = idx
                break

    lines = [
        "🏛️ <b>COMUNIDADE WEbdEX</b>",
        "<i>Score Institucional: PF×40% + WinRate×30% + Eficiência×30%</i>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"👥 <b>{len(ranking)}</b> traders ranqueados",
        "",
    ]
    for i, (sc, wr, pf, liq, tot, ws, env) in enumerate(ranking[:20], 1):
        tag  = f" <i>[{esc(env)}]</i>" if env else ""
        sign = "🟢" if liq >= 0 else "🔴"
        lines.append(f"{_medal(i)}  {code(ws)}{tag}")
        lines.append(
            f"    Score <b>{sc:.0f}</b>/100  ·  WR <b>{wr:.0f}%</b>  ·  "
            f"PF <b>{pf:.2f}</b>  ·  {sign} <b>${liq:+.2f}</b>  ·  {tot} trades"
        )
        lines.append("")

    if user_pos:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📍 <b>Sua posição: #{user_pos}</b> de {len(ranking)} traders")

    # IA audit da comunidade (async)
    def _ai_com_task():
        try:
            from webdex_ai import _ai_comunidade_audit
            audit = _ai_comunidade_audit(ranking[:5], len(ranking))
            if audit:
                send_html(m.chat.id, f"┈┈┈┈┈┈ IA ┈┈┈┈┈┈\n\n🤖 {audit}")
        except Exception:
            pass
    threading.Thread(target=_ai_com_task, daemon=True).start()

    try:
        bot.send_message(m.chat.id, "\n".join(lines).rstrip(),
                         parse_mode="HTML", reply_markup=main_kb())
    except Exception as e:
        logger.warning("[comunidade] send error: %s", e)
        send_html(m.chat.id, "\n".join(lines).rstrip())


# ==============================================================================
# 🌐 PROTOCOLO WEbdEX — TokenPass + TVL + saúde da rede  (item D)
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🌐 Protocolo")
def protocolo(m):
    bot.send_chat_action(m.chat.id, "typing")
    from webdex_monitor import HEALTH

    pol_price = chain_pol_price()
    gwei      = chain_gwei()
    bloco     = chain_block()

    # TokenPass check on-chain
    u = get_user(m.chat.id) or {}
    wallet  = u.get("wallet") or ""
    env_nm  = u.get("env") or "AG_C_bd"
    tokenpass_ok: Optional[bool] = None
    if wallet:
        try:
            from webdex_chain import web3 as _w3
            c = get_contracts(env_nm, _w3)
            bal = c["pass"].functions.balanceOf(
                Web3.to_checksum_address(wallet)
            ).call()
            tokenpass_ok = bal > 0
        except Exception:
            tokenpass_ok = None

    if tokenpass_ok is True:
        pass_icon = "✅ Ativo"
    elif tokenpass_ok is False:
        pass_icon = "❌ Inativo"
    else:
        pass_icon = "— (sem wallet)"

    # TVL por ambiente — capital_cache + fallback user_capital_snapshots
    tvl_ag = tvl_v5 = 0.0
    try:
        with DB_LOCK:
            tvl_rows = cursor.execute("""
                SELECT CASE WHEN LOWER(u.env) LIKE '%v5%' THEN 'bd_v5' ELSE 'AG_C_bd' END AS env_grp,
                       SUM(cc.total_usd)
                FROM capital_cache cc
                JOIN users u ON u.chat_id = cc.chat_id
                WHERE cc.updated_ts > ?
                GROUP BY env_grp
            """, (time.time() - 86400 * 3,)).fetchall()
        if not tvl_rows:
            # Fallback: user_capital_snapshots (snapshots históricos)
            tvl_rows = cursor.execute("""
                SELECT CASE WHEN LOWER(u.env) LIKE '%v5%' THEN 'bd_v5' ELSE 'AG_C_bd' END AS env_grp,
                       SUM(s.total_usd)
                FROM user_capital_snapshots s
                JOIN users u ON LOWER(u.wallet) = LOWER(s.wallet)
                WHERE s.ts >= datetime('now', '-3 days')
                GROUP BY env_grp
            """).fetchall()
        for env_r, total_r in tvl_rows:
            if "v5" in (env_r or "").lower():
                tvl_v5 += float(total_r or 0)
            else:
                tvl_ag += float(total_r or 0)
    except Exception:
        pass
    tvl_total = tvl_ag + tvl_v5

    # Dados do protocolo no ciclo atual (protocol_ops)
    from webdex_db import _ciclo_21h_since as _c21s
    _p_trades = _p_wins = 0
    _p_pnl = _p_wallets = 0.0
    try:
        with DB_LOCK:
            _pr = cursor.execute("""
                SELECT COUNT(*),
                       SUM(CASE WHEN CAST(profit AS REAL) > 0 THEN 1 ELSE 0 END),
                       SUM(CAST(profit AS REAL)),
                       COUNT(DISTINCT wallet)
                FROM protocol_ops
                WHERE data_hora >= ?
            """, (_c21s(),)).fetchone()
        if _pr:
            _p_trades   = int(_pr[0] or 0)
            _p_wins     = int(_pr[1] or 0)
            _p_pnl      = float(_pr[2] or 0)
            _p_wallets  = int(_pr[3] or 0)
    except Exception:
        pass
    _p_wr = (_p_wins / _p_trades * 100) if _p_trades > 0 else 0.0
    _pnl_sign = "+" if _p_pnl >= 0 else ""
    _pnl_icon = "🟢" if _p_pnl >= 0 else "🔴"

    # RPC pool health
    healthy_rpc = sum(1 for cd in rpc_pool._cooldown_until if cd <= time.time())
    vigia_ok    = HEALTH.get("vigia_loops", 0) > 0
    bloco_fmt   = f"{bloco:,}" if bloco else "—"

    lines = [
        "🌐 <b>PROTOCOLO WEbdEX</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"🎟️  TokenPass:  <b>{esc(pass_icon)}</b>",
        f"🏦  Ambiente:   <b>{esc(env_nm)}</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "",
        "┈┈┈┈┈┈ CICLO ATUAL ┈┈┈┈┈┈",
        "",
        f"⚡  Trades:   <b>{_p_trades:,}</b>  ·  👥 <b>{_p_wallets}</b> wallets",
        f"🎯  WinRate:  <b>{_p_wr:.1f}%</b>",
        f"{_pnl_icon}  PnL:      <b>{_pnl_sign}${_p_pnl:,.2f} USD</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💧  TVL AG_C_bd:  <b>${tvl_ag:,.0f}</b>",
        f"💧  TVL bd_v5:    <b>${tvl_v5:,.0f}</b>",
        f"💰  TVL Total:    <b>${tvl_total:,.0f}</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"⚡  Rede:    Polygon",
        f"🧱  Bloco:   <b>{bloco_fmt}</b>",
        f"⛽  Gas:     <b>{gwei:.0f} Gwei</b>",
        f"💲  POL:     <b>${pol_price:.4f}</b>",
        "",
        f"🔌  RPC Pool:  <b>{healthy_rpc}/3</b> endpoints saudáveis",
        f"📡  Monitor:   {'🟢 ativo' if vigia_ok else '🔴 parado'}",
        "",
        "<i>⚡ WEbdEX · New Digital Economy</i>",
    ]
    try:
        bot.send_message(m.chat.id, "\n".join(lines),
                         parse_mode="HTML", reply_markup=main_kb())
    except Exception as e:
        logger.warning("[protocolo] send error: %s", e)
        send_html(m.chat.id, "\n".join(lines))

    # IA audit do protocolo (async — não bloqueia)
    if _p_trades >= 10:
        def _ai_proto_task():
            try:
                from webdex_ai import _ai_protocolo_audit
                audit = _ai_protocolo_audit(_p_trades, _p_wr, _p_pnl, tvl_total)
                if audit:
                    send_html(m.chat.id,
                        f"┈┈┈┈┈┈ IA ┈┈┈┈┈┈\n\n🤖 {audit}")
            except Exception:
                pass
        threading.Thread(target=_ai_proto_task, daemon=True).start()


# ==============================================================================
# ✅ WIZARD (pending-only)
# ==============================================================================
_KNOWN_BUTTONS = {
    # Menu principal (novo — 4 botões)
    "📊 Resultados", "🤖 bdZinho", "🌐 Protocolo", "⚙️ Config",
    # Submenu Resultados
    "📌 Ciclo 21h", "📈 Dashboard PRO", "📍 Posições", "📊 mybdBook",
    "📈 mybdBook (Gráfico)", "🩺 Saúde",
    # Submenu bdZinho
    "🎨 Criar Imagem", "📌 Posição Aberta", "🔬 Análise",
    # Submenu Protocolo
    "🏆 Ranking Lucro", "🧠 Ranking Consistência", "⏱️ Ranking Ciclo",
    "🏛️ Comunidade", "📡 Status", "🔔 Alertas",
    "⛽ Auditoria Gás", "🧬 Ciclo da Subconta",
    "📜 Ops", "🔍 Buscar Tx", "🔄 Sync OnChain", "🧾 IDs com Saldo",
    # Submenu Config
    "🔌 Conectar", "▶️ Ativar", "⏸️ Pausar",
    "🗓️ Escolher Período", "🎛️ Filtros",
    "🔎 Wallet Info", "❓ Ajuda",
    "⏳ Inatividade", "🛠️ ADM",
    # Navegação submenus
    "⬅️ Menu",
    # Backward compat (menu antigo / ia_kb antigo)
    "🧠 IA",
    "📊 Consolidado (24h)",
    "📊 mybdBook ADM",
    "🔬 Análise",
    "🔙 Menu", "🔙 ADM",
    # Botões ADM (handlers em admin.py)
    "📊 Análise SubAccounts", "📊 Relatório Institucional",
    "📸 Progressão do Capital",
    "👥 ADM PRO", "⚙️ Limites", "⏳ Inatividade PRO",
    # Períodos e wizard
    "ciclo", "7d", "30d", "24h",
    "Todas", "cancelar",
    "⏭️ Pular RPC",
}


def _has_pending(m) -> bool:
    u = get_user(m.chat.id)
    return bool(u and (u.get("pending") or "").strip())


@bot.message_handler(func=_has_pending, content_types=["text"])
def step_handler(m):
    u = get_user(m.chat.id)
    if not u:
        return

    txt = (m.text or "").strip()

    # Botao do menu durante pending -> limpa pending e retorna ao menu
    # Exceções: cancelar e botões de navegação do wizard são tratados adiante
    _WIZARD_BUTTONS = {"cancelar", "⏭️ Pular RPC", "⬅️ Voltar", "⬅️ Menu"}
    if txt in _KNOWN_BUTTONS and txt not in _WIZARD_BUTTONS:
        upsert_user(m.chat.id, pending="")
        bot.send_message(m.chat.id, "↩️ Ação cancelada.", reply_markup=main_kb())
        return

    if txt.lower() == "cancelar":
        upsert_user(m.chat.id, pending="")
        send_support(m.chat.id, "↩️ Ação cancelada.", reply_markup=main_kb())
        return

    if txt == "⬅️ Voltar":
        upsert_user(m.chat.id, pending="")
        send_support(m.chat.id, "↩️ Menu principal.", reply_markup=main_kb())
        return

    # 1) Wizard Conectar
    if u["pending"] == "ASK_WALLET":
        if not (txt.startswith("0x") and len(txt) == 42):
            return send_support(m.chat.id, "⚠️ Wallet inválida. Envie no formato 0x...", reply_markup=types.ReplyKeyboardRemove())
        # Normaliza para checksum EIP-55 (evita duplicatas por case diferente)
        try:
            txt = Web3.to_checksum_address(txt)
        except Exception:
            return send_support(m.chat.id, "⚠️ Endereço inválido. Verifique e tente novamente.", reply_markup=types.ReplyKeyboardRemove())
        # ── Fase C: verifica se wallet é conhecida on-chain
        kw = get_known_wallet(txt)
        if kw and kw["trade_count"] > 0:
            _auto_connect_wallet(m, txt)
        else:
            upsert_user(m.chat.id, wallet=txt.lower(), pending="ASK_RPC")
            send_support(m.chat.id, "✅ Salvo!\nPasso 2: Envie sua RPC (http...).", reply_markup=types.ReplyKeyboardRemove())
        return

    if u["pending"] == "ASK_RPC":
        pulou = (txt == "⏭️ Pular RPC")
        if not pulou and not txt.startswith("http"):
            return send_support(
                m.chat.id,
                "⚠️ RPC inválida. Deve começar com <code>http</code>.\n\nOu use <b>⏭️ Pular RPC</b> para continuar sem RPC.",
                reply_markup=_rpc_skip_kb()
            )
        rpc_val = "" if pulou else txt
        # Se wallet já tem env detectado (wallet conhecida), finaliza aqui
        if u.get("env") and u["env"] not in ("", "AG_C_bd"):
            upsert_user(m.chat.id, rpc=rpc_val, active=1, pending="")
            kw = get_known_wallet(u.get("wallet", ""))
            if kw:
                mark_known_wallet_registered(u.get("wallet", ""))
            rpc_msg = "RPC salvo." if not pulou else "RPC pulado."
            send_support(
                m.chat.id,
                f"✅ <b>Conexão concluída!</b>\n\n"
                f"• Wallet: <code>{str(u.get('wallet',''))[:10]}...{str(u.get('wallet',''))[-6:]}</code>\n"
                f"• Ambiente: <b>{esc(u['env'])}</b>\n"
                f"• {rpc_msg}\n\n"
                f"▶️ Monitoramento <b>ativado</b>.",
                reply_markup=main_kb()
            )
        else:
            # Wallet desconhecida — ainda precisa escolher env
            upsert_user(m.chat.id, rpc=rpc_val, pending="ASK_ENV")
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row("AG_C_bd", "bd_v5")
            send_support(m.chat.id, "✅ Salvo!\nPasso 3: Escolha o ambiente:", reply_markup=kb)
        return

    if u["pending"] == "ASK_ENV":
        if txt not in ["AG_C_bd", "bd_v5"]:
            return send_support(m.chat.id, "⚠️ Escolha válida: AG_C_bd ou bd_v5.", reply_markup=main_kb())
        upsert_user(m.chat.id, env=txt, active=1, pending="")
        send_support(m.chat.id, f"✅ Configurado: <b>{txt}</b>\n▶️ Monitoramento ativado.", reply_markup=main_kb())
        return

    # 2) Wizard Período
    if u["pending"] == "ASK_PERIOD":
        if txt not in ("24h", "7d", "30d"):
            return send_support(m.chat.id, "⚠️ Selecione: 24h / 7d / 30d.", reply_markup=main_kb())
        upsert_user(m.chat.id, periodo=txt, pending="")
        send_support(m.chat.id, f"🗓️ Período atualizado para <b>{esc(txt)}</b>.", reply_markup=main_kb())
        return

    # 3) Wizard Filtro Subconta
    if u["pending"] == "ASK_FILTER_SUB":
        if txt.lower() in ("todas", "all"):
            upsert_user(m.chat.id, sub_filter="", pending="")
            return send_support(m.chat.id, "🎛️ Filtro aplicado: <b>Todas</b>.", reply_markup=main_kb())

        upsert_user(m.chat.id, sub_filter=txt.strip(), pending="")
        return send_support(m.chat.id, f"🎛️ Filtro aplicado: <b>{esc(txt.strip())}</b>.", reply_markup=main_kb())

    # 4) Wizard Buscar Tx
    if u["pending"] == "ASK_TX":
        txh = txt.strip()
        if not txh.startswith("0x") or len(txh) < 20:
            return send_support(m.chat.id, "⚠️ Tx inválida. Envie no formato 0x...", reply_markup=types.ReplyKeyboardRemove())
        upsert_user(m.chat.id, pending="")

        r = find_tx_in_db(txh)
        if not r:
            return send_support(m.chat.id, "❌ Não encontrei essa tx no DB (ainda).\n\nDica: rode um 🔄 Sync OnChain para o range do bloco.", reply_markup=main_kb())

        # PnL do dia para esta wallet
        _pnl_dia = 0.0
        try:
            with DB_LOCK:
                _prow = cursor.execute("""
                    SELECT SUM(CAST(o.valor AS REAL) - CAST(o.gas_usd AS REAL))
                    FROM operacoes o
                    JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                    WHERE LOWER(ow.wallet)=? AND o.tipo='Trade'
                      AND DATE(o.data_hora)=DATE(?)
                """, (r["wallet"].lower(), r["data_hora"])).fetchone()
            _pnl_dia = float(_prow[0] or 0) if _prow else 0.0
        except Exception:
            pass

        _pnl_sign2 = "+" if _pnl_dia >= 0 else ""
        _poly = f"https://polygonscan.com/tx/{normalize_txhash(txh)}"

        msg = (
            f"🔍 <b>TX ENCONTRADA</b>\n\n"
            f"🕒 {code(r['data_hora'])}\n"
            f"📦 Tipo: <b>{esc(r['tipo'])}</b>\n"
            f"👤 Sub: {code(r['sub'])}\n"
            f"💰 Valor: <b>{r['valor']:+.6f}</b> {esc(r['token'])}\n"
            f"⛽ Gás: <b>${r['gas_usd']:.4f}</b>\n"
            f"🧱 Bloco: {code(r['bloco'])}\n"
            f"👛 Wallet: {code((r['wallet'][:10]+'...'+r['wallet'][-6:]) if r['wallet'] else '-')}\n"
            f"📊  PnL do dia (wallet): <b>{_pnl_sign2}${_pnl_dia:.2f} USD</b>\n"
            f'🔗  <a href="{_poly}">Ver no Polygonscan ↗</a>\n'
        )
        return send_support(m.chat.id, msg, reply_markup=main_kb(), disable_web_page_preview=True)

    # 5) Wizard Sync Range
    if u["pending"] == "ASK_SYNC_FROM":
        fb = _parse_block(txt)
        if fb is None:
            return send_support(m.chat.id, "⚠️ fromBlock inválido. Envie número (ex 60000000) ou <b>auto</b>.", reply_markup=types.ReplyKeyboardRemove())
        set_config(f"sync_tmp_from_{m.chat.id}", str(fb))
        upsert_user(m.chat.id, pending="ASK_SYNC_TO")

        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("auto", "⬅️ Voltar")
        send_support(
            m.chat.id,
            "Passo 2: envie <b>toBlock</b> (ex: 60005000)\n"
            "ou <b>auto</b> (usa bloco atual).",
            reply_markup=kb
        )
        return

    if u["pending"] == "ASK_SYNC_TO":
        tb = _parse_block(txt)
        if tb is None:
            return send_support(m.chat.id, "⚠️ toBlock inválido. Envie número (ex 60005000) ou <b>auto</b>.", reply_markup=types.ReplyKeyboardRemove())

        try:
            fb_raw = int(get_config(f"sync_tmp_from_{m.chat.id}", "-1"))
        except Exception:
            fb_raw = -1

        env = (u.get("env") or "AG_C_bd").strip()
        try:
            current_blk = int(web3.eth.block_number)
        except Exception:
            current_blk = 0

        if tb == -1:
            tb = current_blk

        if fb_raw == -1:
            last = _get_last_sync(env)
            if last > 0:
                fb = max(1, last + 1)
            else:
                fb = max(1, tb - 10000)
        else:
            fb = fb_raw

        if tb <= 0 or fb <= 0:
            upsert_user(m.chat.id, pending="")
            return send_support(m.chat.id, "⚠️ Range inválido.", reply_markup=main_kb())

        if fb > tb:
            fb, tb = tb, fb

        upsert_user(m.chat.id, pending="")
        t = threading.Thread(target=_sync_thread, args=(m.chat.id, env, fb, tb), daemon=True)
        t.start()
        return

    upsert_user(m.chat.id, pending="")
    send_support(m.chat.id, "Ok.", reply_markup=main_kb())


# ==============================================================================
# 📤 Export CSV
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "📤 Export CSV")
@require_auth
def export_csv(m, u):
    bot.send_chat_action(m.chat.id, "typing")
    hours = period_to_hours(u.get("periodo") or "24h")
    dt = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    extra_sql, extra_params = get_user_filter_clause(u)

    with DB_LOCK:
        cursor.execute(f"""
            SELECT o.data_hora, o.tipo, o.sub_conta, o.valor, o.gas_usd, o.token, o.bloco, o.hash
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=? {extra_sql}
            ORDER BY o.data_hora ASC
        """, (dt, u["wallet"], *extra_params))
        rows = cursor.fetchall()

    if not rows:
        return send_support(m.chat.id, "⚠️ Sem trades para exportar (com o filtro atual).", reply_markup=main_kb())

    filename = f"webdex_export_{u['wallet'][:6]}_{u.get('periodo','24h')}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["data_hora","tipo","sub_conta","valor","gas_usd","token","bloco","tx_hash"])
        for dh,tp,sub,v,g,tk,bl,txh in rows:
            w.writerow([dh,tp,sub,f"{float(v or 0.0):.8f}",f"{float(g or 0.0):.8f}",tk,bl,txh])

    try:
        with open(filename, "rb") as f:
            bot.send_document(m.chat.id, f, caption=f"📤 Export CSV ({esc(u.get('periodo','24h'))})", reply_markup=main_kb())
    except Exception as e:
        send_support(m.chat.id, f"⚠️ Falha ao enviar CSV: {code(e)}", reply_markup=main_kb())


# ==============================================================================
# 🗞️ Resumo Semanal — últimos 7d
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🗞️ Resumo Semanal")
@require_auth
def resumo_semanal(m, u):
    bot.send_chat_action(m.chat.id, "typing")
    dt = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    with DB_LOCK:
        cursor.execute("""
            SELECT o.sub_conta, SUM(o.valor) as s_val, SUM(o.gas_usd) as s_gas, COUNT(*)
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=?
            GROUP BY o.sub_conta
        """, (dt, u["wallet"]))
        rows = cursor.fetchall()

    if not rows:
        return send_support(m.chat.id, "⚠️ Sem trades na última semana.", reply_markup=main_kb())

    rank = []
    total_liq = 0.0
    total_trades = 0
    for sub, s_val, s_gas, cnt in rows:
        liq = float(s_val or 0.0) - float(s_gas or 0.0)
        total_liq += liq
        total_trades += int(cnt or 0)
        rank.append((liq, str(sub), int(cnt)))

    rank.sort(key=lambda x: x[0], reverse=True)
    top = rank[:10]

    out = [f"🗞️ <b>RESUMO SEMANAL (7d)</b>"]
    out.append(f"💰 Líquido total: <b>${total_liq:+.4f}</b> | Trades: <b>{total_trades}</b>")
    out.append("")
    out.append("🏆 Top Subcontas (liq):")
    for i,(liq, sub, cnt) in enumerate(top, start=1):
        dot = "🟢" if liq >= 0 else "🔴"
        out.append(f"{i:02d}) {dot} {esc(sub)} — <b>${liq:+.4f}</b> | trades {cnt}")

    send_support(m.chat.id, "\n".join(out), reply_markup=main_kb())


# ==============================================================================
# 🖼️ Dashboard PRO — Gráficos (Equity / Gás / Distribuição)
# ==============================================================================
def _dash_cache_key(u, sf: str, per: str) -> str:
    raw = f"{u.get('wallet','').lower()}|{sf}|{per}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _dash_make_graphs(nets):
    """Gera 3 gráficos e retorna paths. nets: lista (dh, sub, net, gas_usd)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = list(range(len(nets)))
    net_series = [float(net) for _, _, net, _ in nets]
    gas_series = [float(g) for _, _, _, g in nets]

    equity = []
    acc = 0.0
    for v in net_series:
        acc += v
        equity.append(acc)

    out_paths = []

    def _save_fig(fig, name):
        tmp_dir = os.path.join(os.path.dirname(__file__), "dash_imgs")
        os.makedirs(tmp_dir, exist_ok=True)
        p = os.path.join(tmp_dir, name)
        fig.savefig(p, dpi=140, bbox_inches="tight")
        plt.close(fig)
        return p

    # 1) Equity
    fig = plt.figure()
    plt.plot(x, equity)
    plt.title("WEbdEX — Equity (Líquido acumulado)")
    plt.xlabel("Trades")
    plt.ylabel("USD")
    out_paths.append(_save_fig(fig, "equity.png"))

    # 2) Gas per trade
    fig = plt.figure()
    plt.bar(x, gas_series)
    plt.title("WEbdEX — Gás por Trade (USD)")
    plt.xlabel("Trades")
    plt.ylabel("USD")
    out_paths.append(_save_fig(fig, "gas.png"))

    # 3) Distribution histogram
    fig = plt.figure()
    bins = min(20, max(5, int(len(net_series) ** 0.5)))
    plt.hist(net_series, bins=bins)
    plt.title("WEbdEX — Distribuição de Resultados (Net/Trade)")
    plt.xlabel("USD por trade")
    plt.ylabel("Frequência")
    out_paths.append(_save_fig(fig, "dist.png"))

    return out_paths


def _dash_send_graphs(chat_id: int, u, sf: str, per: str, nets):
    key = _dash_cache_key(u, sf, per)
    now = time.time()
    cached = DASH_GRAPH_CACHE.get(key)
    if cached and (now - cached.get("ts", 0) <= DASH_GRAPH_TTL) and cached.get("paths"):
        paths = cached["paths"]
    else:
        paths = _dash_make_graphs(nets)
        DASH_GRAPH_CACHE[key] = {"ts": now, "paths": paths}

    captions = [
        f"📈 EQUITY — WEbdEX\n🗓️ Período: {per}\n🎛️ Filtro: {sf or 'Todas'}",
        f"⛽ GÁS POR TRADE — WEbdEX\n🗓️ Período: {per}",
        f"📊 DISTRIBUIÇÃO — WEbdEX\n🗓️ Período: {per}",
    ]
    for p, cap in zip(paths, captions):
        try:
            with open(p, "rb") as f:
                bot.send_photo(chat_id, f, caption=cap)
        except Exception:
            pass


# ==============================================================================
# 📊 mybdBook — delegação para reports handler (handlers/reports.py)
# ==============================================================================
@bot.message_handler(func=lambda m: (m.text or "").strip() in {"📊 mybdBook", "📊 Meu mybdBook"})
@require_auth
def myfxbook_user(m, u):
    from webdex_handlers.reports import _handle_myfxbook_user
    _handle_myfxbook_user(m, u)


@bot.message_handler(func=lambda m: (m.text or "").strip() in {"📈 mybdBook (Gráfico)"})
@require_auth
def myfxbook_user_chart(m, u):
    from webdex_handlers.reports import _handle_myfxbook_user_chart
    _handle_myfxbook_user_chart(m, u)


# ==============================================================================
# ⏳ INATIVIDADE — Relatório (com filtro)
# ==============================================================================
@bot.message_handler(func=lambda m: (m.text or "").strip() and "Inatividade" in (m.text or ""))
@require_auth
def inatividade_report(m, u):
    # 🔥 Inatividade PRO-lite (cache): atividade dos últimos 100 blocos
    try:
        # usa cache de 5 min (último registro)
        row = cursor.execute("SELECT start_block,end_block,minutes,tx_count,tx_per_min,accounts_in_cycle,cycle_est_min,created_at FROM inactivity_stats ORDER BY id DESC LIMIT 1").fetchone()
        use_cache = False
        if row and row[7]:
            try:
                use_cache = True
            except Exception:
                use_cache = False

        if use_cache:
            stats = {
                "start_block": int(row[0] or 0),
                "end_block": int(row[1] or 0),
                "minutes": float(row[2] or 0.0),
                "tx_count": int(row[3] or 0),
                "tx_per_min": float(row[4] or 0.0),
                "accounts": int(row[5] or 0),
                "cycle_est_min": float(row[6] or 0.0),
            }
        else:
            from webdex_handlers.admin import _inactivity_pro_compute, _inactivity_pro_reading
            stats = _inactivity_pro_compute(web3, blocks=100)
            try:
                cursor.execute(
                    "INSERT INTO inactivity_stats(end_block,start_block,minutes,tx_count,tx_per_min,accounts_in_cycle,cycle_est_min,note,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        int(stats["end_block"]), int(stats["start_block"]), float(stats["minutes"]), int(stats["tx_count"]),
                        float(stats["tx_per_min"]), int(stats["accounts"]), float(stats["cycle_est_min"]),
                        "auto-lite", now_br()
                    )
                )
                conn.commit()
            except Exception:
                pass

        from webdex_handlers.admin import _inactivity_pro_reading
        reading = _inactivity_pro_reading(stats["tx_per_min"], stats["accounts"], stats["cycle_est_min"])
        header = f"""⏳ <b>INATIVIDADE — Status do Protocolo</b>

📊 <b>Atividade (últimos 100 blocos)</b>
⛓️ {stats['start_block']} → {stats['end_block']}
⏱️ {stats['minutes']:.2f} min | 🔁 {stats['tx_count']} tx | {stats['tx_per_min']:.2f} tx/min
👥 {stats['accounts']:,} contas | ⏳ ciclo ~ {stats['cycle_est_min']:.0f} min

🧠 <b>Leitura Inteligente</b>
{reading}

"""
    except Exception:
        header = ""

    hours = period_to_hours(u.get("periodo") or "24h")
    sf = (u.get("sub_filter") or "").strip()
    only_sub = sf if sf else ""

    data = get_last_trade_by_sub(u["wallet"], hours=hours, only_sub=only_sub)

    if not data:
        return send_support(
            m.chat.id,
            "⚠️ Sem trades no período atual para calcular inatividade (com o filtro atual).",
            reply_markup=main_kb()
        )

    rows = []
    for sub, meta in data.items():
        mins = _minutes_since(meta.get("last_dh", ""))
        rows.append((mins, sub, meta.get("last_dh", ""), int(meta.get("n", 0))))

    rows.sort(key=lambda x: x[0], reverse=True)

    lim = float(LIMITE_INATIV_MIN)
    out = []
    if header:
        out.append(header.strip())
    out.append("📌 <b>Subcontas sem trade</b> (detalhe)")
    out.append(f"🗓️ Período: <b>{esc(u.get('periodo','24h'))}</b>")
    out.append(f"🎛️ Filtro: <b>{esc(sf) if sf else 'Todas'}</b>")
    out.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    above = sum(1 for mins, *_ in rows if mins >= lim)
    out.append(f"⚙️ Limite (config): <b>{int(lim)} min</b>")
    out.append(f"🚨 Subcontas acima do limite: <b>{above}</b>")
    out.append("")
    out.append("📌 Top Inatividade (desde último trade):")
    for i, (mins, sub, last_dh, n) in enumerate(rows[:15], start=1):
        flag = "🔴" if mins >= lim else "🟢"
        out.append(f"{i:02d}) {flag} {code(sub)} — <b>{mins:.0f} min</b> | trades {n} | last {code(last_dh)}")

    send_support(m.chat.id, "\n".join(out), reply_markup=main_kb())


# ==============================================================================
# 🗑️ LGPD — /esquecer_tudo (Story 12.1)
# ==============================================================================

# Confirmações pendentes: chat_id → timestamp da solicitação
_lgpd_pending: dict = {}
_LGPD_TIMEOUT = 60  # segundos para confirmar

@bot.message_handler(commands=["esquecer_tudo"])
def cmd_esquecer_tudo(m):
    """Inicia fluxo LGPD de deleção de memória IA."""
    _lgpd_pending[m.chat.id] = time.time()
    bot.send_message(
        m.chat.id,
        "⚠️ <b>Atenção: Deleção de Memória</b>\n\n"
        "Isso apagará <b>TODA</b> a sua memória do bdZinho.\n"
        "O assistente não se lembrará de nenhuma conversa anterior.\n\n"
        "Para confirmar, envie /confirmar_esquecimento\n"
        "Para cancelar, ignore (expira em 60 segundos).",
        parse_mode="HTML"
    )


@bot.message_handler(commands=["confirmar_esquecimento"])
def cmd_confirmar_esquecimento(m):
    """Executa deleção de memória após confirmação."""
    ts = _lgpd_pending.pop(m.chat.id, None)
    if ts is None or (time.time() - ts) > _LGPD_TIMEOUT:
        bot.send_message(
            m.chat.id,
            "❌ Solicitação expirada ou não iniciada. Use /esquecer_tudo primeiro."
        )
        return
    try:
        from webdex_ai import mem_clear_lgpd
        deleted = mem_clear_lgpd(m.chat.id)
        bot.send_message(
            m.chat.id,
            f"🗑️ <b>Memória apagada com sucesso.</b>\n\n"
            f"O bdZinho não se lembrará de nenhuma conversa anterior.\n"
            f"({deleted} mensagens removidas)",
            parse_mode="HTML",
            reply_markup=main_kb()
        )
        logger.info("[user] LGPD: memória deletada para chat_id=%s (%d registros)", m.chat.id, deleted)
    except Exception as e:
        logger.error("[user] Falha ao deletar memória LGPD (chat_id=%s): %s", m.chat.id, e)


# ==============================================================================
# 🔐 SUBSCRIPTION TIER — Story 14.3
# ==============================================================================
_sub_tier_cache: dict[int, tuple[str, float]] = {}  # chat_id → (tier, timestamp)
_SUB_TIER_CACHE_TTL = 300  # 5 minutos
_sub_tier_lock = threading.Lock()


def check_subscription_tier(chat_id: int) -> str:
    """
    Retorna o tier de subscription ativo para o chat_id.
    Consulta a tabela `subscriptions` e cacheia o resultado por 5 minutos.
    Retorna 'pro' se assinatura ativa e não expirada, 'free' caso contrário.
    Graceful degradation: retorna 'free' em caso de erro de DB.
    """
    now = time.time()

    # Verificar cache
    with _sub_tier_lock:
        cached = _sub_tier_cache.get(chat_id)
        if cached is not None:
            tier, ts = cached
            if now - ts < _SUB_TIER_CACHE_TTL:
                return tier

    try:
        now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with DB_LOCK:
            row = cursor.execute(
                """
                SELECT tier FROM subscriptions
                WHERE chat_id = ?
                  AND status = 'active'
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY expires_at DESC
                LIMIT 1
                """,
                (chat_id, now_utc),
            ).fetchone()

        tier = row[0] if row else "free"

    except Exception as e:
        logger.debug("[sub_tier] Erro ao consultar subscription para chat_id=%s: %s", chat_id, e)
        tier = "free"

    # Atualizar cache
    with _sub_tier_lock:
        _sub_tier_cache[chat_id] = (tier, now)

    return tier


# ==============================================================================
# 🎨 CRIAR IMAGEM — Nano Banana / Gemini via OpenRouter
# ==============================================================================

def _img_throttle(user_id: int) -> float:
    """
    Verifica cooldown de geração de imagem.
    Retorna 0 se liberado, ou segundos restantes se ainda em cooldown.
    """
    now = time.time()
    with _img_rate_lock:
        last = _img_rate_cache.get(user_id, 0.0)
        remaining = IMAGE_GEN_COOLDOWN_S - (now - last)
        if remaining > 0:
            return remaining
        _img_rate_cache[user_id] = now
        return 0.0


@bot.message_handler(func=lambda m: (m.text or "").strip() == "🎨 Criar Imagem")
def img_gen_menu(m):
    chat_id = m.chat.id

    if not _IMG_GEN_AVAILABLE:
        bot.send_message(
            chat_id,
            "🎨 <b>Criar Imagem</b>\n\n"
            "⚠️ Geração de imagens não disponível no momento.\n"
            "Verifique se <code>OPENROUTER_API_KEY</code> está configurada.",
            parse_mode="HTML",
            reply_markup=main_kb(chat_id),
        )
        return

    bot.send_message(
        chat_id,
        "🎨 <b>Criar Imagem com IA</b>\n\n"
        "Descreva a imagem que você quer gerar.\n\n"
        "<b>Exemplos:</b>\n"
        "• Um robô DeFi no espaço com neons azuis\n"
        "• Gráfico de lucro explodindo com confetes\n"
        "• Mascote WEbdEX celebrando um win\n\n"
        "💡 <i>Escreva em português ou inglês.</i>\n"
        "❌ Para cancelar, escreva /cancelar",
        parse_mode="HTML",
        reply_markup=types.ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(m, img_gen_step)


def img_gen_step(m):
    """Recebe o prompt do usuário e gera a imagem."""
    import io as _io

    chat_id = m.chat.id
    prompt  = (m.text or "").strip()

    if prompt.lower() in ("/cancelar", "cancelar", "/cancel"):
        bot.send_message(chat_id, "✅ Geração cancelada.", reply_markup=main_kb(chat_id))
        return

    if not prompt:
        bot.send_message(
            chat_id,
            "⚠️ Prompt vazio. Tente novamente com /criar_imagem ou o botão 🎨.",
            reply_markup=main_kb(chat_id),
        )
        return

    # Rate limit
    remaining = _img_throttle(chat_id)
    if remaining > 0:
        bot.send_message(
            chat_id,
            f"⏳ Aguarde <b>{int(remaining)}s</b> antes de gerar outra imagem.",
            parse_mode="HTML",
            reply_markup=main_kb(chat_id),
        )
        return

    # Feedback imediato
    wait_msg = bot.send_message(
        chat_id,
        "🎨 <b>Gerando sua imagem...</b> ⏳\n\n"
        "<i>Isso pode levar até 30 segundos.</i>",
        parse_mode="HTML",
    )

    try:
        img_bytes = _img_gen(prompt)
    except Exception as e:
        logger.warning("[img_gen] Erro ao gerar imagem: %s", e)
        img_bytes = None

    # Remove mensagem de espera
    try:
        bot.delete_message(chat_id, wait_msg.message_id)
    except Exception:
        pass

    if not img_bytes:
        bot.send_message(
            chat_id,
            "❌ <b>Falha ao gerar imagem.</b>\n\n"
            "O serviço pode estar temporariamente indisponível. Tente novamente em instantes.",
            parse_mode="HTML",
            reply_markup=main_kb(chat_id),
        )
        return

    caption = f"🎨 <b>WEbdEX AI Art</b>\n<i>{prompt[:120]}</i>"
    try:
        bot.send_photo(
            chat_id,
            _io.BytesIO(img_bytes),
            caption=caption,
            parse_mode="HTML",
            reply_markup=main_kb(chat_id),
        )
        logger.info("[img_gen] Imagem enviada para chat_id=%s | prompt=%s...", chat_id, prompt[:60])
    except Exception as e:
        logger.warning("[img_gen] Falha ao enviar foto para chat_id=%s: %s", chat_id, e)
        bot.send_message(
            chat_id,
            "⚠️ Imagem gerada mas falhou ao enviar. Tente novamente.",
            reply_markup=main_kb(chat_id),
        )


# ==============================================================================
# 👁️ VISION: análise de imagens enviadas pelo usuário
# ==============================================================================

@bot.message_handler(content_types=["photo"])
def vision_photo_handler(m):
    """
    Usuário envia uma foto → bdZinho analisa via Gemini Vision.
    Suporta: charts, dashboards, screenshots de carteira, gráficos on-chain.
    """
    import io as _io2

    chat_id = m.chat.id

    if not _VISION_AVAILABLE:
        return  # módulo indisponível — silencioso

    # Rate limit
    now = time.time()
    with _vision_rate_lock:
        last = _vision_rate_cache.get(chat_id, 0.0)
        remaining = _VISION_COOLDOWN_S - (now - last)
        if remaining > 0:
            bot.send_message(
                chat_id,
                f"⏳ Aguarde <b>{int(remaining)}s</b> antes de enviar outra imagem.",
                parse_mode="HTML",
            )
            return
        _vision_rate_cache[chat_id] = now

    # Mensagem de espera
    wait_msg = bot.send_message(
        chat_id,
        "👁️ <b>bdZinho analisando sua imagem...</b> ⏳\n"
        "<i>Pode levar até 15 segundos.</i>",
        parse_mode="HTML",
    )

    try:
        # Baixar a maior versão disponível da foto
        file_id   = m.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)

        # Captura a legenda/pergunta do usuário (se enviou junto com a foto)
        question = (m.caption or "").strip()

        # Perfil do trader para enriquecer análise
        profile_context = ""
        if _VISION_PROFILE_ENABLED and _profile_ctx:
            try:
                profile_context = _profile_ctx(chat_id) or ""
            except Exception:
                pass

        # Analisar via Vision
        analysis = _vision_analyze(  # type: ignore
            image_bytes=file_bytes,
            question=question,
            profile_context=profile_context,
        )
    except Exception as e:
        logger.warning("[vision] Erro ao processar foto chat_id=%s: %s", chat_id, e)
        analysis = None

    # Remove mensagem de espera
    try:
        bot.delete_message(chat_id, wait_msg.message_id)
    except Exception:
        pass

    if not analysis:
        bot.send_message(
            chat_id,
            "❌ <b>Não consegui analisar a imagem.</b>\n\n"
            "Verifique se a imagem está nítida e tente novamente.",
            parse_mode="HTML",
            reply_markup=main_kb(chat_id),
        )
        return

    bot.send_message(
        chat_id,
        f"👁️ <b>Análise bdZinho:</b>\n\n{analysis}",
        parse_mode="HTML",
        reply_markup=main_kb(chat_id),
    )
    logger.info("[vision] Análise enviada para chat_id=%s", chat_id)
