from __future__ import annotations
# ==============================================================================
# webdex_monitor.py — WEbdEX Monitor Engine (extraído de WEbdEX_V30_24_SPEED_PATCH_FIXED.py)
# Linhas fonte: ~1939-2420 (HEALTH, safe_get_logs, notificar, process_log, fetch_range, vigia)
# ==============================================================================

import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from webdex_config import (
    logger, log_error, Web3, CONTRACTS, TOKENS_TO_WATCH,
    MONITOR_MAX_BLOCKS_PER_LOOP, MONITOR_FETCH_CHUNK,
    MONITOR_IDLE_SLEEP, MONITOR_BUSY_SLEEP, MONITOR_BACKLOG_WARN_AT,
    _RPC_PUBLICOS, _POA_MW, infer_env_by_address,
)
from webdex_db import (
    DB_LOCK, conn, cursor, get_config, set_config,
    now_br, get_block_ts, op_set_block_ts, normalize_txhash,
)
from webdex_chain import (
    web3, CONTRACTS_A, CONTRACTS_B, TOPIC_OPENPOSITION, TOPIC_TRANSFER,
    erc20_contract, get_active_wallet_map, notify_cids_for_wallet,
    obter_preco_pol, _is_429_error,
)
from webdex_bot_core import (
    send_html, esc, code, get_token_meta, formatar_moeda,
)

# ==============================================================================
# 🧠 HEALTH
# ==============================================================================
HEALTH = {
    "started_at":       time.time(),
    "last_block_seen":  0,
    "last_fetch_ok_ts": 0,
    "vigia_loops":      0,
    "logs_trade":       0,
    "logs_transfer":    0,
    "last_error":       "",
    "cooldown_until":   0,
    "sync_running":     0,
    "sync_last":        "",
    "tg_last_ok_ts":    0,
    "rpc_latency_ms":   0.0,
    "rpc_latency_avg":  0.0,
    "rpc_errors_total": 0,
    "blocks_skipped":   0,
    "blocks_processed": 0,
    "capture_rate":     100.0,
    "last_rpc_ok_ts":   0.0,
    "events_lost_est":  0,
}

def _health_touch(k: str):
    HEALTH[k] = time.time()

# ==============================================================================
# 🔁 LOGS SAFE (ANTI-429)
# ==============================================================================
def _safe_get_logs(params, depth=0):
    try:
        return web3.eth.get_logs(params)
    except Exception as e:
        if _is_429_error(e):
            HEALTH["last_error"] = f"get_logs 429: {e}"
            cd = min(180, 15 * (depth + 1))
            HEALTH["cooldown_until"] = time.time() + cd
            time.sleep(min(10, cd))
            return []
        if depth >= 4:
            HEALTH["last_error"] = f"get_logs: {e}"
            return []
        try:
            fb, tb = int(params["fromBlock"], 16), int(params["toBlock"], 16)
        except Exception:
            HEALTH["last_error"] = f"get_logs_parse: {e}"
            return []
        if tb <= fb:
            return []
        mid = (fb + tb) // 2
        l, r = dict(params), dict(params)
        l["toBlock"] = Web3.to_hex(mid)
        r["fromBlock"] = Web3.to_hex(mid + 1)
        return _safe_get_logs(l, depth + 1) + _safe_get_logs(r, depth + 1)

# ==============================================================================
# 🔔 NOTIFICAÇÃO
# ==============================================================================
def _fmt_time_ago_from_block(bloco: int) -> str:
    ts = get_block_ts(int(bloco or 0))
    if ts <= 0:
        return "agora"
    now_ts = int(now_br().timestamp())
    diff = max(0, now_ts - int(ts))
    mins = diff // 60
    if mins < 1:
        return "agora"
    if mins < 60:
        return f"{mins} min atrás"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs}h atrás"
    days = hrs // 24
    return f"{days}d atrás"

def notificar(
    chat_id: int,
    titulo: str,
    sub: str,
    val: float,
    gas_usd: float,
    token: str,
    tx: str,
    *,
    env_tag: str = "",
    strategy_name: str = "",
    gas_pol: float = 0.0,
    pass_fee_bd: float = 0.0,
    bloco: int = 0,
    network: str = "Polygon",
    **_ignored,
):
    try:
        tx = normalize_txhash(tx)
        titulo_u = (titulo or "").upper()
        is_exec = bool(env_tag or strategy_name or pass_fee_bd or ("EXECU" in titulo_u) or ("OPENPOSITION" in titulo_u))

        if not is_exec:
            pct = ""
            if val and abs(val) > 0:
                pct = f" ({(gas_usd / abs(val)) * 100:.1f}%)"
            msg = (
                f"{titulo}\n"
                f"👤 {code(sub)}\n"
                f"────────────────────\n"
                f"⛽ Gás: {code(f'${gas_usd:.4f}')}" + esc(pct) + "\n"
                f'🔗 <a href="https://polygonscan.com/tx/{esc(tx)}">Scan</a>'
            )
            send_html(chat_id, msg, disable_web_page_preview=True)
            return

        tag = env_tag or "AG"
        strat = (strategy_name or "-").strip() or "-"
        prof_ball = "🟢" if val >= 0 else "🔴"
        profit_line = f"{prof_ball} Profit: {val:+.4f} {esc(token)}"
        gas_pct = ""
        if val and abs(val) > 0:
            gas_pct = f" ({(gas_usd / abs(val)) * 100:.1f}%)"
        if gas_pol and gas_pol > 0:
            gas_extra = f" • ${gas_usd:.4f}" + gas_pct if gas_usd else gas_pct
            gas_line = f"⛽ Gas fee: {gas_pol:.4f} POL" + esc(gas_extra)
        else:
            gas_line = f"⛽ Gas fee: ${gas_usd:.4f}" + esc(gas_pct)
        pass_line = "🎟️ Pass fee: -"
        if pass_fee_bd and pass_fee_bd > 0:
            pass_line = f"🎟️ Pass fee: {pass_fee_bd:.4f} BD"
        ago = "-"
        if bloco and bloco > 0:
            ts = get_block_ts(bloco)
            if ts:
                delta = max(0, int(now_br().timestamp() - ts))
                mins = delta // 60
                if mins < 1:
                    ago = "agora"
                elif mins < 60:
                    ago = f"{mins} min atrás"
                elif mins < 60 * 24:
                    ago = f"{mins // 60} h atrás"
                else:
                    ago = f"{mins // (60 * 24)} d atrás"
        msg = (
            f"🔵 <b>EXECUÇÃO — WEbdEX [{esc(tag)}]</b>\n\n"
            f"Account: {esc(sub)}\n"
            f"Strategy: {esc(strat)}\n"
            f"────────────────────\n"
            f"{profit_line}\n"
            f"{gas_line}\n"
            f"{pass_line}\n"
            f"────────────────────\n"
            f"🧱 Network: {esc(network)}\n"
            f"🕒 {esc(ago)}\n"
            f'🔗 <a href="https://polygonscan.com/tx/{esc(tx)}">Scan</a>'
        )
        send_html(chat_id, msg, disable_web_page_preview=True)
    except Exception as e:
        log_error("notificar", e)

# ==============================================================================
# 🔁 MONITOR (CORE)
# ==============================================================================
_TX_CACHE_TS: Dict[str, float] = {}

def _get_tx_and_receipt_safely(tx: str):
    now = time.time()
    if tx in _TX_CACHE_TS and (now - _TX_CACHE_TS[tx]) < 60:
        return None, None
    _TX_CACHE_TS[tx] = now
    try:
        t = web3.eth.get_transaction(tx)
        r = web3.eth.get_transaction_receipt(tx)
        return t, r
    except Exception:
        return None, None

def registrar_operacao(tx_hash, log_index, tipo, valor, gas_usd, token, sub_id, bloco, owner_wallet,
                       ambiente='UNKNOWN', fee=0.0,
                       strategy_addr='', bot_id='', gas_protocol=0.0, old_balance_usd=0.0):
    dt = now_br().strftime("%Y-%m-%d %H:%M:%S")
    tx_hash = normalize_txhash(tx_hash)
    with DB_LOCK:
        try:
            if cursor.execute("SELECT 1 FROM operacoes WHERE hash=? AND log_index=?", (tx_hash, int(log_index))).fetchone():
                return False
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO operacoes "
                    "(hash,log_index,data_hora,tipo,valor,gas_usd,token,sub_conta,bloco,ambiente,fee,"
                    " strategy_addr,bot_id,gas_protocol,old_balance_usd) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (tx_hash, int(log_index), dt, tipo, float(valor), float(gas_usd), token,
                     sub_id, int(bloco), ambiente, float(fee),
                     str(strategy_addr or ''), str(bot_id or ''),
                     float(gas_protocol or 0.0), float(old_balance_usd or 0.0))
                )
            except Exception:
                cursor.execute(
                    "INSERT OR IGNORE INTO operacoes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (tx_hash, int(log_index), dt, tipo, float(valor), float(gas_usd),
                     token, sub_id, int(bloco), ambiente, float(fee))
                )
            cursor.execute(
                "INSERT OR REPLACE INTO op_owner (hash, log_index, wallet) VALUES (?,?,?)",
                (tx_hash, int(log_index), str(owner_wallet).lower())
            )
            conn.commit()
        except Exception:
            return False
    try:
        op_set_block_ts(tx_hash, int(log_index), int(bloco), str(ambiente))
    except Exception:
        pass
    return True

def _update_user_funnel(chat_id: int, wallet: str):
    """Atualiza funil do usuário após trade real."""
    try:
        from datetime import datetime as _dt
        now_s = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
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

def process_log(log, tipo_evento):
    tx = normalize_txhash(log.get("transactionHash"))
    wallet_map, _ = get_active_wallet_map()

    try:
        if tipo_evento == "Trade":
            addr = str(log.get("address", "")).lower()
            ambiente = infer_env_by_address(Web3.to_checksum_address(addr))
            c = CONTRACTS_B if addr == CONTRACTS["bd_v5"]["PAYMENTS"].lower() else CONTRACTS_A
            evt = c["payments"].events.OpenPosition().process_log(log)
            args = evt["args"]
            uw = str(args["user"]).lower().strip()
            if uw not in wallet_map:
                return
            meta = get_token_meta(args["details"]["coin"])
            val = formatar_moeda(args["details"]["profit"], meta["dec"])
            gas_usd = 0.0
            gas_pol = 0.0
            t, r = _get_tx_and_receipt_safely(tx)
            if t and r:
                try:
                    gas_pol = float(Decimal(r["gasUsed"]) * Decimal(t["gasPrice"]) / Decimal(10**18))
                    gas_usd = gas_pol * obter_preco_pol()
                except Exception:
                    gas_usd = 0.0
                    gas_pol = 0.0
            pass_fee_bd = float(formatar_moeda(args["details"].get("fee", 0), 9))
            strategy_name = str(args["details"].get("botId") or "").strip()
            if not strategy_name:
                st = str(args["details"].get("strategy") or "")
                strategy_name = (st[:10] + "..." + st[-6:]) if len(st) > 16 else (st or "-")
            _strategy_addr  = str(args["details"].get("strategy") or "").lower().strip()
            _bot_id         = str(args["details"].get("botId") or strategy_name or "").strip()
            _gas_proto_raw  = int(args["details"].get("gas") or 0)
            _gas_proto_usd  = float(_gas_proto_raw) / (10 ** meta["dec"]) * obter_preco_pol() if _gas_proto_raw > 0 else 0.0
            _old_bal_raw2   = int(args["details"].get("oldBalance") or 0)
            _old_bal_usd2   = float(_old_bal_raw2) / (10 ** meta["dec"]) if _old_bal_raw2 > 0 else 0.0

            if registrar_operacao(tx, int(log["logIndex"]), "Trade", val, gas_usd, meta["sym"],
                                  args["accountId"], int(log["blockNumber"]), uw,
                                  ambiente=ambiente, fee=pass_fee_bd,
                                  strategy_addr=_strategy_addr, bot_id=_bot_id,
                                  gas_protocol=_gas_proto_usd, old_balance_usd=_old_bal_usd2):
                op_set_block_ts(tx, int(log["logIndex"]), int(log["blockNumber"]))
                try:
                    _old_bal_raw = int(args["details"].get("oldBalance") or 0)
                    _coin_meta   = get_token_meta(args["details"]["coin"])
                    _old_bal_usd = float(_old_bal_raw) / (10 ** _coin_meta["dec"]) if _old_bal_raw > 0 else 0.0
                    _now_str     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with DB_LOCK:
                        conn.execute("""
                            INSERT INTO sub_positions
                                (wallet, sub_conta, ambiente, saldo_usdt,
                                 last_trade, old_balance, trade_count, updated_at)
                            VALUES (?,?,?,?,?,?,1,?)
                            ON CONFLICT(wallet, sub_conta, ambiente) DO UPDATE SET
                                saldo_usdt  = excluded.old_balance + excluded.saldo_usdt - saldo_usdt,
                                last_trade  = excluded.last_trade,
                                old_balance = excluded.old_balance,
                                trade_count = trade_count + 1,
                                updated_at  = excluded.updated_at
                        """, (uw, str(args["accountId"]), ambiente,
                              _old_bal_usd, _now_str, _old_bal_usd, _now_str))
                        conn.commit()
                except Exception:
                    pass
                HEALTH["logs_trade"] += 1
                try:
                    for _fcid in wallet_map.get(uw, []):
                        _update_user_funnel(int(_fcid), str(uw))
                except Exception:
                    pass
                for cid in notify_cids_for_wallet(wallet_map, uw):
                    notificar(
                        int(cid),
                        "EXECUÇÃO",
                        str(args["accountId"]),
                        float(val),
                        float(gas_usd),
                        str(meta["sym"]),
                        tx,
                        env_tag=str(c["tag"]),
                        strategy_name=strategy_name,
                        gas_pol=float(gas_pol),
                        pass_fee_bd=float(pass_fee_bd),
                        bloco=int(log.get("blockNumber") or 0),
                        network="Polygon",
                    )

        elif tipo_evento == "Transfer":
            addr = str(log.get("address", "")).lower()
            ambiente = infer_env_by_address(Web3.to_checksum_address(addr))
            if addr not in [t.lower() for t in TOKENS_TO_WATCH]:
                return
            evt = erc20_contract(addr).events.Transfer().process_log(log)
            args = evt["args"]
            to, fr = str(args["to"]).lower(), str(args["from"]).lower()
            if (to not in wallet_map) and (fr not in wallet_map):
                return
            meta = get_token_meta(addr)
            val = formatar_moeda(args["value"], meta["dec"])
            if to in wallet_map:
                if registrar_operacao(tx, int(log["logIndex"]), "Transfer", val, 0.0, meta["sym"], "WALLET", int(log["blockNumber"]), to, ambiente=ambiente):
                    HEALTH["logs_transfer"] += 1
                    for cid in notify_cids_for_wallet(wallet_map, to):
                        notificar(cid, f"📥 <b>ENTRADA ({esc(meta['sym'])})</b>", "Carteira", val, 0.0, meta["sym"], tx)
            if fr in wallet_map:
                if registrar_operacao(tx, int(log["logIndex"]), "Transfer", -val, 0.0, meta["sym"], "WALLET", int(log["blockNumber"]), fr):
                    HEALTH["logs_transfer"] += 1
                    for cid in notify_cids_for_wallet(wallet_map, fr):
                        notificar(cid, f"📤 <b>SAÍDA ({esc(meta['sym'])})</b>", "Carteira", -val, 0.0, meta["sym"], tx)

    except Exception as e:
        HEALTH["last_error"] = f"process_log: {e}"
        HEALTH["process_log_fail"] = int(HEALTH.get("process_log_fail", 0)) + 1
        try:
            _txh = normalize_txhash(log.get("transactionHash"))
            logger.warning(f"⚠️ process_log falhou | tipo={tipo_evento} tx={_txh} err={e}")
        except Exception:
            pass

def fetch_range(start, end, env_only=None, include_transfers=True):
    try:
        start_i, end_i = int(start), int(end)
    except Exception:
        return
    if end_i < start_i:
        return
    chunk = max(1, int(MONITOR_FETCH_CHUNK))
    envs = (env_only,) if env_only in ("AG_C_bd", "bd_v5") else ("AG_C_bd", "bd_v5")
    cur = start_i
    while cur <= end_i:
        nxt = min(end_i, cur + chunk - 1)
        p_from, p_to = Web3.to_hex(int(cur)), Web3.to_hex(int(nxt))
        for env in envs:
            try:
                addr = Web3.to_checksum_address(CONTRACTS[env]["PAYMENTS"])
                logs = _safe_get_logs({"fromBlock": p_from, "toBlock": p_to, "address": addr, "topics": [TOPIC_OPENPOSITION]})
                for l in logs:
                    process_log(l, "Trade")
            except Exception as e:
                HEALTH["last_error"] = f"fetch_range trade {env}: {e}"
        if include_transfers:
            try:
                logs_t = _safe_get_logs({"fromBlock": p_from, "toBlock": p_to, "address": TOKENS_TO_WATCH, "topics": [TOPIC_TRANSFER]})
                for l in logs_t:
                    process_log(l, "Transfer")
            except Exception as e:
                HEALTH["last_error"] = f"fetch_range transfer: {e}"
        cur = nxt + 1

def vigia():
    logger.info("👀 VIGIA: Iniciado...")
    try:
        curr_bn = int(web3.eth.block_number)
        persisted = str(get_config("last_block", "") or "").strip()
        if persisted.isdigit():
            last = int(persisted)
            if last > curr_bn:
                last = max(1, curr_bn - 5)
        else:
            last = max(1, curr_bn - 5)
        HEALTH["last_block_seen"] = last
    except Exception as e:
        HEALTH["last_error"] = f"vigia_init: {e}"
        time.sleep(5)
        return

    while True:
        try:
            _health_touch("last_vigia_ts")
            HEALTH["vigia_loops"] += 1
            if time.time() < float(HEALTH.get("cooldown_until") or 0):
                time.sleep(max(1.0, MONITOR_IDLE_SLEEP))
                continue
            curr = int(web3.eth.block_number)
            HEALTH["last_block_seen"] = curr
            if curr > last:
                _t0_rpc = time.time()
                backlog = curr - last
                max_blocks = max(1, int(MONITOR_MAX_BLOCKS_PER_LOOP))
                target = min(curr, last + max_blocks)
                if backlog > int(MONITOR_BACKLOG_WARN_AT):
                    logger.warning(
                        f"⚠️ Backlog detectado: {backlog} blocos | processando janela {last + 1}->{target} para manter realtime vivo"
                    )
                fetch_range(last + 1, target, include_transfers=True)
                _lat_ms = (time.time() - _t0_rpc) * 1000
                HEALTH["rpc_latency_ms"] = _lat_ms
                HEALTH["rpc_latency_avg"] = (
                    0.9 * HEALTH["rpc_latency_avg"] + 0.1 * _lat_ms
                    if HEALTH["rpc_latency_avg"] > 0 else _lat_ms
                )
                HEALTH["blocks_processed"] += (target - last)
                HEALTH["last_rpc_ok_ts"] = time.time()
                _total = HEALTH["blocks_processed"] + HEALTH["blocks_skipped"]
                HEALTH["capture_rate"] = (
                    HEALTH["blocks_processed"] / _total * 100 if _total > 0 else 100.0
                )
                last = target
                try:
                    set_config("last_block", str(last))
                except Exception:
                    pass
                HEALTH["last_fetch_ok_ts"] = time.time()
                if last < curr:
                    time.sleep(max(0.05, MONITOR_BUSY_SLEEP))
                    continue
            time.sleep(max(0.2, MONITOR_IDLE_SLEEP))
        except Exception as e:
            HEALTH["last_error"] = f"vigia: {e}"
            HEALTH["rpc_errors_total"] += 1
            if _is_429_error(e):
                HEALTH["cooldown_until"] = time.time() + 60
                time.sleep(10)
            else:
                _err_count = HEALTH["rpc_errors_total"]
                if _err_count > 0 and _err_count % 5 == 0:
                    _n_rpcs = len(_RPC_PUBLICOS)
                    _next_rpc = _RPC_PUBLICOS[(_err_count // 5) % _n_rpcs]
                    try:
                        _w3_new = Web3(Web3.HTTPProvider(_next_rpc, request_kwargs={"timeout": 20}))
                        if _POA_MW:
                            _w3_new.middleware_onion.inject(_POA_MW, layer=0)
                        web3.__class__ = _w3_new.__class__
                        web3.provider = _w3_new.provider
                        logger.warning(f"👀 VIGIA: RPC trocado para {_next_rpc} (erros: {_err_count})")
                    except Exception:
                        pass
                time.sleep(5)
