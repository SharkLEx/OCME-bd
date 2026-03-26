from __future__ import annotations
# ==============================================================================
# webdex_handlers/admin.py — WEbdEX Monitor Engine
# Extraído de WEbdEX_V30_24_SPEED_PATCH_FIXED.py
# Linhas fonte: ~2902-4754 (ADM handlers)
# ==============================================================================

import time, json, threading
from datetime import datetime, timedelta
from typing import Any, Dict, List

from webdex_config import (
    logger, Web3, CONTRACTS, ABI_SUBACCOUNTS, ABI_MANAGER,
)
from webdex_db import (
    DB_LOCK, conn, cursor, get_config, set_config, now_br,
    get_user, period_to_hours, _period_since, _period_label,
    reload_limites, LIMITE_GWEI, LIMITE_GAS_BAIXO_POL, LIMITE_INATIV_MIN,
    _set_limit, normalize_txhash,
    get_known_wallets_unregistered,
    load_trade_times_by_sub, ciclo_stats, consist_score,
)
from webdex_bot_core import (
    bot, send_html, send_support, _send, _send_long, _clear_pending,
    _is_admin, is_admin_chat, is_admin, esc, code, barra_progresso,
    _get_admin_chat_ids, get_token_meta,
)
from webdex_chain import (
    web3, CONTRACTS_A, CONTRACTS_B, get_contracts,
    web3_for_rpc, obter_preco_pol, get_active_wallet_map,
)

import telebot
from telebot import types

# Forward-declare require_auth (defined in user.py, imported via main)
def _get_require_auth():
    from webdex_handlers.user import require_auth
    return require_auth

def _get_main_kb():
    from webdex_handlers.user import main_kb
    return main_kb

def _get_username_from_db(chat_id: int):
    from webdex_db import _get_username_from_db as _fn
    return _fn(chat_id)

def _medal(pos: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"{pos:02d} ")


# ==============================================================================
# 🎛️ ADM KEYBOARDS & MENUS
# ==============================================================================
def adm_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🧠 IA Governança", "⚙️ Limites")
    kb.row("👥 ADM PRO", "⏳ Inatividade PRO")
    kb.row("📊 Análise SubAccounts")
    kb.row("📊 Relatório Institucional")
    kb.row("📊 mybdBook ADM")
    kb.row("📈 Lucro Real (Total/Ambiente)")
    kb.row("💎 Lucro Total do Protocolo")
    kb.row("🧾 Fornecimento e Liquidez")
    kb.row("📸 Progressão do Capital")
    kb.row("📨 Gerar Convites", "📢 Broadcast")
    kb.row("📡 Status Monitor")
    kb.row("🤖 Content Engine")
    kb.row("🔙 Menu")
    return kb

def adm_pro_menu(m, u=None):
    if not _is_admin(m.chat.id):
        bot.send_message(m.chat.id, "⚠️ Acesso restrito.", reply_markup=_get_main_kb()())
        return
    bot.send_chat_action(m.chat.id, "typing")
    try:
        msg = _adm_pro_report()
        _send_long(m.chat.id, msg, reply_markup=adm_kb())
    except Exception as e:
        logger.error("[admin] %s", e)
        send_support(m.chat.id, "⚠️ Erro ao gerar relatório ADM PRO.", reply_markup=adm_kb())

def adm_menu(m, u=None, *args, **kwargs):
    from webdex_db import ai_global_enabled, ai_admin_only, ai_mode
    _clear_pending(m.chat.id)
    from webdex_db import touch_user
    touch_user(m.chat.id, getattr(m.from_user, "username", None))
    if not _is_admin(m.chat.id):
        bot.send_message(m.chat.id, "⚠️ Acesso restrito.", reply_markup=_get_main_kb()())
        return
    total = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active = cursor.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
    try:
        since = time.time() - 24*3600
        online24 = cursor.execute("SELECT COUNT(*) FROM users WHERE COALESCE(last_seen_ts,0) >= ?", (since,)).fetchone()[0]
    except Exception:
        online24 = 0
    g = "ON" if ai_global_enabled() else "OFF"
    only = "ON" if ai_admin_only() else "OFF"
    mode = "DEV" if ai_mode() == "dev" else "COMUNIDADE"
    msg = (
        "🛠️ ADM — WEbdEX\n\n"
        f"👥 Usuários totais: {total}\n"
        f"✅ Ativos (alerts=ON): {active}\n"
        f"🟢 Online (últimas 24h): {online24}\n\n"
        "🧠 IA (Governança)\n"
        f"• Global: {g}\n"
        f"• ADM-only: {only}\n"
        f"• Modo: {mode}\n\n"
        "Ações rápidas:\n"
        "• Use os botões abaixo para governar a IA.\n"
        "• Use: 📈 Dashboard PRO / 🏆 Ranking Lucro\n"
    )
    bot.send_message(m.chat.id, msg, reply_markup=adm_kb())


# ==============================================================================
# 🛠️ ADM > ADM PRO helpers (declarados antes dos handlers)
# ==============================================================================
_STABLE_SYMS = {"USDT", "USDC", "DAI", "USDT0", "LP-USD", "LP-USDT0", "LP-V5", "LP-USDC", "LP-DAI"}
_CAPITAL_CACHE_TTL = 10 * 60

def _env_label(env):
    e = (env or "").strip().lower()
    if not e: return "Inativo"
    if "ag" in e and "bd" in e: return "AG_bd"
    if "v5" in e: return "V5"
    return env or "Inativo"

def _iter_linked_users():
    with DB_LOCK:
        cur = conn.cursor()
        cur.execute(
            "SELECT chat_id, COALESCE(env,''), COALESCE(wallet,''), COALESCE(rpc,'') "
            "FROM users WHERE COALESCE(active,0)=1 AND COALESCE(wallet,'')<>''"
        )
        rows = cur.fetchall()
    for chat_id, env, wallet, rpc in rows:
        w = (wallet or "").strip()
        if not w or not w.startswith("0x") or len(w) < 10:
            continue
        yield {"chat_id": int(chat_id), "env": (env or "").strip(), "wallet": w, "rpc": (rpc or "").strip()}

def _capital_cache_set(chat_id: int, env: str, total_usd: float, breakdown: dict):
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO capital_cache(chat_id, env, total_usd, breakdown_json, updated_ts) VALUES(?,?,?,?,?)",
            (chat_id, env, float(total_usd), json.dumps(breakdown, ensure_ascii=False), float(time.time()))
        )
        conn.commit()
    except Exception:
        pass

def _compute_user_capital(urow: dict):
    from webdex_handlers.reports import _mybdbook_fetch_capital_rpc
    env    = urow.get("env") or ""
    wallet = urow.get("wallet") or ""
    rpc    = urow.get("rpc") or ""
    if not wallet or not env:
        return 0.0, {}
    try:
        result = _mybdbook_fetch_capital_rpc(wallet, env, rpc)
        if result.get("ok") and float(result.get("total_usd") or 0) > 0:
            return float(result["total_usd"]), result.get("breakdown") or {}
    except Exception:
        pass
    return 0.0, {}

def _adm_pro_report(limit_users: int = 80) -> str:
    from webdex_db import _ciclo_21h_since, _ciclo_21h_label, now_br
    now_ts = time.time()
    dt_24h = _ciclo_21h_since()   # P&L do ciclo atual (desde 21h)
    dt_7d  = (now_br() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    total_users = int(cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0] or 0)
    active_users = int(cursor.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0] or 0)

    env_rows = cursor.execute("SELECT COALESCE(env,''), COUNT(*) FROM users GROUP BY COALESCE(env,'')").fetchall()
    env_count = {"V5": 0, "AG_bd": 0, "Inativo": 0}
    for ev, cnt in env_rows:
        lbl = _env_label(ev)
        env_count[lbl] = env_count.get(lbl, 0) + int(cnt or 0)

    # Capital por usuário (capital_cache)
    cached_rows = cursor.execute(
        "SELECT u.chat_id, COALESCE(u.env,''), COALESCE(c.total_usd, 0), COALESCE(c.breakdown_json,'{}') "
        "FROM users u LEFT JOIN capital_cache c ON c.chat_id=u.chat_id "
        "WHERE c.updated_ts > ? OR c.updated_ts IS NULL",
        (now_ts - 86400 * 3,)
    ).fetchall()
    per_user = []
    env_cap = {"V5": 0.0, "AG_bd": 0.0, "Inativo": 0.0}
    for cid, ev, tot, brj in cached_rows:
        label = _env_label(ev)
        try:
            br = json.loads(brj or "{}") if isinstance(brj, str) else {}
        except Exception:
            br = {}
        totf = float(tot or 0.0)
        if totf > 0.0:
            per_user.append((totf, int(cid), label, br))
            env_cap[label] = env_cap.get(label, 0.0) + totf
    capital_total = float(sum(x[0] for x in per_user))
    per_user.sort(key=lambda x: x[0], reverse=True)

    # P&L agregado do protocolo (24h e 7d)
    try:
        pnl_24h_row = cursor.execute("""
            SELECT COALESCE(SUM(valor - gas_usd), 0), COUNT(*)
            FROM operacoes WHERE tipo='Trade' AND data_hora >= ?
        """, (dt_24h,)).fetchone()
        pnl_24h  = float(pnl_24h_row[0] or 0)
        trd_24h  = int(pnl_24h_row[1] or 0)
        pnl_7d   = float(cursor.execute("""
            SELECT COALESCE(SUM(valor - gas_usd), 0)
            FROM operacoes WHERE tipo='Trade' AND data_hora >= ?
        """, (dt_7d,)).fetchone()[0] or 0)
    except Exception:
        pnl_24h = pnl_7d = 0.0
        trd_24h = 0

    # Wallets ativas (com trade nas últimas 24h)
    try:
        wallets_ativas_24h = int(cursor.execute("""
            SELECT COUNT(DISTINCT ow.wallet)
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora >= ?
        """, (dt_24h,)).fetchone()[0] or 0)
    except Exception:
        wallets_ativas_24h = 0

    # WinRate geral (24h)
    try:
        wr_row = cursor.execute("""
            SELECT COUNT(CASE WHEN valor > 0 THEN 1 END), COUNT(*)
            FROM operacoes WHERE tipo='Trade' AND data_hora >= ?
        """, (dt_24h,)).fetchone()
        wins_24h   = int(wr_row[0] or 0)
        total_24h  = int(wr_row[1] or 0)
        wr_24h     = wins_24h / total_24h * 100 if total_24h > 0 else 0
    except Exception:
        wr_24h = 0.0

    # Concentração de capital (top 3 wallets / total)
    top3_capital = sum(x[0] for x in per_user[:3])
    conc_pct = top3_capital / capital_total * 100 if capital_total > 0 else 0
    conc_icon = "🔴" if conc_pct > 80 else ("🟡" if conc_pct > 50 else "🟢")

    # Top 15 usuários por capital
    top_n = 15
    top_lines = []
    for tot, cid, label, br in per_user[:top_n]:
        parts = []
        try:
            for k in list(br.keys())[:3]:
                parts.append(f"{esc(str(k)[:10])}:{float(br[k]):.2f}")
        except Exception:
            parts = []
        extra = (" | " + ", ".join(parts)) if parts else ""
        uname = _get_username_from_db(cid)
        uname_txt = f" @{uname}" if uname else ""
        pct_of_total = tot / capital_total * 100 if capital_total > 0 else 0
        top_lines.append(
            f"• <b>{tot:,.2f}</b> ({pct_of_total:.1f}%) — ID {cid}{esc(uname_txt)} [{esc(label)}]{extra}"
        )

    pnl24_sign = "+" if pnl_24h >= 0 else ""
    pnl7d_sign = "+" if pnl_7d >= 0 else ""
    wr_icon = "🟢" if wr_24h >= 55 else ("🟡" if wr_24h >= 40 else "🔴")

    lines = [
        "🛠️ <b>ADM PRO — Governança Viva</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"👥  Usuários:  <b>{total_users}</b> total  ·  <b>{active_users}</b> ativos",
        f"🌐  Ambientes: V5=<b>{env_count.get('V5',0)}</b>  AG_bd=<b>{env_count.get('AG_bd',0)}</b>",
        f"📡  Wallets com trade (24h): <b>{wallets_ativas_24h}</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💰 <b>Capital em Fluxo</b>",
        f"    Total:   <b>${capital_total:,.2f}</b>",
        f"    V5:      <b>${env_cap.get('V5', 0):,.2f}</b>",
        f"    AG_bd:   <b>${env_cap.get('AG_bd', 0):,.2f}</b>",
        f"    {conc_icon} Concentração top3: <b>{conc_pct:.1f}%</b> do capital total",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📊 <b>Performance do Protocolo</b>",
        f"    Trades (ciclo):<b>{trd_24h}</b>",
        f"    {wr_icon} WinRate (ciclo):<b>{wr_24h:.1f}%</b>",
        f"    P&L (ciclo):   <b>{pnl24_sign}${pnl_24h:,.2f}</b>",
        f"    P&L (7d):      <b>{pnl7d_sign}${pnl_7d:,.2f}</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🧮 <b>Top {top_n} por Capital:</b>",
    ]
    lines += top_lines if top_lines else ["• (sem dados de capital ainda)"]
    return "\n".join(lines)


# ==============================================================================
# 📋 LIMITES MENU
# ==============================================================================
def limites_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🔙 ADM")
    return kb

def _limites_inline_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("⚡ GWEI +100",   callback_data="lim_gwei_p"),
        types.InlineKeyboardButton("⚡ GWEI -100",   callback_data="lim_gwei_m"),
    )
    kb.row(
        types.InlineKeyboardButton("⛽ Gás +0.5",    callback_data="lim_gas_p"),
        types.InlineKeyboardButton("⛽ Gás -0.5",    callback_data="lim_gas_m"),
    )
    kb.row(
        types.InlineKeyboardButton("⏱️ Inativ +10m", callback_data="lim_inativ_p"),
        types.InlineKeyboardButton("⏱️ Inativ -10m", callback_data="lim_inativ_m"),
    )
    kb.row(types.InlineKeyboardButton("✅ Fechar", callback_data="lim_close"))
    return kb

def _limites_status_text():
    reload_limites()
    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    lines = [
        "⚙️ <b>LIMITES DO SISTEMA</b>",
        sep,
        "",
        f"  ├─ ⚡ <b>GWEI máx:</b>       <b>{LIMITE_GWEI:.0f} gwei</b>",
        f"  ├─ ⛽ <b>Gás baixo:</b>      <b>{LIMITE_GAS_BAIXO_POL:.2f} POL</b>",
        f"  └─ ⏱️ <b>Inatividade:</b>    <b>{LIMITE_INATIV_MIN:.0f} min</b>",
        "",
        "<i>Ajuste com os botões abaixo. Salva automaticamente.</i>",
    ]
    return "\n".join(lines)

def _adj_and_save(key: str, delta: float, min_v: float, max_v: float, fmt: str):
    reload_limites()
    from webdex_db import LIMITE_GWEI as LG, LIMITE_GAS_BAIXO_POL as LGBP, LIMITE_INATIV_MIN as LIM
    cur = {
        "limite_gwei": LG,
        "limite_gas_baixo_pol": LGBP,
        "limite_inativ_min": LIM,
    }[key]
    newv = float(cur) + float(delta)
    if newv < min_v: newv = min_v
    if newv > max_v: newv = max_v
    _set_limit(key, newv)
    reload_limites()
    return fmt.format(newv)


# ==============================================================================
# 🤖 BOT HANDLERS — ADM
# ==============================================================================
@bot.message_handler(func=lambda m: (m.text or "").strip() == "🛠️ ADM")
def _go_adm(m):
    u = get_user(m.chat.id) or {}
    if not u:
        _clear_pending(m.chat.id)
        bot.reply_to(m, "❌ Você não está cadastrado. Use /start.")
        return
    if not _is_admin(m.chat.id):
        bot.reply_to(m, "⛔ Acesso negado.")
        return
    return adm_menu(m, u)

@bot.message_handler(func=lambda m: (m.text or "").strip() == "🔙 Menu")
def _back_to_main(m):
    _clear_pending(m.chat.id)
    bot.send_message(m.chat.id, "✅ Menu principal.", reply_markup=_get_main_kb()(m.chat.id))

@bot.message_handler(func=lambda m: (m.text or "").strip() == "🔙 ADM")
def _back_to_adm(m):
    _clear_pending(m.chat.id)
    u = get_user(m.chat.id) or {}
    adm_menu(m, u)

# ==============================================================================
# 🧠 IA GOVERNANÇA — painel unificado com toggles inline
# ==============================================================================
def _ia_panel_text():
    from webdex_db import ai_global_enabled, ai_admin_only, ai_mode
    g   = "🟢 ON"  if ai_global_enabled() else "🔴 OFF"
    adm = "🟢 ON"  if ai_admin_only()     else "🔴 OFF"
    m   = "🛠️ DEV" if ai_mode() == "dev"  else "🌐 COMUNIDADE"
    return (
        "🧠 <b>IA Governança</b>\n\n"
        f"• Global:    {g}\n"
        f"• ADM-only:  {adm}\n"
        f"• Modo:      {m}\n\n"
        "<i>Clique para alternar cada opção.</i>"
    )

def _ia_panel_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Global ON/OFF",    callback_data="ia_toggle_global"),
        types.InlineKeyboardButton("🔄 ADM-only ON/OFF",  callback_data="ia_toggle_admin"),
    )
    kb.row(
        types.InlineKeyboardButton("🔄 Modo DEV↔️COMUNIDADE", callback_data="ia_toggle_mode"),
    )
    kb.row(types.InlineKeyboardButton("✅ Fechar", callback_data="ia_close"))
    return kb

@bot.message_handler(func=lambda m: (m.text or "").strip() == "🧠 IA Governança")
def adm_ia_panel(m):
    if not _is_admin(m.chat.id):
        return bot.send_message(m.chat.id, "⚠️ Acesso restrito.", reply_markup=_get_main_kb()())
    bot.send_message(m.chat.id, _ia_panel_text(), parse_mode="HTML", reply_markup=_ia_panel_kb())

@bot.callback_query_handler(func=lambda c: c.data in ("ia_toggle_global", "ia_toggle_admin", "ia_toggle_mode", "ia_close"))
def _ia_panel_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "ia_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    if c.data == "ia_toggle_global":
        from webdex_db import ai_global_enabled
        set_config("ai_global_enabled", "0" if ai_global_enabled() else "1")
        bot.answer_callback_query(c.id, "✅ IA Global alterada!")
    elif c.data == "ia_toggle_admin":
        from webdex_db import ai_admin_only
        set_config("ai_admin_only", "0" if ai_admin_only() else "1")
        bot.answer_callback_query(c.id, "✅ ADM-only alterado!")
    elif c.data == "ia_toggle_mode":
        from webdex_db import ai_mode
        set_config("ai_mode", "community" if ai_mode() == "dev" else "dev")
        bot.answer_callback_query(c.id, "✅ Modo alterado!")
    try:
        bot.edit_message_text(
            _ia_panel_text(), c.message.chat.id, c.message.message_id,
            parse_mode="HTML", reply_markup=_ia_panel_kb()
        )
    except Exception:
        pass

@bot.message_handler(func=lambda m: (m.text or "") == "⚙️ Limites")
def _go_limites_menu(m):
    if not _is_admin(m.chat.id):
        bot.send_message(m.chat.id, "⛔ Acesso negado.", reply_markup=_get_main_kb()())
        return
    bot.send_message(m.chat.id, "⚙️ Painel de Limites", reply_markup=limites_kb())
    bot.send_message(m.chat.id, _limites_status_text(), parse_mode="HTML", reply_markup=_limites_inline_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("lim_"))
def _limites_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "lim_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    try:
        if   c.data == "lim_gwei_p":    tip = _adj_and_save("limite_gwei",          +100, 10,    50000,  "⚡ GWEI: {:.0f}")
        elif c.data == "lim_gwei_m":    tip = _adj_and_save("limite_gwei",          -100, 10,    50000,  "⚡ GWEI: {:.0f}")
        elif c.data == "lim_gas_p":     tip = _adj_and_save("limite_gas_baixo_pol", +0.5, 0.1,  1000,   "⛽ Gás: {:.2f} POL")
        elif c.data == "lim_gas_m":     tip = _adj_and_save("limite_gas_baixo_pol", -0.5, 0.1,  1000,   "⛽ Gás: {:.2f} POL")
        elif c.data == "lim_inativ_p":  tip = _adj_and_save("limite_inativ_min",    +10,  1,    100000, "⏱️ Inativ: {:.0f} min")
        elif c.data == "lim_inativ_m":  tip = _adj_and_save("limite_inativ_min",    -10,  1,    100000, "⏱️ Inativ: {:.0f} min")
        else:                            tip = "✅"
        bot.answer_callback_query(c.id, f"✅ {tip}")
    except Exception as e:
        logger.error("Erro ajustando limites: %s", e)
        bot.answer_callback_query(c.id, "⚠️ Erro ao ajustar.")
    try:
        bot.edit_message_text(
            _limites_status_text(), c.message.chat.id, c.message.message_id,
            parse_mode="HTML", reply_markup=_limites_inline_kb()
        )
    except Exception:
        pass

def _adm_pro_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="admpr_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="admpr_close"),
    )
    return kb

@bot.message_handler(func=lambda m: (m.text or "").strip() == "👥 ADM PRO")
def adm_pro_handler(m):
    if not _is_admin(m.chat.id):
        bot.send_message(m.chat.id, "⚠️ Acesso restrito.", reply_markup=_get_main_kb()())
        return
    bot.send_chat_action(m.chat.id, "typing")
    try:
        _send_long(m.chat.id, _adm_pro_report(), reply_markup=_adm_pro_kb())
    except Exception as e:
        logger.error("[admin] %s", e)
        send_support(m.chat.id, "⚠️ Erro ao gerar relatório ADM PRO.", reply_markup=adm_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("admpr_"))
def _adm_pro_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "admpr_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    bot.answer_callback_query(c.id, "⏳ Atualizando...")
    try:
        bot.edit_message_text(
            _adm_pro_report(), c.message.chat.id, c.message.message_id,
            parse_mode="HTML", reply_markup=_adm_pro_kb()
        )
    except Exception as e:
        logger.error("[admpr] refresh error: %s", e)

def _relatorio_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="relatorio_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="relatorio_close"),
    )
    return kb

def _relatorio_build_text():
    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    with DB_LOCK:
        cur = conn.cursor()

        # 1. Usuários bot por ambiente
        bot_users = cur.execute("""
            SELECT COALESCE(env, 'AG_C_bd') AS env,
                   COUNT(*) AS total,
                   COUNT(CASE WHEN active=1 THEN 1 END) AS ativos
            FROM users
            GROUP BY env
        """).fetchall()
        bot_users = sorted(bot_users, key=lambda r: (0 if "v5" in str(r[0]).lower() else 1))

        total_bot_users  = sum(int(r[1] or 0) for r in bot_users)
        total_bot_ativos = sum(int(r[2] or 0) for r in bot_users)

        # 2. Capital por ambiente — capital_cache (100% DB, zero RPC)
        cap_rows = cur.execute("""
            SELECT COALESCE(cc.env, 'AG_C_bd') AS env,
                   COUNT(*) AS users_com_cap,
                   ROUND(SUM(cc.total_usd), 2) AS capital
            FROM capital_cache cc
            WHERE cc.total_usd > 0.5
            GROUP BY cc.env
        """).fetchall()
        cap_rows = sorted(cap_rows, key=lambda r: (0 if "v5" in str(r[0]).lower() else 1))

        cap_map = {r[0]: {"users": int(r[1]), "capital": float(r[2] or 0)} for r in cap_rows}
        total_capital = sum(v["capital"] for v in cap_map.values())

        # Concentração Top 3 (capital_cache individual)
        all_caps = [float(r[0] or 0) for r in cur.execute(
            "SELECT total_usd FROM capital_cache WHERE total_usd > 0.5 ORDER BY total_usd DESC"
        ).fetchall()]
        top3_pct = (sum(all_caps[:3]) / total_capital * 100) if total_capital > 0 and all_caps else 0.0

        # 3. On-chain por ambiente — protocol_ops
        proto_rows = cur.execute("""
            SELECT COALESCE(env, 'UNKNOWN') AS env,
                   COUNT(DISTINCT wallet)                          AS wallets,
                   COUNT(*)                                        AS trades,
                   ROUND(SUM(profit), 2)                          AS lucro,
                   COUNT(CASE WHEN profit > 0 THEN 1 END)         AS wins,
                   ROUND(SUM(fee_bd), 4)                          AS bd
            FROM protocol_ops
            WHERE wallet != '' AND env != 'UNKNOWN'
            GROUP BY env
        """).fetchall()
        proto_rows = sorted(proto_rows, key=lambda r: (0 if "v5" in str(r[0]).lower() else 1))

        proto_map = {
            r[0]: {"wallets": int(r[1] or 0), "trades": int(r[2] or 0),
                    "lucro": float(r[3] or 0), "wins": int(r[4] or 0), "bd": float(r[5] or 0)}
            for r in proto_rows
        }
        total_wallets = sum(v["wallets"] for v in proto_map.values())
        total_trades  = sum(v["trades"]  for v in proto_map.values())
        total_lucro   = sum(v["lucro"]   for v in proto_map.values())
        total_wins    = sum(v["wins"]    for v in proto_map.values())
        total_bd      = sum(v["bd"]      for v in proto_map.values())
        wr_global     = total_wins / total_trades * 100 if total_trades else 0.0
        cobertura     = (total_bot_ativos / total_wallets * 100) if total_wallets > 0 else 0.0
        sg_lucro      = "🟢" if total_lucro >= 0 else "🔴"

    # ── HEADER ──────────────────────────────────────────────────────────
    lines = [
        "🏛️ <b>RELATÓRIO INSTITUCIONAL — WEbdEX</b>",
        f"🕒 <i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>",
        sep,
        "",
        "🌐 <b>CONSOLIDADO GLOBAL</b>",
        f"  ├─ 👥 Bot: <b>{total_bot_ativos}</b> ativos / <b>{total_bot_users}</b> total",
        f"  ├─ 🔗 On-chain: <b>{total_wallets:,}</b> traders  ·  <b>{total_trades:,}</b> trades",
        f"  ├─ 📡 Cobertura bot: <b>{cobertura:.1f}%</b>  ({total_bot_ativos}/{total_wallets})",
        f"  ├─ 💰 Capital (cache): <b>${total_capital:,.2f}</b>  🏆 Top3: <b>{top3_pct:.1f}%</b>",
        f"  ├─ {sg_lucro} Lucro on-chain: <b>{total_lucro:+,.2f} USD</b>  WR: <b>{wr_global:.1f}%</b>",
        f"  └─ 💎 BD coletado: <b>{total_bd:.4f}</b> tokens  <i>(all-time)</i>",
    ]

    # ── POR AMBIENTE ─────────────────────────────────────────────────────
    all_envs = sorted(
        set(list(proto_map.keys()) + [r[0] for r in bot_users]),
        key=lambda e: (0 if "v5" in e.lower() else 1, e)
    )

    for env in all_envs:
        eico = "🔵" if "v5" in env.lower() else "🟠"
        p    = proto_map.get(env, {})
        b    = cap_map.get(env, {})
        bu   = next((r for r in bot_users if r[0] == env), None)

        wr_e = p.get("wins", 0) / p.get("trades", 1) * 100 if p.get("trades") else 0
        sg_e = "🟢" if p.get("lucro", 0) >= 0 else "🔴"

        lines += ["", sep, "", f"{eico} <b>{esc(env)}</b>"]

        if bu:
            lines.append(f"  ├─ 👥 Bot: <b>{int(bu[2] or 0)}</b> ativos / <b>{int(bu[1] or 0)}</b> total")
        if b.get("capital", 0) > 0:
            lines.append(f"  ├─ 💰 Capital (cache): <b>${b['capital']:,.2f}</b>  ({b['users']} users)")

        if p:
            lines += [
                f"  ├─ 🔗 Traders: <b>{p['wallets']:,}</b>  📊 Trades: <b>{p['trades']:,}</b>  WR: <b>{wr_e:.1f}%</b>",
                f"  ├─ {sg_e} Lucro: <b>{p['lucro']:+,.2f} USD</b>",
                f"  └─ 💎 BD: <b>{p['bd']:.4f}</b> tokens",
            ]
        else:
            lines.append("  └─ <i>(sem dados on-chain)</i>")

    lines += ["", sep, "", f"<i>🔍 Fonte: 100% DB · zero RPC · {datetime.now().strftime('%H:%M')}</i>"]
    return "\n".join(lines)

@bot.message_handler(func=lambda m: (m.text or "").strip() == "📊 Relatório Institucional")
def adm_relatorio_institucional(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    try:
        _send_long(m.chat.id, _relatorio_build_text(), reply_markup=_relatorio_kb())
    except Exception as e:
        logger.error("[admin] %s", e)
        bot.send_message(m.chat.id, f"⚠️ Erro: {e}", reply_markup=adm_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("relatorio_"))
def _relatorio_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "relatorio_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    bot.answer_callback_query(c.id, "⏳ Atualizando...")
    try:
        bot.edit_message_text(
            _relatorio_build_text(), c.message.chat.id, c.message.message_id,
            parse_mode="HTML", reply_markup=_relatorio_kb()
        )
    except Exception as e:
        logger.error("[relatorio] refresh error: %s", e)

def _inatividade_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="inativ_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="inativ_close"),
    )
    return kb

def _inatividade_text():
    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    dt = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    with DB_LOCK:
        sub_rows = cursor.execute("""
            SELECT o.sub_conta,
                   COALESCE(o.ambiente,'?') AS amb,
                   COUNT(*) AS trades,
                   COUNT(CASE WHEN o.valor>0 THEN 1 END) AS wins,
                   MIN(o.data_hora) AS first_t,
                   MAX(o.data_hora) AS last_t,
                   COALESCE(ow.wallet,'') AS wallet
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=?
            GROUP BY o.sub_conta, o.ambiente
            ORDER BY trades DESC
            LIMIT 30
        """, (dt,)).fetchall()

    if not sub_rows:
        return "⏳ <b>INATIVIDADE PRO</b>\n\n⚠️ Nenhuma subconta com trade nas últimas 24h."

    lines = [
        "⏳ <b>INATIVIDADE PRO — Qualificação de Ciclos</b>",
        sep,
        f"🗓️ <i>Últimas 24h  ·  {len(sub_rows)} subcontas</i>",
        "",
    ]

    qualif_counts = {"🔥 Muito Ativa": 0, "✅ Ativa": 0, "⚠️ Letárgica": 0, "🔴 Inativa": 0}

    for sub, amb, trades, wins, first_t, last_t, wallet in sub_rows:
        wr = wins / trades * 100 if trades > 0 else 0

        times_data = load_trade_times_by_sub(wallet, hours=168, only_sub=str(sub))
        if times_data and str(sub) in times_data:
            times_list = times_data[str(sub)]
            cs = ciclo_stats(times_list) if len(times_list) >= 3 else {}
            smq = consist_score(cs.get("med", 0), cs.get("p95", 0)) if cs else 0
            med_min = int(cs.get("med", 0).total_seconds() / 60) if cs and hasattr(cs.get("med", 0), "total_seconds") else 0
        else:
            smq = 0
            med_min = 0

        trades_per_h = trades / 24
        if trades_per_h >= 5:      classif = "🔥 Muito Ativa"
        elif trades_per_h >= 0.5:  classif = "✅ Ativa"
        elif trades_per_h >= 0.1:  classif = "⚠️ Letárgica"
        else:                       classif = "🔴 Inativa"
        qualif_counts[classif] = qualif_counts.get(classif, 0) + 1

        wr_emoji  = "🟢" if wr >= 60 else ("🟡" if wr >= 40 else "🔴")
        sub_short = (str(sub)[:20] + "…") if len(str(sub)) > 20 else str(sub)
        med_str   = f"  ·  ciclo ~{med_min}min" if med_min > 0 else ""
        smq_str   = f"  ·  SMQ {smq:.0f}" if smq > 0 else ""
        lines.append(
            f"{classif}  <code>{esc(sub_short)}</code>\n"
            f"   {wr_emoji} WR: <b>{wr:.0f}%</b>  |  Trades: <b>{trades}</b>{med_str}{smq_str}"
        )
        lines.append("")

    lines += [sep, "<b>Distribuição:</b>"]
    for classif, cnt in qualif_counts.items():
        if cnt > 0:
            lines.append(f"  {classif}: <b>{cnt}</b> subcontas")
    return "\n".join(lines)

@bot.message_handler(func=lambda m: (m.text or "").strip() == "⏳ Inatividade PRO")
def inatividade_pro(m):
    if not _is_admin(m.chat.id):
        return send_support(m.chat.id, "⛔ Acesso restrito.", reply_markup=_get_main_kb()())
    bot.send_chat_action(m.chat.id, "typing")
    try:
        _send_long(m.chat.id, _inatividade_text(), reply_markup=_inatividade_kb())
    except Exception as e:
        logger.error("[admin] %s", e)
        send_support(m.chat.id, f"⚠️ Erro: {e}", reply_markup=adm_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("inativ_"))
def _inatividade_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "inativ_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    bot.answer_callback_query(c.id, "⏳ Atualizando...")
    try:
        bot.edit_message_text(
            _inatividade_text(), c.message.chat.id, c.message.message_id,
            parse_mode="HTML", reply_markup=_inatividade_kb()
        )
    except Exception as e:
        logger.error("[inativ] refresh error: %s", e)


# ==============================================================================
# 📊 ANÁLISE SUBACCOUNTS — resumo on-chain de subcontas por ambiente
# ==============================================================================
def _subaccounts_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="subac_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="subac_close"),
    )
    return kb

def _subaccounts_text():
    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    with DB_LOCK:
            cur = conn.cursor()

            # 1. Por ambiente — subconta, wallet, trades, liq, wins/losses
            env_rows = cur.execute("""
                SELECT
                    COALESCE(o.ambiente, 'UNKNOWN')                        AS amb,
                    COUNT(DISTINCT o.sub_conta)                            AS n_subs,
                    COUNT(*)                                               AS trades,
                    ROUND(SUM(o.valor) - SUM(o.gas_usd), 4)              AS liq,
                    COUNT(CASE WHEN o.valor - o.gas_usd > 0 THEN 1 END)  AS wins,
                    COUNT(CASE WHEN o.valor - o.gas_usd < 0 THEN 1 END)  AS losses,
                    COUNT(DISTINCT ow.wallet)                             AS wallets
                FROM operacoes o
                LEFT JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade'
                GROUP BY amb
            """).fetchall()

            # bd_v5 primeiro
            env_rows = sorted(env_rows, key=lambda r: (0 if "v5" in str(r[0]).lower() else 1, -float(r[3] or 0)))

            # 2. Top 10 subcontas por lucro líquido (all time)
            top_subs = cur.execute("""
                SELECT sub_conta, COALESCE(ambiente,'?') AS amb,
                       COUNT(*) AS trades,
                       ROUND(SUM(valor) - SUM(gas_usd), 4) AS liq,
                       COUNT(CASE WHEN valor - gas_usd > 0 THEN 1 END) AS wins,
                       COUNT(CASE WHEN valor - gas_usd < 0 THEN 1 END) AS losses
                FROM operacoes WHERE tipo='Trade'
                GROUP BY sub_conta, amb
                ORDER BY liq DESC
                LIMIT 10
            """).fetchall()

            # 3. Totais globais
            total_subs  = cur.execute("SELECT COUNT(DISTINCT sub_conta) FROM operacoes WHERE tipo='Trade'").fetchone()[0]
            total_wlt   = cur.execute("SELECT COUNT(DISTINCT ow.wallet) FROM operacoes o LEFT JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index WHERE o.tipo='Trade'").fetchone()[0]
            total_trade = cur.execute("SELECT COUNT(*) FROM operacoes WHERE tipo='Trade'").fetchone()[0]

            # 4. Capital vivo — capital_cache por ambiente (100% DB, zero RPC)
            cap_cache = cur.execute("""
                SELECT COALESCE(cc.env, 'AG_C_bd') AS env,
                       COUNT(*) AS users,
                       ROUND(SUM(cc.total_usd), 2) AS total
                FROM capital_cache cc
                WHERE cc.total_usd > 0.5
                GROUP BY cc.env
            """).fetchall()

    # ── totais globais ─────────────────────────────────────────────────
    total_liq  = sum(float(r[3] or 0) for r in env_rows)
    total_wins = sum(int(r[4] or 0) for r in env_rows)
    total_loss = sum(int(r[5] or 0) for r in env_rows)
    wr_g   = total_wins / total_trade * 100 if total_trade else 0
    pf_g   = (total_wins / total_loss) if total_loss else float("inf")
    pf_g_s = f"{pf_g:.2f}" if pf_g != float("inf") else "∞"
    lpt_g  = total_liq / total_trade if total_trade else 0
    sg_g   = "🟢" if total_liq >= 0 else "🔴"

    lines = [
        "📊 <b>ANÁLISE SUBACCOUNTS — WEbdEX</b>",
        f"🕒 <i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>",
        sep,
        "",
        "🌐 <b>CONSOLIDADO GLOBAL</b>",
        f"  ├─ 🔑 Subcontas: <b>{total_subs:,}</b>  👥 Wallets: <b>{total_wlt:,}</b>",
        f"  ├─ 📊 Trades:    <b>{total_trade:,}</b>  (WR: <b>{wr_g:.1f}%</b>  PF: <b>{pf_g_s}</b>)",
        f"  └─ {sg_g} Líquido: <b>{total_liq:+.2f} USD</b>  (<b>{lpt_g:+.4f}/trade</b>)",
        "",
        sep,
    ]

    # ── por ambiente ───────────────────────────────────────────────────
    for amb, n_subs, trades, liq, wins, losses, wallets in env_rows:
        wr   = wins / trades * 100 if trades else 0
        pf_v = (wins / losses) if losses else float("inf")
        pf_s = f"{pf_v:.2f}" if pf_v != float("inf") else "∞"
        sg   = "🟢" if (liq or 0) >= 0 else "🔴"
        lpt  = (liq or 0) / trades if trades else 0
        eico = "🔵" if "v5" in str(amb).lower() else "🟠"
        lines += [
            "",
            f"{eico} <b>{esc(str(amb))}</b>",
            f"  ├─ 🔑 Subs: <b>{n_subs:,}</b>  👥 Wallets: <b>{wallets:,}</b>",
            f"  ├─ 📊 Trades: <b>{trades:,}</b>  (WR: <b>{wr:.1f}%</b>  PF: <b>{pf_s}</b>)",
            f"  └─ {sg} Líquido: <b>{(liq or 0):+.2f} USD</b>  (<b>{lpt:+.4f}/trade</b>)",
        ]

    # ── top 10 subcontas ───────────────────────────────────────────────
    lines += ["", sep, "", "🏆 <b>TOP 10 SUBCONTAS (Lucro all time)</b>"]
    for i, (sub, amb, trades, liq, wins, losses) in enumerate(top_subs, 1):
        sg   = "🟢" if (liq or 0) >= 0 else "🔴"
        wr   = wins / trades * 100 if trades else 0
        eico = "🔵" if "v5" in str(amb).lower() else "🟠"
        sub_s = f"{str(sub or '')[:6]}…{str(sub or '')[-4:]}" if len(str(sub or "")) > 12 else str(sub or "—")
        lines += [
            f"  {_medal(i) or f'{i:02d}.'} {eico} <code>{esc(sub_s)}</code>",
            f"       {sg} <b>{(liq or 0):+.2f} USD</b>  ({trades:,}t · WR: {wr:.0f}%)",
        ]

    # ── capital vivo (capital_cache — 100% DB) ─────────────────────────
    lines += ["", sep, "", "💼 <b>CAPITAL VIVO (mybdBook snapshots)</b>"]
    if cap_cache:
        cap_sorted = sorted(cap_cache, key=lambda r: (0 if "v5" in str(r[0]).lower() else 1))
        total_cap  = sum(float(r[2] or 0) for r in cap_sorted)
        for env_c, users_c, total_c in cap_sorted:
            eico = "🔵" if "v5" in str(env_c).lower() else "🟠"
            lines.append(f"  {eico} <b>{esc(str(env_c))}</b>: <b>${total_c:,.2f}</b>  ({users_c} usuários)")
        lines.append(f"  └─ 💼 Total: <b>${total_cap:,.2f}</b>")
    else:
        lines.append("  <i>(sem dados — usuários precisam chamar mybdBook ao menos 1x)</i>")

    return "\n".join(lines)

@bot.message_handler(func=lambda m: (m.text or "").strip() == "📊 Análise SubAccounts")
def adm_analise_subaccounts(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    try:
        _send_long(m.chat.id, _subaccounts_text(), reply_markup=_subaccounts_kb())
    except Exception as e:
        logger.error("[admin] %s", e)
        bot.send_message(m.chat.id, f"⚠️ Erro: {e}", reply_markup=adm_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("subac_"))
def _subaccounts_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "subac_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    bot.answer_callback_query(c.id, "⏳ Atualizando...")
    try:
        bot.edit_message_text(
            _subaccounts_text(), c.message.chat.id, c.message.message_id,
            parse_mode="HTML", reply_markup=_subaccounts_kb()
        )
    except Exception as e:
        logger.error("[subac] refresh error: %s", e)


# ==============================================================================
# 📈 LUCRO REAL — total e por ambiente com seletor de período inline
# ==============================================================================
def _lucro_real_text(periodo: str = "ciclo") -> str:
    from webdex_db import _ciclo_21h_since, _ciclo_21h_label, period_to_hours
    from datetime import datetime, timedelta

    if periodo == "ciclo":
        since = _ciclo_21h_since()
        label = _ciclo_21h_label()
    else:
        hours = period_to_hours(periodo)
        since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        label = periodo.upper()

    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    with DB_LOCK:
        cur = conn.cursor()
        env_rows = cur.execute("""
            SELECT
                COALESCE(ambiente, 'UNKNOWN') AS amb,
                COUNT(*)                                              AS trades,
                ROUND(SUM(valor), 4)                                  AS bruto,
                ROUND(SUM(gas_usd), 4)                                AS gas,
                ROUND(SUM(valor) - SUM(gas_usd), 4)                  AS liq,
                COUNT(CASE WHEN valor - gas_usd > 0 THEN 1 END)      AS wins,
                COUNT(CASE WHEN valor - gas_usd < 0 THEN 1 END)      AS losses
            FROM operacoes
            WHERE tipo='Trade' AND data_hora >= ?
            GROUP BY amb
        """, (since,)).fetchall()

        daily = cur.execute("""
            SELECT DATE(datetime(data_hora, '-21 hours')) AS dia_ciclo,
                   ROUND(SUM(valor) - SUM(gas_usd), 2) AS liq,
                   COUNT(*) AS trades
            FROM operacoes
            WHERE tipo='Trade' AND data_hora >= ?
            GROUP BY dia_ciclo ORDER BY dia_ciclo DESC LIMIT 7
        """, (since,)).fetchall()

    # bd_v5 sempre primeiro, depois demais por liq desc
    env_rows = sorted(env_rows, key=lambda r: (0 if "v5" in str(r[0]).lower() else 1, -float(r[4] or 0)))

    total_trades = sum(int(r[1] or 0) for r in env_rows)
    total_bruto  = sum(float(r[2] or 0) for r in env_rows)
    total_gas    = sum(float(r[3] or 0) for r in env_rows)
    total_liq    = sum(float(r[4] or 0) for r in env_rows)
    total_wins   = sum(int(r[5] or 0) for r in env_rows)
    wr_global    = total_wins / total_trades * 100 if total_trades else 0
    lpt_global   = total_liq / total_trades if total_trades else 0  # liq per trade

    sg_g = "🟢" if total_liq >= 0 else "🔴"
    lines = [
        "📈 <b>LUCRO REAL — WEbdEX</b>",
        f"🗓️ <i>{esc(label)}</i>",
        sep,
        "",
        "🌐 <b>CONSOLIDADO GLOBAL</b>",
        f"  ├─ 📊 Trades:    <b>{total_trades:,}</b>  (WR: <b>{wr_global:.1f}%</b>)",
        f"  ├─ 💰 Bruto:     <b>{total_bruto:+.2f} USD</b>",
        f"  ├─ ⛽ Gás:      <b>{total_gas:.2f} USD</b>",
        f"  └─ {sg_g} Líquido: <b>{total_liq:+.2f} USD</b>  (<b>{lpt_global:+.4f}/trade</b>)",
    ]

    lines += ["", sep]

    for amb, trades, bruto, gas, liq, wins, losses in env_rows:
        wr   = wins / trades * 100 if trades else 0
        sg   = "🟢" if (liq or 0) >= 0 else "🔴"
        pf_g = wins / losses if losses else float("inf")
        pf_s = f"{pf_g:.2f}" if pf_g != float("inf") else "∞"
        lpt  = (liq or 0) / trades if trades else 0
        eico = "🔵" if "v5" in str(amb).lower() else "🟠"
        lines += [
            "",
            f"{eico} <b>{esc(str(amb))}</b>",
            f"  ├─ 📊 Trades:  <b>{trades:,}</b>  (WR: <b>{wr:.1f}%</b>  PF: <b>{pf_s}</b>)",
            f"  ├─ 💰 Bruto:   <b>{(bruto or 0):+.2f}</b>  ⛽ Gás: <b>{(gas or 0):.2f}</b>",
            f"  └─ {sg} Líquido: <b>{(liq or 0):+.2f} USD</b>  (<b>{lpt:+.4f}/trade</b>)",
        ]

    if daily:
        lines += ["", sep, "", "📅 <b>ÚLTIMOS 7 CICLOS</b>"]
        for dia_ciclo, liq_d, trades_d in daily:
            ic  = "🟢" if (liq_d or 0) >= 0 else "🔴"
            dt  = str(dia_ciclo)[5:]  # MM-DD → mas queremos DD/MM
            try:
                dt = f"{str(dia_ciclo)[8:10]}/{str(dia_ciclo)[5:7]}"
            except Exception:
                pass
            lines.append(f"  {ic} {dt}  <b>{(liq_d or 0):+.2f} USD</b>  ({trades_d:,}t)")

    return "\n".join(lines)

def _lucro_real_kb(periodo: str = "ciclo") -> types.InlineKeyboardMarkup:
    periodos = [("Ciclo", "ciclo"), ("24h", "24h"), ("7d", "7d"), ("30d", "30d")]
    kb = types.InlineKeyboardMarkup()
    row = []
    for label, p in periodos:
        mark = f"✅ {label}" if p == periodo else label
        row.append(types.InlineKeyboardButton(mark, callback_data=f"lucro_{p}"))
    kb.row(*row)
    kb.row(types.InlineKeyboardButton("✅ Fechar", callback_data="lucro_close"))
    return kb

@bot.message_handler(func=lambda m: (m.text or "").strip() == "📈 Lucro Real (Total/Ambiente)")
def adm_lucro_real(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    try:
        bot.send_message(m.chat.id, _lucro_real_text("ciclo"),
                         parse_mode="HTML", reply_markup=_lucro_real_kb("ciclo"))
    except Exception as e:
        logger.error("[admin] %s", e)
        bot.send_message(m.chat.id, f"⚠️ Erro: {e}", reply_markup=adm_kb())

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("lucro_"))
def _lucro_real_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "lucro_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    periodo = c.data.replace("lucro_", "")
    bot.answer_callback_query(c.id, f"Carregando {periodo.upper()}...")
    try:
        txt = _lucro_real_text(periodo)
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_lucro_real_kb(periodo))
    except Exception as e:
        logger.error("[admin] %s", e)


# ==============================================================================
# 💎 LUCRO TOTAL DO PROTOCOLO
# Fonte: protocol_ops (TODOS os traders, on-chain) + fl_snapshots (TVL)
# 3 métricas:
#   1. Lucro dos Traders    = SUM(protocol_ops.profit) — todos os traders
#   2. Gás consumido        = SUM(protocol_ops.gas_pol) — gas real em POL
#   3. BD/Passe coletado    = SUM(protocol_ops.fee_bd)  — fees em BD/LOOP
# ==============================================================================

def _lucro_protocolo_text(periodo: str = "ciclo") -> str:
    from webdex_db import _ciclo_21h_since, _ciclo_21h_label, period_to_hours
    from webdex_chain import chain_pol_price
    from datetime import datetime, timedelta

    if periodo == "ciclo":
        since = _ciclo_21h_since()
        label = _ciclo_21h_label()
    elif periodo == "all":
        since = "2000-01-01 00:00:00"
        label = "All-Time"
    else:
        hours = period_to_hours(periodo)
        since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        label = periodo.upper()

    pol_price = chain_pol_price()

    _bf_data: dict = {}
    _monthly_by_env: dict = {}

    with DB_LOCK:
        cur = conn.cursor()

        # Conta total de registros em protocol_ops para saber se backfill rodou
        proto_count = cur.execute("SELECT COUNT(*) FROM protocol_ops").fetchone()[0] or 0

        # ── Backfill progress (só usado na aba All) ────────────────────────────
        # NOTA: usa cur.execute direto (chave/valor) — get_config() adquire DB_LOCK → deadlock
        if periodo == "all":
            try:
                from webdex_config import CONTRACTS_DEPLOY_BLOCK
                def _cfg(k, d="0"):
                    row = cur.execute("SELECT valor FROM config WHERE chave=?", (k,)).fetchone()
                    return row[0] if row else d
                _curr_blk = int(_cfg("last_block") or "0")
                for _ek in ("bd_v5", "AG_C_bd"):
                    _synced = int(_cfg(f"proto_sync_block_{_ek}") or "0")
                    _deploy = CONTRACTS_DEPLOY_BLOCK.get(_ek, 0)
                    _total  = max(1, _curr_blk - _deploy)
                    _done   = max(0, _synced - _deploy)
                    _pct    = min(100.0, _done / _total * 100)
                    _genesis = _cfg(f"proto_genesis_done_{_ek}") or "0"
                    _bf_data[_ek] = {
                        "synced": _synced, "deploy": _deploy,
                        "curr": _curr_blk, "pct": _pct,
                        "complete": _genesis == "1",
                    }
            except Exception as _bf_err:
                logger.warning("[lucro_proto] backfill data error: %s", _bf_err)

            # Breakdown mensal por ambiente
            _monthly = cur.execute("""
                SELECT env,
                       strftime('%Y-%m', ts)                             AS mes,
                       COUNT(*)                                          AS trades,
                       COUNT(DISTINCT wallet)                            AS wallets,
                       ROUND(SUM(profit), 2)                            AS lucro,
                       COUNT(CASE WHEN profit > 0 THEN 1 END)           AS wins,
                       ROUND(SUM(fee_bd), 4)                            AS bd
                FROM protocol_ops
                WHERE wallet != '' AND env != 'UNKNOWN'
                GROUP BY env, mes
                ORDER BY env, mes
            """).fetchall()
            # agrupa por env
            for _r in _monthly:
                _monthly_by_env.setdefault(str(_r[0]), []).append(_r[1:])  # (mes, trades, wallets, lucro, wins, bd)

        # ── protocol_ops: TODOS os traders (on-chain completo) ─────────────────
        proto_rows = cur.execute("""
            SELECT
                COALESCE(env, 'UNKNOWN')                               AS env,
                COUNT(*)                                               AS trades,
                COUNT(DISTINCT wallet)                                 AS traders,
                ROUND(SUM(profit), 4)                                  AS lucro_total,
                ROUND(SUM(CASE WHEN profit > 0 THEN profit ELSE 0 END), 4) AS ganhos,
                ROUND(SUM(CASE WHEN profit < 0 THEN profit ELSE 0 END), 4) AS perdas,
                COUNT(CASE WHEN profit > 0 THEN 1 END)                AS wins,
                ROUND(SUM(fee_bd), 6)                                  AS bd_total,
                ROUND(SUM(gas_pol), 6)                                 AS gas_pol_total
            FROM protocol_ops
            WHERE ts >= ?
            GROUP BY env
        """, (since,)).fetchall()

        # bd_v5 sempre primeiro
        proto_rows = sorted(proto_rows, key=lambda r: (0 if "v5" in str(r[0]).lower() else 1, -float(r[3] or 0)))

        # Totais globais
        p_trades  = sum(int(r[1] or 0)   for r in proto_rows)
        p_traders = max(int(r[2] or 0)   for r in proto_rows) if proto_rows else 0
        p_lucro   = sum(float(r[3] or 0) for r in proto_rows)
        p_ganhos  = sum(float(r[4] or 0) for r in proto_rows)
        p_perdas  = sum(float(r[5] or 0) for r in proto_rows)
        p_wins    = sum(int(r[6] or 0)   for r in proto_rows)
        p_bd      = sum(float(r[7] or 0) for r in proto_rows)
        p_gas_pol = sum(float(r[8] or 0) for r in proto_rows)
        p_wr      = p_wins / p_trades * 100 if p_trades else 0.0
        p_gas_usd = p_gas_pol * pol_price

        # BD all-time (sem filtro de período)
        bd_alltime = float(cur.execute(
            "SELECT ROUND(SUM(fee_bd),4) FROM protocol_ops WHERE fee_bd > 0"
        ).fetchone()[0] or 0)

        # Top 5 traders por lucro (período)
        top_traders = cur.execute("""
            SELECT wallet,
                   ROUND(SUM(profit),4)  AS lucro,
                   COUNT(*)              AS trades,
                   ROUND(SUM(fee_bd),4)  AS bd_pago,
                   ROUND(SUM(gas_pol),4) AS gas
            FROM protocol_ops
            WHERE ts >= ?
            GROUP BY wallet ORDER BY lucro DESC LIMIT 5
        """, (since,)).fetchall()

        # ── TVL delta (fl_snapshots) ───────────────────────────────────────────
        snap_rows = cur.execute("""
            SELECT env,
                   (SELECT total_usd FROM fl_snapshots s2
                    WHERE s2.env = s1.env AND s2.ts >= ?
                    ORDER BY s2.ts ASC LIMIT 1) AS tvl_inicio,
                   (SELECT total_usd FROM fl_snapshots s2
                    WHERE s2.env = s1.env
                    ORDER BY s2.ts DESC LIMIT 1) AS tvl_fim
            FROM fl_snapshots s1
            GROUP BY env
        """, (since,)).fetchall()

        tvl_data: dict = {}
        for env, tvl_i, tvl_f in snap_rows:
            if tvl_i is not None and tvl_f is not None:
                tvl_data[env] = {
                    "inicio": float(tvl_i),
                    "fim":    float(tvl_f),
                    "delta":  float(tvl_f) - float(tvl_i),
                    "pct":    ((float(tvl_f) - float(tvl_i)) / float(tvl_i) * 100) if float(tvl_i) > 0 else 0.0,
                }

        tvl_total_inicio = sum(v["inicio"] for v in tvl_data.values())
        tvl_total_fim    = sum(v["fim"]    for v in tvl_data.values())
        tvl_total_delta  = tvl_total_fim - tvl_total_inicio
        tvl_total_pct    = (tvl_total_delta / tvl_total_inicio * 100) if tvl_total_inicio > 0 else 0.0

    sg_lucro = "🟢" if p_lucro >= 0 else "🔴"
    sg_tvl   = "🟢" if tvl_total_delta >= 0 else "🔴"
    s_lucro  = "+" if p_lucro >= 0 else ""

    lines = [
        "💎 <b>LUCRO TOTAL DO PROTOCOLO — WEbdEX</b>",
        f"🗓️ <i>{esc(label)}</i>  |  POL: <b>${pol_price:.4f}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if proto_count == 0:
        lines += ["", "⏳ <i>Backfill on-chain em andamento (worker ativo)...</i>",
                  "💡 <i>Dados disponíveis em ~30min após a primeira sincronização.</i>"]
    else:
        # ── Bloco 1: P&L dos Traders (resultado on-chain) ─────────────────────
        lpt_p = p_lucro / p_trades if p_trades else 0
        lines += [
            "",
            "📈 <b>P&amp;L DOS TRADERS</b>  <i>(resultado on-chain dos usuários)</i>",
            f"  ├─ 📊 Trades: <b>{p_trades:,}</b>  👥 Traders: <b>{p_traders:,}</b>  WR: <b>{p_wr:.1f}%</b>",
            f"  ├─ ✅ Lucros: <b>+${p_ganhos:,.2f}</b>  ❌ Perdas: <b>${p_perdas:,.2f}</b>",
            f"  └─ {sg_lucro} Resultado: <b>{s_lucro}${p_lucro:,.2f} USD</b>  (<b>{lpt_p:+.4f}/trade</b>)",
            "",
            sep,
        ]

        # ── Por ambiente ───────────────────────────────────────────────────────
        for env, trades, traders, lucro, ganhos, perdas, wins, bd_tot, gas_pol in proto_rows:
            ic  = "🔵" if "v5" in str(env).lower() else "🟠"
            sg  = "🟢" if (lucro or 0) >= 0 else "🔴"
            s   = "+" if (lucro or 0) >= 0 else ""
            wr  = wins / trades * 100 if trades else 0.0
            lpt = (lucro or 0) / trades if trades else 0
            lines += [
                "",
                f"{ic} <b>{esc(str(env))}</b>",
                f"  ├─ 📊 Trades: <b>{trades:,}</b>  👥 Traders: <b>{traders:,}</b>  WR: <b>{wr:.1f}%</b>",
                f"  ├─ ✅ Lucros: <b>+${(ganhos or 0):,.2f}</b>  ❌ Perdas: <b>${(perdas or 0):,.2f}</b>",
                f"  └─ {sg} Resultado: <b>{s}${(lucro or 0):,.2f} USD</b>  (<b>{lpt:+.4f}/trade</b>)",
            ]

        # ── Bloco 2: Gás consumido ─────────────────────────────────────────────
        lines += ["", sep, "", "⛽ <b>GÁS CONSUMIDO (Transações)</b>"]
        if p_trades:
            lines += [
                f"  ├─ 🔴 Total POL: <b>{p_gas_pol:,.4f} POL</b>  (~<b>${p_gas_usd:,.2f}</b>)",
                f"  └─ 📊 Média/trade: <b>{(p_gas_pol/p_trades):,.6f} POL</b>",
            ]
        else:
            lines.append("  <i>sem dados</i>")

        # ── Bloco 3: Receita do protocolo (BD fee) ─────────────────────────────
        lines += [
            "", sep, "",
            "💎 <b>RECEITA DO PROTOCOLO</b>  <i>(BD/Passe coletado on-chain)</i>",
            f"  ├─ 🏦 Período:   <b>{p_bd:,.4f} BD</b>",
            f"  └─ 📦 Acumulado: <b>{bd_alltime:,.4f} BD</b>  <i>(all-time indexado)</i>",
        ]

        # ── Bloco 4: TVL delta ─────────────────────────────────────────────────
        if tvl_data:
            s_tvl = "+" if tvl_total_delta >= 0 else ""
            tvl_sorted = sorted(tvl_data.items(), key=lambda kv: (0 if "v5" in kv[0].lower() else 1))
            lines += [
                "", sep, "",
                "🏦 <b>TVL DO PROTOCOLO</b>",
                f"  ├─ {sg_tvl} Delta: <b>{s_tvl}${tvl_total_delta:,.2f}</b>  ({s_tvl}{tvl_total_pct:.2f}%)",
                f"  └─ 📊 Início: <b>${tvl_total_inicio:,.2f}</b>  →  Atual: <b>${tvl_total_fim:,.2f}</b>",
            ]
            for env, v in tvl_sorted:
                ic = "🔵" if "v5" in env.lower() else "🟠"
                s  = "+" if v["delta"] >= 0 else ""
                lines.append(f"       {ic} <b>{esc(env)}</b>: <b>${v['fim']:,.2f}</b>  ({s}${v['delta']:,.2f})")

        # ── Bloco 5: Top 5 traders ─────────────────────────────────────────────
        if top_traders:
            lines += ["", sep, "", "🏆 <b>TOP 5 TRADERS (período)</b>"]
            for i, (wallet, lucro, trades, bd_pago, gas) in enumerate(top_traders, 1):
                short_w = f"{wallet[:6]}…{wallet[-4:]}" if len(str(wallet)) > 10 else str(wallet)
                sg = "🟢" if (lucro or 0) >= 0 else "🔴"
                s  = "+" if (lucro or 0) >= 0 else ""
                lines += [
                    f"  {_medal(i)} <code>{esc(short_w)}</code>",
                    f"       {sg} <b>{s}${(lucro or 0):,.2f}</b>  ·  {trades:,}t  ·  💎 {(bd_pago or 0):.3f} BD",
                ]

        # ── Bloco 6: All-time — backfill + histórico mensal ───────────────────
        if periodo == "all" and _bf_data:
            lines += ["", sep, "", "📡 <b>BACKFILL STATUS (on-chain)</b>"]
            all_complete = True
            for _ek in ("bd_v5", "AG_C_bd"):
                _b = _bf_data.get(_ek, {})
                if not _b:
                    continue
                _ic = "🔵" if "v5" in _ek.lower() else "🟠"
                if _b.get("complete"):
                    lines.append(f"  {_ic} <b>{esc(_ek)}</b>: ✅ <b>100%</b> completo")
                else:
                    all_complete = False
                    lines.append(
                        f"  {_ic} <b>{esc(_ek)}</b>: ⏳ <b>{_b.get('pct', 0):.1f}%</b>"
                        f"  (bloco {_b.get('synced', 0):,} / {_b.get('curr', 0):,})"
                    )
            if not all_complete:
                lines.append("  <i>💡 Dados históricos serão completados ao final do backfill</i>")

            if _monthly_by_env:
                lines += ["", sep, "", "📅 <b>HISTÓRICO MENSAL</b>  <i>(P&amp;L traders | 💎 receita protocolo)</i>"]
                for _env in sorted(_monthly_by_env, key=lambda e: (0 if "v5" in e.lower() else 1, e)):
                    _ic = "🔵" if "v5" in _env.lower() else "🟠"
                    lines += ["", f"{_ic} <b>{esc(_env)}</b>"]
                    _env_months = _monthly_by_env[_env]
                    _env_total_lucro = sum(float(r[3] or 0) for r in _env_months)
                    _env_total_trades = sum(int(r[1] or 0) for r in _env_months)
                    _env_total_wins = sum(int(r[4] or 0) for r in _env_months)
                    _env_total_bd = sum(float(r[5] or 0) for r in _env_months)
                    for _mes, _t, _w, _liq, _wins, _bd in _env_months:
                        _wr = _wins / _t * 100 if _t else 0
                        _sg = "🟢" if (_liq or 0) >= 0 else "🔴"
                        _s  = "+" if (_liq or 0) >= 0 else ""
                        lines.append(
                            f"  {_sg} <b>{_mes}</b>  <b>{_s}${(_liq or 0):,.2f}</b>"
                            f"  ·  {_t:,}t  ·  WR {_wr:.0f}%  ·  💎 {(_bd or 0):.2f}"
                        )
                    _env_wr = _env_total_wins / _env_total_trades * 100 if _env_total_trades else 0
                    _env_sg = "🟢" if _env_total_lucro >= 0 else "🔴"
                    _env_s  = "+" if _env_total_lucro >= 0 else ""
                    lines.append(
                        f"  ─── Total  {_env_sg} <b>{_env_s}${_env_total_lucro:,.2f}</b>"
                        f"  ·  {_env_total_trades:,}t  ·  WR {_env_wr:.0f}%  ·  💎 {_env_total_bd:.2f}"
                    )

    lines += ["", f"<i>🔍 Fonte: on-chain ({proto_count:,} ops indexadas)</i>"]
    return "\n".join(lines)


def _lucro_protocolo_kb(periodo: str = "ciclo") -> types.InlineKeyboardMarkup:
    periodos = [("Ciclo", "ciclo"), ("24h", "24h"), ("7d", "7d"), ("30d", "30d"), ("All", "all")]
    kb = types.InlineKeyboardMarkup()
    row = []
    for label, p in periodos:
        mark = f"✅ {label}" if p == periodo else label
        row.append(types.InlineKeyboardButton(mark, callback_data=f"lproto_{p}"))
    kb.row(*row)
    kb.row(types.InlineKeyboardButton("✅ Fechar", callback_data="lproto_close"))
    return kb


@bot.message_handler(func=lambda m: (m.text or "").strip() == "💎 Lucro Total do Protocolo")
def adm_lucro_protocolo(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    try:
        bot.send_message(m.chat.id, _lucro_protocolo_text("ciclo"),
                         parse_mode="HTML", reply_markup=_lucro_protocolo_kb("ciclo"))
    except Exception as e:
        logger.error("[admin] %s", e)
        bot.send_message(m.chat.id, f"⚠️ Erro: {e}", reply_markup=adm_kb())


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("lproto_"))
def _lucro_protocolo_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "lproto_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    periodo = c.data.replace("lproto_", "")
    bot.answer_callback_query(c.id, f"Carregando {periodo.upper()}...")
    try:
        txt = _lucro_protocolo_text(periodo)
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_lucro_protocolo_kb(periodo))
    except Exception as e:
        logger.error("[admin] %s", e)


# ==============================================================================
# 🧾 FORNECIMENTO E LIQUIDEZ — on-chain (padrão original WEbdEX V30)
#
# Lógica correta:
#   Fornecimento = LP_token.totalSupply()            — quantos LP tokens existem
#   Liquidez     = TOKEN.balanceOf(SUBACCOUNTS_addr) — capital no contrato SubAccounts
#   Gás          = w3.eth.get_balance(MANAGER_addr)  — saldo nativo POL do contrato
# ==============================================================================

_ABI_ERC20_BASIC = json.loads('[{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]')

def _fl_supply(w3, lp_addr: str, dec: int) -> float:
    """totalSupply do LP token — quantos LP tokens foram emitidos."""
    try:
        c = w3.eth.contract(address=Web3.to_checksum_address(lp_addr), abi=_ABI_ERC20_BASIC)
        return float(c.functions.totalSupply().call()) / (10 ** dec)
    except Exception:
        return -1.0

def _fl_balance(w3, token_addr: str, holder_addr: str, dec: int) -> float:
    """balanceOf(holder) — capital do token mantido no endereço holder."""
    try:
        c = w3.eth.contract(address=Web3.to_checksum_address(token_addr), abi=_ABI_ERC20_BASIC)
        return float(c.functions.balanceOf(Web3.to_checksum_address(holder_addr)).call()) / (10 ** dec)
    except Exception:
        return -1.0

def _fl_manager_gas(w3, mgr_addr: str) -> float:
    """Saldo nativo POL do Manager — capital depositado por usuários para gas de transações."""
    try:
        raw = w3.eth.get_balance(Web3.to_checksum_address(mgr_addr))
        return float(w3.from_wei(raw, "ether"))
    except Exception:
        return -1.0

def _fl_save_snapshot(env: str, lp_u: float, lp_l: float,
                      liq_u: float, liq_l: float, gas_pol: float, pol_price: float,
                      liq_d: float = 0.0):
    try:
        from webdex_db import now_br
        ts        = now_br().strftime("%Y-%m-%d %H:%M:%S")
        total_usd = max(liq_u, 0) + max(liq_l, 0) + max(liq_d, 0)
        with DB_LOCK:
            conn.execute(
                "INSERT INTO fl_snapshots "
                "(ts,env,lp_usdt_supply,lp_loop_supply,liq_usdt,liq_loop,liq_dai,gas_pol,pol_price,total_usd) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ts, env, max(lp_u, 0), max(lp_l, 0),
                 max(liq_u, 0), max(liq_l, 0), max(liq_d, 0), max(gas_pol, 0), pol_price, total_usd)
            )
            conn.commit()
    except Exception:
        pass

def _fl_last_snapshot(env: str) -> dict:
    try:
        with DB_LOCK:
            row = conn.execute(
                "SELECT ts,lp_usdt_supply,lp_loop_supply,liq_usdt,liq_loop,COALESCE(liq_dai,0),gas_pol "
                "FROM fl_snapshots WHERE env=? ORDER BY id DESC LIMIT 1",
                (env,)
            ).fetchone()
        if row:
            return {"ts": row[0], "lp_usdt": row[1], "lp_loop": row[2],
                    "liq_usdt": row[3], "liq_loop": row[4], "liq_dai": row[5], "gas": row[6]}
    except Exception:
        pass
    return {}

def _fl_fmt(v: float, dec: int = 4) -> str:
    return "⚠️ RPC" if v < 0 else f"{v:,.{dec}f}"

def _fl_pct_bar(pct: float, width: int = 10) -> str:
    if pct < 0: return "░" * width
    filled = min(round(pct / 100 * width), width)
    return "█" * filled + "░" * (width - filled)

def _fl_delta_str(now: float, prev: float) -> str:
    if prev <= 0 or now < 0: return ""
    diff = now - prev
    pct  = diff / prev * 100
    arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "≈")
    return f" {arrow}{abs(pct):.2f}%"

def _fl_proto_stats(env_key: str, days: int = 30) -> dict:
    """Atividade 30d de protocol_ops (on-chain) para um ambiente."""
    from datetime import timedelta
    from webdex_db import now_br
    since = (now_br() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with DB_LOCK:
            r = conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT wallet), "
                "ROUND(SUM(profit),2), COUNT(CASE WHEN profit>0 THEN 1 END), "
                "ROUND(SUM(fee_bd),4) "
                "FROM protocol_ops WHERE env=? AND ts>=?",
                (env_key, since)
            ).fetchone()
        return {"trades": int(r[0] or 0), "wallets": int(r[1] or 0),
                "resultado": float(r[2] or 0), "wins": int(r[3] or 0),
                "bd": float(r[4] or 0)}
    except Exception:
        return {"trades": 0, "wallets": 0, "resultado": 0.0, "wins": 0, "bd": 0.0}

def _fl_proto_stats_total(days: int = 30) -> dict:
    """Atividade 30d + BD all-time de protocol_ops (ambos os ambientes)."""
    from datetime import timedelta
    from webdex_db import now_br
    since = (now_br() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with DB_LOCK:
            r = conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT wallet), "
                "ROUND(SUM(profit),2), COUNT(CASE WHEN profit>0 THEN 1 END), "
                "ROUND(SUM(fee_bd),4) "
                "FROM protocol_ops WHERE ts>=?",
                (since,)
            ).fetchone()
            bd_all = float(conn.execute(
                "SELECT ROUND(SUM(fee_bd),4) FROM protocol_ops WHERE fee_bd>0"
            ).fetchone()[0] or 0)
        return {"trades": int(r[0] or 0), "wallets": int(r[1] or 0),
                "resultado": float(r[2] or 0), "wins": int(r[3] or 0),
                "bd": float(r[4] or 0), "bd_alltime": bd_all}
    except Exception:
        return {"trades": 0, "wallets": 0, "resultado": 0.0, "wins": 0,
                "bd": 0.0, "bd_alltime": 0.0}

def _fl_build_text(env_data: dict, ts_now: str, gwei: float, pol_price: float) -> str:
    """Monta o texto do dashboard 🧾 Fornecimento & Liquidez."""
    sep = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    lines = [
        "🧾 <b>FORNECIMENTO &amp; LIQUIDEZ — WEbdEX</b>",
        f"🕒 {esc(ts_now)}  |  ⛽ {_fl_fmt(gwei, 1)} Gwei  |  💱 ${pol_price:.4f} POL",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for env_name in ("bd_v5", "AG_C_bd"):
        if env_name not in env_data:
            continue
        d    = env_data[env_name]
        prev = d["prev"]
        ic   = "🔵" if "v5" in env_name.lower() else "🟠"

        s_u  = d["lp_usdt_supply"]
        s_l  = d["lp_loop_supply"]
        lq_u = d["liq_usdt"]
        lq_l = d["liq_loop"]
        lq_d = d.get("liq_dai", -1.0)
        gp   = d["gas_pol"]
        st   = d["stat"]

        lines += ["", f"{ic} <b>{esc(d['tag'])}</b>"]

        # Fornecimento
        d_su = _fl_delta_str(s_u, prev.get("lp_usdt", 0))
        d_sl = _fl_delta_str(s_l, prev.get("lp_loop", 0))
        lines += [
            "  ├─ 📦 <b>LP Supply</b>",
            f"  │    🟣 LP-USDT:  <b>{_fl_fmt(s_u, 4)}</b>{esc(d_su)}",
            f"  │    🟣 LP-LOOP:  <b>{_fl_fmt(s_l, 4)}</b>{esc(d_sl)}",
        ]

        # Liquidez
        d_lu = _fl_delta_str(lq_u, prev.get("liq_usdt", 0))
        d_ll = _fl_delta_str(lq_l, prev.get("liq_loop", 0))
        d_ld = _fl_delta_str(lq_d, prev.get("liq_dai", 0))
        lines += [
            "  ├─ 💧 <b>Liquidez (SubAccounts)</b>",
            f"  │    💵 USDT:  <b>{_fl_fmt(lq_u, 2)}</b>{esc(d_lu)}",
            f"  │    🔄 LOOP:  <b>{_fl_fmt(lq_l, 4)}</b>{esc(d_ll)}",
            f"  │    🟡 DAI:   <b>{_fl_fmt(lq_d, 2)}</b>{esc(d_ld)}",
        ]

        # Ratio Capital / Supply
        ratio_lines = []
        if s_u > 0 and lq_u >= 0:
            r = lq_u / s_u * 100
            flag = "  🟢" if r >= 80 else ("  ⚠️ Baixo" if r < 10 else "")
            ratio_lines.append(f"  │    💵 USDT: {_fl_pct_bar(r)} <b>{r:.1f}%</b>{flag}")
        if s_l > 0 and lq_l >= 0:
            r = lq_l / s_l * 100
            flag = "  🟢" if r >= 80 else ("  ⚠️ Baixo" if r < 10 else "")
            ratio_lines.append(f"  │    🔄 LOOP: {_fl_pct_bar(r)} <b>{r:.1f}%</b>{flag}")
        if ratio_lines:
            lines.append("  ├─ 📐 <b>Ratio Capital / Supply</b>")
            lines += ratio_lines

        # Gas Manager
        g_s = "🟢" if gp >= 100 else ("🟡" if gp >= 10 else ("🔴 BAIXO" if gp >= 0 else "⚠️ RPC"))
        g_u = f"  (~${gp * pol_price:,.2f})" if gp >= 0 and pol_price > 0 else ""
        lines.append(f"  ├─ ⛽ <b>Gas Manager</b>: <b>{_fl_fmt(gp, 2)} POL</b>{esc(g_u)}  {g_s}")

        # Atividade 30d on-chain
        wr  = st["wins"] / st["trades"] * 100 if st["trades"] else 0
        sg  = "🟢" if (st["resultado"] or 0) >= 0 else "🔴"
        s_r = "+" if (st["resultado"] or 0) >= 0 else ""
        lines += [
            "  └─ 📈 <b>30d on-chain</b>",
            f"       {st['trades']:,} trades  ·  {st['wallets']:,} wallets  ·  WR {wr:.0f}%",
            f"       {sg} P&amp;L traders: <b>{s_r}${st['resultado']:,.2f}</b>  ·  💎 {st['bd']:.4f} BD",
        ]

        lines += ["", sep]

    # Consolidado global
    if len(env_data) >= 2:
        total_usdt = sum(max(d["liq_usdt"], 0) for d in env_data.values())
        total_loop = sum(max(d["liq_loop"], 0) for d in env_data.values())
        total_dai  = sum(max(d.get("liq_dai", 0), 0) for d in env_data.values())
        lines += ["", "🌐 <b>CONSOLIDADO PROTOCOLO</b>"]

        if total_usdt > 0:
            lines.append(f"  ├─ 💵 USDT total: <b>${total_usdt:,.2f}</b>")
            for en in ("bd_v5", "AG_C_bd"):
                if en not in env_data:
                    continue
                ic2 = "🔵" if "v5" in en.lower() else "🟠"
                v   = max(env_data[en]["liq_usdt"], 0)
                pct = v / total_usdt * 100
                lines.append(f"  │    {ic2} {esc(env_data[en]['tag'])}: {_fl_pct_bar(pct, 8)} <b>{pct:.1f}%</b>  (${v:,.2f})")

        if total_loop > 0:
            lines.append(f"  ├─ 🔄 LOOP total: <b>{total_loop:,.4f}</b>")
            for en in ("bd_v5", "AG_C_bd"):
                if en not in env_data:
                    continue
                ic2 = "🔵" if "v5" in en.lower() else "🟠"
                v   = max(env_data[en]["liq_loop"], 0)
                pct = v / total_loop * 100
                lines.append(f"  │    {ic2} {esc(env_data[en]['tag'])}: {_fl_pct_bar(pct, 8)} <b>{pct:.1f}%</b>  ({v:,.4f})")

        if total_dai > 0:
            lines.append(f"  ├─ 🟡 DAI total:  <b>${total_dai:,.2f}</b>")
            for en in ("bd_v5", "AG_C_bd"):
                if en not in env_data:
                    continue
                ic2 = "🔵" if "v5" in en.lower() else "🟠"
                v   = max(env_data[en].get("liq_dai", 0), 0)
                pct = v / total_dai * 100
                lines.append(f"  │    {ic2} {esc(env_data[en]['tag'])}: {_fl_pct_bar(pct, 8)} <b>{pct:.1f}%</b>  (${v:,.2f})")

        tot  = _fl_proto_stats_total(days=30)
        wr_t = tot["wins"] / tot["trades"] * 100 if tot["trades"] else 0
        lines += [
            f"  ├─ 📈 30d: <b>{tot['trades']:,}</b> trades  ·  <b>{tot['wallets']:,}</b> wallets  ·  WR <b>{wr_t:.0f}%</b>",
            f"  └─ 💎 BD all-time: <b>{tot['bd_alltime']:,.4f} BD</b>",
        ]

    lines += ["", f"<i>🔍 Fonte: contratos WEbdEX · Polygon · {esc(ts_now)}</i>"]
    return "\n".join(lines)

def _fl_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="fl_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="fl_close"),
    )
    return kb


def _fl_fetch_all() -> tuple:
    """Coleta todos os dados on-chain para o dashboard. Retorna (env_data, ts_now, gwei, pol_price)."""
    from webdex_config import CONTRACTS, ADDR_USDT0, ADDR_LPLPUSD, ADDR_DAI, RPC_CAPITAL
    from webdex_chain import chain_pol_price, web3_for_rpc
    from webdex_db import now_br
    import concurrent.futures as _cf

    pol_price = chain_pol_price() or 0.50
    w3        = web3_for_rpc(RPC_CAPITAL, timeout=8)
    ts_now    = now_br().strftime("%d/%m/%Y %H:%M:%S")

    try:
        gwei = float(w3.eth.gas_price) / 1e9
    except Exception:
        gwei = -1.0

    def _collect_env(env_name: str, c_info: dict) -> dict:
        sub_addr     = c_info.get("SUBACCOUNTS", "")
        mgr_addr     = c_info.get("MANAGER", "")
        lp_usdt_addr = c_info.get("LP_USDT", "")
        lp_loop_addr = c_info.get("LP_LOOP", "")

        lp_usdt_s = _fl_supply(w3, lp_usdt_addr, 6) if lp_usdt_addr else -1.0
        lp_loop_s = _fl_supply(w3, lp_loop_addr, 9) if lp_loop_addr else -1.0
        liq_usdt  = _fl_balance(w3, ADDR_USDT0,   sub_addr, 6)  if sub_addr else -1.0
        liq_loop  = _fl_balance(w3, ADDR_LPLPUSD, sub_addr, 9)  if sub_addr else -1.0
        liq_dai   = _fl_balance(w3, ADDR_DAI,     sub_addr, 18) if sub_addr else -1.0
        gas_pol   = _fl_manager_gas(w3, mgr_addr) if mgr_addr else -1.0
        prev      = _fl_last_snapshot(env_name)

        _fl_save_snapshot(env_name, lp_usdt_s, lp_loop_s,
                          liq_usdt, liq_loop, gas_pol, pol_price, liq_d=liq_dai)
        return {
            "tag":            c_info["TAG"],
            "lp_usdt_supply": lp_usdt_s,
            "lp_loop_supply": lp_loop_s,
            "liq_usdt":       liq_usdt,
            "liq_loop":       liq_loop,
            "liq_dai":        liq_dai,
            "gas_pol":        gas_pol,
            "prev":           prev,
            "stat":           _fl_proto_stats(env_name, days=30),
        }

    env_futures = {}
    with _cf.ThreadPoolExecutor(max_workers=2) as ex:
        for env_name, c_info in CONTRACTS.items():
            env_futures[ex.submit(_collect_env, env_name, c_info)] = env_name

    env_data = {}
    for fut, env_name in env_futures.items():
        env_data[env_name] = fut.result()

    return env_data, ts_now, gwei, pol_price


@bot.message_handler(func=lambda m: (m.text or "").strip() in {
    "🧾 Fornecimento e Liquidez", "🧾 Fornecimento & Liquidez"
})
def adm_fornecimento_liquidez(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    loading = bot.send_message(m.chat.id, "🔄 <i>Consultando contratos on-chain...</i>",
                               parse_mode="HTML")
    try:
        env_data, ts_now, gwei, pol_price = _fl_fetch_all()
        txt = _fl_build_text(env_data, ts_now, gwei, pol_price)
        bot.delete_message(m.chat.id, loading.message_id)
        bot.send_message(m.chat.id, txt, parse_mode="HTML", reply_markup=_fl_kb())
    except Exception as e:
        logger.error("[admin] %s", e)
        bot.edit_message_text(f"⚠️ Erro: {e}", m.chat.id, loading.message_id,
                              reply_markup=adm_kb())


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("fl_"))
def _fl_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "fl_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    if c.data == "fl_refresh":
        bot.answer_callback_query(c.id, "🔄 Atualizando dados on-chain...")
        try:
            env_data, ts_now, gwei, pol_price = _fl_fetch_all()
            txt = _fl_build_text(env_data, ts_now, gwei, pol_price)
            bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                                  parse_mode="HTML", reply_markup=_fl_kb())
        except Exception as e:
            logger.error("[admin] %s", e)
            bot.answer_callback_query(c.id, f"⚠️ Erro: {e}")


# ==============================================================================
# 📊 MYBDBOOK ADM — delega para reports.py
# ==============================================================================
@bot.message_handler(func=lambda m: (m.text or "").strip() == "📊 mybdBook ADM")
def adm_mybdbook_adm(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    from webdex_handlers.reports import _handle_myfxbook_adm
    _handle_myfxbook_adm(m)


# ==============================================================================
# 📸 PROGRESSÃO DO CAPITAL — snapshots históricos por ambiente
# ==============================================================================
def _prog_capital_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar", callback_data="prog_refresh"),
        types.InlineKeyboardButton("✅ Fechar",    callback_data="prog_close"),
    )
    return kb

def _prog_capital_text():
    """Gera o texto do dashboard Progressão do Capital. 100% DB, zero RPC."""
    now_dt = datetime.now()
    sep    = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    def _pct(val, ref):
        return (val / ref * 100) if ref and ref != 0 else 0.0

    def _dico(d):
        return "📈" if d is not None and d >= 0 else ("📉" if d is not None and d < 0 else "─")

    # ─────────────────────────────────────────────────────────────────────────
    # COLETA DE DADOS — tudo em paralelo lógico via DB (sem RPC)
    # ─────────────────────────────────────────────────────────────────────────

    # 1. TVL fl_snapshots — últimos 10 por ambiente para sparkline + delta
    pool_data: dict = {}
    try:
        with DB_LOCK:
            _fl_rows = conn.execute(
                "SELECT env, total_usd, liq_usdt, ts FROM fl_snapshots "
                "WHERE total_usd > 0 ORDER BY env, ts DESC"
            ).fetchall()
        _fl_map: dict = {}
        for _fe, _fv, _fliq, _ft in _fl_rows:
            _fl_map.setdefault(str(_fe), []).append({
                "tvl": float(_fv or 0), "liq": float(_fliq or 0), "ts": str(_ft or "")[:16]
            })
        for _ek, _snaps in _fl_map.items():
            _c = _snaps[0]
            _p = _snaps[1] if len(_snaps) >= 2 else None
            _d_tvl = (_c["tvl"] - _p["tvl"]) if _p else None
            pool_data[_ek] = {
                "curr_tvl": _c["tvl"], "curr_liq": _c["liq"], "curr_ts": _c["ts"],
                "prev_tvl": _p["tvl"] if _p else None, "prev_ts": _p["ts"] if _p else None,
                "delta": _d_tvl, "delta_pct": _pct(_d_tvl, _p["tvl"]) if _d_tvl and _p else None,
                # últimos 7 snapshots para sparkline ASCII
                "history": [s["tvl"] for s in _snaps[:7]],
            }
    except Exception as _e1:
        logger.debug("[prog_capital] fl_snapshots: %s", _e1)

    # 2. Protocol_ops — por ambiente + totais + top 3
    proto_env: dict = {}
    proto_total: dict = {"wallets": 0, "trades": 0, "profit": 0.0,
                         "wins": 0, "losses": 0, "fee_bd": 0.0, "first": "", "last": ""}
    top_traders: list = []
    try:
        with DB_LOCK:
            _pe_rows = conn.execute("""
                SELECT env,
                    COUNT(DISTINCT wallet)                     AS wallets,
                    COUNT(*)                                   AS trades,
                    ROUND(SUM(profit), 4)                      AS profit,
                    COUNT(CASE WHEN profit > 0 THEN 1 END)     AS wins,
                    COUNT(CASE WHEN profit < 0 THEN 1 END)     AS losses,
                    ROUND(SUM(fee_bd), 4)                      AS fee_bd,
                    ROUND(SUM(gas_pol), 4)                     AS gas_pol,
                    MIN(ts)                                    AS first_ts,
                    MAX(ts)                                    AS last_ts
                FROM protocol_ops
                WHERE wallet != '' AND env != 'UNKNOWN'
                GROUP BY env
            """).fetchall()
            _pt = conn.execute("""
                SELECT COUNT(DISTINCT wallet), COUNT(*),
                       ROUND(SUM(profit),4),
                       COUNT(CASE WHEN profit>0 THEN 1 END),
                       COUNT(CASE WHEN profit<0 THEN 1 END),
                       ROUND(SUM(fee_bd),4), ROUND(SUM(gas_pol),4),
                       MIN(ts), MAX(ts)
                FROM protocol_ops WHERE wallet != '' AND env != 'UNKNOWN'
            """).fetchone()
            top_traders = conn.execute("""
                SELECT wallet, env, COUNT(*) AS t,
                       ROUND(SUM(profit),4) AS p,
                       COUNT(CASE WHEN profit>0 THEN 1 END) AS w
                FROM protocol_ops WHERE wallet!='' AND env!='UNKNOWN'
                GROUP BY wallet, env ORDER BY p DESC LIMIT 5
            """).fetchall()
        for _r in _pe_rows:
            proto_env[str(_r[0])] = {
                "wallets": int(_r[1] or 0), "trades": int(_r[2] or 0),
                "profit":  float(_r[3] or 0), "wins":  int(_r[4] or 0),
                "losses":  int(_r[5] or 0),   "fee_bd": float(_r[6] or 0),
                "gas_pol": float(_r[7] or 0),
                "first":   str(_r[8] or "")[:10], "last": str(_r[9] or "")[:16],
            }
        if _pt:
            proto_total = {
                "wallets": int(_pt[0] or 0), "trades":  int(_pt[1] or 0),
                "profit":  float(_pt[2] or 0), "wins":  int(_pt[3] or 0),
                "losses":  int(_pt[4] or 0),   "fee_bd": float(_pt[5] or 0),
                "gas_pol": float(_pt[6] or 0),
                "first":   str(_pt[7] or "")[:10], "last": str(_pt[8] or "")[:16],
            }
    except Exception as _e2:
        logger.debug("[prog_capital] protocol_ops: %s", _e2)

    # 3. Usuários bot — user_capital_snapshots (histórico) + capital_cache (fallback)
    user_prog: list = []
    try:
        with DB_LOCK:
            _snap_all = conn.execute("""
                SELECT s.chat_id, s.env, s.total_usd, s.ts, u.username
                FROM user_capital_snapshots s
                LEFT JOIN users u ON u.chat_id = s.chat_id
                WHERE s.total_usd > 0.5
                ORDER BY s.chat_id, s.env, s.ts DESC
            """).fetchall()
        _by_user: dict = {}
        _umap: dict = {}
        for _cid, _env, _usd, _ts, _un in _snap_all:
            _key = (int(_cid), str(_env or "AG_C_bd"))
            _by_user.setdefault(_key, []).append((float(_usd or 0), str(_ts or "")))
            if _un and int(_cid) not in _umap:
                _umap[int(_cid)] = str(_un)
        for (_cid2, _env2), _snaps2 in _by_user.items():
            _c2, _cts2 = _snaps2[0]
            _p2, _pts2 = (_snaps2[1][0], _snaps2[1][1]) if len(_snaps2) >= 2 else (None, None)
            _dlt = (_c2 - _p2) if _p2 is not None else None
            user_prog.append({
                "chat_id": _cid2, "env": _env2, "uname": _umap.get(_cid2),
                "curr": _c2, "curr_ts": str(_cts2)[:16],
                "prev": _p2, "prev_ts": str(_pts2)[:16] if _pts2 else None,
                "delta": _dlt,
                "delta_pct": _pct(_dlt, _p2) if _dlt is not None and _p2 else None,
            })
        user_prog.sort(key=lambda x: x["delta"] if x["delta"] is not None else -1e9, reverse=True)
    except Exception as _e3:
        logger.debug("[prog_capital] snapshots: %s", _e3)

    # fallback capital_cache
    _seen = {(u["chat_id"], u["env"]) for u in user_prog}
    try:
        with DB_LOCK:
            _cc = conn.execute("""
                SELECT cc.chat_id, COALESCE(cc.env,'AG_C_bd'), cc.total_usd,
                       cc.updated_ts, u.username
                FROM capital_cache cc LEFT JOIN users u ON u.chat_id = cc.chat_id
                WHERE cc.total_usd > 0.5
            """).fetchall()
        for _rc in _cc:
            _cid3, _env3, _usd3, _uts3, _un3 = _rc
            if (int(_cid3), str(_env3)) not in _seen:
                _cts3 = datetime.fromtimestamp(float(_uts3)).strftime("%m/%d %H:%M") if _uts3 else "?"
                user_prog.append({
                    "chat_id": int(_cid3), "env": str(_env3), "uname": _un3,
                    "curr": float(_usd3 or 0), "curr_ts": _cts3,
                    "prev": None, "prev_ts": None,
                    "delta": None, "delta_pct": None, "_cache": True,
                })
    except Exception as _e4:
        logger.debug("[prog_capital] cache fallback: %s", _e4)

    # agregações bot
    _udelta   = [u for u in user_prog if u["delta"] is not None]
    _bot_curr = sum(u["curr"] for u in user_prog)
    _bot_prev = sum(u["prev"] for u in _udelta if u["prev"])
    _bot_delt = sum(u["delta"] for u in _udelta)
    _bot_dpct = _pct(_bot_delt, _bot_prev)

    _users_by_env: dict = {}
    for _u in user_prog:
        _users_by_env.setdefault(str(_u["env"]), []).append(_u)

    # tabela de progresso diário (user_capital_snapshots agrupado por data)
    daily_user_cap: list = []
    try:
        with DB_LOCK:
            _daily = conn.execute("""
                SELECT DATE(ts) AS dia,
                       COUNT(DISTINCT chat_id) AS users,
                       ROUND(AVG(total_usd), 2) AS avg_cap,
                       ROUND(MAX(total_usd), 2) AS max_cap
                FROM user_capital_snapshots
                WHERE total_usd > 0.5
                GROUP BY DATE(ts)
                ORDER BY dia DESC LIMIT 7
            """).fetchall()
        daily_user_cap = list(reversed(_daily))
    except Exception:
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # MONTA MENSAGEM
    # ─────────────────────────────────────────────────────────────────────────
    # bd_v5 sempre primeiro (principal), AG_C_bd depois (colaboração)
    _all_envs = sorted(
        set(list(pool_data.keys()) + list(proto_env.keys()) + list(_users_by_env.keys())),
        key=lambda e: (0 if "v5" in e.lower() else 1, e)
    )

    lines = [
        "📸 <b>PROGRESSÃO DO CAPITAL — WEbdEX</b>",
        f"🕒 <i>{now_dt.strftime('%d/%m/%Y %H:%M')}</i>",
        sep,
    ]

    # ═══ POR AMBIENTE ══════════════════════════════════════════════════════════
    for _ek in _all_envs:
        _eico = "🔵" if "v5" in str(_ek).lower() else "🟠"
        lines += ["", f"{_eico} <b>{esc(_ek)}</b>", ""]

        # ── TVL ─────────────────────────────────────────────────────────────
        _pd = pool_data.get(_ek)
        if _pd:
            _td = _pd["delta"]
            lines.append(f"  🏦 <b>TVL (USDT0 no protocolo)</b>")
            if _pd["prev_tvl"] is not None:
                lines.append(
                    f"     Antes → Agora: <b>${_pd['prev_tvl']:,.2f}</b> → <b>${_pd['curr_tvl']:,.2f}</b>"
                )
                lines.append(
                    f"     └─ {_dico(_td)} <b>{_td:>+,.2f} USD</b>  (<b>{(_pd['delta_pct'] or 0.0):>+.2f}%</b>)"
                )
            else:
                lines.append(f"     Atual: <b>${_pd['curr_tvl']:,.2f}</b>  <i>[{_pd['curr_ts']}]</i>")
                lines.append("     └─ <i>(aguardando 2º snapshot do worker ~30min)</i>")

        # ── Traders on-chain ─────────────────────────────────────────────────
        _pe = proto_env.get(_ek)
        if _pe:
            _wr  = _pct(_pe["wins"], _pe["trades"])
            _pf  = (_pe["wins"] / _pe["losses"]) if _pe["losses"] > 0 else float(_pe["wins"] or 0)
            lines += [
                "",
                f"  🌐 <b>RESULTADOS ACUMULADOS (on-chain)</b>",
                f"     ├─ 👥 Carteiras:   <b>{_pe['wallets']:,}</b>",
                f"     ├─ 📊 Trades:      <b>{_pe['trades']:,}</b>",
                f"     ├─ {_dico(_pe['profit'])} P&amp;L líquido: <b>{_pe['profit']:>+,.4f} USDT</b>",
                f"     ├─ 🏆 Acerto:      <b>{_wr:.1f}%</b>",
                f"     ├─ 📐 Profit Factor: <b>{_pf:.2f}</b>",
                f"     └─ 💎 Fees BD:     <b>{_pe['fee_bd']:,.4f}</b>",
            ]

        # ── Usuários bot ─────────────────────────────────────────────────────
        _eu = _users_by_env.get(_ek, [])
        if _eu:
            _eu_curr = sum(u["curr"] for u in _eu)
            _eu_prev = sum(u["prev"] for u in _eu if u["prev"])
            _eu_delt = sum(u["delta"] for u in _eu if u["delta"] is not None)
            _eu_w    = [u for u in _eu if u["delta"] is not None]
            lines += [
                "",
                f"  💼 <b>CAPITAL DOS USUÁRIOS (bot)</b>",
            ]
            if _eu_w:
                lines.append(
                    f"     Antes → Agora: <b>${_eu_prev:,.2f}</b> → <b>${_eu_curr:,.2f}</b>"
                )
                lines.append(
                    f"     └─ {_dico(_eu_delt)} <b>{_eu_delt:>+,.2f} USD</b>"
                    f"  (<b>{_pct(_eu_delt, _eu_prev):>+.2f}%</b>)"
                )
            else:
                lines.append(f"     Capital atual: <b>${_eu_curr:,.2f}</b>  ({len(_eu)} usuários)")
            lines.append("")

            for _u in _eu:
                _lbl = f"@{esc(_u['uname'])}" if _u.get("uname") else f"…{str(_u['chat_id'])[-4:]}"
                if _u["delta"] is not None:
                    _ud = _u["delta"]
                    lines.append(
                        f"     • <b>{_lbl}</b>"
                        f"  ${_u['prev']:,.0f} → ${_u['curr']:,.0f}"
                        f"  {_dico(_ud)} <b>{_ud:>+,.2f}</b> ({(_u['delta_pct'] or 0.0):>+.2f}%)"
                    )
                    lines.append(
                        f"       <i>{_u['prev_ts']} → {_u['curr_ts']}</i>"
                    )
                else:
                    _note = "(cache)" if _u.get("_cache") else "(1 snapshot)"
                    lines.append(
                        f"     • <b>{_lbl}</b>  ${_u['curr']:,.2f}  <i>{_note}</i>"
                    )

    # ═══ CONSOLIDADO GLOBAL ════════════════════════════════════════════════════
    _tvl_curr = sum(v["curr_tvl"] for v in pool_data.values())
    _tvl_prev = sum(v["prev_tvl"] for v in pool_data.values() if v["prev_tvl"] is not None)
    _tvl_delt = _tvl_curr - _tvl_prev if _tvl_prev > 0 else None

    lines += ["", sep, "", "🌐 <b>CONSOLIDADO GLOBAL</b>", ""]

    # TVL + on-chain — linha compacta
    if _tvl_prev > 0:
        _tvl_d_str = f"{_dico(_tvl_delt)} <b>{_tvl_delt:>+,.0f}</b>" if _tvl_delt else ""
        lines += [
            f"  🏦 <b>TVL Total:</b> ${_tvl_prev:,.0f} → ${_tvl_curr:,.0f}  {_tvl_d_str}",
            "",
        ]
    else:
        lines += [f"  🏦 <b>TVL Total:</b> <b>${_tvl_curr:,.0f}</b>", ""]

    if proto_total["trades"] > 0:
        _pt_wr = _pct(proto_total["wins"], proto_total["trades"])
        _pt_pf = (proto_total["wins"] / proto_total["losses"]) if proto_total["losses"] > 0 else float(proto_total["wins"] or 0)
        _pt_pico = _dico(proto_total["profit"])
        lines += [
            f"  👥 <b>{proto_total['wallets']:,}</b> carteiras  ·  📊 <b>{proto_total['trades']:,}</b> trades",
            f"  {_pt_pico} P&amp;L: <b>{proto_total['profit']:>+,.0f} USDT</b>  ·  🏆 <b>{_pt_wr:.1f}%</b>  ·  PF: <b>{_pt_pf:.2f}</b>",
            "",
        ]

    # Top traders global
    if top_traders:
        lines.append("  🏆 <b>Top 5 Traders (P&amp;L acumulado)</b>")
        for _pos, (_tw, _te, _tt, _tp, _tw2) in enumerate(top_traders, 1):
            _twr  = _pct(_tw2, _tt)
            _eico = "🔵" if "v5" in str(_te).lower() else "🟠"
            _ws   = f"{str(_tw)[:6]}…{str(_tw)[-4:]}" if len(str(_tw)) > 12 else str(_tw)
            lines.append(
                f"     {_medal(_pos)} {_eico} <code>{esc(_ws)}</code>"
                f"  {_dico(_tp)} <b>{float(_tp or 0):>+,.4f}</b>"
                f"  ({int(_tt):,}t · {_twr:.0f}%✅)"
            )
        lines.append("")

    # Capital bot total
    if user_prog:
        if _udelta:
            lines.append(
                f"  💼 <b>Capital Bot:</b> ${_bot_prev:,.0f} → ${_bot_curr:,.0f}"
                f"  {_dico(_bot_delt)} <b>{_bot_delt:>+,.2f}</b> ({_bot_dpct:>+.2f}%)"
            )
        else:
            lines.append(f"  💼 <b>Capital Bot:</b> <b>${_bot_curr:,.0f}</b>  ({len(user_prog)} usuários)")

    # Tabela diária de capital bot (se disponível)
    if daily_user_cap:
        lines += ["", "  📅 <b>Evolução Diária do Capital Bot</b>"]
        lines.append("  <code>Data       Usuários  Avg Capital   Max Capital</code>")
        for _dia, _du, _avg, _mx in daily_user_cap:
            lines.append(
                f"  <code>{str(_dia)[5:]}   {_du:>4}u    ${_avg:>10,.2f}   ${_mx:>10,.2f}</code>"
            )

    lines += [
        "",
        "<i>💡 TVL = fl_snapshots (worker ~30min) · Capital bot = mybdBook snapshots · On-chain = todos os traders desde deploy</i>",
    ]
    return "\n".join(lines)

@bot.message_handler(func=lambda m: (m.text or "").strip() == "📸 Progressão do Capital")
def adm_progressao_capital(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    try:
        _send_long(m.chat.id, _prog_capital_text(), reply_markup=_prog_capital_kb())
    except Exception as e:
        logger.error("[admin] %s", e)
        bot.send_message(m.chat.id, f"⚠️ Erro ao enviar: {e}", reply_markup=adm_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("prog_"))
def _prog_capital_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "prog_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    bot.answer_callback_query(c.id, "⏳ Atualizando...")
    try:
        bot.edit_message_text(
            _prog_capital_text(), c.message.chat.id, c.message.message_id,
            parse_mode="HTML", reply_markup=_prog_capital_kb()
        )
    except Exception as e:
        logger.error("[prog_capital] refresh error: %s", e)


# ==============================================================================
# 📡 STATUS MONITOR — saúde do vigia e threads em tempo real
# ==============================================================================
def _status_monitor_text() -> str:
    import threading as _th
    from webdex_monitor import HEALTH

    now = time.time()

    # Uptime
    up_s  = int(now - HEALTH.get("started_at", now))
    up_h, up_m = divmod(up_s // 60, 60)
    uptime = f"{up_h}h {up_m}m" if up_h else f"{up_m}m"

    # Último bloco e latência
    last_block   = HEALTH.get("last_block_seen", 0)
    rpc_lat      = HEALTH.get("rpc_latency_ms", 0)
    rpc_lat_avg  = HEALTH.get("rpc_latency_avg", 0)
    capture_rate = HEALTH.get("capture_rate", 100.0)
    loops        = HEALTH.get("vigia_loops", 0)
    trades_det   = HEALTH.get("logs_trade", 0)
    transfers    = HEALTH.get("logs_transfer", 0)
    rpc_errors   = HEALTH.get("rpc_errors_total", 0)
    last_err     = HEALTH.get("last_error", "") or "—"
    cooldown_ts  = float(HEALTH.get("cooldown_until") or 0)

    # Segundos desde o último fetch OK
    last_ok = HEALTH.get("last_rpc_ok_ts", 0)
    ago_ok  = int(now - last_ok) if last_ok else -1
    ok_str  = f"{ago_ok}s atrás" if ago_ok >= 0 else "—"

    # Status do cooldown
    if cooldown_ts > now:
        cd_str = f"🔴 cooldown {int(cooldown_ts - now)}s"
    else:
        cd_str = "🟢 normal"

    # Threads vivas
    alive = [t.name for t in _th.enumerate()]
    critical = ["vigia", "notif_worker", "chain_cache_worker", "sentinela", "watchdog"]
    thread_lines = []
    for name in critical:
        icon = "🟢" if name in alive else "🔴"
        thread_lines.append(f"  {icon} {name}")

    # Wallet map
    from webdex_chain import _WALLET_MAP_CACHE, rpc_pool
    wm_age = int(now - _WALLET_MAP_CACHE["ts"]) if _WALLET_MAP_CACHE["ts"] > 0 else -1
    wm_size = len(_WALLET_MAP_CACHE["data"][0]) if _WALLET_MAP_CACHE.get("data") else 0
    wm_str = f"{wm_size} wallets (cache {wm_age}s)" if wm_age >= 0 else "não carregado"

    # RPC Pool status
    pool_lines = []
    labels = ["RPC_URL", "RPC_CAPITAL", "RPC_FALLBACK"]
    for i, (errs, cd_until) in enumerate(zip(rpc_pool._errors, rpc_pool._cooldown_until)):
        label = labels[i] if i < len(labels) else f"RPC#{i}"
        if cd_until > now:
            icon = "🔴"
            detail = f"cooldown {int(cd_until - now)}s"
        else:
            icon = "🟢"
            detail = f"erros: {errs}" if errs > 0 else "ok"
        pool_lines.append(f"  {icon} {label} ({detail})")

    # protocol_ops sync status
    proto_sync_icon = "🟢" if "protocol_ops_sync" in alive else "🔴"
    try:
        with DB_LOCK:
            _ops_count = conn.execute("SELECT COUNT(*) FROM protocol_ops").fetchone()[0]
            _sync_b1 = conn.execute(
                "SELECT value FROM config WHERE key='proto_sync_block_AG_C_bd'"
            ).fetchone()
            _sync_b2 = conn.execute(
                "SELECT value FROM config WHERE key='proto_sync_block_bd_v5'"
            ).fetchone()
        _sync_b1_str = f"AG_C_bd→{int(_sync_b1[0]):,}" if _sync_b1 else "AG_C_bd→n/a"
        _sync_b2_str = f"bd_v5→{int(_sync_b2[0]):,}" if _sync_b2 else "bd_v5→n/a"
        proto_sync_str = (
            f"{proto_sync_icon} ops={_ops_count:,}  "
            f"{_sync_b1_str}  {_sync_b2_str}"
        )
    except Exception:
        proto_sync_str = f"{proto_sync_icon} (indisponível)"

    return (
        "📡 <b>STATUS DO MONITOR</b>\n\n"
        f"⏱️ Uptime:       {uptime}\n"
        f"🔄 RPC global:  {cd_str}\n"
        f"🧱 Último bloco: {last_block:,}\n"
        f"🕒 Último fetch: {ok_str}\n"
        f"📶 Latência:     {rpc_lat:.0f}ms  (avg {rpc_lat_avg:.0f}ms)\n"
        f"📊 Capture rate: {capture_rate:.1f}%\n"
        f"🔁 Loops vigia:  {loops:,}\n\n"
        f"📈 Eventos detectados\n"
        f"  Trades:     {trades_det}\n"
        f"  Transfers:  {transfers}\n"
        f"  RPC errors: {rpc_errors}\n\n"
        f"🔌 RPC Pool (3 endpoints)\n"
        + "\n".join(pool_lines) + "\n\n"
        f"🗂️ Wallet map: {wm_str}\n\n"
        f"🔗 Protocol sync (protocol_ops)\n"
        f"  {proto_sync_str}\n\n"
        f"🧵 Threads críticas\n"
        + "\n".join(thread_lines) + "\n\n"
        f"⚠️ Último erro:\n<code>{esc(str(last_err)[:200])}</code>"
    )

def _status_monitor_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Atualizar",          callback_data="status_refresh"),
        types.InlineKeyboardButton("🔃 Refresh wallet map", callback_data="status_reload_wm"),
    )
    kb.row(types.InlineKeyboardButton("✅ Fechar", callback_data="status_close"))
    return kb

@bot.message_handler(func=lambda m: (m.text or "").strip() == "📡 Status Monitor")
def adm_status_monitor(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    try:
        bot.send_message(m.chat.id, _status_monitor_text(), parse_mode="HTML",
                         reply_markup=_status_monitor_kb())
    except Exception as e:
        logger.error("[admin] %s", e)
        bot.send_message(m.chat.id, f"⚠️ Erro: {e}", reply_markup=adm_kb())

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("status_"))
def _status_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")

    if c.data == "status_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)

    if c.data == "status_reload_wm":
        from webdex_chain import get_active_wallet_map
        get_active_wallet_map(force_refresh=True)
        bot.answer_callback_query(c.id, "✅ Wallet map recarregado!")

    # status_refresh ou após reload_wm
    try:
        bot.edit_message_text(_status_monitor_text(), c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_status_monitor_kb())
    except Exception:
        pass
    if c.data == "status_refresh":
        bot.answer_callback_query(c.id, "Atualizado!")


# ==============================================================================
# 📨 GERAR CONVITES — paginado com navegação inline
# ==============================================================================
_CONVITES_PER_PAGE = 5
_CONVITES_CACHE: dict[int, list] = {}   # chat_id → lista de wallets
_CONVITES_PAGE:  dict[int, int]  = {}   # chat_id → página atual

def _convites_build(chat_id: int, page: int, bot_username: str):
    wallets = _CONVITES_CACHE.get(chat_id, [])
    total   = len(wallets)
    if not total:
        return "✅ Todas as wallets já estão registradas!", None
    pages   = max(1, (total + _CONVITES_PER_PAGE - 1) // _CONVITES_PER_PAGE)
    page    = max(0, min(page, pages - 1))
    _CONVITES_PAGE[chat_id] = page
    start   = page * _CONVITES_PER_PAGE
    chunk   = wallets[start:start + _CONVITES_PER_PAGE]

    lines = [f"📨 <b>CONVITES</b>  •  {total} sem registro  •  Pág {page+1}/{pages}\n"]
    kb = types.InlineKeyboardMarkup()
    for w in chunk:
        wallet = w["wallet"]
        short  = wallet[:6] + "..." + wallet[-4:]
        link   = f"https://t.me/{bot_username}?start={wallet}" if bot_username else wallet
        sinal  = "+" if (w["lucro"] or 0) >= 0 else ""
        lucro  = f"{sinal}{(w['lucro'] or 0):.2f}"
        lines.append(
            f"<code>{short}</code> [{w['env']}]  "
            f"T:{w['trade_count']} W:{w['wins']}/L:{w['losses']}  L:{lucro}"
        )
        kb.row(types.InlineKeyboardButton(f"🔗 Convidar {short}", url=link))

    # Navegação
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️ Ant", callback_data=f"convite_pg_{page-1}"))
    nav.append(types.InlineKeyboardButton(f"{page+1}/{pages}", callback_data="convite_noop"))
    if page < pages - 1:
        nav.append(types.InlineKeyboardButton("Próx ➡️", callback_data=f"convite_pg_{page+1}"))
    if nav:
        kb.row(*nav)
    kb.row(
        types.InlineKeyboardButton("📥 CSV completo", callback_data="convite_csv"),
        types.InlineKeyboardButton("✅ Fechar",        callback_data="convite_close"),
    )
    return "\n".join(lines), kb

@bot.message_handler(func=lambda m: (m.text or "").strip() == "📨 Gerar Convites")
def adm_gerar_convites(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    try:
        bot_username = (bot.get_me().username or "")
        wallets = get_known_wallets_unregistered(limit=500)
        _CONVITES_CACHE[m.chat.id] = wallets
        _CONVITES_PAGE[m.chat.id]  = 0
        txt, kb = _convites_build(m.chat.id, 0, bot_username)
        if kb is None:
            return bot.send_message(m.chat.id, txt, reply_markup=adm_kb())
        bot.send_message(m.chat.id, txt, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error("[admin] %s", e)
        bot.send_message(m.chat.id, f"⚠️ Erro: {e}", reply_markup=adm_kb())

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("convite_"))
def _convites_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    cid  = c.from_user.id
    data = c.data

    if data == "convite_noop":
        return bot.answer_callback_query(c.id)

    if data == "convite_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)

    if data == "convite_csv":
        bot.answer_callback_query(c.id, "⏳ Gerando CSV...")
        _do_convites_csv(c.message.chat.id)
        return

    if data.startswith("convite_pg_"):
        try:
            page = int(data.split("_")[-1])
        except ValueError:
            return bot.answer_callback_query(c.id)
        bot_username = (bot.get_me().username or "")
        txt, kb = _convites_build(cid, page, bot_username)
        if kb:
            try:
                bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                                      parse_mode="HTML", reply_markup=kb)
            except Exception:
                pass
        bot.answer_callback_query(c.id)

def _do_convites_csv(chat_id: int):
    try:
        wallets = _CONVITES_CACHE.get(chat_id) or get_known_wallets_unregistered(limit=500)
        bot_info = bot.get_me()
        bot_username = bot_info.username or "SEU_BOT"
        import io
        lines = ["wallet,env,trades,wins,losses,lucro,ultimo_trade,link_convite"]
        for w in wallets:
            wallet = w["wallet"]
            link   = f"https://t.me/{bot_username}?start={wallet}"
            lines.append(
                f"{wallet},{w['env']},{w['trade_count']},{w['wins']},"
                f"{w['losses']},{w['lucro']:.4f},{w['last_trade'] or ''},{link}"
            )
        csv_bytes = "\n".join(lines).encode("utf-8")
        bot.send_document(
            chat_id,
            document=io.BytesIO(csv_bytes),
            visible_file_name="convites_wallets.csv",
            caption=f"📨 {len(wallets)} wallets — links de convite prontos.",
        )
    except Exception as e:
        logger.error("[admin] %s", e)
        bot.send_message(chat_id, f"⚠️ Erro ao gerar CSV: {e}")


@bot.message_handler(commands=["convites_csv"])
def adm_convites_csv(m):
    if not _is_admin(m.chat.id):
        return
    bot.send_chat_action(m.chat.id, "upload_document")
    _do_convites_csv(m.chat.id)


# ==============================================================================
# 📢 BROADCAST — com seletor de audiência e preview interativo
# ==============================================================================
_BROADCAST_PENDING:  dict[int, str] = {}   # chat_id → texto da mensagem
_BROADCAST_AUDIENCE: dict[int, str] = {}   # chat_id → filtro escolhido

def _bcast_audience_kb():
    """Inline keyboard para selecionar audiência."""
    try:
        total    = cursor.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
        online   = cursor.execute(
            "SELECT COUNT(*) FROM users WHERE COALESCE(last_seen_ts,0) >= ?",
            (time.time() - 24 * 3600,)
        ).fetchone()[0]
        v5       = cursor.execute("SELECT COUNT(*) FROM users WHERE active=1 AND env LIKE '%v5%'").fetchone()[0]
        agbd     = cursor.execute("SELECT COUNT(*) FROM users WHERE active=1 AND env LIKE '%ag%' AND env LIKE '%bd%'").fetchone()[0]
    except Exception:
        total = online = v5 = agbd = 0

    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton(f"👥 Todos ativos ({total})",    callback_data="bcast_aud_all"))
    kb.row(types.InlineKeyboardButton(f"🟢 Online 24h ({online})",     callback_data="bcast_aud_24h"))
    kb.row(
        types.InlineKeyboardButton(f"🌐 V5 ({v5})",    callback_data="bcast_aud_v5"),
        types.InlineKeyboardButton(f"⚙️ AG_bd ({agbd})", callback_data="bcast_aud_agbd"),
    )
    kb.row(types.InlineKeyboardButton("❌ Cancelar", callback_data="bcast_cancel"))
    return kb

@bot.message_handler(func=lambda m: (m.text or "").strip() == "📢 Broadcast")
def adm_broadcast_start(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_message(
        m.chat.id,
        "📢 <b>BROADCAST</b>\n\n"
        "Selecione o público-alvo:",
        parse_mode="HTML",
        reply_markup=_bcast_audience_kb(),
    )

@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("bcast_aud_"))
def _broadcast_audience_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    _BROADCAST_AUDIENCE[c.from_user.id] = c.data.replace("bcast_aud_", "")
    labels = {"all": "Todos ativos", "24h": "Online 24h", "v5": "Ambiente V5", "agbd": "Ambiente AG_bd"}
    label  = labels.get(_BROADCAST_AUDIENCE[c.from_user.id], "?")
    bot.edit_message_text(
        f"📢 <b>Broadcast → {label}</b>\n\n"
        "Digite a mensagem abaixo.\n"
        "💡 Suporta HTML (<code>&lt;b&gt;</code>, <code>&lt;i&gt;</code>, links).\n"
        "Envie /cancelar para abortar.",
        c.message.chat.id, c.message.message_id,
        parse_mode="HTML",
    )
    bot.answer_callback_query(c.id, f"✅ Audiência: {label}")
    bot.register_next_step_handler_by_chat_id(c.from_user.id, _broadcast_receive_text)

_MAX_BROADCAST_CHARS = 4000   # Telegram limita mensagens a ~4096 chars

def _broadcast_receive_text(m):
    if not _is_admin(m.chat.id):
        return
    txt = (m.text or "").strip()
    if txt.lower() in ["/cancelar", "cancelar"]:
        _BROADCAST_AUDIENCE.pop(m.chat.id, None)
        return bot.send_message(m.chat.id, "❌ Broadcast cancelado.", reply_markup=adm_kb())
    if not txt:
        return bot.send_message(m.chat.id, "⚠️ Mensagem vazia. Tente novamente.", reply_markup=adm_kb())
    if len(txt) > _MAX_BROADCAST_CHARS:
        return bot.send_message(
            m.chat.id,
            f"⚠️ Mensagem muito longa ({len(txt):,} chars). Máximo: {_MAX_BROADCAST_CHARS:,} chars.",
            reply_markup=adm_kb(),
        )

    audience = _BROADCAST_AUDIENCE.get(m.chat.id, "all")
    try:
        if audience == "24h":
            n = cursor.execute(
                "SELECT COUNT(*) FROM users WHERE COALESCE(last_seen_ts,0) >= ?",
                (time.time() - 24 * 3600,)
            ).fetchone()[0]
        elif audience == "v5":
            n = cursor.execute("SELECT COUNT(*) FROM users WHERE active=1 AND env LIKE '%v5%'").fetchone()[0]
        elif audience == "agbd":
            n = cursor.execute("SELECT COUNT(*) FROM users WHERE active=1 AND env LIKE '%ag%' AND env LIKE '%bd%'").fetchone()[0]
        else:
            n = cursor.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
    except Exception:
        n = 0

    labels = {"all": "Todos ativos", "24h": "Online 24h", "v5": "V5", "agbd": "AG_bd"}
    label  = labels.get(audience, "?")
    _BROADCAST_PENDING[m.chat.id] = txt

    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton(f"✅ Enviar para {n} pessoas", callback_data="bcast_confirm"),
        types.InlineKeyboardButton("✏️ Editar",                   callback_data="bcast_edit"),
    )
    kb.row(types.InlineKeyboardButton("❌ Cancelar", callback_data="bcast_cancel"))

    preview = txt[:400] + ("..." if len(txt) > 400 else "")
    bot.send_message(
        m.chat.id,
        f"📢 <b>PREVIEW — {label}</b>\n\n"
        f"<blockquote>{preview}</blockquote>\n\n"
        f"👥 <b>{n} destinatários</b>",
        parse_mode="HTML",
        reply_markup=kb,
    )

@bot.callback_query_handler(func=lambda c: c.data in ("bcast_confirm", "bcast_cancel", "bcast_edit"))
def _broadcast_callback(c):
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")

    if c.data == "bcast_cancel":
        _BROADCAST_PENDING.pop(c.from_user.id, None)
        _BROADCAST_AUDIENCE.pop(c.from_user.id, None)
        bot.edit_message_text("❌ Broadcast cancelado.", c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id, "Cancelado.")

    if c.data == "bcast_edit":
        _BROADCAST_PENDING.pop(c.from_user.id, None)
        bot.edit_message_text(
            "✏️ Digite a nova mensagem:",
            c.message.chat.id, c.message.message_id,
        )
        bot.answer_callback_query(c.id)
        bot.register_next_step_handler_by_chat_id(c.from_user.id, _broadcast_receive_text)
        return

    # bcast_confirm
    txt      = _BROADCAST_PENDING.pop(c.from_user.id, None)
    audience = _BROADCAST_AUDIENCE.pop(c.from_user.id, "all")
    if not txt:
        return bot.answer_callback_query(c.id, "⚠️ Nenhuma mensagem pendente.")

    bot.edit_message_text("⏳ Enviando...", c.message.chat.id, c.message.message_id)
    bot.answer_callback_query(c.id, "Enviando!")
    admin_chat_id = c.from_user.id

    def _send_broadcast():
        with DB_LOCK:
            cur = conn.cursor()
            if audience == "24h":
                rows = cur.execute(
                    "SELECT chat_id FROM users WHERE COALESCE(last_seen_ts,0) >= ?",
                    (time.time() - 24 * 3600,)
                ).fetchall()
            elif audience == "v5":
                rows = cur.execute("SELECT chat_id FROM users WHERE active=1 AND env LIKE '%v5%'").fetchall()
            elif audience == "agbd":
                rows = cur.execute("SELECT chat_id FROM users WHERE active=1 AND env LIKE '%ag%' AND env LIKE '%bd%'").fetchall()
            else:
                rows = cur.execute("SELECT chat_id FROM users WHERE active=1").fetchall()

        ids     = [int(r[0]) for r in rows]
        sent    = failed = blocked = 0
        total   = len(ids)

        for i, cid in enumerate(ids, 1):
            try:
                bot.send_message(cid, txt, parse_mode="HTML")
                sent += 1
                time.sleep(0.05)
            except Exception as ex:
                err = str(ex).lower()
                if any(w in err for w in ("blocked", "deactivated", "not found", "forbidden")):
                    blocked += 1
                else:
                    failed += 1
            # Progresso a cada 25%
            if total > 10 and i % max(1, total // 4) == 0:
                try:
                    bot.send_message(
                        admin_chat_id,
                        f"⏳ Progresso: {i}/{total}  ({sent} OK, {blocked} bloqueados)",
                    )
                except Exception:
                    pass

        try:
            bot.send_message(
                admin_chat_id,
                f"📢 <b>Broadcast concluído!</b>\n\n"
                f"✅ Enviados: <b>{sent}</b>\n"
                f"🚫 Bloqueados: {blocked}\n"
                f"⚠️ Erros: {failed}\n"
                f"📊 Total: {total}",
                parse_mode="HTML",
                reply_markup=adm_kb(),
            )
        except Exception:
            pass

    threading.Thread(target=_send_broadcast, daemon=True, name="broadcast_worker").start()


# ==============================================================================
# 🤖 bdZinho Content Engine (ADM only)
# Comandos: /gerar_post, /criar_copy, /relatorio_mkt, /thread_x
# ==============================================================================

def _content_adm_only(m) -> bool:
    """Retorna False e avisa se não for admin."""
    if not is_admin(m.chat.id):
        bot.send_message(m.chat.id, "🔒 Acesso restrito.")
        return False
    return True


def _content_kb():
    """Keyboard do menu Content Engine."""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🖼️ Card Ciclo", "📝 Post Discord")
    kb.row("📱 Post Telegram", "🎯 Copy Tráfego")
    kb.row("📊 Relatório Mkt", "🐦 Thread X")
    kb.row("🔙 ADM")
    return kb


@bot.message_handler(func=lambda m: (m.text or "").strip() == "🤖 Content Engine")
def adm_content_menu(m):
    if not _content_adm_only(m):
        return
    bot.send_message(
        m.chat.id,
        "🤖 <b>bdZinho — Content Engine</b>\n\n"
        "Selecione o tipo de conteúdo a gerar:",
        parse_mode="HTML",
        reply_markup=_content_kb(),
    )


@bot.message_handler(func=lambda m: (m.text or "").strip() == "🖼️ Card Ciclo")
def adm_content_card_ciclo(m):
    if not _content_adm_only(m):
        return
    bot.send_message(m.chat.id, "⏳ Gerando card visual do ciclo 21h...", parse_mode="HTML")
    def _gen():
        try:
            from webdex_ai_image import gerar_card_ciclo
            buf = gerar_card_ciclo()
            buf.seek(0)
            bot.send_photo(m.chat.id, buf,
                           caption="📊 Card Ciclo 21h — WEbdEX Protocol\n#WEbdEX",
                           reply_markup=_content_kb())
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ {e}", reply_markup=_content_kb())
    threading.Thread(target=_gen, daemon=True).start()


@bot.message_handler(commands=["card_ciclo"])
def cmd_card_ciclo(m):
    if not _content_adm_only(m):
        return
    bot.send_message(m.chat.id, "⏳ Gerando card...")
    def _gen():
        try:
            from webdex_ai_image import gerar_card_ciclo
            buf = gerar_card_ciclo()
            buf.seek(0)
            bot.send_photo(m.chat.id, buf,
                           caption="📊 Card Ciclo 21h · WEbdEX Protocol",
                           reply_markup=_content_kb())
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ {e}", reply_markup=_content_kb())
    threading.Thread(target=_gen, daemon=True).start()


@bot.message_handler(func=lambda m: (m.text or "").strip() == "📝 Post Discord")
def adm_content_discord(m):
    if not _content_adm_only(m):
        return
    bot.send_message(m.chat.id, "⏳ Gerando post Discord (ciclo)...", parse_mode="HTML")
    _run_content_gen(m.chat.id, "post_discord", "ciclo")


@bot.message_handler(func=lambda m: (m.text or "").strip() == "📱 Post Telegram")
def adm_content_telegram(m):
    if not _content_adm_only(m):
        return
    bot.send_message(m.chat.id, "⏳ Gerando post Telegram...", parse_mode="HTML")
    _run_content_gen(m.chat.id, "post_telegram", "ciclo")


@bot.message_handler(func=lambda m: (m.text or "").strip() == "🎯 Copy Tráfego")
def adm_content_copy(m):
    if not _content_adm_only(m):
        return
    bot.send_message(m.chat.id, "⏳ Gerando copy de captação...", parse_mode="HTML")
    _run_content_gen(m.chat.id, "copy_trafego", "captacao")


@bot.message_handler(func=lambda m: (m.text or "").strip() == "📊 Relatório Mkt")
def adm_content_relatorio(m):
    if not _content_adm_only(m):
        return
    bot.send_message(m.chat.id, "⏳ Gerando relatório de marketing...", parse_mode="HTML")
    _run_content_gen(m.chat.id, "relatorio_mkt", None)


@bot.message_handler(func=lambda m: (m.text or "").strip() == "🐦 Thread X")
def adm_content_thread_x(m):
    if not _content_adm_only(m):
        return
    bot.send_message(m.chat.id, "⏳ Gerando thread Twitter/X...", parse_mode="HTML")
    _run_content_gen(m.chat.id, "thread_x", None)


@bot.message_handler(commands=["gerar_post"])
def cmd_gerar_post(m):
    if not _content_adm_only(m):
        return
    parts = (m.text or "").split(maxsplit=1)
    style = parts[1].strip() if len(parts) > 1 else "ciclo"
    bot.send_message(m.chat.id, f"⏳ Gerando post ({style})...")
    _run_content_gen(m.chat.id, "post_discord", style)


@bot.message_handler(commands=["criar_copy"])
def cmd_criar_copy(m):
    if not _content_adm_only(m):
        return
    parts = (m.text or "").split(maxsplit=1)
    obj = parts[1].strip() if len(parts) > 1 else "captacao"
    bot.send_message(m.chat.id, f"⏳ Gerando copy ({obj})...")
    _run_content_gen(m.chat.id, "copy_trafego", obj)


@bot.message_handler(commands=["relatorio_mkt"])
def cmd_relatorio_mkt(m):
    if not _content_adm_only(m):
        return
    bot.send_message(m.chat.id, "⏳ Gerando relatório de marketing...")
    _run_content_gen(m.chat.id, "relatorio_mkt", None)


@bot.message_handler(commands=["thread_x"])
def cmd_thread_x(m):
    if not _content_adm_only(m):
        return
    bot.send_message(m.chat.id, "⏳ Gerando thread X...")
    _run_content_gen(m.chat.id, "thread_x", None)


@bot.message_handler(commands=["bdz_stats"])
def cmd_matrix3_stats(m):
    """Mostra estatísticas do bdz_knowledge."""
    if not _content_adm_only(m):
        return
    try:
        from webdex_ai_knowledge import knowledge_stats
        stats = knowledge_stats()
        if not stats:
            bot.send_message(m.chat.id, "📊 bdz_knowledge: (vazio — treino ainda não rodou)")
            return
        lines = ["📊 <b>bdZinho — Knowledge Stats</b>\n"]
        total = 0
        for cat, info in stats.items():
            n = info["total"]
            total += n
            lu = (info.get("last_update") or "")[:10]
            lines.append(f"• <b>{cat}</b>: {n} itens ({lu})")
        lines.append(f"\n🧠 Total: <b>{total} itens</b>")
        bot.send_message(m.chat.id, "\n".join(lines), parse_mode="HTML", reply_markup=adm_kb())
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Erro: {e}")


def _run_content_gen(chat_id: int, content_type: str, style: str | None):
    """Executa geração de conteúdo em thread separada para não bloquear o bot."""
    def _gen():
        try:
            from webdex_ai_content import (
                gerar_post_discord, gerar_post_telegram,
                gerar_copy_trafego, gerar_relatorio_marketing, gerar_thread_x,
            )
            result = None
            if content_type == "post_discord":
                result = gerar_post_discord(style or "ciclo")
            elif content_type == "post_telegram":
                result = gerar_post_telegram(style or "ciclo")
            elif content_type == "copy_trafego":
                result = gerar_copy_trafego(style or "captacao")
            elif content_type == "relatorio_mkt":
                result = gerar_relatorio_marketing()
            elif content_type == "thread_x":
                result = gerar_thread_x()

            if result:
                # Envia em chunks se for texto longo
                if len(result) <= 4000:
                    bot.send_message(
                        chat_id,
                        f"✅ <b>Conteúdo gerado:</b>\n\n{result}",
                        parse_mode="HTML",
                        reply_markup=_content_kb(),
                    )
                else:
                    # Parte 1: cabeçalho
                    bot.send_message(chat_id, "✅ <b>Conteúdo gerado:</b>", parse_mode="HTML")
                    # Parte 2+: texto em chunks de 3800 chars
                    for i in range(0, len(result), 3800):
                        chunk = result[i:i+3800]
                        bot.send_message(chat_id, chunk, reply_markup=_content_kb() if i+3800 >= len(result) else None)
            else:
                bot.send_message(chat_id, "❌ Geração falhou. Verifique API key.", reply_markup=_content_kb())
        except Exception as e:
            logger.error("[content] _run_content_gen falhou: %s", e)
            bot.send_message(chat_id, f"❌ Erro interno: {e}", reply_markup=_content_kb())

    threading.Thread(target=_gen, daemon=True, name=f"content_{content_type}").start()
