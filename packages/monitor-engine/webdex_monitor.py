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
    web3, rpc_pool, CONTRACTS_A, CONTRACTS_B, TOPIC_OPENPOSITION, TOPIC_TRANSFER,
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
        return rpc_pool.get_logs(params)
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

def _profit_emoji(val: float) -> str:
    if val >= 10:  return "💰"
    if val >= 0:   return "🟢"
    if val >= -2:  return "🔴"
    return "🚨"

def _today_stats(chat_id: int) -> tuple[int, float]:
    """Retorna (trades_hoje, pnl_hoje) para o chat_id. Silencioso em erro."""
    try:
        with DB_LOCK:
            row = cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(CAST(o.valor AS REAL)) - SUM(CAST(o.gas_usd AS REAL)), 0)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                JOIN users u ON LOWER(u.wallet)=LOWER(ow.wallet)
                WHERE o.tipo='Trade'
                  AND DATE(o.data_hora)=DATE('now','localtime')
                  AND u.chat_id=?
            """, (chat_id,)).fetchone()
        if row:
            return int(row[0] or 0), float(row[1] or 0)
    except Exception:
        pass
    return 0, 0.0

def _today_wins(chat_id: int) -> int:
    """Retorna número de trades vencedores (valor > 0) hoje para o chat_id."""
    try:
        with DB_LOCK:
            row = cursor.execute("""
                SELECT COUNT(*)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                JOIN users u ON LOWER(u.wallet)=LOWER(ow.wallet)
                WHERE o.tipo='Trade'
                  AND CAST(o.valor AS REAL) > 0
                  AND DATE(o.data_hora)=DATE('now','localtime')
                  AND u.chat_id=?
            """, (chat_id,)).fetchone()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0

def _today_streak(chat_id: int) -> int:
    """Conta wins consecutivos mais recentes hoje (do mais novo para o mais antigo)."""
    try:
        with DB_LOCK:
            rows = cursor.execute("""
                SELECT CAST(o.valor AS REAL)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                JOIN users u ON LOWER(u.wallet)=LOWER(ow.wallet)
                WHERE o.tipo='Trade'
                  AND DATE(o.data_hora)=DATE('now','localtime')
                  AND u.chat_id=?
                ORDER BY o.data_hora DESC
            """, (chat_id,)).fetchall()
        streak = 0
        for (v,) in rows:
            if float(v or 0) > 0:
                streak += 1
            else:
                break
        return streak
    except Exception:
        return 0

def _sub_cycle(sub: str) -> str:
    """Tempo entre as 2 últimas operações desta subconta. Retorna string formatada ou ''."""
    try:
        with DB_LOCK:
            rows = cursor.execute("""
                SELECT data_hora FROM operacoes
                WHERE sub_conta=? AND tipo='Trade'
                ORDER BY data_hora DESC
                LIMIT 2
            """, (sub,)).fetchall()
        if not rows or len(rows) < 2:
            return ""
        t1 = datetime.strptime(rows[0][0][:19], "%Y-%m-%d %H:%M:%S")
        t2 = datetime.strptime(rows[1][0][:19], "%Y-%m-%d %H:%M:%S")
        delta = int((t1 - t2).total_seconds())
        if delta <= 0:
            return ""
        if delta < 60:
            return f"{delta}s"
        if delta < 3600:
            m, s = divmod(delta, 60)
            return f"{m}min {s}s"
        h, rem = divmod(delta, 3600)
        return f"{h}h {rem // 60}min"
    except Exception:
        return ""

def _sub_efficiency(sub: str, env_tag: str) -> str:
    """Compara ops da subconta hoje vs média do ambiente. Retorna string ou ''."""
    try:
        with DB_LOCK:
            sub_row = cursor.execute("""
                SELECT COUNT(*) FROM operacoes
                WHERE sub_conta=? AND tipo='Trade'
                  AND DATE(data_hora)=DATE('now','localtime')
            """, (sub,)).fetchone()
            env_row = cursor.execute("""
                SELECT COUNT(DISTINCT sub_conta), COUNT(*)
                FROM operacoes
                WHERE ambiente=? AND tipo='Trade'
                  AND DATE(data_hora)=DATE('now','localtime')
            """, (env_tag,)).fetchone()
        sub_ops = int(sub_row[0] or 0) if sub_row else 0
        if not env_row or not env_row[0] or env_row[0] == 0:
            return ""
        n_subs = int(env_row[0])
        total  = int(env_row[1] or 0)
        avg    = total / n_subs if n_subs > 0 else 0
        if avg <= 0:
            return ""
        diff_pct = ((sub_ops - avg) / avg) * 100
        sign = "+" if diff_pct >= 0 else ""
        arrow = "▲" if diff_pct >= 0 else "▼"
        return f"{sub_ops} ops  ·  média env: {avg:.0f}  ({arrow}{sign}{diff_pct:.0f}%)"
    except Exception:
        return ""

def _sub_drawdown(sub: str) -> str:
    """Pior ponto e pico do dia para esta subconta. Retorna string ou ''."""
    try:
        with DB_LOCK:
            rows = cursor.execute("""
                SELECT CAST(valor AS REAL) FROM operacoes
                WHERE sub_conta=? AND tipo='Trade'
                  AND DATE(data_hora)=DATE('now','localtime')
                ORDER BY data_hora ASC
            """, (sub,)).fetchall()
        if not rows:
            return ""
        acc, peak, trough = 0.0, 0.0, 0.0
        for (v,) in rows:
            acc += float(v or 0)
            if acc > peak:
                peak = acc
            if acc < trough:
                trough = acc
        if peak == 0.0 and trough == 0.0:
            return ""
        peak_s   = f"+${peak:.2f}"   if peak   >= 0 else f"-${abs(peak):.2f}"
        trough_s = f"-${abs(trough):.2f}" if trough < 0 else f"+${trough:.2f}"
        return f"{trough_s}  →  pico {peak_s}"
    except Exception:
        return ""

def _sub_gas_today(sub: str) -> str:
    """Gás total acumulado hoje por esta subconta."""
    try:
        with DB_LOCK:
            row = cursor.execute("""
                SELECT SUM(CAST(gas_usd AS REAL)) FROM operacoes
                WHERE sub_conta=? AND tipo='Trade'
                  AND DATE(data_hora)=DATE('now','localtime')
            """, (sub,)).fetchone()
        total = float(row[0] or 0) if row else 0.0
        if total <= 0:
            return ""
        return f"${total:.4f} hoje"
    except Exception:
        return ""

def _sub_rank(sub: str, env_tag: str) -> str:
    """Rank desta subconta no ambiente pelo P&L de hoje. Retorna string ou ''."""
    try:
        with DB_LOCK:
            rows = cursor.execute("""
                SELECT sub_conta, SUM(CAST(valor AS REAL)) as pnl
                FROM operacoes
                WHERE ambiente=? AND tipo='Trade'
                  AND DATE(data_hora)=DATE('now','localtime')
                GROUP BY sub_conta
                ORDER BY pnl DESC
            """, (env_tag,)).fetchall()
        if not rows:
            return ""
        total = len(rows)
        for i, (s, _) in enumerate(rows, 1):
            if s == sub:
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "")
                return f"{medal} #{i} de {total} subcontas ativas"
        return ""
    except Exception:
        return ""

_STABLE_TOKENS = {"USDT0", "USDT", "USDC", "DAI", "BUSD"}

def _net_usd(val: float, token: str, gas_usd: float) -> str:
    """Net pós-gás em USD para stablecoins. Retorna string formatada ou ''."""
    if token.upper() in _STABLE_TOKENS and abs(val) > 0:
        net = val - gas_usd
        sign = "+" if net >= 0 else ""
        return f"{sign}${net:.4f}"
    return ""

def _capital_pct(chat_id: int, val: float) -> str:
    """Retorna string '(+X.XX% capital)' ou '' se sem dados."""
    try:
        with DB_LOCK:
            row = cursor.execute(
                "SELECT total_usd FROM capital_cache WHERE chat_id=? ORDER BY updated_ts DESC LIMIT 1",
                (chat_id,)
            ).fetchone()
        if row and float(row[0] or 0) > 0:
            pct = val / float(row[0]) * 100
            sign = "+" if pct >= 0 else ""
            return f"  <i>({sign}{pct:.2f}% capital)</i>"
    except Exception:
        pass
    return ""


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
            # Transferência simples — formato compacto
            gas_pct = f" ({(gas_usd / abs(val)) * 100:.1f}%)" if val and abs(val) > 0 else ""
            msg = (
                f"{titulo}\n"
                f"👤 {code(sub)}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⛽ Gás: {code(f'${gas_usd:.4f}')}{esc(gas_pct)}\n"
                f'🔗 <a href="https://polygonscan.com/tx/{esc(tx)}">PolygonScan</a>'
            )
            send_html(chat_id, msg, disable_web_page_preview=True)
            return

        # ── EXECUÇÃO — formato rico WEbdEX (Fase 1) ────────────────────────
        tag   = env_tag or "AG"
        strat = (strategy_name or "Standard").strip() or "Standard"

        # ── RESULTADO ──────────────────────────────────────────────────────
        p_emoji  = _profit_emoji(val)
        cap_pct  = _capital_pct(chat_id, val)
        gas_pct  = f"  <i>({(gas_usd / abs(val)) * 100:.1f}%)</i>" if val and abs(val) > 0 else ""
        net_str  = _net_usd(val, token, gas_usd)
        net_line = f"💵  Net pós-gás: <b>{esc(net_str)}</b>{cap_pct}\n" if net_str else ""

        if gas_pol and gas_pol > 0:
            gas_line = f"⛽  Gás: <code>{gas_pol:.4f} POL</code>  ·  <code>${gas_usd:.4f}</code>{esc(gas_pct)}"
        else:
            gas_line = f"⛽  Gás: <code>${gas_usd:.4f}</code>{esc(gas_pct)}"

        pass_line = f"🎟️  Fee Protocolo: <code>{pass_fee_bd:.4f} BD</code>" if (pass_fee_bd and pass_fee_bd > 0) else ""

        # ── BLOCKCHAIN ─────────────────────────────────────────────────────
        ago = "Confirmado agora"
        bloco_line = ""
        if bloco and bloco > 0:
            bloco_line = f"🔷  Polygon  ·  Bloco <code>{bloco:,}</code>\n"
            ts = get_block_ts(bloco)
            if ts:
                delta = max(0, int(now_br().timestamp() - ts))
                mins  = delta // 60
                if mins < 1:
                    ago = "Confirmado agora"
                elif mins < 60:
                    ago = f"Confirmado há {mins} min"
                elif mins < 60 * 24:
                    ago = f"Confirmado há {mins // 60}h"
                else:
                    ago = f"Confirmado há {mins // (60 * 24)}d"
        else:
            bloco_line = "🔷  Polygon\n"

        cycle = _sub_cycle(sub)
        cycle_line = f"⏱️  Ciclo SubConta: <b>{esc(cycle)}</b>\n" if cycle else ""

        # ── HOJE ───────────────────────────────────────────────────────────
        trades_hj, pnl_hj = _today_stats(chat_id)
        wins_hj   = _today_wins(chat_id)
        losses_hj = max(0, trades_hj - wins_hj)
        wr_hj     = (wins_hj / trades_hj * 100) if trades_hj > 0 else 0.0
        wr_emoji  = "🟢" if wr_hj >= 60 else ("🟡" if wr_hj >= 40 else "🔴")
        pnl_sign  = "+" if pnl_hj >= 0 else ""
        filled    = round(wr_hj / 10)
        wr_bar    = "█" * filled + "░" * (10 - filled)

        streak      = _today_streak(chat_id)
        streak_line = f"🔥  Sequência: <b>{streak} wins seguidos</b>\n" if streak >= 3 else ""

        # ── SUBCONTA (Fase 2) ───────────────────────────────────────────────
        efficiency  = _sub_efficiency(sub, tag)
        drawdown    = _sub_drawdown(sub)
        gas_acc     = _sub_gas_today(sub)
        rank        = _sub_rank(sub, tag)

        sub_lines = ""
        if efficiency:
            sub_lines += f"📈  Eficiência: <b>{esc(efficiency)}</b>\n"
        if drawdown:
            sub_lines += f"📉  Drawdown hoje: <b>{esc(drawdown)}</b>\n"
        if gas_acc:
            sub_lines += f"⛽  Gás acumulado: <b>{esc(gas_acc)}</b>\n"
        if rank:
            sub_lines += f"🏅  Rank no ambiente: <b>{esc(rank)}</b>\n"

        sub_section = (
            f"┈┈┈┈┈┈ SUBCONTA ┈┈┈┈┈┈\n\n{sub_lines}\n"
        ) if sub_lines else ""

        msg = (
            f"⚡ <b>WEbdEX ENGINE</b>  ·  <code>{esc(tag)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"🔵  <b>EXECUÇÃO CONFIRMADA</b>  ·  #{trades_hj}\n"
            f"👤  {code(sub)}\n"
            f"🔄  Estratégia: <b>{esc(strat)}</b>  ·  🪙 <b>{esc(token)}</b>\n"
            f"\n"
            f"┈┈┈┈┈┈ RESULTADO ┈┈┈┈┈┈\n"
            f"\n"
            f"{p_emoji}  <b>{val:+.4f} {esc(token)}</b>\n"
            f"{net_line}"
            f"{gas_line}\n"
            f"{pass_line + chr(10) if pass_line else ''}"
            f"\n"
            f"┈┈┈┈┈┈ BLOCKCHAIN ┈┈┈┈┈┈\n"
            f"\n"
            f"{bloco_line}"
            f"🕒  <i>{esc(ago)}</i>\n"
            f"{cycle_line}"
            f'🔗  <a href="https://polygonscan.com/tx/{esc(tx)}">Ver transação ↗</a>\n'
            f"\n"
            f"{sub_section}"
            f"┈┈┈┈┈┈ HOJE ┈┈┈┈┈┈\n"
            f"\n"
            f"📊  <b>{trades_hj} trades</b>  ·  WinRate <b>{wr_hj:.0f}%</b>  {wr_emoji}\n"
            f"<code>    {wr_bar}</code>\n"
            f"💰  P&L: <b>{pnl_sign}${pnl_hj:.2f}</b>  ·  {wins_hj}W / {losses_hj}L\n"
            f"{streak_line}"
            f"\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>⚡ WEbdEX · New Digital Economy</i>"
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
