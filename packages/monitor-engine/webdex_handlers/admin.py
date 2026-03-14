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

        # Cobertura do protocolo via protocol_ops
        try:
            with DB_LOCK:
                _cov_wallets = cursor.execute(
                    "SELECT COUNT(DISTINCT wallet) FROM protocol_ops"
                ).fetchone()[0]
                _cov_trades = cursor.execute(
                    "SELECT COUNT(*) FROM protocol_ops"
                ).fetchone()[0]
                _cov_bd = cursor.execute(
                    "SELECT ROUND(SUM(fee_bd),4) FROM protocol_ops"
                ).fetchone()[0] or 0.0
                _cov_profit = cursor.execute(
                    "SELECT ROUND(SUM(profit),4) FROM protocol_ops"
                ).fetchone()[0] or 0.0
            _coverage = (total_users / _cov_wallets * 100) if _cov_wallets > 0 else 0.0
            lines += [
                "",
                "🔗 <b>Cobertura do Protocolo (on-chain)</b>",
                f"  👤 Traders on-chain: <b>{_cov_wallets:,}</b>",
                f"  🤖 No bot (OCME):    <b>{total_users}</b>",
                f"  📊 Cobertura:        <b>{_coverage:.1f}%</b>",
                f"  📈 Trades indexados: <b>{_cov_trades:,}</b>",
                f"  💵 Lucro total:      <b>{_cov_profit:+.4f}</b>",
                f"  💎 BD coletado:      <b>{_cov_bd:.4f}</b> tokens",
            ]
        except Exception as _ce:
            logger.debug("[relatorio_institucional coverage] %s", _ce)

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

        # ── Seção protocol_ops: TODOS os traders on-chain ──────────────────
        lines.append("\n🌐 <b>Todos os Traders On-Chain (protocol_ops)</b>")
        try:
            with DB_LOCK:
                _proto_env = cursor.execute("""
                    SELECT env,
                           COUNT(DISTINCT wallet)                          AS wallets,
                           COUNT(*)                                        AS trades,
                           ROUND(SUM(profit), 4)                          AS profit,
                           ROUND(SUM(fee_bd), 4)                          AS fee_bd,
                           COUNT(CASE WHEN profit > 0 THEN 1 END)         AS wins
                    FROM protocol_ops
                    GROUP BY env ORDER BY trades DESC
                """).fetchall()
                _proto_total_w = cursor.execute(
                    "SELECT COUNT(DISTINCT wallet) FROM protocol_ops"
                ).fetchone()[0]
                _proto_total_t = cursor.execute(
                    "SELECT COUNT(*) FROM protocol_ops"
                ).fetchone()[0]
            lines.append(
                f"  📊 Total wallets únicas: <b>{_proto_total_w:,}</b>  "
                f"Trades: <b>{_proto_total_t:,}</b>"
            )
            for _env, _wlt, _tr, _pft, _fbd, _wns in _proto_env:
                _wr = _wns / _tr * 100 if _tr else 0
                _sg = "🟢" if (_pft or 0) >= 0 else "🔴"
                _ico = "🔵" if "v5" in str(_env).lower() else "🟠"
                lines.append(
                    f"  {_ico} <b>{esc(str(_env)[:14])}</b>  "
                    f"Wallets:{_wlt}  Trades:{_tr:,}\n"
                    f"     {_sg} Lucro:{(_pft or 0):+.4f}  "
                    f"BD:{(_fbd or 0):.4f}  WR:{_wr:.1f}%"
                )
        except Exception as _pe:
            logger.debug("[adm_subaccounts proto_ops] %s", _pe)
            lines.append("  <i>(protocol_ops indisponível — sync em andamento)</i>")

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

        # Agrupa por ciclo 21h: shift -21h para que o "dia" do ciclo comece às 21h
        # Ex.: trade às 22:00 do dia X → datetime(22:00, '-21h') = 01:00 do dia X+1 → DATE = X+1 (ciclo X→X+1)
        daily = cur.execute("""
            SELECT DATE(datetime(data_hora, '-21 hours')) AS dia_ciclo,
                   ROUND(SUM(valor) - SUM(gas_usd), 4) AS liq,
                   COUNT(*) AS trades
            FROM operacoes
            WHERE tipo='Trade' AND data_hora >= ?
            GROUP BY dia_ciclo ORDER BY dia_ciclo DESC LIMIT 7
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
        lines.append("\n\n📅 <b>ÚLTIMOS 7 CICLOS (21h→21h)</b>")
        for dia_ciclo, liq, trades in daily:
            ic = "🟢" if (liq or 0) >= 0 else "🔴"
            lines.append(f"  {ic} {dia_ciclo} (21h→): <b>{(liq or 0):+.4f}</b>  ({trades} trades)")

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

    with DB_LOCK:
        cur = conn.cursor()

        # Conta total de registros em protocol_ops para saber se backfill rodou
        proto_count = cur.execute("SELECT COUNT(*) FROM protocol_ops").fetchone()[0] or 0

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
            GROUP BY env ORDER BY lucro_total DESC
        """, (since,)).fetchall()

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

    if proto_count == 0:
        lines.append("\n⏳ <i>Backfill on-chain em andamento (worker ativo)...</i>")
        lines.append("💡 <i>Dados disponíveis em ~30min após a primeira sincronização.</i>")
    else:
        # ── Bloco 1: Lucro total dos traders ──────────────────────────────────
        lines.append(
            f"\n📈 <b>LUCRO DOS TRADERS (Protocolo Completo)</b>\n"
            f"  {sg_lucro} Lucro Líquido: <b>{s_lucro}${p_lucro:,.2f} USD</b>\n"
            f"  💰 Ganhos:   <b>+${p_ganhos:,.2f}</b>  |  📉 Perdas: <b>${p_perdas:,.2f}</b>\n"
            f"  📊 Trades: <b>{p_trades:,}</b>  |  👥 Traders: <b>{p_traders:,}</b>  |  WR: <b>{p_wr:.1f}%</b>"
        )
        for env, trades, traders, lucro, ganhos, perdas, wins, bd_tot, gas_pol in proto_rows:
            ic  = "🔵" if "v5" in str(env).lower() else "🟠"
            sg  = "🟢" if (lucro or 0) >= 0 else "🔴"
            s   = "+" if (lucro or 0) >= 0 else ""
            wr  = wins / trades * 100 if trades else 0.0
            lines.append(
                f"\n  {ic} <b>{esc(str(env))}</b>\n"
                f"     {sg} Lucro: <b>{s}${(lucro or 0):,.2f}</b>  "
                f"Trades: <b>{trades:,}</b>  WR: <b>{wr:.1f}%</b>\n"
                f"     👥 Traders: <b>{traders}</b>  |  Gás: <b>{(gas_pol or 0):,.2f} POL</b>"
            )

        # ── Bloco 2: Gás consumido ─────────────────────────────────────────────
        lines.append(
            f"\n\n⛽ <b>GÁS CONSUMIDO (Transações)</b>\n"
            f"  🔴 Total POL:  <b>{p_gas_pol:,.4f} POL</b>  (~<b>${p_gas_usd:,.2f}</b>)\n"
            f"  📊 Média/trade: <b>{(p_gas_pol/p_trades):,.6f} POL</b>" if p_trades else
            f"\n\n⛽ <b>GÁS CONSUMIDO</b>  <i>sem dados</i>"
        )

        # ── Bloco 3: BD/Passe coletado ─────────────────────────────────────────
        lines.append(
            f"\n\n🎟️ <b>BD/PASSE COLETADO (Fee Protocolo)</b>\n"
            f"  💎 Período:    <b>{p_bd:,.4f} BD</b>\n"
            f"  🏦 Acumulado:  <b>{bd_alltime:,.4f} BD</b>  <i>(all-time)</i>"
        )

        # ── Bloco 4: TVL delta ─────────────────────────────────────────────────
        if tvl_data:
            s_tvl = "+" if tvl_total_delta >= 0 else ""
            lines.append(
                f"\n\n🏦 <b>TVL DO PROTOCOLO</b>\n"
                f"  {sg_tvl} Delta: <b>{s_tvl}${tvl_total_delta:,.2f}</b>  ({s_tvl}{tvl_total_pct:.2f}%)\n"
                f"  📊 Início: <b>${tvl_total_inicio:,.2f}</b>  →  Atual: <b>${tvl_total_fim:,.2f}</b>"
            )
            for env, v in tvl_data.items():
                ic = "🔵" if "v5" in env.lower() else "🟠"
                s  = "+" if v["delta"] >= 0 else ""
                lines.append(
                    f"\n  {ic} <b>{esc(env)}</b>  "
                    f"<b>${v['fim']:,.2f}</b>  ({s}${v['delta']:,.2f})"
                )

        # ── Bloco 5: Top 5 traders ─────────────────────────────────────────────
        if top_traders:
            lines.append("\n\n🏆 <b>TOP 5 TRADERS (período)</b>")
            for i, (wallet, lucro, trades, bd_pago, gas) in enumerate(top_traders, 1):
                short_w = f"{wallet[:6]}...{wallet[-4:]}" if len(str(wallet)) > 10 else str(wallet)
                sg = "🟢" if (lucro or 0) >= 0 else "🔴"
                s  = "+" if (lucro or 0) >= 0 else ""
                lines.append(
                    f"  {i}. <code>{short_w}</code>\n"
                    f"     {sg} <b>{s}${(lucro or 0):,.2f}</b>  |  {trades} trades  |  💎 {(bd_pago or 0):.3f} BD"
                )

    lines.append(f"\n\n<i>🔍 Fonte: on-chain ({proto_count:,} ops indexadas)</i>")
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
        logger.exception(e)
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
        logger.exception(e)


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
                      liq_u: float, liq_l: float, gas_pol: float, pol_price: float):
    try:
        from webdex_db import now_br
        ts        = now_br().strftime("%Y-%m-%d %H:%M:%S")
        total_usd = max(liq_u, 0) + max(liq_l, 0)
        with DB_LOCK:
            conn.execute(
                "INSERT INTO fl_snapshots "
                "(ts,env,lp_usdt_supply,lp_loop_supply,liq_usdt,liq_loop,gas_pol,pol_price,total_usd) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (ts, env, max(lp_u, 0), max(lp_l, 0),
                 max(liq_u, 0), max(liq_l, 0), max(gas_pol, 0), pol_price, total_usd)
            )
            conn.commit()
    except Exception:
        pass

def _fl_last_snapshot(env: str) -> dict:
    try:
        with DB_LOCK:
            row = conn.execute(
                "SELECT ts,lp_usdt_supply,lp_loop_supply,liq_usdt,liq_loop,gas_pol "
                "FROM fl_snapshots WHERE env=? ORDER BY id DESC LIMIT 1",
                (env,)
            ).fetchone()
        if row:
            return {"ts": row[0], "lp_usdt": row[1], "lp_loop": row[2],
                    "liq_usdt": row[3], "liq_loop": row[4], "gas": row[5]}
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

def _fl_db_stats(env_tag: str, days: int = 30) -> dict:
    from datetime import timedelta
    from webdex_db import now_br
    since = (now_br() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with DB_LOCK:
            r = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(valor),0), COALESCE(SUM(gas_usd),0), "
                "COALESCE(SUM(valor)-SUM(gas_usd),0) "
                "FROM operacoes WHERE tipo='Trade' AND data_hora>=? AND ambiente=?",
                (since, env_tag)
            ).fetchone()
        return {"trades": int(r[0] or 0), "bruto": float(r[1] or 0),
                "gas": float(r[2] or 0), "liquido": float(r[3] or 0)}
    except Exception:
        return {"trades": 0, "bruto": 0.0, "gas": 0.0, "liquido": 0.0}

def _fl_db_stats_total(days: int = 30) -> dict:
    from datetime import timedelta
    from webdex_db import now_br
    since = (now_br() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with DB_LOCK:
            r = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(valor),0), COALESCE(SUM(gas_usd),0), "
                "COALESCE(SUM(valor)-SUM(gas_usd),0) "
                "FROM operacoes WHERE tipo='Trade' AND data_hora>=?",
                (since,)
            ).fetchone()
        return {"trades": int(r[0] or 0), "bruto": float(r[1] or 0),
                "gas": float(r[2] or 0), "liquido": float(r[3] or 0)}
    except Exception:
        return {"trades": 0, "bruto": 0.0, "gas": 0.0, "liquido": 0.0}


@bot.message_handler(func=lambda m: (m.text or "").strip() in {
    "🧾 Fornecimento e Liquidez", "🧾 Fornecimento & Liquidez"
})
def adm_fornecimento_liquidez(m):
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    bot.send_message(m.chat.id, "🔄 Consultando protocolo on-chain...", parse_mode="HTML")
    try:
        from webdex_config import CONTRACTS, ADDR_USDT0, ADDR_LPLPUSD, RPC_CAPITAL
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

        # ── Coleta on-chain por ambiente em paralelo ──────────────────────────
        def _collect_env(env_name: str, c_info: dict) -> dict:
            sub_addr     = c_info.get("SUBACCOUNTS", "")
            mgr_addr     = c_info.get("MANAGER", "")
            lp_usdt_addr = c_info.get("LP_USDT", "")
            lp_loop_addr = c_info.get("LP_LOOP", "")

            # FORNECIMENTO: totalSupply dos tokens LP
            lp_usdt_s = _fl_supply(w3, lp_usdt_addr, 6) if lp_usdt_addr else -1.0
            lp_loop_s = _fl_supply(w3, lp_loop_addr, 9) if lp_loop_addr else -1.0

            # LIQUIDEZ: capital USDT e LOOP custodiado no SubAccounts
            liq_usdt  = _fl_balance(w3, ADDR_USDT0,   sub_addr, 6) if sub_addr else -1.0
            liq_loop  = _fl_balance(w3, ADDR_LPLPUSD, sub_addr, 9) if sub_addr else -1.0

            # GÁS do Manager
            gas_pol   = _fl_manager_gas(w3, mgr_addr) if mgr_addr else -1.0

            # Snapshot anterior para deltas
            prev = _fl_last_snapshot(env_name)

            # Salva snapshot no DB
            _fl_save_snapshot(env_name, lp_usdt_s, lp_loop_s,
                              liq_usdt, liq_loop, gas_pol, pol_price)

            return {
                "tag": c_info["TAG"],
                "lp_usdt_addr": lp_usdt_addr,
                "lp_loop_addr": lp_loop_addr,
                "lp_usdt_supply": lp_usdt_s,
                "lp_loop_supply": lp_loop_s,
                "liq_usdt": liq_usdt,
                "liq_loop": liq_loop,
                "gas_pol": gas_pol,
                "prev": prev,
                "stat": _fl_db_stats(env_name, days=30),
            }

        env_futures = {}
        with _cf.ThreadPoolExecutor(max_workers=2) as ex:
            for env_name, c_info in CONTRACTS.items():
                env_futures[ex.submit(_collect_env, env_name, c_info)] = env_name

        env_data = {}
        for fut, env_name in env_futures.items():
            env_data[env_name] = fut.result()

        # ── Monta relatório ───────────────────────────────────────────────────
        msg  = "🧾 <b>FORNECIMENTO &amp; LIQUIDEZ — WEbdEX</b>\n"
        msg += f"🕒 {ts_now}  |  ⛽ {_fl_fmt(gwei, 1)} Gwei  |  💱 ${pol_price:.4f} POL\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        for env_name in ("AG_C_bd", "bd_v5"):
            if env_name not in env_data:
                continue
            d    = env_data[env_name]
            prev = d["prev"]

            msg += f"🏛 <b>{esc(d['tag'])}</b>\n"

            # Fornecimento
            msg += "  📦 <b>Fornecimento (Supply LP)</b>\n"
            s_u = d["lp_usdt_supply"]
            msg += f"  🟣 LP-USDT supply: <b>{_fl_fmt(s_u, 4)}</b>{esc(_fl_delta_str(s_u, prev.get('lp_usdt', 0)))}\n"
            msg += f"     <code>{esc(d['lp_usdt_addr'])}</code>\n"
            s_l = d["lp_loop_supply"]
            msg += f"  🟣 LP-LOOP supply: <b>{_fl_fmt(s_l, 4)}</b>{esc(_fl_delta_str(s_l, prev.get('lp_loop', 0)))}\n"
            msg += f"     <code>{esc(d['lp_loop_addr'])}</code>\n"

            # Liquidez (capital no SubAccounts)
            msg += "  💧 <b>Liquidez (Capital no SubAccounts)</b>\n"
            lq_u = d["liq_usdt"]
            msg += f"  🔵 USDT: <b>{_fl_fmt(lq_u, 4)}</b>{esc(_fl_delta_str(lq_u, prev.get('liq_usdt', 0)))}\n"
            lq_l = d["liq_loop"]
            msg += f"  🔄 LOOP: <b>{_fl_fmt(lq_l, 4)}</b>{esc(_fl_delta_str(lq_l, prev.get('liq_loop', 0)))}\n"

            # Ratio capital/supply
            msg += "  📐 <b>Ratio Capital / Supply</b>\n"
            if s_u > 0 and lq_u >= 0:
                r = lq_u / s_u * 100
                st = " 🟢" if r >= 80 else (" ⚠️ Baixo" if r < 10 else "")
                msg += f"  🔵 USDT/LP-USDT: {_fl_pct_bar(r)} <b>{r:.2f}%</b>{st}\n"
            if s_l > 0 and lq_l >= 0:
                r = lq_l / s_l * 100
                st = " 🟢" if r >= 80 else (" ⚠️ Baixo" if r < 10 else "")
                msg += f"  🔄 LOOP/LP-LOOP: {_fl_pct_bar(r)} <b>{r:.2f}%</b>{st}\n"

            # Gás (saldo nativo POL depositado pelos usuários no Manager)
            gp = d["gas_pol"]
            g_s = "🟢" if gp >= 100 else ("🟡" if gp >= 10 else ("🔴 BAIXO" if gp >= 0 else "⚠️"))
            g_u = f" (~${gp * pol_price:,.2f})" if gp >= 0 and pol_price > 0 else ""
            msg += f"  ⛽ Gas Manager (usuários): <b>{_fl_fmt(gp, 2)} POL</b>{esc(g_u)} {g_s}\n"

            # Atividade 30d
            st = d["stat"]
            if st["trades"] > 0:
                lq_ic = "🟢" if st["liquido"] > 0 else "🔴"
                msg += (f"  📈 30d: <b>{st['trades']:,}</b> trades | "
                        f"Bruto <b>{st['bruto']:,.2f}</b> | "
                        f"{lq_ic} Líq <b>{st['liquido']:,.2f} USD</b>\n")

            if prev.get("ts"):
                msg += f"  🗂 Snapshot anterior: <i>{esc(prev['ts'])}</i>\n"

            msg += "\n"

        # Análise comparativa
        if len(env_data) >= 2:
            envs = list(env_data.values())
            e1, e2 = envs[0], envs[1]
            msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += "📊 <b>ANÁLISE COMPARATIVA</b>\n\n"
            for sym, k1, k2, icon in [("USDT", "liq_usdt", "lp_usdt_supply", "🔵"),
                                       ("LOOP", "liq_loop", "lp_loop_supply", "🔄")]:
                v1 = e1[k1]; v2 = e2[k1]
                tot = max(v1, 0) + max(v2, 0)
                msg += f"{icon} <b>{sym} Liquidez</b>"
                if tot <= 0 or v1 < 0 or v2 < 0:
                    msg += ": sem dados\n\n"
                    continue
                p1 = v1 / tot * 100; p2 = v2 / tot * 100
                dom = e1["tag"] if p1 >= p2 else e2["tag"]
                msg += f" — Total: <b>{tot:,.4f}</b>\n"
                msg += f"  {esc(e1['tag'])}: {_fl_pct_bar(p1)} <b>{p1:.1f}%</b>  ({v1:,.4f})\n"
                msg += f"  {esc(e2['tag'])}: {_fl_pct_bar(p2)} <b>{p2:.1f}%</b>  ({v2:,.4f})\n"
                msg += f"  Δ <b>{abs(p1-p2):.1f}pp</b> → <b>{esc(dom)}</b> lidera\n\n"

        # Total protocolo
        total_stat = _fl_db_stats_total(days=30)
        lq_ic = "🟢" if total_stat["liquido"] > 0 else "🔴"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "🌐 <b>TOTAL PROTOCOLO (30 dias)</b>\n"
        msg += f"📈 Trades: <b>{total_stat['trades']:,}</b>\n"
        msg += f"💰 Vol. Bruto: <b>{total_stat['bruto']:,.4f} USD</b>\n"
        msg += f"⛽ Gás Total: <b>{total_stat['gas']:,.4f} USD</b>\n"
        msg += f"{lq_ic} Líq. Total: <b>{total_stat['liquido']:,.4f} USD</b>\n"
        msg += "\n🗂 <i>Snapshot salvo · Fonte: Contratos WEbdEX · Polygon · Tempo real</i>"

        send_support(m.chat.id, msg, reply_markup=adm_kb())
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
    """Dashboard de Progressão do Capital — duas visões integradas.

    Seção A — CAPITAL DOS USUÁRIOS (user_capital_snapshots):
        Compara último snapshot vs anterior de cada usuário do bot.
        Mostra: capital atual, capital antes, delta USD, delta %.
        Fonte: user_capital_snapshots (inserido cada vez que mybdBook é chamado).
        Fallback: capital_cache (valor mais recente sem histórico).

    Seção B — P&L DE TRADING DO PROTOCOLO (protocol_ops):
        Todos os traders on-chain desde deploy, sem filtro de bot.
        Mostra: trades, wallets, P&L total, taxa de acerto, top traders.

    Seção C — LIQUIDEZ (fl_snapshots):
        TVL atual vs snapshot anterior por ambiente.

    Zero chamadas on-chain. 100% DB. Resposta imediata.
    """
    if not _is_admin(m.chat.id):
        return bot.reply_to(m, "⛔ Acesso negado.")
    bot.send_chat_action(m.chat.id, "typing")
    bot.send_message(m.chat.id, "⏳ Carregando progressão do capital...", parse_mode="HTML")

    now_dt = datetime.now()
    sep    = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # ── helper ────────────────────────────────────────────────────────────────
    def _d(val, ref):
        """Delta percentual seguro."""
        return (val / ref * 100) if ref and ref > 0 else 0.0

    def _ico_delta(d):
        if d is None: return "📊"
        return "📈" if d >= 0 else "📉"

    # ─────────────────────────────────────────────────────────────────────────
    # 1. TVL POR AMBIENTE — fl_snapshots (2 mais recentes por env)
    # ─────────────────────────────────────────────────────────────────────────
    pool_data: dict = {}  # env → {curr, curr_ts, prev, prev_ts, delta, delta_pct}
    try:
        with DB_LOCK:
            _fl_all = conn.execute(
                "SELECT env, total_usd, ts FROM fl_snapshots "
                "WHERE total_usd > 0 ORDER BY env, ts DESC"
            ).fetchall()
        _fl_by_env: dict = {}
        for _fe, _fv, _ft in _fl_all:
            _fl_by_env.setdefault(str(_fe), []).append((float(_fv or 0), str(_ft or "")[:16]))
        for _ek, _snaps in _fl_by_env.items():
            _c, _cts = _snaps[0]
            _p, _pts = (_snaps[1][0], _snaps[1][1]) if len(_snaps) >= 2 else (None, None)
            pool_data[_ek] = {
                "curr": _c, "curr_ts": _cts,
                "prev": _p, "prev_ts": _pts,
                "delta": (_c - _p) if _p is not None else None,
                "delta_pct": _d(_c - _p, _p) if _p is not None else None,
            }
    except Exception as _e1:
        logger.debug("[prog_capital] fl_snapshots: %s", _e1)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. WALLETS ON-CHAIN POR AMBIENTE — protocol_ops
    # ─────────────────────────────────────────────────────────────────────────
    proto_env: dict = {}  # env → {wallets, trades, profit, wins, losses}
    proto_total: dict = {}
    try:
        with DB_LOCK:
            _pe_rows = conn.execute("""
                SELECT env,
                       COUNT(DISTINCT wallet)                      AS wallets,
                       COUNT(*)                                    AS trades,
                       ROUND(SUM(profit), 4)                       AS profit,
                       COUNT(CASE WHEN profit > 0 THEN 1 END)      AS wins,
                       COUNT(CASE WHEN profit < 0 THEN 1 END)      AS losses,
                       ROUND(SUM(fee_bd), 4)                       AS fee_bd
                FROM protocol_ops
                WHERE wallet != '' AND env != 'UNKNOWN'
                GROUP BY env
            """).fetchall()
            _pt = conn.execute("""
                SELECT COUNT(DISTINCT wallet), COUNT(*),
                       ROUND(SUM(profit),4),
                       COUNT(CASE WHEN profit > 0 THEN 1 END),
                       COUNT(CASE WHEN profit < 0 THEN 1 END),
                       ROUND(SUM(fee_bd),4), MIN(ts), MAX(ts)
                FROM protocol_ops WHERE wallet != '' AND env != 'UNKNOWN'
            """).fetchone()
        for _r in _pe_rows:
            proto_env[str(_r[0])] = {
                "wallets": int(_r[1] or 0), "trades": int(_r[2] or 0),
                "profit":  float(_r[3] or 0), "wins":   int(_r[4] or 0),
                "losses":  int(_r[5] or 0),   "fee_bd": float(_r[6] or 0),
            }
        proto_total = {
            "wallets": int(_pt[0] or 0), "trades":  int(_pt[1] or 0),
            "profit":  float(_pt[2] or 0), "wins":   int(_pt[3] or 0),
            "losses":  int(_pt[4] or 0),  "fee_bd": float(_pt[5] or 0),
            "first":   str(_pt[6] or "")[:10], "last": str(_pt[7] or "")[:16],
        }
    except Exception as _e2:
        logger.debug("[prog_capital] protocol_ops: %s", _e2)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. CAPITAL DOS USUÁRIOS BOT — user_capital_snapshots (2 por user/env)
    # Fallback: capital_cache para users sem snapshots históricos
    # ─────────────────────────────────────────────────────────────────────────
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
        _uname_map: dict = {}
        for _cid, _env, _usd, _ts, _un in _snap_all:
            key = (int(_cid), str(_env or "AG_C_bd"))
            _by_user.setdefault(key, []).append((float(_usd or 0), str(_ts or "")))
            if _un and int(_cid) not in _uname_map:
                _uname_map[int(_cid)] = _un
        for (cid, env), snaps in _by_user.items():
            curr, curr_ts = snaps[0]
            prev, prev_ts = (snaps[1][0], snaps[1][1]) if len(snaps) >= 2 else (None, None)
            delta = (curr - prev) if prev is not None else None
            user_prog.append({
                "chat_id": cid, "env": env, "uname": _uname_map.get(cid),
                "curr": curr, "curr_ts": str(curr_ts)[:16],
                "prev": prev, "prev_ts": str(prev_ts)[:16] if prev_ts else None,
                "delta": delta,
                "delta_pct": _d(delta, prev) if delta is not None and prev else None,
            })
        user_prog.sort(key=lambda x: x["delta"] if x["delta"] is not None else -1e9, reverse=True)
    except Exception as _e3:
        logger.debug("[prog_capital] user_capital_snapshots: %s", _e3)

    # Fallback capital_cache para usuários sem user_capital_snapshots
    _seen_users = {(u["chat_id"], u["env"]) for u in user_prog}
    try:
        with DB_LOCK:
            _cc = conn.execute("""
                SELECT cc.chat_id, COALESCE(cc.env,'AG_C_bd'), cc.total_usd,
                       cc.updated_ts, u.username
                FROM capital_cache cc LEFT JOIN users u ON u.chat_id = cc.chat_id
                WHERE cc.total_usd > 0.5
            """).fetchall()
        for _cid2, _env2, _usd2, _uts2, _un2 in _cc:
            if (int(_cid2), str(_env2)) not in _seen_users:
                _cts2 = datetime.fromtimestamp(float(_uts2)).strftime("%Y-%m-%d %H:%M") if _uts2 else "?"
                user_prog.append({
                    "chat_id": int(_cid2), "env": str(_env2), "uname": _un2,
                    "curr": float(_usd2 or 0), "curr_ts": _cts2,
                    "prev": None, "prev_ts": None, "delta": None, "delta_pct": None,
                    "_cache_only": True,
                })
    except Exception as _e4:
        logger.debug("[prog_capital] capital_cache fallback: %s", _e4)

    # Totais bot
    _users_w_delta = [u for u in user_prog if u["delta"] is not None]
    _total_curr_bot = sum(u["curr"] for u in user_prog)
    _total_prev_bot = sum(u["prev"] for u in _users_w_delta if u["prev"])
    _total_delta_bot = sum(u["delta"] for u in _users_w_delta)
    _total_delta_pct_bot = _d(_total_delta_bot, _total_prev_bot)

    # Agrupa usuários por ambiente para exibir dentro de cada seção
    _users_by_env: dict = {}
    for _u in user_prog:
        _users_by_env.setdefault(str(_u["env"]), []).append(_u)

    # ─────────────────────────────────────────────────────────────────────────
    # MONTA MENSAGEM — organizado POR AMBIENTE
    # ─────────────────────────────────────────────────────────────────────────
    _all_envs = sorted(set(list(pool_data.keys()) + list(proto_env.keys()) + list(_users_by_env.keys())))

    lines = [
        "📸 <b>PROGRESSÃO DO CAPITAL — WEbdEX</b>",
        f"🕒 <i>{now_dt.strftime('%Y-%m-%d %H:%M')}</i>",
        sep,
    ]

    for _env_k in _all_envs:
        _e_ico = "🔵" if "v5" in str(_env_k).lower() else "🟠"
        lines += ["", f"{_e_ico} ═══════ <b>{esc(_env_k)}</b> ═══════"]

        # ── TVL do Protocolo ──────────────────────────────────────────────
        _pd = pool_data.get(_env_k)
        lines.append("")
        lines.append("  🏦 <b>TVL DO PROTOCOLO</b>")
        if _pd:
            _td_ico = _ico_delta(_pd["delta"])
            lines.append(f"     Agora:  <b>${_pd['curr']:>12,.2f}</b>  <i>[{_pd['curr_ts']}]</i>")
            if _pd["prev"] is not None:
                lines.append(f"     Antes:  ${_pd['prev']:>12,.2f}  <i>[{_pd['prev_ts']}]</i>")
                lines.append(
                    f"     {_td_ico} Delta: <b>{_pd['delta']:>+10,.2f} USD</b>"
                    f"  (<b>{_pd['delta_pct']:>+.2f}%</b>)"
                )
            else:
                lines.append("     <i>(aguardando 2º snapshot do worker)</i>")
        else:
            lines.append("     <i>(sem dados de pool para este ambiente)</i>")

        # ── Wallets on-chain ──────────────────────────────────────────────
        _pe = proto_env.get(_env_k)
        lines.append("")
        lines.append("  🌐 <b>TRADERS ON-CHAIN (protocol_ops)</b>")
        if _pe:
            _wr = _d(_pe["wins"], _pe["trades"])
            _p_ico = _ico_delta(_pe["profit"])
            lines += [
                f"     👥 Carteiras únicas: <b>{_pe['wallets']:,}</b>",
                f"     📊 Trades:           <b>{_pe['trades']:,}</b>",
                f"     {_p_ico} P&amp;L total:      <b>{_pe['profit']:>+,.4f} USDT</b>",
                f"     🏆 Taxa de acerto:   <b>{_wr:.1f}%</b>  ({_pe['wins']:,}✅ / {_pe['losses']:,}❌)",
                f"     💎 Fees BD:          <b>{_pe['fee_bd']:,.4f}</b>",
            ]
        else:
            lines.append("     <i>(sem dados on-chain para este ambiente)</i>")

        # ── Usuários do bot ───────────────────────────────────────────────
        _env_users = _users_by_env.get(_env_k, [])
        lines.append("")
        lines.append("  💼 <b>USUÁRIOS BOT (capital USDT0)</b>")
        if _env_users:
            _eu_curr = sum(u["curr"] for u in _env_users)
            _eu_prev = sum(u["prev"] for u in _env_users if u["prev"] is not None)
            _eu_delt = sum(u["delta"] for u in _env_users if u["delta"] is not None)
            _eu_with = [u for u in _env_users if u["delta"] is not None]
            lines.append(
                f"     👥 Usuários: <b>{len(_env_users)}</b>"
                f"  ({len(_eu_with)} c/ histórico de comparação)"
            )
            lines.append(f"     💵 Capital atual total: <b>${_eu_curr:,.2f}</b>")
            if _eu_with:
                _eu_delt_pct = _d(_eu_delt, _eu_prev)
                _eu_d_ico    = _ico_delta(_eu_delt)
                lines.append(f"     💵 Capital antes total: ${_eu_prev:,.2f}")
                lines.append(
                    f"     {_eu_d_ico} Progressão:     <b>{_eu_delt:>+,.2f} USD</b>"
                    f"  (<b>{_eu_delt_pct:>+.2f}%</b>)"
                )
            lines.append("")

            # Detalhe por usuário (máx 12 por ambiente)
            for _u in _env_users[:12]:
                _lbl = f"@{esc(_u['uname'])}" if _u.get("uname") else f"ID:…{str(_u['chat_id'])[-4:]}"
                if _u["delta"] is not None:
                    _ud_ico = _ico_delta(_u["delta"])
                    lines.append(
                        f"     • <b>{_lbl}</b>"
                        f"  ${_u['curr']:,.2f}  ← ${_u['prev']:,.2f}"
                        f"  {_ud_ico} <b>{_u['delta']:+,.2f}</b> ({_u['delta_pct']:+.2f}%)"
                    )
                    lines.append(
                        f"       <i>agora: {_u['curr_ts']}  /  antes: {_u['prev_ts']}</i>"
                    )
                else:
                    _src = "<i>(só cache)</i>" if _u.get("_cache_only") else "<i>(só 1 snapshot)</i>"
                    lines.append(
                        f"     • <b>{_lbl}</b>"
                        f"  ${_u['curr']:,.2f}  {_src}"
                    )
        else:
            lines.append("     <i>(nenhum usuário bot neste ambiente)</i>")

    # ── CONSOLIDADO GLOBAL ────────────────────────────────────────────────────
    _tvl_total_curr = sum(v["curr"] for v in pool_data.values())
    _tvl_total_prev = sum(v["prev"] for v in pool_data.values() if v["prev"] is not None)
    _tvl_total_delt = _tvl_total_curr - _tvl_total_prev if _tvl_total_prev > 0 else None

    lines += ["", sep, "", "🌐 <b>CONSOLIDADO GLOBAL</b>", ""]

    # TVL protocolo
    _tvl_d_ico = _ico_delta(_tvl_total_delt)
    _tvl_d_str = f"{_tvl_total_delt:+,.2f}" if _tvl_total_delt is not None else "—"
    _tvl_d_pct = _d(_tvl_total_delt, _tvl_total_prev) if _tvl_total_delt else 0.0
    lines += [
        "  🏦 <b>TVL Total do Protocolo</b>",
        f"     Agora:  <b>${_tvl_total_curr:>12,.2f}</b>",
        f"     {_tvl_d_ico} Delta: <b>{_tvl_d_str}</b>  ({_tvl_d_pct:+.2f}%)",
        "",
    ]

    # Wallets on-chain total
    if proto_total.get("wallets"):
        _pt_wr = _d(proto_total["wins"], proto_total["trades"])
        _pt_pico = _ico_delta(proto_total["profit"])
        lines += [
            "  🌐 <b>Traders On-Chain Total</b>",
            f"     👥 Carteiras:      <b>{proto_total['wallets']:,}</b>  (todos os ambientes)",
            f"     📊 Trades:         <b>{proto_total['trades']:,}</b>",
            f"     {_pt_pico} P&amp;L total:   <b>{proto_total['profit']:>+,.4f} USDT</b>",
            f"     🏆 Taxa de acerto: <b>{_pt_wr:.1f}%</b>",
            f"     💎 Fees BD:        <b>{proto_total['fee_bd']:,.4f}</b>",
            f"     🗓️ Período: <i>{proto_total['first']} → {proto_total['last']}</i>",
            "",
        ]

    # Capital bot total
    if user_prog:
        _bot_d_ico = _ico_delta(_total_delta_bot if _users_w_delta else None)
        lines += [
            "  💼 <b>Capital Bot Total (usuários)</b>",
            f"     💵 Capital atual:  <b>${_total_curr_bot:>10,.2f}</b>",
        ]
        if _users_w_delta:
            lines += [
                f"     💵 Capital antes:  ${_total_prev_bot:>10,.2f}",
                f"     {_bot_d_ico} Progressão: <b>{_total_delta_bot:>+,.2f} USD</b>"
                f"  (<b>{_total_delta_pct_bot:>+.2f}%</b>)",
            ]

    lines += [
        "",
        "<i>💡 TVL = USDT0 custodiado no contrato SubAccounts (fl_snapshots worker ~30min).</i>",
        "<i>   Capital bot = USDT0 por usuário salvo ao chamar mybdBook (user_capital_snapshots).</i>",
        "<i>   Carteiras on-chain = todos os traders indexados desde o deploy do contrato.</i>",
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
