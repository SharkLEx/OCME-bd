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
    DEFAULT_RPC if False else None,
)
from webdex_config import logger, Web3, CONTRACTS, ABI_SUBACCOUNTS
from webdex_db import (
    DB_LOCK, conn, cursor, get_config, set_config, now_br,
    get_user, period_to_hours, _period_since, _period_label,
    reload_limites, LIMITE_GWEI, LIMITE_GAS_BAIXO_POL, LIMITE_INATIV_MIN,
    _set_limit, normalize_txhash,
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


# ==============================================================================
# 🎛️ ADM KEYBOARDS & MENUS
# ==============================================================================
def adm_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🧠 IA Global (ON/OFF)", "🔒 IA ADM-only (ON/OFF)")
    kb.row("🧠 IA Modo (DEV/COMUNIDADE)")
    kb.row("👥 ADM PRO", "⚙️ Limites")
    kb.row("⏳ Inatividade PRO")
    kb.row("📊 Análise SubAccounts")
    kb.row("📊 Relatório Institucional")
    kb.row("📊 mybdBook ADM")
    kb.row("📈 Lucro Real (Total/Ambiente)")
    kb.row("🧾 Fornecimento e Liquidez")
    kb.row("📸 Progressão do Capital")
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
    total_users = int(cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0] or 0)
    env_rows = cursor.execute("SELECT COALESCE(env,''), COUNT(*) FROM users GROUP BY COALESCE(env,'')").fetchall()
    env_count = {"V5": 0, "AG_bd": 0, "Inativo": 0}
    for ev, cnt in env_rows:
        lbl = _env_label(ev)
        env_count[lbl] = env_count.get(lbl, 0) + int(cnt or 0)
    cached_rows = cursor.execute(
        "SELECT u.chat_id, COALESCE(u.env,''), COALESCE(c.total_usd, 0), COALESCE(c.breakdown_json,'{}') "
        "FROM users u LEFT JOIN capital_cache c ON c.chat_id=u.chat_id"
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
        top_lines.append(f"• ID {cid}{esc(uname_txt)} ({esc(label)}): <b>{tot:,.2f}</b>{extra}")
    msg = (
        "🛠️ <b>ADM PRO — Governança Viva (Capital & Ambientes)</b>\n\n"
        f"👥 <b>Total de usuários:</b> {total_users}\n"
        f"🌐 <b>Ambientes (contagem):</b> V5={env_count.get('V5',0)} | AG_bd={env_count.get('AG_bd',0)} | Inativo={env_count.get('Inativo',0)}\n\n"
        f"💰 <b>Capital total em fluxo (estimado):</b> {capital_total:,.2f}\n"
        f"🏷️ <b>Capital por ambiente:</b> V5={env_cap.get('V5',0.0):,.2f} | AG_bd={env_cap.get('AG_bd',0.0):,.2f} | Inativo={env_cap.get('Inativo',0.0):,.2f}\n\n"
        f"🧮 <b>Capital por usuário (Top {top_n}):</b>\n"
        + ("\n".join(top_lines) if top_lines else "• (sem dados suficientes ainda)\n")
    )
    return msg


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

@bot.message_handler(func=lambda m: (m.text or "").strip() == "🧠 IA Global (ON/OFF)")
def adm_toggle_ai_global(m):
    if not _is_admin(m.chat.id):
        bot.send_message(m.chat.id, "⚠️ Acesso restrito.", reply_markup=_get_main_kb()())
        return
    from webdex_db import ai_global_enabled
    newv = "0" if ai_global_enabled() else "1"
    set_config("ai_global_enabled", newv)
    status = "ON" if newv == "1" else "OFF"
    bot.send_message(m.chat.id, f"🧠 IA Global agora: {status}", reply_markup=adm_kb())

@bot.message_handler(func=lambda m: (m.text or "").strip() == "🔒 IA ADM-only (ON/OFF)")
def adm_toggle_ai_admin_only(m):
    if not _is_admin(m.chat.id):
        bot.send_message(m.chat.id, "⚠️ Acesso restrito.", reply_markup=_get_main_kb()())
        return
    from webdex_db import ai_admin_only
    newv = "0" if ai_admin_only() else "1"
    set_config("ai_admin_only", newv)
    status = "ON" if newv == "1" else "OFF"
    bot.send_message(m.chat.id, f"🔒 IA ADM-only agora: {status}", reply_markup=adm_kb())

@bot.message_handler(func=lambda m: (m.text or "").strip() == "🧠 IA Modo (DEV/COMUNIDADE)")
def adm_toggle_ai_mode(m):
    if not _is_admin(m.chat.id):
        bot.send_message(m.chat.id, "⚠️ Acesso restrito.", reply_markup=_get_main_kb()())
        return
    from webdex_db import ai_mode
    newm = "community" if ai_mode() == "dev" else "dev"
    set_config("ai_mode", newm)
    label = "DEV" if newm == "dev" else "COMUNIDADE"
    bot.send_message(m.chat.id, f"🧠 IA Modo agora: {label}", reply_markup=adm_kb())

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
    send_support(m.chat.id, "⏳ <b>Inatividade PRO</b>\n\nVerifique o painel de inatividade na tela principal.", reply_markup=adm_kb())
