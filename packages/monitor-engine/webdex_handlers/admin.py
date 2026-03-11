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
    kb.row("🧾 Fornecimento e Liquidez")
    kb.row("📸 Progressão do Capital")
    kb.row("📨 Gerar Convites", "📢 Broadcast")
    kb.row("📡 Status Monitor")
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
        logger.exception(e)
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
    now_ts = time.time()
    dt_24h = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    dt_7d  = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

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
        f"    Trades (24h):  <b>{trd_24h}</b>",
        f"    {wr_icon} WinRate (24h): <b>{wr_24h:.1f}%</b>",
        f"    P&L (24h):     <b>{pnl24_sign}${pnl_24h:,.2f}</b>",
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
    kb.row("GWEI +100", "GWEI -100")
    kb.row("Gás baixo +0.5", "Gás baixo -0.5")
    kb.row("Inativ +10m", "Inativ -10m")
    kb.row("🔙 ADM")
    return kb

def _limites_status_text():
    reload_limites()
    return (
        "⚙️ LIMITES (ADM)\n\n"
        f"• LIMITE_GWEI: {LIMITE_GWEI:.0f} gwei\n"
        f"• GÁS BAIXO: {LIMITE_GAS_BAIXO_POL:.2f} POL\n"
        f"• INATIVIDADE: {LIMITE_INATIV_MIN:.0f} min\n\n"
        "Ajuste pelos botões abaixo. Cada ajuste salva automaticamente."
    )

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
    bot.send_message(m.chat.id, _limites_status_text(), reply_markup=limites_kb())

@bot.message_handler(func=lambda m: m.text in ["GWEI +100", "GWEI -100", "Gás baixo +0.5", "Gás baixo -0.5", "Inativ +10m", "Inativ -10m"])
def limites_actions(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    t = (m.text or "").strip()
    try:
        if t == "GWEI +100":
            msg = _adj_and_save("limite_gwei", +100, 10, 50000, "✅ LIMITE_GWEI ajustado: {:.0f} gwei")
        elif t == "GWEI -100":
            msg = _adj_and_save("limite_gwei", -100, 10, 50000, "✅ LIMITE_GWEI ajustado: {:.0f} gwei")
        elif t == "Gás baixo +0.5":
            msg = _adj_and_save("limite_gas_baixo_pol", +0.5, 0.1, 1000, "✅ GÁS BAIXO ajustado: {:.2f} POL")
        elif t == "Gás baixo -0.5":
            msg = _adj_and_save("limite_gas_baixo_pol", -0.5, 0.1, 1000, "✅ GÁS BAIXO ajustado: {:.2f} POL")
        elif t == "Inativ +10m":
            msg = _adj_and_save("limite_inativ_min", +10, 1, 100000, "✅ INATIVIDADE ajustada: {:.0f} min")
        elif t == "Inativ -10m":
            msg = _adj_and_save("limite_inativ_min", -10, 1, 100000, "✅ INATIVIDADE ajustada: {:.0f} min")
        else:
            msg = "✅ Ok."
    except Exception as e:
        logger.exception("Erro ajustando limites: %s", e)
        msg = "⚠️ Erro ao ajustar limites."
    bot.send_message(m.chat.id, msg + "\n\n" + _limites_status_text(), reply_markup=limites_kb())

@bot.message_handler(func=lambda m: (m.text or "").strip() == "👥 ADM PRO")
def adm_pro_handler(m):
    if not _is_admin(m.chat.id):
        bot.send_message(m.chat.id, "⚠️ Acesso restrito.", reply_markup=_get_main_kb()())
        return
    bot.send_chat_action(m.chat.id, "typing")
    try:
        msg = _adm_pro_report()
        _send_long(m.chat.id, msg, reply_markup=adm_kb())
    except Exception as e:
        logger.exception(e)
        send_support(m.chat.id, "⚠️ Erro ao gerar relatório ADM PRO.", reply_markup=adm_kb())

@bot.message_handler(func=lambda m: (m.text or "").strip() == "📊 Relatório Institucional")
def adm_relatorio_institucional(m):
    if not _is_admin(m.chat.id):
        return send_support(m.chat.id, "⛔ Acesso restrito.", reply_markup=_get_main_kb()())
    bot.send_chat_action(m.chat.id, "typing")
    try:
        from webdex_db import _ensure_institutional_table
        _ensure_institutional_table()
        users = list(_iter_linked_users())
        total_users = len(users)
        per_user_caps = []
        env_cap = {}
        for u in users:
            try:
                total, breakdown = _compute_user_capital(u)
                t = float(total or 0.0)
                per_user_caps.append(t)
                env = (u.get("env") or "default").strip() or "default"
                env_cap[env] = env_cap.get(env, 0.0) + t
            except Exception:
                continue
        total_capital = float(sum(per_user_caps) if per_user_caps else 0.0)
        top3_percent = 0.0
        if total_capital > 0 and per_user_caps:
            top3 = sum(sorted(per_user_caps, reverse=True)[:3])
            top3_percent = (top3 / total_capital) * 100.0
        lines = [
            "🏛️ <b>RELATÓRIO INSTITUCIONAL WEbdEX</b>",
            f"👥 <b>Usuários:</b> {total_users}",
            f"💰 <b>Capital Total:</b> ${total_capital:,.2f} (on-chain)",
            f"🏆 <b>Concentração Top 3:</b> {top3_percent:.1f}%",
        ]
        _send_long(m.chat.id, "\n".join(lines), reply_markup=adm_kb())
    except Exception as e:
        logger.exception(e)
        send_support(m.chat.id, "⚠️ Erro ao gerar relatório institucional.", reply_markup=adm_kb())

@bot.message_handler(func=lambda m: (m.text or "").strip() == "⏳ Inatividade PRO")
def inatividade_pro(m):
    if not _is_admin(m.chat.id):
        return send_support(m.chat.id, "⛔ Acesso restrito.", reply_markup=_get_main_kb()())
    bot.send_chat_action(m.chat.id, "typing")
    try:
        hours = 24
        dt = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

        with DB_LOCK:
            # Subcontas com atividade nos últimas 24h
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
            return send_support(m.chat.id,
                "⏳ <b>INATIVIDADE PRO</b>\n\n⚠️ Nenhuma subconta com trade nas últimas 24h.",
                reply_markup=adm_kb())

        lines = [
            "⏳ <b>INATIVIDADE PRO — Qualificação de Ciclos</b>",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"🗓️ <i>Últimas 24h  ·  {len(sub_rows)} subcontas</i>",
            "",
        ]

        qualif_counts = {"🔥 Muito Ativa": 0, "✅ Ativa": 0, "⚠️ Letárgica": 0, "🔴 Inativa": 0}

        for sub, amb, trades, wins, first_t, last_t, wallet in sub_rows:
            wr = wins / trades * 100 if trades > 0 else 0

            # Calcular ciclo stats se tiver histórico suficiente
            times_data = load_trade_times_by_sub(wallet, hours=168, only_sub=str(sub))  # 7d para ciclo
            if times_data and str(sub) in times_data:
                times_list = times_data[str(sub)]
                cs = ciclo_stats(times_list) if len(times_list) >= 3 else {}
                smq = consist_score(cs.get("med", 0), cs.get("p95", 0)) if cs else 0
                med_min = int(cs.get("med", 0).total_seconds() / 60) if cs and hasattr(cs.get("med", 0), "total_seconds") else 0
            else:
                smq = 0
                med_min = 0

            # Classificação de atividade
            trades_per_h = trades / 24
            if trades_per_h >= 5:
                classif = "🔥 Muito Ativa"
            elif trades_per_h >= 0.5:
                classif = "✅ Ativa"
            elif trades_per_h >= 0.1:
                classif = "⚠️ Letárgica"
            else:
                classif = "🔴 Inativa"
            qualif_counts[classif] = qualif_counts.get(classif, 0) + 1

            wr_emoji = "🟢" if wr >= 60 else ("🟡" if wr >= 40 else "🔴")
            sub_short = (str(sub)[:20] + "…") if len(str(sub)) > 20 else str(sub)
            med_str = f"  ·  ciclo ~{med_min}min" if med_min > 0 else ""
            smq_str = f"  ·  SMQ {smq:.0f}" if smq > 0 else ""
            lines.append(
                f"{classif}  <code>{esc(sub_short)}</code>\n"
                f"   {wr_emoji} WR: <b>{wr:.0f}%</b>  |  Trades: <b>{trades}</b>{med_str}{smq_str}"
            )
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("<b>Distribuição:</b>")
        for classif, cnt in qualif_counts.items():
            if cnt > 0:
                lines.append(f"  {classif}: <b>{cnt}</b> subcontas")

        _send_long(m.chat.id, "\n".join(lines), reply_markup=adm_kb())
    except Exception as e:
        logger.exception(e)
        send_support(m.chat.id, f"⚠️ Erro: {e}", reply_markup=adm_kb())


# ==============================================================================
# 📊 ANÁLISE SUBACCOUNTS — resumo on-chain de subcontas por ambiente
# ==============================================================================
@bot.message_handler(func=lambda m: (m.text or "").strip() == "📊 Análise SubAccounts")
def adm_analise_subaccounts(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    try:
        with DB_LOCK:
            cur = conn.cursor()

            # Por ambiente: n° de subcontas distintas, trades, lucro, wallets
            env_rows = cur.execute("""
                SELECT
                    COALESCE(o.ambiente, 'UNKNOWN') AS amb,
                    COUNT(DISTINCT o.sub_conta)                             AS n_subs,
                    COUNT(*)                                                AS trades,
                    ROUND(SUM(o.valor) - SUM(o.gas_usd), 4)               AS liq,
                    COUNT(CASE WHEN o.valor - o.gas_usd > 0 THEN 1 END)   AS wins,
                    COUNT(DISTINCT ow.wallet)                              AS wallets
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade'
                GROUP BY amb
                ORDER BY liq DESC
            """).fetchall()

            # Top 15 subcontas por lucro líquido (all time)
            top_subs = cur.execute("""
                SELECT sub_conta, COALESCE(ambiente,'?') AS amb,
                       COUNT(*) AS trades,
                       ROUND(SUM(valor) - SUM(gas_usd), 4) AS liq,
                       COUNT(CASE WHEN valor > 0 THEN 1 END) AS wins
                FROM operacoes WHERE tipo='Trade'
                GROUP BY sub_conta, amb
                ORDER BY liq DESC
                LIMIT 15
            """).fetchall()

            total_subs  = cur.execute("SELECT COUNT(DISTINCT sub_conta) FROM operacoes WHERE tipo='Trade'").fetchone()[0]
            total_trade = cur.execute("SELECT COUNT(*) FROM operacoes WHERE tipo='Trade'").fetchone()[0]

        lines = [
            "📊 <b>ANÁLISE SUBACCOUNTS — WEbdEX</b>\n",
            f"🔢 Total subcontas únicas: <b>{total_subs:,}</b>",
            f"📈 Total trades (all time): <b>{total_trade:,}</b>\n",
            "🌐 <b>Por Ambiente</b>",
        ]
        for amb, n_subs, trades, liq, wins, wallets in env_rows:
            wr  = wins / trades * 100 if trades else 0
            sg  = "🟢" if (liq or 0) >= 0 else "🔴"
            lines.append(
                f"  {'🔵' if 'v5' in str(amb).lower() else '🟠'} <b>{esc(str(amb)[:14])}</b>\n"
                f"     Subs: <b>{n_subs}</b>  Wallets: <b>{wallets}</b>  Trades: <b>{trades:,}</b>\n"
                f"     {sg} Líquido: <b>{(liq or 0):+.4f}</b>  WR: <b>{wr:.1f}%</b>"
            )

        lines.append("\n🏆 <b>Top 15 Subcontas (Lucro Líquido)</b>")
        for i, (sub, amb, trades, liq, wins) in enumerate(top_subs, 1):
            sg = "🟢" if (liq or 0) >= 0 else "🔴"
            wr = wins / trades * 100 if trades else 0
            med = _medal(i)
            sub_short = (str(sub or "")[:18] + "…") if len(str(sub or "")) > 18 else str(sub or "—")
            lines.append(
                f"  {med or f'{i}.'} <code>{esc(sub_short)}</code> [{esc(str(amb)[:8])}]\n"
                f"     {sg} <b>{(liq or 0):+.4f}</b>  T:{trades}  WR:{wr:.0f}%"
            )

        # ── Seção On-Chain: saldos vivos por ambiente ──────────────────────
        lines.append("\n🔗 <b>Saldos On-Chain (Capital Vivo)</b>")
        onchain_ok = False
        try:
            from webdex_chain import get_contracts, web3, rpc_pool
            from webdex_config import CONTRACTS, ADDR_USDT0
            from webdex_db import DB_LOCK as _DL
            import concurrent.futures

            # Busca wallets ativas com capital para consultar
            with _DL:
                wallets_to_check = cursor.execute(
                    "SELECT DISTINCT u.wallet, u.env FROM users u "
                    "JOIN capital_cache cc ON cc.chat_id=u.chat_id "
                    "WHERE u.wallet<>'' AND u.active=1 AND cc.total_usd>0 "
                    "LIMIT 10"
                ).fetchall()

            env_onchain: dict = {}
            def _fetch_wallet_capital(wallet_env):
                wlt, env = wallet_env
                try:
                    from webdex_chain import get_contracts, web3
                    from webdex_config import ADDR_USDT0
                    c = get_contracts(env or "AG_C_bd", web3)
                    mgr = web3.to_checksum_address(c["addr"]["MANAGER"])
                    usr = web3.to_checksum_address(wlt)
                    subs = c["sub"].functions.getSubAccounts(mgr, usr).call()[:20]
                    total = 0.0
                    for s in subs:
                        sid = s[0]
                        try:
                            strats = c["sub"].functions.getStrategies(mgr, usr, sid).call()[:10]
                        except Exception:
                            continue
                        for st in strats:
                            try:
                                bals = c["sub"].functions.getBalances(mgr, usr, sid, st).call()
                            except Exception:
                                continue
                            for b in bals:
                                if str(b[1]).lower() == ADDR_USDT0.lower():
                                    total += int(b[0]) / (10 ** int(b[2]))
                    return (env or "AG_C_bd"), total
                except Exception:
                    return None, 0.0

            if wallets_to_check:
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                    results = list(ex.map(_fetch_wallet_capital, wallets_to_check, timeout=15))
                for env_r, cap_r in results:
                    if env_r:
                        env_onchain[env_r] = env_onchain.get(env_r, 0.0) + cap_r
                total_onchain = sum(env_onchain.values())
                for env_r, cap_r in sorted(env_onchain.items()):
                    icon = "🔵" if "v5" in str(env_r).lower() else "🟠"
                    lines.append(f"  {icon} <b>{esc(str(env_r)[:12])}</b>: <b>${cap_r:,.2f}</b>")
                lines.append(f"  💼 <b>Total on-chain:</b> <b>${total_onchain:,.2f}</b>")
                onchain_ok = True
        except Exception as _oc_e:
            logger.warning("[adm_subaccounts onchain] %s", _oc_e)
        if not onchain_ok:
            lines.append("  <i>(dados on-chain indisponíveis — use mybdBook para capital individual)</i>")

        _send_long(m.chat.id, "\n".join(lines), reply_markup=adm_kb())
    except Exception as e:
        logger.exception(e)
        bot.send_message(m.chat.id, f"⚠️ Erro: {e}", reply_markup=adm_kb())


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

    with DB_LOCK:
        cur = conn.cursor()

        env_rows = cur.execute("""
            SELECT
                COALESCE(ambiente, 'UNKNOWN') AS amb,
                COUNT(*)                                              AS trades,
                ROUND(SUM(valor), 6)                                  AS bruto,
                ROUND(SUM(gas_usd), 6)                                AS gas,
                ROUND(SUM(valor) - SUM(gas_usd), 6)                  AS liq,
                COUNT(CASE WHEN valor - gas_usd > 0 THEN 1 END)      AS wins,
                COUNT(CASE WHEN valor - gas_usd < 0 THEN 1 END)      AS losses
            FROM operacoes
            WHERE tipo='Trade' AND data_hora >= ?
            GROUP BY amb
            ORDER BY liq DESC
        """, (since,)).fetchall()

        daily = cur.execute("""
            SELECT DATE(data_hora) AS dia,
                   ROUND(SUM(valor) - SUM(gas_usd), 4) AS liq,
                   COUNT(*) AS trades
            FROM operacoes
            WHERE tipo='Trade' AND data_hora >= ?
            GROUP BY dia ORDER BY dia DESC LIMIT 7
        """, (since,)).fetchall()

    total_trades = sum(int(r[1] or 0) for r in env_rows)
    total_bruto  = sum(float(r[2] or 0) for r in env_rows)
    total_gas    = sum(float(r[3] or 0) for r in env_rows)
    total_liq    = sum(float(r[4] or 0) for r in env_rows)
    total_wins   = sum(int(r[5] or 0) for r in env_rows)
    wr_global    = total_wins / total_trades * 100 if total_trades else 0

    sg_g = "🟢" if total_liq >= 0 else "🔴"
    lines = [
        f"📈 <b>LUCRO REAL — WEbdEX</b>",
        f"🗓️ <i>{esc(label)}</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"\n💼 <b>TOTAL GLOBAL</b>",
        f"  📊 Trades:   <b>{total_trades:,}</b>  WR: <b>{wr_global:.1f}%</b>",
        f"  💰 Bruto:    <b>{total_bruto:+.4f} USD</b>",
        f"  ⛽ Gás:     <b>{total_gas:.4f} USD</b>",
        f"  {sg_g} Líquido: <b>{total_liq:+.4f} USD</b>\n",
        "🌐 <b>POR AMBIENTE</b>",
    ]
    for amb, trades, bruto, gas, liq, wins, losses in env_rows:
        wr  = wins / trades * 100 if trades else 0
        sg  = "🟢" if (liq or 0) >= 0 else "🔴"
        pf_g = wins / losses if losses else float("inf")
        pf_s = f"{pf_g:.2f}" if pf_g != float("inf") else "∞"
        lines.append(
            f"\n  {'🔵' if 'v5' in str(amb).lower() else '🟠'} <b>{esc(str(amb)[:16])}</b>\n"
            f"     Trades: <b>{trades:,}</b>  WR: <b>{wr:.1f}%</b>  PF: <b>{pf_s}</b>\n"
            f"     Bruto: <b>{(bruto or 0):+.4f}</b>  Gás: <b>{(gas or 0):.4f}</b>\n"
            f"     {sg} Líquido: <b>{(liq or 0):+.4f} USD</b>"
        )

    if daily:
        lines.append("\n\n📅 <b>ÚLTIMOS 7 DIAS</b>")
        for dia, liq, trades in daily:
            ic = "🟢" if (liq or 0) >= 0 else "🔴"
            lines.append(f"  {ic} {dia}: <b>{(liq or 0):+.4f}</b>  ({trades} trades)")

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
        logger.exception(e)
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
        logger.exception(e)


# ==============================================================================
# 🧾 FORNECIMENTO E LIQUIDEZ — on-chain LP reserves por ambiente
# ==============================================================================
_ABI_LP_MIN = json.loads('[{"inputs":[],"name":"getReserves","outputs":[{"name":"reserve0","type":"uint128"},{"name":"reserve1","type":"uint128"},{"name":"blockTimestampLast","type":"uint32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"totalSupply","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"}]')

def _fetch_lp_data(lp_addr: str, label: str, dec_r0: int = 6, dec_r1: int = 9) -> dict:
    """Busca reserves e totalSupply de um LP on-chain."""
    from webdex_config import RPC_CAPITAL
    from webdex_chain import web3_for_rpc
    try:
        w3 = web3_for_rpc(RPC_CAPITAL, timeout=8)
        c  = w3.eth.contract(address=Web3.to_checksum_address(lp_addr), abi=_ABI_LP_MIN)
        reserves    = c.functions.getReserves().call()
        total_supply_raw = c.functions.totalSupply().call()
        r0 = float(reserves[0]) / (10 ** dec_r0)
        r1 = float(reserves[1]) / (10 ** dec_r1)
        ts = float(total_supply_raw) / (10 ** dec_r0)  # LP dec = same as r0 for these pools
        pool_usd = r0 * 2  # AMM invariant: pool_total_usd = reserve_stable * 2
        return {"ok": True, "label": label, "r0": r0, "r1": r1, "supply": ts,
                "pool_usd": pool_usd, "addr": lp_addr}
    except Exception as e:
        return {"ok": False, "label": label, "error": str(e), "addr": lp_addr}

@bot.message_handler(func=lambda m: (m.text or "").strip() == "🧾 Fornecimento e Liquidez")
def adm_fornecimento_liquidez(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    bot.send_message(m.chat.id, "⏳ Consultando pools on-chain...", parse_mode="HTML")
    try:
        from webdex_config import CONTRACTS
        from webdex_chain import chain_pol_price

        pol_price = chain_pol_price() or 0.50

        # Definição dos LPs por ambiente
        lps = [
            # (env_label, lp_addr, pool_name, dec_r0, dec_r1)
            ("AG_C_bd", CONTRACTS["AG_C_bd"]["LP_USDT"], "LP-USDT (AG_C_bd)", 6, 9),
            ("AG_C_bd", CONTRACTS["AG_C_bd"]["LP_LOOP"], "LP-LOOP (AG_C_bd)", 6, 9),
            ("bd_v5",   CONTRACTS["bd_v5"]["LP_USDT"],  "LP-USDT (bd_v5)",   6, 9),
            ("bd_v5",   CONTRACTS["bd_v5"]["LP_LOOP"],  "LP-LOOP (bd_v5)",   6, 9),
        ]

        # Busca capital dos usuários por env (do capital_cache)
        with DB_LOCK:
            cap_rows = conn.execute("""
                SELECT COALESCE(c.env, u.env, 'AG_C_bd'), COALESCE(SUM(c.total_usd), 0)
                FROM capital_cache c
                JOIN users u ON u.chat_id = c.chat_id
                WHERE c.total_usd > 0
                GROUP BY COALESCE(c.env, u.env, 'AG_C_bd')
            """).fetchall()
        cap_by_env: dict = {}
        for env_raw, cap in cap_rows:
            cap_by_env[str(env_raw or "").lower()] = float(cap or 0)

        lines = [
            "🧾 <b>FORNECIMENTO E LIQUIDEZ — WEbdEX</b>",
            f"💰 POL/USD: <b>${pol_price:.4f}</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n",
        ]

        # Busca on-chain em paralelo
        import concurrent.futures as _cf
        futures = {}
        with _cf.ThreadPoolExecutor(max_workers=4) as ex:
            for env_label, addr, pool_name, d0, d1 in lps:
                futures[ex.submit(_fetch_lp_data, addr, pool_name, d0, d1)] = (env_label, pool_name)

        results_by_env: dict = {}
        for fut, (env_label, pool_name) in futures.items():
            r = fut.result()
            results_by_env.setdefault(env_label, []).append(r)

        total_pool_usd = 0.0
        for env_label, pool_results in results_by_env.items():
            env_cap = cap_by_env.get(env_label.lower(), 0.0)
            lines.append(f"{'🔵' if 'v5' in env_label.lower() else '🟠'} <b>{esc(env_label)}</b>")
            env_pool_usd = 0.0
            for r in pool_results:
                if r["ok"]:
                    coverage = (env_cap / r["pool_usd"] * 100) if r["pool_usd"] > 0 else 0
                    cov_icon = "🟢" if coverage < 80 else ("🟡" if coverage < 95 else "🔴")
                    lines.append(
                        f"  📦 <b>{esc(r['label'])}</b>\n"
                        f"     USDT reserve: <b>{r['r0']:,.2f}</b>  LOOP reserve: <b>{r['r1']:,.4f}</b>\n"
                        f"     Pool total:   <b>${r['pool_usd']:,.2f} USD</b>\n"
                        f"     {cov_icon} Cobertura (cap/pool): <b>{coverage:.1f}%</b>"
                    )
                    env_pool_usd += r["pool_usd"]
                else:
                    lines.append(f"  ⚠️ {esc(r['label'])}: erro — {esc(str(r.get('error','?'))[:60])}")
            lines.append(f"  💰 Capital usuários ({env_label}): <b>${env_cap:,.2f}</b>")
            lines.append(f"  🏊 Liquidez total pool: <b>${env_pool_usd:,.2f}</b>\n")
            total_pool_usd += env_pool_usd

        total_cap = sum(cap_by_env.values())
        cov_total = (total_cap / total_pool_usd * 100) if total_pool_usd > 0 else 0
        cov_icon  = "🟢" if cov_total < 80 else ("🟡" if cov_total < 95 else "🔴")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🌐 <b>GLOBAL</b>")
        lines.append(f"  💼 Capital total usuários: <b>${total_cap:,.2f}</b>")
        lines.append(f"  🏊 Liquidez total pools:   <b>${total_pool_usd:,.2f}</b>")
        lines.append(f"  {cov_icon} Cobertura global: <b>{cov_total:.1f}%</b>")
        lines.append("\n<i>💡 Cobertura &lt; 80% = pool tem folga. &gt; 95% = pool próximo da capacidade.</i>")

        send_support(m.chat.id, "\n".join(lines), reply_markup=adm_kb())
    except Exception as e:
        logger.exception(e)
        bot.send_message(m.chat.id, f"⚠️ Erro: {e}", reply_markup=adm_kb())


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
@bot.message_handler(func=lambda m: (m.text or "").strip() == "📸 Progressão do Capital")
def adm_progressao_capital(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    bot.send_message(m.chat.id, "⏳ Consultando SubAccounts on-chain + pools LP...", parse_mode="HTML")

    now_ts   = time.time()
    now_dt   = datetime.now()
    hoje_str = now_dt.strftime("%Y-%m-%d")

    # ── 1. Capital on-chain ao vivo via SubAccounts ──────────────────────────
    import concurrent.futures as _cf
    from webdex_config import CONTRACTS, ADDR_USDT0
    from webdex_chain import get_contracts, web3_for_rpc, chain_pol_price

    pol_price = chain_pol_price() or 0.50

    # Wallets ativas com capital > 0
    with DB_LOCK:
        wallets = conn.execute(
            "SELECT DISTINCT chat_id, wallet, COALESCE(env,'AG_C_bd'), rpc "
            "FROM users WHERE wallet<>'' AND wallet IS NOT NULL AND active=1"
        ).fetchall()

    def _fetch_onchain(row):
        chat_id, wallet, env, rpc = row
        try:
            w3  = web3_for_rpc(rpc or "", timeout=10)
            c   = get_contracts(env, w3)
            mgr = w3.to_checksum_address(c["addr"]["MANAGER"])
            usr = w3.to_checksum_address(wallet)
            subs = c["sub"].functions.getSubAccounts(mgr, usr).call()[:30]
            usdt0_total = 0.0
            sub_caps: dict = {}
            for s in subs:
                sid = s[0]
                sub_total = 0.0
                try:
                    strats = c["sub"].functions.getStrategies(mgr, usr, sid).call()[:15]
                    for st in strats:
                        try:
                            bals = c["sub"].functions.getBalances(mgr, usr, sid, st).call()
                            for b in bals:
                                if str(b[1]).lower() == ADDR_USDT0.lower():
                                    sub_total += int(b[0]) / (10 ** int(b[2]))
                        except Exception:
                            pass
                except Exception:
                    pass
                usdt0_total += sub_total
                if sub_total > 0:
                    sub_caps[str(sid)] = sub_total
            return int(chat_id), wallet.lower(), env, usdt0_total, sub_caps
        except Exception:
            return int(chat_id), (wallet or "").lower(), env, 0.0, {}

    onchain_results = []
    if wallets:
        with _cf.ThreadPoolExecutor(max_workers=5) as ex:
            futs = {ex.submit(_fetch_onchain, row): row for row in wallets}
            for fut in _cf.as_completed(futs, timeout=20):
                try:
                    onchain_results.append(fut.result())
                except Exception:
                    pass

    # Agrupa por ambiente
    env_totals: dict = {}    # env -> total_usd
    env_wallets: dict = {}   # env -> count
    env_sub_caps: dict = {}  # env -> list of (sub_id, val)
    grand_total = 0.0
    for cid, wlt, env, total, sub_caps in onchain_results:
        if total <= 0:
            continue
        env_totals[env] = env_totals.get(env, 0.0) + total
        env_wallets[env] = env_wallets.get(env, 0) + 1
        env_sub_caps.setdefault(env, []).extend(sub_caps.items())
        grand_total += total

    # ── 2. Salva snapshot on-chain no capital_cache ──────────────────────────
    for cid, wlt, env, total, _ in onchain_results:
        if total > 0.5:
            with DB_LOCK:
                conn.execute(
                    "INSERT OR REPLACE INTO capital_cache (chat_id, env, total_usd, breakdown_json, updated_ts) "
                    "VALUES (?,?,?,?,?)",
                    (cid, env, total, '{}', now_ts)
                )
            conn.commit()

    # ── 3. Snapshot anterior (capital_cache 24h atrás) para delta ────────────
    with DB_LOCK:
        prev_rows = conn.execute(
            "SELECT COALESCE(env,'?'), SUM(total_usd) FROM capital_cache "
            "WHERE updated_ts < ? GROUP BY COALESCE(env,'?')",
            (now_ts - 3600,)   # snapshots com > 1h de diferença
        ).fetchall()
    prev_totals = {r[0]: float(r[1] or 0) for r in prev_rows}
    prev_grand  = sum(prev_totals.values())

    # ── 4. LP Reserves on-chain (pool liquidity) ──────────────────────────────
    lps_config = []
    try:
        for env_key, c_data in CONTRACTS.items():
            for lp_key in ("LP_USDT", "LP_LOOP"):
                addr = c_data.get(lp_key)
                if addr:
                    lps_config.append((env_key, addr, lp_key))
    except Exception:
        pass

    lp_results: dict = {}  # env -> {pool: pool_usd}
    def _fetch_lp(env_key, addr, pool_name):
        try:
            w3 = web3_for_rpc("", timeout=8)
            c  = w3.eth.contract(
                address=w3.to_checksum_address(addr),
                abi=_ABI_LP_MIN
            )
            res = c.functions.getReserves().call()
            r0  = float(res[0]) / 1e6   # USDT0 = 6 dec
            r1  = float(res[1]) / 1e9   # LOOP  = 9 dec
            pool_usd = r0 * 2           # AMM invariant
            return env_key, pool_name, r0, r1, pool_usd
        except Exception:
            return env_key, pool_name, 0.0, 0.0, 0.0

    if lps_config:
        with _cf.ThreadPoolExecutor(max_workers=4) as ex:
            lp_futs = [ex.submit(_fetch_lp, *lp) for lp in lps_config]
            for fut in _cf.as_completed(lp_futs, timeout=15):
                try:
                    env_k, pool_n, r0, r1, pool_usd = fut.result()
                    lp_results.setdefault(env_k, []).append((pool_n, r0, r1, pool_usd))
                except Exception:
                    pass

    # ── 5. Monta relatório ───────────────────────────────────────────────────
    delta_grand = grand_total - prev_grand
    delta_icon  = "📈" if delta_grand >= 0 else "📉"
    delta_pct   = (delta_grand / prev_grand * 100) if prev_grand > 0 else 0

    lines = [
        "📸 <b>PROGRESSÃO DO CAPITAL — WEbdEX</b>",
        f"🕒 <i>{hoje_str}  ·  dados on-chain ao vivo</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "💼 <b>CAPITAL SUBACCOUNTS (USDT0)</b>",
    ]

    total_pool_all = 0.0
    for env_k in sorted(set(list(env_totals.keys()) + list(lp_results.keys()))):
        cap  = env_totals.get(env_k, 0.0)
        wlts = env_wallets.get(env_k, 0)
        prev = prev_totals.get(env_k, 0.0)
        d    = cap - prev
        d_ic = "📈" if d >= 0 else "📉"
        icon = "🔵" if "v5" in env_k.lower() else "🟠"

        # Top subcontas desse ambiente
        subs_env = sorted(env_sub_caps.get(env_k, []), key=lambda x: x[1], reverse=True)[:3]
        subs_str = ""
        for i, (sid, sv) in enumerate(subs_env, 1):
            subs_str += f"\n     {_medal(i)} Sub {str(sid)[:16]}: <b>${sv:,.2f}</b>"

        # LP pools desse ambiente
        pool_usd_env = 0.0
        pool_lines = []
        for pool_n, r0, r1, pool_usd in lp_results.get(env_k, []):
            pool_usd_env += pool_usd
            pool_lines.append(
                f"     🏊 {esc(pool_n[:16])}: <b>${pool_usd:,.2f}</b>"
                f"  (r0={r0:,.0f} USDT0 | r1={r1:,.2f} LOOP)"
            )
        total_pool_all += pool_usd_env

        # Cobertura capital vs pool
        cov = (cap / pool_usd_env * 100) if pool_usd_env > 0 else 0
        cov_icon = "🔴" if cov > 90 else ("🟡" if cov > 70 else "🟢")

        lines += [
            f"",
            f"{icon} <b>{esc(env_k)}</b>",
            f"   💵 Capital: <b>${cap:,.2f}</b>  ({wlts} wallets)",
            f"   {d_ic} Delta: <b>{d:+,.2f}</b>",
        ]
        lines += [subs_str] if subs_str else []
        lines += [
            f"   🏦 Liquidez pool: <b>${pool_usd_env:,.2f}</b>",
            f"   {cov_icon} Cobertura: <b>{cov:.1f}%</b>  capital/pool",
        ]
        lines += pool_lines

    # Totais globais
    cov_total = (grand_total / total_pool_all * 100) if total_pool_all > 0 else 0
    cov_t_icon = "🔴" if cov_total > 90 else ("🟡" if cov_total > 70 else "🟢")
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🌐 <b>GLOBAL</b>",
        f"   💼 Capital total:   <b>${grand_total:,.2f} USD</b>",
        f"   🏊 Liquidez total:  <b>${total_pool_all:,.2f} USD</b>",
        f"   {cov_t_icon} Cobertura global: <b>{cov_total:.1f}%</b>",
        f"   {delta_icon} Delta vs anterior: <b>{delta_grand:+,.2f}</b> ({delta_pct:+.2f}%)",
        f"   💲 POL/USD: <b>${pol_price:.4f}</b>",
        "",
        "<i>💡 Cobertura &lt;70% = pool com folga · &gt;90% = pool próximo capacidade</i>",
        "<i>📸 Snapshot salvo — próxima comparação mostrará delta de crescimento</i>",
    ]

    try:
        _send_long(m.chat.id, "\n".join(lines), reply_markup=adm_kb())
    except Exception as e:
        logger.exception(e)
        bot.send_message(m.chat.id, f"⚠️ Erro ao enviar: {e}", reply_markup=adm_kb())


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
        logger.exception(e)
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
        logger.exception(e)
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
        logger.exception(e)
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

def _broadcast_receive_text(m):
    if not _is_admin(m.chat.id):
        return
    txt = (m.text or "").strip()
    if txt.lower() in ["/cancelar", "cancelar"]:
        _BROADCAST_AUDIENCE.pop(m.chat.id, None)
        return bot.send_message(m.chat.id, "❌ Broadcast cancelado.", reply_markup=adm_kb())
    if not txt:
        return bot.send_message(m.chat.id, "⚠️ Mensagem vazia. Tente novamente.", reply_markup=adm_kb())

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
