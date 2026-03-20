from __future__ import annotations
# ==============================================================================
# webdex_workers.py — WEbdEX Monitor Engine (extraído de WEbdEX_V30_24_SPEED_PATCH_FIXED.py)
# Linhas fonte: ~2420-2560 (sentinela, agendador_21h, _chain_cache_worker)
#               + ~6156-7460 (capital_snapshot_worker, user_capital_refresh_worker, funnel_worker)
# ==============================================================================

import time, threading
from datetime import datetime, timedelta
from typing import Any, Dict

# Lock compartilhado: impede que capital_snapshot e user_capital_refresh
# rodem simultaneamente (dobrariam RPC calls e poderiam sobrescrever uns aos outros)
_capital_lock = threading.Lock()

from webdex_config import logger, Web3, CONTRACTS, ADDR_USDT0, ADDR_LPLPUSD, ADDR_LPUSDT0
from webdex_db import (
    DB_LOCK, conn, cursor, get_config, set_config, now_br, get_user,
    LIMITE_GWEI, LIMITE_GAS_BAIXO_POL, LIMITE_INATIV_MIN,
    reload_limites, period_to_hours, _ciclo_21h_since,
)
from webdex_chain import (
    web3, CONTRACTS_A, CONTRACTS_B, get_active_wallet_map,
    obter_preco_pol, _chain_cache_worker,
)
from webdex_bot_core import send_html, _notif_worker, send_logo_photo
from webdex_discord_sync import (
    notify_ciclo_report, notify_protocolo_relatorio, notify_protocolo_relatorio_telegram,
    notify_protocolo_relatorio_onchain, notify_gm, _WEBHOOK_GM,
    notify_operacoes_horario, notify_swaps_horario, notify_onchain_heartbeat,
    _WEBHOOK_OPERACOES, _WEBHOOK_SWAPS, _WEBHOOK_RELATORIO, _WEBHOOK_ONCHAIN,
    get_pulse_stats_and_reset,
)

try:
    from webdex_discord_animate import animate_and_post as _animate
except ImportError:
    _animate = None  # type: ignore[assignment]

try:
    from webdex_creatomate import render_relatorio_21h as _render_21h
except ImportError:
    _render_21h = None  # type: ignore[assignment]

try:
    from telegram_design_tokens import (
        HDR, SEP, EMOJI as TG, winrate_bar, format_currency, cta_ocme,
    )
    _TG_TOKENS = True
except ImportError:
    _TG_TOKENS = False

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
                            w_short = m["wallet"][:6] + "..." + m["wallet"][-4:]
                            send_html(cid, (
                                f"⛽ <b>GÁS BAIXO</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"💰 Saldo: <code>{gas:.4f} POL</code>\n"
                                f"🔑 Carteira: <code>{w_short}</code>\n\n"
                                f"<i>Recarregue POL para continuar operando.</i>"
                            ))
                    except Exception as e:
                        logger.debug(f"[sentinela] gasBalance falhou cid={cid}: {e}")
                last = time.time()
        except Exception as e:
            logger.warning(f"[sentinela] Erro no loop de verificação: {e}")
        time.sleep(30)

# ==============================================================================
# ⏰ AGENDADOR 21H
# ==============================================================================
def agendador_21h():
    logger.info("⏰ Agendador 21h: Ativo...")
    while True:
        try:
            now = now_br()
            # ── Ritual GM 7h → #gm-wagmi ──────────────────────────
            if now.hour >= 7:
                gm_key = f"gm_sent_{now.strftime('%Y-%m-%d')}"
                if get_config(gm_key, "") != "ok":
                    notify_gm(now.strftime('%Y-%m-%d'))
                    if _animate:
                        _animate(
                            "gm", _WEBHOOK_GM,
                            title="☀️ Bom dia, WEbdEX!",
                            description="O protocolo está ativo. Que os ciclos sejam verdes! 🚀",
                            color=0xE91E8C,
                        )
                    set_config(gm_key, "ok")
            if now.hour >= 21:
                hoje = now.strftime("%Y-%m-%d")
                with DB_LOCK:
                    rows = cursor.execute("SELECT chat_id FROM users WHERE active=1").fetchall()
                # Acumuladores para o relatório agregado Discord
                _agg_liq = 0.0; _agg_gas = 0.0; _agg_trades = 0; _agg_wins = 0
                for (cid,) in rows:
                    if get_config(f"last_rep_{cid}", "") == hoje:
                        continue
                    u = get_user(cid)
                    if not u or not u.get("wallet"):
                        continue
                    dt_lim = _ciclo_21h_since()  # corte 21h BR (não meia-noite)
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
                        # Mensagem 21h — via design tokens (telegram_design_tokens.py)
                        if _TG_TOKENS:
                            _emoji_res = TG.resultado_win if liq >= 0 else TG.resultado_loss
                            _wr_bar    = winrate_bar(wins, total_t, width=10)
                            msg = (
                                HDR.ciclo_21h()
                                + f"{SEP.linha}\n\n"
                                + f"{_emoji_res}  Líquido: <b>{format_currency(liq, signed=True)}</b>\n"
                                + f"{TG.gas}  Gás Total: <b>{format_currency(gas_t)}</b>\n"
                                + f"{TG.grafico}  Trades: <b>{total_t}</b>  |  Wins: <b>{wins}</b>\n\n"
                                + f"🎯  WinRate: <b>{wr_pct:.0f}%</b>\n"
                                + f"<code>{_wr_bar}</code>\n\n"
                                + f"{SEP.linha}\n"
                                + f"{TG.calendario}  {hoje}"
                                + cta_ocme()
                            )
                        else:
                            filled  = round(wr_pct / 10)
                            _wr_bar = "█" * filled + "░" * (10 - filled)
                            _emoji  = "🟢" if liq >= 0 else "🔴"
                            msg = (
                                f"🌙 <b>RELATÓRIO 21H — WEbdEX</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"{_emoji}  Líquido: <b>${liq:+.2f}</b>\n"
                                f"⛽  Gás Total: <b>${gas_t:.2f}</b>\n"
                                f"📊  Trades: <b>{total_t}</b>  |  Wins: <b>{wins}</b>\n\n"
                                f"🎯  WinRate: <b>{wr_pct:.0f}%</b>\n"
                                f"<code>{_wr_bar}</code>\n\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"🗓️  {hoje}"
                            )
                        send_html(cid, msg)
                        send_logo_photo(cid, f"{'🌙' if not _TG_TOKENS else TG.ciclo_noite} <b>WEbdEX</b> — bom descanso, até amanhã! 🚀")
                        _agg_liq += liq; _agg_gas += gas_t
                        _agg_trades += total_t; _agg_wins += wins
                    set_config(f"last_rep_{cid}", hoje)
                # Relatório protocolo Discord — UMA mensagem por noite (guard de data)
                _discord_21h_key = f"discord_21h_{hoje}"
                _21h_val = get_config(_discord_21h_key, "")
                # "ok" = enviado; "pending:TS" = em andamento (TTL 10 min)
                _21h_skip = _21h_val == "ok"
                if not _21h_skip and _21h_val.startswith("pending:"):
                    try:
                        _21h_ts = int(_21h_val.split(":", 1)[1])
                        _21h_skip = (time.time() - _21h_ts) < 600  # 10 min TTL
                    except (ValueError, IndexError):
                        pass
                if not _21h_skip:
                    try:
                        # Marcar em-progresso com timestamp — TTL 10 min evita deadlock em restart
                        set_config(_discord_21h_key, f"pending:{int(time.time())}")
                        _dt_lim_brt = _ciclo_21h_since()  # corte 21h em BRT
                        # protocol_ops.ts é UTC; _ciclo_21h_since() retorna BRT → converter +3h
                        _dt_lim = (
                            datetime.strptime(_dt_lim_brt, "%Y-%m-%d %H:%M:%S") + timedelta(hours=3)
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        with DB_LOCK:
                            _pr = cursor.execute("""
                                SELECT COUNT(DISTINCT wallet),
                                       COUNT(CASE WHEN profit>0 THEN 1 END),
                                       COUNT(*),
                                       ROUND(SUM(fee_bd),6),
                                       ROUND(SUM(CASE WHEN profit>0 THEN profit ELSE 0 END),4)
                                FROM protocol_ops WHERE ts>=?
                            """, (_dt_lim,)).fetchone()
                            _tvl_row = cursor.execute("""
                                SELECT ROUND(SUM(lp_usdt_supply + lp_loop_supply),2)
                                FROM fl_snapshots WHERE ts = (SELECT MAX(ts) FROM fl_snapshots)
                            """).fetchone()
                            _top5 = cursor.execute("""
                                SELECT wallet,
                                       ROUND(SUM(profit),4),
                                       ROUND(SUM(fee_bd),4)
                                FROM protocol_ops WHERE ts>=?
                                GROUP BY wallet ORDER BY SUM(profit) DESC LIMIT 5
                            """, (_dt_lim,)).fetchall()
                        if not _pr or _pr[0] is None:
                            logger.info("[agendador_21h] Sem ops no ciclo atual — pulando relatório Discord")
                            set_config(_discord_21h_key, "")   # resetar para retry (sem ops)
                            continue
                        _p_traders = int(_pr[0] or 0)
                        _p_wins    = int(_pr[1] or 0)
                        _p_total   = int(_pr[2] or 0)
                        _p_bd      = float(_pr[3] or 0)
                        _p_bruto   = float(_pr[4] or 0)
                        _p_wr      = (_p_wins / _p_total * 100) if _p_total > 0 else 0.0
                        _tvl_usd   = float(_tvl_row[0] or 0) if _tvl_row else 0.0
                        # Confirmar envio Discord — agora é seguro setar "ok"
                        notify_protocolo_relatorio(
                            hoje=hoje,
                            tvl_usd=_tvl_usd,
                            bd_periodo=_p_bd,
                            p_traders=_p_traders,
                            p_wr=_p_wr,
                            p_bruto=_p_bruto,
                            top_traders=_top5,
                            label="Ciclo 21h",
                        )
                        set_config(_discord_21h_key, "ok")

                        # ── SEGUNDO CANAL DISCORD: #webdex-on-chain (resumo compacto) ──
                        try:
                            notify_protocolo_relatorio_onchain(
                                hoje=hoje,
                                tvl_usd=_tvl_usd,
                                bd_periodo=_p_bd,
                                p_traders=_p_traders,
                                p_wr=_p_wr,
                                p_bruto=_p_bruto,
                            )
                        except Exception as _oc_err:
                            logger.error(f"[agendador_21h] Onchain channel falhou: {_oc_err}")

                        # ── BROADCAST TELEGRAM (mesmo modelo) ─────────────────
                        try:
                            _tg_msg = notify_protocolo_relatorio_telegram(
                                hoje=hoje,
                                tvl_usd=_tvl_usd,
                                bd_periodo=_p_bd,
                                p_traders=_p_traders,
                                p_wr=_p_wr,
                                p_bruto=_p_bruto,
                                top_traders=_top5,
                            )
                            with DB_LOCK:
                                _tg_users = cursor.execute(
                                    "SELECT chat_id FROM users WHERE active=1"
                                ).fetchall()
                            _sent_broadcast = 0
                            for (uid,) in _tg_users:
                                send_html(uid, _tg_msg)
                                _sent_broadcast += 1
                            logger.info(f"[agendador_21h] Broadcast Telegram protocolo: {_sent_broadcast}/{len(_tg_users)} users (todos ativos)")
                        except Exception as _tg_err:
                            logger.error(f"[agendador_21h] Broadcast Telegram falhou: {_tg_err}")

                        # Animação bdZinho → #relatório-diário
                        if _animate and _p_total > 0:
                            _ev = "relatorio_win" if _p_bruto >= 0 else "relatorio_loss"
                            _em = "🟢" if _p_bruto >= 0 else "🔴"
                            _pl = f"+${_p_bruto:.2f}" if _p_bruto >= 0 else f"-${abs(_p_bruto):.2f}"
                            _wr_anim = (_p_wins / _p_total * 100) if _p_total > 0 else 0.0
                            _animate(
                                _ev, _WEBHOOK_RELATORIO,
                                title=f"{_em}  RELATÓRIO NOTURNO — WEbdEX PROTOCOL",
                                description=(
                                    f"## {_em} RESULTADO DO DIA\n"
                                    f"💎 **TVL:** `${_tvl_usd:,.0f} USD`\n"
                                    f"📈 **P&L Bruto:** `{_pl}`  ·  🎯 **WR {_wr_anim:.0f}%**\n"
                                    f"👥 **{_p_traders} traders** · 📊 **{_p_total:,} trades**\n"
                                    f"💰 **BD coletado:** `{_p_bd:.4f} BD`\n"
                                    f"🗓️ {hoje}"
                                ),
                                color=0x00FF88 if _p_bruto >= 0 else 0xFF4444,
                            )
                    except Exception as _de:
                        logger.error("[agendador_21h] agendador_21h erro: %s", _de)
                        if get_config(_discord_21h_key, "") != "ok":
                            set_config(_discord_21h_key, "")  # resetar para retry
                time.sleep(70)
        except Exception as _ae:
            logger.warning("[agendador_21h] erro no ciclo: %s", _ae)
        time.sleep(30)

# ==============================================================================
# ⏰ AGENDADOR HORÁRIO — #operações, #swaps e heartbeat #webdex-on-chain
# ==============================================================================

def agendador_horario():
    """Relatórios horários ao vivo → #operações, #swaps, #webdex-on-chain."""
    from webdex_swapbook_notify import get_swap_stats_and_reset
    logger.info("⏰ Agendador horário: Ativo...")
    last_hour = -1

    while True:
        try:
            now = now_br()
            # Dispara a cada 2h (par: 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22)
            is_2h_mark = (now.hour % 2 == 0) and (now.minute < 5)
            if is_2h_mark and now.hour != last_hour:
                last_hour = now.hour
                hora_str  = now.strftime("%H:00")
                two_h_ago = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")

                # ── Operações: query protocol_ops (últimas 2h) ──────────
                with DB_LOCK:
                    rows = cursor.execute(
                        "SELECT COUNT(*) FROM protocol_ops WHERE ts >= ?",
                        (two_h_ago,)
                    ).fetchone()
                total_ops = rows[0] if rows else 0
                notify_operacoes_horario(total_ops, {}, hora_str)

                # ── Swaps: contador em memória ──────────────────────────
                sw = get_swap_stats_and_reset()
                total_sw = sw["create"] + sw["execute"]
                notify_swaps_horario(total_sw, sw["create"], sw["execute"], hora_str)

                # ── Pulso curado + P&L 2h → #webdex-on-chain ───────────
                pulse = get_pulse_stats_and_reset()
                try:
                    with DB_LOCK:
                        pnl_row = cursor.execute(
                            "SELECT SUM(valor) FROM operacoes WHERE data_hora >= ? AND tipo='Trade'",
                            (two_h_ago,)
                        ).fetchone()
                    pnl_2h = float(pnl_row[0] or 0.0) if pnl_row else 0.0
                except Exception:
                    pnl_2h = 0.0
                notify_onchain_heartbeat(
                    total_ops, hora_str,
                    swaps=sw["execute"],
                    webdex_moves=pulse["webdex_moves"],
                    new_holders=pulse["new_holders"],
                    new_wallets=pulse["new_wallets"],
                    pnl=pnl_2h,
                )

                # ── Animações bdZinho ───────────────────────────────────
                if _animate:
                    _animate(
                        "trade_win", _WEBHOOK_OPERACOES,
                        f"⚡ {total_ops:,} OPS NAS ÚLTIMAS 2H!",
                        f"O protocolo WEbdEX operou {total_ops:,} vezes. Imparável! 🚀",
                        0xFF6B35,
                    )
                    if total_sw > 0:
                        _animate(
                            "milestone", _WEBHOOK_SWAPS,
                            f"🔄 {total_sw} SWAPS EM {hora_str}!",
                            f"Create: {sw['create']} · Executados: {sw['execute']} — SwapBook vivo!",
                            0x38BDF8,
                        )
                    # Heartbeat on-chain → #webdex-on-chain (só quando há atividade)
                    if total_ops > 0 and _WEBHOOK_ONCHAIN:
                        _pnl_sign = "📈" if pnl_2h >= 0 else "📉"
                        _animate(
                            "trade_win" if pnl_2h >= 0 else "relatorio_loss",
                            _WEBHOOK_ONCHAIN,
                            f"🔗 PULSO ON-CHAIN — {hora_str}",
                            (
                                f"{_pnl_sign} P&L 2h: `{'+'if pnl_2h>=0 else ''}{pnl_2h:.2f}` USD\n"
                                f"⚡ {total_ops:,} ops · 🔄 {pulse['webdex_moves']} moves WEbdEX\n"
                                f"👛 {pulse['new_wallets']} novas carteiras · "
                                f"👥 {pulse['new_holders']} novos holders"
                            ),
                            0x00FFB2 if pnl_2h >= 0 else 0xFF4444,
                        )

                logger.info(
                    "[agendador_horario] %s — %d ops, %d swaps",
                    hora_str, total_ops, total_sw,
                )

        except Exception as _he:
            logger.warning("[agendador_horario] erro: %s", _he)
        time.sleep(30)


# ==============================================================================
# 💰 CAPITAL SNAPSHOT WORKER
# ==============================================================================
_CAPITAL_SNAP_INTERVAL = 30 * 60  # 30 minutos

# Tokens contados no capital (todos USD-denominados no protocolo WEbdEX)
_CAPITAL_TOKENS = {
    ADDR_USDT0.lower():   {"dec": 6,  "sym": "USDT",   "factor": 1.0},
    ADDR_LPLPUSD.lower(): {"dec": 9,  "sym": "LP-USD",  "factor": 1.0},
    ADDR_LPUSDT0.lower(): {"dec": 6,  "sym": "LP-V5",   "factor": 1.0},
}

# ABI mínima: totalSupply + balanceOf
_ABI_ERC20_BASIC = '[{"inputs":[],"name":"totalSupply","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"}]'
_USDT0_LOWER = ADDR_USDT0.lower()

_lp_price_cache: dict = {}       # lp_addr_lower → price (limpo todo ciclo)
_lp_price_last_known: dict = {}  # lp_addr_lower → último preço válido (persiste entre ciclos)

def _fetch_lp_price_per_unit(w3, lp_addr: str, lp_dec: int) -> float:
    """Busca preço por unidade LP token via DexScreener (sem API key).
    Cacheado por sessão. Fallback: último preço válido conhecido (não usa 1.0).
    """
    key = lp_addr.lower()
    if key in _lp_price_cache:
        return _lp_price_cache[key]
    try:
        import requests as _req
        url = f"https://api.dexscreener.com/latest/dex/tokens/{lp_addr}"
        resp = _req.get(url, timeout=10)
        data = resp.json()
        pairs = data.get("pairs") or []
        # Pega o par com maior liquidez em USD
        best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd") or 0), default=None) if pairs else None
        if best:
            price = float(best.get("priceUsd") or 0)
            if price > 0:
                _lp_price_cache[key] = price
                _lp_price_last_known[key] = price  # salva como último preço válido
                logger.info("💱 LP price (DexScreener): %s = $%.6f/unit", lp_addr[:10], price)
                return price
    except Exception as _e:
        logger.warning("⚠️ LP price DexScreener falhou %s: %s", lp_addr[:10], _e)
    # Fallback: usa último preço válido conhecido (não usa 1.0 que seria errado)
    fallback = _lp_price_last_known.get(key, 0.0)
    if fallback > 0:
        logger.info("💱 LP price fallback (último conhecido): %s = $%.6f/unit", lp_addr[:10], fallback)
    _lp_price_cache[key] = fallback
    return fallback


def _val_balance(w3, st_addr: str, addr_raw: str, bal_raw: int) -> tuple[float, str]:
    """Converte balance on-chain em (valor_usd, symbol).
    - USDT: direto (dec=6)
    - LP tokens: preço Uniswap V2 cacheado × quantidade
    """
    if bal_raw <= 0:
        return 0.0, ""
    if addr_raw == _USDT0_LOWER:
        return bal_raw / 1e6, "USDT"
    tok = _CAPITAL_TOKENS.get(addr_raw)
    if not tok:
        return 0.0, ""
    lp_units = bal_raw / (10 ** tok["dec"])
    price = _fetch_lp_price_per_unit(w3, addr_raw, tok["dec"])
    if price > 0:
        return lp_units * price, tok["sym"]
    # Fallback: usa último preço conhecido ou estimativa (factor=1.0)
    # Nunca retorna 0 — evita que capital_cache deixe de ser escrito
    last = _lp_price_last_known.get(addr_raw.lower())
    if last and last > 0:
        return lp_units * last, tok["sym"]
    return lp_units * tok["factor"], tok["sym"]


def _query_user_capital(w3, wallet: str) -> tuple[float, dict]:
    """Agrega capital de um usuário nos DOIS envs (AG_C_bd e bd_v5).
    Retorna (total_usd, breakdown).
    """
    from webdex_chain import get_contracts
    from webdex_config import CONTRACTS as _CONTRACTS
    total_usd = 0.0
    breakdown: dict = {}
    usr_addr = Web3.to_checksum_address(wallet)
    for env_name in _CONTRACTS:
        try:
            c = get_contracts(env_name, w3)
            mgr_addr = Web3.to_checksum_address(c["addr"]["MANAGER"])
            subs = c["sub"].functions.getSubAccounts(mgr_addr, usr_addr).call()
            for s in subs:
                sid = s[0]
                try:
                    strats = c["sub"].functions.getStrategies(mgr_addr, usr_addr, sid).call()[:25]
                except Exception:
                    continue
                # getBalances returns the SAME total balance per coin regardless of which
                # strategy address is passed. Deduplicate by coin to avoid N×inflation.
                seen_coins: set = set()
                for st in strats:
                    try:
                        bals = c["sub"].functions.getBalances(mgr_addr, usr_addr, sid, st).call()
                    except Exception:
                        continue
                    for b in bals:
                        try:
                            addr_raw = str(b[1]).lower()
                            if addr_raw in seen_coins:
                                continue
                            bal_raw = int(b[0])
                            val, sym = _val_balance(w3, st, addr_raw, bal_raw)
                            if val > 0 and sym:
                                seen_coins.add(addr_raw)
                                total_usd += val
                                breakdown[sym] = breakdown.get(sym, 0.0) + val
                        except Exception:
                            continue
        except Exception:
            continue
    return total_usd, breakdown


def _capital_snapshot_worker():
    """Worker de background: tira snapshot de capital de todos usuários a cada 30min."""
    logger.info("💰 Capital snapshot worker: Ativo...")
    while True:
        _lp_price_cache.clear()  # limpa cache de preços a cada ciclo
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
                    total_usd, breakdown = _query_user_capital(w3, wallet)
                    if total_usd > 1.0:
                        import json as _json
                        ts_now = time.time()
                        with DB_LOCK:
                            conn.execute(
                                "INSERT OR REPLACE INTO capital_cache (chat_id, env, total_usd, breakdown_json, updated_ts) VALUES (?,?,?,?,?)",
                                (int(chat_id), env or "AG_C_bd", total_usd, _json.dumps(breakdown), ts_now)
                            )
                            conn.commit()
                        logger.info("✅ capital_cache: chat_id=%s env=%s total_usd=%.2f breakdown=%s", chat_id, env or "AG_C_bd", total_usd, breakdown)
                        # Salva snapshot histórico para gráfico de Progressão de Capital
                        try:
                            from webdex_handlers.reports import _mybdbook_save_snapshot
                            _usdt0 = float(breakdown.get("USDT", breakdown.get("USDT0", 0.0)))
                            _lp    = float(breakdown.get("LP-USD", breakdown.get("LP-V5", 0.0)))
                            _mybdbook_save_snapshot(int(chat_id), wallet, env or "AG_C_bd", _usdt0, _lp, total_usd)
                        except Exception as _snap_e:
                            logger.debug("capital_snapshot save_snapshot: %s", _snap_e)
                    else:
                        logger.debug("capital_cache sem posição ativa: chat_id=%s env=%s total_usd=%.4f", chat_id, env or "AG_C_bd", total_usd)
                except Exception as _usr_e:
                    logger.warning("❌ capital_cache falhou: chat_id=%s erro=%s", chat_id, _usr_e)
        except Exception as _we:
            logger.warning(f"capital_snapshot_worker erro: {_we}")
        time.sleep(_CAPITAL_SNAP_INTERVAL)

# ==============================================================================
# 🔍 PROTOCOL OPS SYNC WORKER — backfill histórico de TODOS os traders
# ==============================================================================
_PROTO_SYNC_BATCH        = 2000    # blocos por lote (máx Alchemy getLogs)
_PROTO_SYNC_SLEEP        = 1800    # 30min entre ciclos quando em dia
_PROTO_BACKFILL_SLEEP    = 0.3     # 300ms entre batches durante backfill histórico
_PROTO_BACKFILL_THRESHOLD = 200_000  # gap > 200k blocos → modo backfill acelerado

def _protocol_ops_sync_worker():
    """
    Worker de background: sincroniza TODOS os eventos OpenPosition de ambos
    os ambientes para a tabela protocol_ops, independente de registro no bot.
    - 1ª execução: começa do bloco de DEPLOY do contrato (histórico completo)
    - Backfill acelerado: batches de 2000 blocos, sleep 300ms (não bloqueia bot)
    - Modo incremental: quando em dia, ciclo a cada 30min
    - Reset automático: se proto_genesis_done_* não setado, reinicia do deploy
    """
    from webdex_config import CONTRACTS, Web3 as _W3, logger as _log
    from webdex_chain import rpc_pool, TOPIC_OPENPOSITION
    from webdex_bot_core import get_token_meta, formatar_moeda
    from webdex_db import DB_LOCK, conn, get_config, set_config
    from datetime import datetime

    _log.info("🔍 Protocol ops sync worker: Ativo (histórico completo desde deploy)...")
    time.sleep(90)  # aguarda vigia e chain_cache inicializarem

    from webdex_config import CONTRACTS_DEPLOY_BLOCK

    while True:
        try:
            curr_block = int(web3.eth.block_number)

            for env_key, c_data in CONTRACTS.items():
                payments_addr  = _W3.to_checksum_address(c_data["PAYMENTS"])
                config_key     = f"proto_sync_block_{env_key}"
                genesis_key    = f"proto_genesis_done_{env_key}"
                deploy_block   = CONTRACTS_DEPLOY_BLOCK.get(env_key, 1)

                last_synced = int(get_config(config_key, "0") or "0")

                # Primeiro run OU genesis não concluído → começa do deploy
                genesis_done = get_config(genesis_key, "0")
                if genesis_done != "1":
                    if last_synced == 0:
                        # Primeira execução — inicia backfill do bloco de deploy
                        last_synced = deploy_block - 1
                        set_config(config_key, str(last_synced))
                        _log.info(
                            "[proto_sync] %s: iniciando backfill desde deploy bloco %d "
                            "(curr=%d, gap=%d blocos / ~%.1f dias)",
                            env_key, deploy_block, curr_block,
                            curr_block - deploy_block,
                            (curr_block - deploy_block) * 2.4 / 86400
                        )
                    # else: backfill em progresso — continua de last_synced sem resetar

                if last_synced >= curr_block:
                    # Histórico 100% completo — marca genesis como done
                    if genesis_done != "1":
                        set_config(genesis_key, "1")
                        _log.info("[proto_sync] %s: ✅ genesis completo — histórico 100%% indexado", env_key)
                    continue

                gap = curr_block - last_synced
                # Modo backfill acelerado quando gap > 200k blocos
                in_backfill = gap > _PROTO_BACKFILL_THRESHOLD
                batch_size  = _PROTO_SYNC_BATCH          # 2000 blocos/batch
                batch_sleep = _PROTO_BACKFILL_SLEEP if in_backfill else 1.0

                # Processa até 200 batches por ciclo (não bloqueia outras threads)
                from_block = last_synced + 1
                to_block   = min(curr_block, from_block + batch_size * 200)
                saved = 0

                if in_backfill and from_block % 100_000 == 0:
                    pct = (from_block - deploy_block) / max(1, curr_block - deploy_block) * 100
                    _log.info(
                        "[proto_sync] %s backfill: bloco %d / %d (%.1f%% | gap=%d blocos)",
                        env_key, from_block, curr_block, pct, gap
                    )

                b = from_block
                while b <= to_block:
                    end = min(b + batch_size - 1, to_block)
                    try:
                        logs = rpc_pool.get_logs({
                            "fromBlock": hex(b),
                            "toBlock":   hex(end),
                            "address":   payments_addr,
                            "topics":    [TOPIC_OPENPOSITION],
                        })
                        for log in logs:
                            try:
                                tx       = str(log["transactionHash"].hex()) if hasattr(log["transactionHash"], "hex") else str(log["transactionHash"])
                                log_idx  = int(log["logIndex"])
                                bloco    = int(log["blockNumber"])
                                from webdex_chain import CONTRACTS_A, CONTRACTS_B
                                _c = CONTRACTS_B if env_key == "bd_v5" else CONTRACTS_A
                                evt  = _c["payments"].events.OpenPosition().process_log(log)
                                args = evt["args"]
                                uw   = str(args["user"]).lower().strip()
                                meta = get_token_meta(args["details"]["coin"])
                                profit_usd  = float(int(args["details"].get("profit", 0))) / (10 ** meta["dec"])
                                fee_bd      = float(int(args["details"].get("fee", 0))) / 1e9
                                gas_pol     = float(int(args["details"].get("gas", 0))) / 1e18
                                old_bal_usd = float(int(args["details"].get("oldBalance", 0))) / (10 ** meta["dec"])
                                bot_id      = str(args["details"].get("botId") or "").strip()
                                sub_conta   = str(args.get("accountId", ""))
                                coin_sym    = str(meta["sym"])
                                try:
                                    from webdex_db import get_block_ts
                                    bts = get_block_ts(bloco)
                                    ts_str = datetime.utcfromtimestamp(bts).strftime("%Y-%m-%d %H:%M:%S") if bts else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                                except Exception:
                                    ts_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                                with DB_LOCK:
                                    conn.execute("""
                                        INSERT OR IGNORE INTO protocol_ops
                                            (hash, log_index, ts, bloco, env, wallet, sub_conta,
                                             bot_id, coin, profit, fee_bd, gas_pol, old_balance)
                                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                                    """, (tx, log_idx, ts_str, bloco, env_key, uw, sub_conta,
                                          bot_id, coin_sym, profit_usd, fee_bd, gas_pol, old_bal_usd))
                                    conn.commit()
                                saved += 1
                            except Exception as _le:
                                logger.debug("[proto_sync] decode err: %s", _le)
                    except Exception as _be:
                        logger.debug("[proto_sync] getLogs err bloco %d-%d: %s", b, end, _be)
                        time.sleep(2)
                    b = end + 1
                    time.sleep(batch_sleep)

                set_config(config_key, str(to_block))
                if saved:
                    _log.info("[proto_sync] %s: +%d eventos | bloco %d | gap=%d", env_key, saved, to_block, curr_block - to_block)

        except Exception as _e:
            logger.warning("[protocol_ops_sync_worker] erro: %s", _e)

        # Em backfill: reinicia imediatamente. Em dia: espera 30min
        try:
            curr_b = int(web3.eth.block_number)
            any_backfill = any(
                (curr_b - int(get_config(f"proto_sync_block_{ek}", "0") or "0")) > _PROTO_BACKFILL_THRESHOLD
                for ek in CONTRACTS
            )
            if not any_backfill:
                time.sleep(_PROTO_SYNC_SLEEP)
            else:
                time.sleep(5)  # pausa mínima entre ciclos de backfill
        except Exception:
            time.sleep(_PROTO_SYNC_SLEEP)


# ==============================================================================
# 📸 FL SNAPSHOT WORKER — TVL automático a cada 30min
# ==============================================================================
_FL_SNAP_INTERVAL = 1800  # 30 minutos

def _fl_snapshot_worker():
    """
    Worker de background: salva snapshot de TVL (fl_snapshots) a cada 30min.
    Alimenta o cálculo de Lucro do Protocolo (delta TVL ao longo do tempo).
    """
    logger.info("📸 FL Snapshot worker: Ativo...")
    time.sleep(60)  # aguarda sistema inicializar
    while True:
        try:
            from webdex_config import CONTRACTS, RPC_URL, RPC_CAPITAL
            from webdex_chain import web3_for_rpc, obter_preco_pol
            from webdex_db import now_br

            w3 = web3_for_rpc(RPC_CAPITAL, timeout=10)
            pol_price = obter_preco_pol()
            ts_now = now_br().strftime("%Y-%m-%d %H:%M:%S")

            _ABI_ERC20 = '[{"inputs":[],"name":"totalSupply","outputs":[{"type":"uint256"}],"type":"function"},{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"type":"uint256"}],"type":"function"}]'
            import json as _json

            for env_key, c_data in CONTRACTS.items():
                try:
                    lp_usdt_addr = c_data.get("LP_USDT", "")
                    lp_loop_addr = c_data.get("LP_LOOP", "")
                    sub_addr     = c_data.get("SUBACCOUNTS", "")
                    mgr_addr     = c_data.get("MANAGER", "")

                    from webdex_config import ADDR_USDT0, ADDR_LPLPUSD
                    from web3 import Web3 as _W3

                    _erc20 = lambda a: w3.eth.contract(
                        address=_W3.to_checksum_address(a),
                        abi=_json.loads(_ABI_ERC20)
                    )

                    lp_usdt_supply = float(_erc20(lp_usdt_addr).functions.totalSupply().call()) / 1e6  if lp_usdt_addr else 0.0
                    lp_loop_supply = float(_erc20(lp_loop_addr).functions.totalSupply().call()) / 1e9  if lp_loop_addr else 0.0
                    liq_usdt       = float(_erc20(ADDR_USDT0).functions.balanceOf(_W3.to_checksum_address(sub_addr)).call()) / 1e6  if sub_addr else 0.0
                    liq_loop       = float(_erc20(ADDR_LPLPUSD).functions.balanceOf(_W3.to_checksum_address(sub_addr)).call()) / 1e9 if sub_addr else 0.0
                    gas_pol        = float(w3.from_wei(w3.eth.get_balance(_W3.to_checksum_address(mgr_addr)), "ether")) if mgr_addr else 0.0

                    # LP price via DexScreener (reutiliza lógica existente)
                    try:
                        lp_usdt_price = _fetch_lp_price_per_unit(w3, lp_usdt_addr, 6)
                        lp_loop_price = _fetch_lp_price_per_unit(w3, lp_loop_addr, 9)
                    except Exception as _lpe:
                        logger.warning("[fl_snap] LP price fetch falhou: %s", _lpe)
                        # usa último preço válido ou 0.0 (não usa 1.0)
                        lp_usdt_price = _lp_price_last_known.get((lp_usdt_addr or "").lower(), 0.0)
                        lp_loop_price = _lp_price_last_known.get((lp_loop_addr or "").lower(), 0.0)

                    total_usd = (
                        liq_usdt +
                        liq_loop * lp_loop_price +
                        lp_usdt_supply * lp_usdt_price +
                        gas_pol * pol_price
                    )

                    with DB_LOCK:
                        conn.execute(
                            """INSERT INTO fl_snapshots
                               (ts, env, lp_usdt_supply, lp_loop_supply, liq_usdt, liq_loop, gas_pol, pol_price, total_usd)
                               VALUES (?,?,?,?,?,?,?,?,?)""",
                            (ts_now, env_key, lp_usdt_supply, lp_loop_supply,
                             liq_usdt, liq_loop, gas_pol, pol_price, total_usd)
                        )
                        conn.commit()

                    logger.info("[fl_snap] %s total_usd=%.2f liq_usdt=%.2f gas_pol=%.2f",
                                env_key, total_usd, liq_usdt, gas_pol)
                except Exception as _env_e:
                    logger.warning("[fl_snap] erro env=%s: %s", env_key, _env_e)

        except Exception as _e:
            logger.warning("[fl_snapshot_worker] erro geral: %s", _e)

        time.sleep(_FL_SNAP_INTERVAL)


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
                    total_usd, breakdown = _query_user_capital(w3, wallet)
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
                except Exception as _cap_e:
                    logger.debug("[capital_refresh] falhou chat_id=%s: %s", chat_id, _cap_e)
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
    except Exception as _ffe:
        logger.debug("[update_user_funnel] erro chat_id=%s: %s", chat_id, _ffe)

def _funnel_worker():
    """Worker: atualiza inatividade do funil a cada 10min.
    - Marca ativos sem trades há 7d como 'inativo'
    - Reativa inativos que voltaram a operar nas últimas 48h
    """
    logger.info("📊 Funnel worker: Ativo...")
    while True:
        try:
            now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            threshold_7d  = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            threshold_48h = (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
            with DB_LOCK:
                # 1. Marca ativos sem trades há 7d como inativo
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

                # 2. Reativa inativos que voltaram a operar nas últimas 48h
                inativos = conn.execute(
                    "SELECT chat_id FROM user_funnel WHERE stage='inativo'"
                ).fetchall()
                for (cid_in,) in inativos:
                    wal_row = conn.execute(
                        "SELECT wallet FROM users WHERE chat_id=?", (str(cid_in),)
                    ).fetchone()
                    if not wal_row or not wal_row[0]:
                        continue
                    recent = cursor.execute("""
                        SELECT COUNT(*), MAX(o.data_hora) FROM operacoes o
                        JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                        WHERE LOWER(ow.wallet)=LOWER(?) AND o.tipo='Trade' AND o.data_hora >= ?
                    """, (wal_row[0], threshold_48h)).fetchone()
                    if recent and int(recent[0] or 0) > 0:
                        conn.execute(
                            "UPDATE user_funnel SET stage='ativo', last_trade=?, inactive_days=0, updated_at=? WHERE chat_id=?",
                            (recent[1], now_s, str(cid_in))
                        )
                        logger.info("[funnel] reativado: chat_id=%s last_trade=%s", cid_in, recent[1])

                conn.commit()
        except Exception as _fe:
            logger.debug("[funnel_worker] erro: %s", _fe)
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
                    except Exception as _rpc_e:
                        logger.debug("[inactivity] getLogs falhou env=%s: %s", env_key, _rpc_e)
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
                        except Exception as _send_e:
                            logger.debug("[inactivity] send_html falhou aid=%s: %s", aid, _send_e)
            except Exception as _inner_e:
                logger.debug("[inactivity] erro verificação chain: %s", _inner_e)
            time.sleep(check_min * 60)
        except Exception as _outer_e:
            logger.warning("[inactivity_auto_loop] erro: %s", _outer_e)
        time.sleep(check_min * 60 if 'check_min' in dir() else 600)
