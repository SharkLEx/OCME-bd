from __future__ import annotations
# ==============================================================================
# webdex_workers.py — WEbdEX Monitor Engine (extraído de WEbdEX_V30_24_SPEED_PATCH_FIXED.py)
# Linhas fonte: ~2420-2560 (sentinela, agendador_21h, _chain_cache_worker)
#               + ~6156-7460 (capital_snapshot_worker, user_capital_refresh_worker, funnel_worker)
# ==============================================================================

import time, threading
from datetime import datetime, timedelta
from typing import Any, Dict

from webdex_config import logger, Web3, CONTRACTS
from webdex_db import (
    DB_LOCK, conn, cursor, get_config, set_config, now_br, get_user,
    LIMITE_GWEI, LIMITE_GAS_BAIXO_POL, LIMITE_INATIV_MIN,
    reload_limites, period_to_hours,
)
from webdex_chain import (
    web3, CONTRACTS_A, CONTRACTS_B, get_active_wallet_map,
    obter_preco_pol, _chain_cache_worker,
)
from webdex_bot_core import send_html, _notif_worker, send_logo_photo

# ==============================================================================
# 🛡️ SENTINELA
# ==============================================================================
def sentinela():
    logger.info("🛡️ Sentinela: Ativo...")
    last = 0
    while True:
        try:
            if time.time() - last > 300:
                _, meta = get_active_wallet_map()
                if not meta:
                    time.sleep(10)
                    continue
                gwei = web3.eth.gas_price / 10**9
                for cid, m in meta.items():
                    if gwei > LIMITE_GWEI:
                        send_html(cid, f"🔥 <b>GÁS ALTO:</b> <code>{gwei:.0f} Gwei</code>")
                    try:
                        c_mgr = CONTRACTS_A["mgr"] if m["env"] == "AG_C_bd" else CONTRACTS_B["mgr"]
                        raw = c_mgr.functions.gasBalance().call({"from": Web3.to_checksum_address(m["wallet"])})
                        gas = float(web3.from_wei(raw, "ether"))
                        if gas < LIMITE_GAS_BAIXO_POL:
                            send_html(cid, f"⛽ <b>GÁS BAIXO:</b> <code>{gas:.4f} POL</code>")
                    except Exception:
                        pass
                last = time.time()
        except Exception:
            pass
        time.sleep(30)

# ==============================================================================
# ⏰ AGENDADOR 21H
# ==============================================================================
def agendador_21h():
    logger.info("⏰ Agendador 21h: Ativo...")
    while True:
        try:
            now = now_br()
            if now.hour == 21 and now.minute == 0:
                hoje = now.strftime("%Y-%m-%d")
                with DB_LOCK:
                    rows = cursor.execute("SELECT chat_id FROM users WHERE active=1").fetchall()
                for (cid,) in rows:
                    if get_config(f"last_rep_{cid}", "") == hoje:
                        continue
                    u = get_user(cid)
                    if not u or not u.get("wallet"):
                        continue
                    dt_lim = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
                    with DB_LOCK:
                        cursor.execute("""
                            SELECT SUM(o.valor), SUM(o.gas_usd)
                            FROM operacoes o
                            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=?
                        """, (dt_lim, u["wallet"]))
                        r = cursor.fetchone()
                    if r and r[0] is not None:
                        liq   = float(r[0]) - float(r[1] or 0.0)
                        gas_t = float(r[1] or 0.0)
                        # Busca contagem e WinRate
                        with DB_LOCK:
                            wr_row = cursor.execute("""
                                SELECT COUNT(*), SUM(CASE WHEN o.valor>0 THEN 1 ELSE 0 END)
                                FROM operacoes o
                                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                                WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=?
                            """, (dt_lim, u["wallet"])).fetchone()
                        total_t = int(wr_row[0] or 0) if wr_row else 0
                        wins    = int(wr_row[1] or 0) if wr_row else 0
                        wr_pct  = (wins / total_t * 100) if total_t > 0 else 0
                        # Barra de WinRate (10 blocos)
                        filled  = round(wr_pct / 10)
                        wr_bar  = "█" * filled + "░" * (10 - filled)
                        emoji   = "🟢" if liq >= 0 else "🔴"
                        msg = (
                            f"🌙 <b>RELATÓRIO 21H — WEbdEX</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"{emoji}  Líquido: <b>${liq:+.2f}</b>\n"
                            f"⛽  Gás Total: <b>${gas_t:.2f}</b>\n"
                            f"📊  Trades: <b>{total_t}</b>  |  Wins: <b>{wins}</b>\n\n"
                            f"🎯  WinRate: <b>{wr_pct:.0f}%</b>\n"
                            f"<code>{wr_bar}</code>\n\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🗓️  {hoje}"
                        )
                        send_html(cid, msg)
                        send_logo_photo(cid, "🌙 <b>WEbdEX</b> — bom descanso, até amanhã! 🚀")
                    set_config(f"last_rep_{cid}", hoje)
                time.sleep(70)
        except Exception:
            pass
        time.sleep(30)

# ==============================================================================
# 💰 CAPITAL SNAPSHOT WORKER
# ==============================================================================
_CAPITAL_SNAP_INTERVAL = 30 * 60  # 30 minutos

def _capital_snapshot_worker():
    """Worker de background: tira snapshot de capital de todos usuários a cada 30min."""
    logger.info("💰 Capital snapshot worker: Ativo...")
    while True:
        try:
            with DB_LOCK:
                users = cursor.execute(
                    "SELECT chat_id, wallet, env, rpc FROM users WHERE wallet<>'' AND wallet IS NOT NULL AND active=1"
                ).fetchall()
            for chat_id, wallet, env, rpc in users:
                try:
                    from webdex_chain import web3_for_rpc
                    from webdex_config import RPC_CAPITAL
                    w3 = web3_for_rpc(rpc or RPC_CAPITAL, timeout=6)
                    from webdex_chain import get_contracts
                    c = get_contracts(env or "AG_C_bd", w3)
                    mgr_addr = Web3.to_checksum_address(c["addr"]["MANAGER"])
                    usr_addr = Web3.to_checksum_address(wallet)
                    subs = c["sub"].functions.getSubAccounts(mgr_addr, usr_addr).call()[:40]
                    total_usd = 0.0
                    breakdown: dict = {}
                    from webdex_config import ADDR_USDT0
                    for s in subs:
                        sid = s[0]
                        try:
                            strats = c["sub"].functions.getStrategies(mgr_addr, usr_addr, sid).call()[:25]
                        except Exception:
                            continue
                        for st in strats:
                            try:
                                bals = c["sub"].functions.getBalances(mgr_addr, usr_addr, sid, st).call()
                            except Exception:
                                continue
                            for b in bals:
                                try:
                                    addr_raw = str(b[1]).lower()
                                    bal_raw  = int(b[0])
                                    dec_raw  = int(b[2])
                                    if bal_raw <= 0:
                                        continue
                                    if addr_raw == ADDR_USDT0.lower():
                                        val = bal_raw / (10 ** dec_raw)
                                        total_usd += val
                                        breakdown["USDT0"] = breakdown.get("USDT0", 0.0) + val
                                except Exception:
                                    continue
                    if total_usd > 1.0:
                        import json as _json
                        ts_now = time.time()
                        with DB_LOCK:
                            conn.execute(
                                "INSERT OR REPLACE INTO capital_cache (chat_id, env, total_usd, breakdown_json, updated_ts) VALUES (?,?,?,?,?)",
                                (int(chat_id), env or "AG_C_bd", total_usd, _json.dumps(breakdown), ts_now)
                            )
                            conn.commit()
                        logger.info("✅ capital_cache: chat_id=%s env=%s total_usd=%.2f", chat_id, env or "AG_C_bd", total_usd)
                    else:
                        logger.warning("⚠️ capital_cache baixo/zero: chat_id=%s env=%s total_usd=%.4f", chat_id, env or "AG_C_bd", total_usd)
                except Exception as _usr_e:
                    logger.warning("❌ capital_cache falhou: chat_id=%s erro=%s", chat_id, _usr_e)
        except Exception as _we:
            logger.warning(f"capital_snapshot_worker erro: {_we}")
        time.sleep(_CAPITAL_SNAP_INTERVAL)

# ==============================================================================
# 👥 USER CAPITAL REFRESH WORKER
# ==============================================================================
_CAP_WORKER_RUNNING = False
_CAP_FAIL_COUNT = 0
_CAP_SKIP_UNTIL = 0.0
_CAP_MAX_FAILS  = 5

def _user_capital_refresh_worker():
    """Worker: atualiza capital on-chain para todos usuários ativos a cada 15min."""
    global _CAP_WORKER_RUNNING, _CAP_FAIL_COUNT, _CAP_SKIP_UNTIL
    _CAP_WORKER_RUNNING = True
    logger.info("👥 User capital refresh worker: Ativo...")
    while True:
        try:
            if time.time() < _CAP_SKIP_UNTIL:
                time.sleep(60)
                continue
            with DB_LOCK:
                users = cursor.execute(
                    "SELECT chat_id, wallet, env, rpc FROM users WHERE wallet<>'' AND wallet IS NOT NULL AND active=1"
                ).fetchall()
            for chat_id, wallet, env, rpc in users:
                try:
                    from webdex_chain import web3_for_rpc
                    from webdex_config import RPC_CAPITAL
                    w3 = web3_for_rpc(rpc or RPC_CAPITAL, timeout=6)
                    from webdex_chain import get_contracts
                    c = get_contracts(env or "AG_C_bd", w3)
                    mgr_addr = Web3.to_checksum_address(c["addr"]["MANAGER"])
                    usr_addr = Web3.to_checksum_address(wallet)
                    subs = c["sub"].functions.getSubAccounts(mgr_addr, usr_addr).call()[:40]
                    total_usd = 0.0
                    breakdown: dict = {}
                    from webdex_config import ADDR_USDT0
                    for s in subs:
                        sid = s[0]
                        try:
                            strats = c["sub"].functions.getStrategies(mgr_addr, usr_addr, sid).call()[:25]
                        except Exception:
                            continue
                        for st in strats:
                            try:
                                bals = c["sub"].functions.getBalances(mgr_addr, usr_addr, sid, st).call()
                            except Exception:
                                continue
                            for b in bals:
                                try:
                                    addr_raw = str(b[1]).lower()
                                    bal_raw  = int(b[0])
                                    dec_raw  = int(b[2])
                                    if bal_raw <= 0:
                                        continue
                                    if addr_raw == ADDR_USDT0.lower():
                                        val = bal_raw / (10 ** dec_raw)
                                        total_usd += val
                                        breakdown["USDT0"] = breakdown.get("USDT0", 0.0) + val
                                except Exception:
                                    continue
                    if total_usd > 1.0:
                        import json as _json
                        ts_now = time.time()
                        with DB_LOCK:
                            conn.execute(
                                "INSERT OR REPLACE INTO capital_cache (chat_id, env, total_usd, breakdown_json, updated_ts) VALUES (?,?,?,?,?)",
                                (int(chat_id), env or "AG_C_bd", total_usd, _json.dumps(breakdown), ts_now)
                            )
                            conn.commit()
                    _CAP_FAIL_COUNT = 0
                except Exception:
                    _CAP_FAIL_COUNT += 1
                    if _CAP_FAIL_COUNT >= _CAP_MAX_FAILS:
                        _CAP_SKIP_UNTIL = time.time() + 600
                        logger.warning(f"Capital refresh: muitos erros ({_CAP_FAIL_COUNT}), pausando 10min")
                        break
        except Exception as _we:
            logger.warning(f"user_capital_refresh_worker erro: {_we}")
        time.sleep(15 * 60)

# ==============================================================================
# 📊 FUNNEL WORKER
# ==============================================================================
def _update_user_funnel(chat_id: int, wallet: str):
    try:
        now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = conn.execute(
            "SELECT stage, total_trades, first_trade FROM user_funnel WHERE chat_id=?", (str(chat_id),)
        ).fetchone()
        if existing:
            new_trades = int(existing[1] or 0) + 1
            first_t = existing[2] or now_s
            conn.execute(
                "UPDATE user_funnel SET stage='ativo', total_trades=?, last_trade=?, inactive_days=0, updated_at=? WHERE chat_id=?",
                (new_trades, now_s, now_s, str(chat_id))
            )
        else:
            conn.execute(
                "INSERT INTO user_funnel (chat_id, stage, first_trade, last_trade, total_trades, inactive_days, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (str(chat_id), 'ativo', now_s, now_s, 1, 0, now_s)
            )
        conn.commit()
    except Exception:
        pass

def _funnel_worker():
    """Worker: atualiza inatividade do funil a cada 10min."""
    logger.info("📊 Funnel worker: Ativo...")
    while True:
        try:
            now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            threshold_7d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            with DB_LOCK:
                rows = conn.execute(
                    "SELECT chat_id, last_trade, stage FROM user_funnel WHERE stage='ativo'"
                ).fetchall()
                for chat_id, last_trade, stage in rows:
                    if last_trade and last_trade < threshold_7d:
                        days_inactive = int((datetime.now() - datetime.strptime(last_trade[:19], "%Y-%m-%d %H:%M:%S")).total_seconds() / 86400)
                        conn.execute(
                            "UPDATE user_funnel SET stage='inativo', inactive_days=?, updated_at=? WHERE chat_id=?",
                            (days_inactive, now_s, str(chat_id))
                        )
                conn.commit()
        except Exception:
            pass
        time.sleep(10 * 60)

# ==============================================================================
# ⏳ INACTIVITY AUTO LOOP
# ==============================================================================
def _inactivity_auto_loop():
    """Loop automático de alertas de inatividade para admins."""
    from webdex_config import ADMIN_USER_IDS
    logger.info("⏳ Inactivity auto loop: Ativo...")
    while True:
        try:
            auto_en = str(get_config("inactivity_auto_enabled", "1")).strip()
            if auto_en in ("0", "false", "False"):
                time.sleep(60)
                continue
            check_min = int(get_config("inactivity_auto_minutes", "10") or "10")
            cooldown_min = int(get_config("inactivity_alert_cooldown_min", "30") or "30")
            last_alert_ts = float(get_config("inactivity_last_alert_ts", "0") or "0")
            now_ts = time.time()
            if (now_ts - last_alert_ts) < (cooldown_min * 60):
                time.sleep(check_min * 60)
                continue
            # Detecta inatividade no protocolo (últimos ~check_min*2 blocos = ~2.4s/bloco)
            try:
                from webdex_config import CONTRACTS, Web3 as _W3
                from webdex_chain import TOPIC_OPENPOSITION, rpc_pool
                curr  = int(web3.eth.block_number)
                span  = max(50, int(check_min * 60 / 2.4))
                start = max(1, curr - span)
                logs  = []
                for env_key, c_data in CONTRACTS.items():
                    try:
                        logs += rpc_pool.get_logs({
                            "fromBlock": hex(start),
                            "toBlock":   hex(curr),
                            "address":   _W3.to_checksum_address(c_data["PAYMENTS"]),
                            "topics":    [TOPIC_OPENPOSITION],
                        })
                    except Exception:
                        pass
                if not logs:
                    # Sem trades no período — alerta admins
                    set_config("inactivity_last_alert_ts", str(time.time()))
                    msg = (
                        f"⚠️ <b>INATIVIDADE DETECTADA</b>\n"
                        f"Sem trades nos últimos <b>{check_min} min</b>\n"
                        f"Bloco <code>{start}</code> → <code>{curr}</code>"
                    )
                    for aid in ADMIN_USER_IDS:
                        try:
                            from webdex_bot_core import send_html as _sh
                            _sh(int(aid), msg)
                        except Exception:
                            pass
            except Exception:
                pass
            time.sleep(check_min * 60)
        except Exception:
            pass
        time.sleep(check_min * 60 if 'check_min' in dir() else 600)
