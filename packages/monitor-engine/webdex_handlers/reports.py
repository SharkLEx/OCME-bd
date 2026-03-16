from __future__ import annotations
# ==============================================================================
# webdex_handlers/reports.py — WEbdEX Monitor Engine
# mybdBook capital engine + performance reports + bot handlers
# Linhas fonte: ~5767-5809 (ABIs/constantes LP), ~8012-8915 (mybdBook)
# ==============================================================================

import os
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Any

import requests

from webdex_config import (
    logger, Web3,
    ADDR_USDT0, ADDR_LPLPUSD, ADDR_LPUSDT0,
    RPC_CAPITAL, CONTRACTS,
    OPENAI_MODEL,
)
from webdex_db import (
    DB_LOCK, conn, cursor, now_br,
    period_to_hours,
    _ciclo_21h_since, _ciclo_21h_label,
)
from webdex_chain import web3_for_rpc, get_contracts
from telebot import types as _tg_types
from webdex_bot_core import bot, send_html, esc, barra_progresso

# ==============================================================================
# 🔧 HELPER — PERIOD
# ==============================================================================

def _period_since(p: str) -> str:
    """Retorna o datetime string de início do período selecionado."""
    p = (p or "ciclo").lower().strip()
    if p == "ciclo":
        return _ciclo_21h_since()
    hours = period_to_hours(p)
    return (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


def _period_label(p: str) -> str:
    """Label legível para exibição no Telegram."""
    p = (p or "ciclo").lower().strip()
    if p == "ciclo":
        return _ciclo_21h_label()
    return p.upper()


# ==============================================================================
# 📐 MAX DRAWDOWN (duplicado aqui para uso local, sem dep circular com user.py)
# ==============================================================================

def _max_drawdown(equity: list) -> float:
    if not equity:
        return 0.0
    peak = equity[0]
    mdd  = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = peak - v
        if dd > mdd:
            mdd = dd
    return mdd


# ==============================================================================
# 🔩 LP ABIs & CONSTANTES
# ==============================================================================

_ERC20_MIN_ABI = json.loads('[{"inputs":[],"name":"totalSupply","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"}]')

# ABI mínima para LP Uniswap V2: getReserves + totalSupply + balanceOf
_ABI_LP_V2 = json.loads('[{"inputs":[],"name":"getReserves","outputs":[{"name":"reserve0","type":"uint128"},{"name":"reserve1","type":"uint128"},{"name":"blockTimestampLast","type":"uint32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"totalSupply","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"}]')

# LP: reserva0 = USDT (dec=6 para AG_C_bd, dec=6 para bd_v5)
# LP-USD (LPLPUSD): stable+stable, reserve0~USDT dec=6
# LP-V5  (LPUSDT0): stable+stable, reserve0~USDT dec=6
_LP_USDT_RESERVE_DEC = {
    "0xc4cf5093676e8a61404f51bc6ceaec5279ce8645": 6,  # LP-USD (LPLPUSD)
    "0x238966212e0446c04a225343daafb3c3a7d4f37c": 6,  # LP-V5  (LPUSDT0)
    "0xfb2e2ff7b51c2bcaf58619a55e7d2ff88cfd8aca": 6,  # LP-USDT bd_v5
    "0xb56032d0b576472b3f0f1e4747f488769de2b00b": 6,  # LP-LOOP bd_v5
    "0xc3adc8b72b1c3f208e5d1614cdf87fdd93762812": 6,  # LP-LOOP AG_C_bd
}

# ── Tokens de liquidez (base de capital — iguais nos dois ambientes) ──────────
_ADDR_USDT  = (os.getenv("TOKEN_USDT_ADDRESS") or ADDR_USDT0).strip()
_ADDR_LOOP  = (os.getenv("TOKEN_LOOP_ADDRESS") or ADDR_LPLPUSD).strip()
_DEC_USDT   = 6
_DEC_LOOP   = 9
_DEC_LP_USDT = 6
_DEC_LP_LOOP = 9


# ==============================================================================
# 💰 LP FAIR VALUE
# ==============================================================================

def _lp_fair_value_usd(lp_addr: str, user_lp_balance: float, lp_dec: int,
                        w3: Web3, timeout: int = 6) -> float:
    """
    Valor justo em USD de posição LP — Uniswap V2.

    Invariante AMM: em qualquer pool balanceado, ambos os lados valem igual em USD.
    Logo: pool_total_usd = reserve0_usdt * 2
    Usamos APENAS reserve0 (USDT/USDT0, dec=6) e multiplicamos por 2.
    NÃO usamos reserve1: pode ser LOOP (dec=9, preco != 1 USD) — infla o calculo.

    Exemplo: Pool USDT/LOOP com reserve0=9000 USDT
      pool_usd = 9000 * 2 = 18000
      user_share = user_lp / total_supply
      user_usd = user_share * 18000  ~= 8818 (se share ~49%)
    """
    try:
        lp_c = w3.eth.contract(
            address=Web3.to_checksum_address(lp_addr),
            abi=_ABI_LP_V2
        )
        total_supply_raw = lp_c.functions.totalSupply().call()
        if total_supply_raw <= 0:
            return 0.0

        reserves = lp_c.functions.getReserves().call()

        # reserve0 = USDT/USDT0 (dec=6 — stablecoin real)
        # reserve1 = LOOP ou outro token — IGNORADO (dec e preco diferentes)
        reserve0_usd = float(reserves[0]) / 1_000_000  # dec=6 USDT fixo

        # Invariante AMM: total_pool_usd = reserve0_usd * 2
        pool_total_usd = reserve0_usd * 2.0

        # Share do usuario no pool
        total_supply = float(total_supply_raw) / (10 ** lp_dec)
        if total_supply <= 0:
            return 0.0

        share = user_lp_balance / total_supply
        return share * pool_total_usd

    except Exception:
        return 0.0  # sem fallback para nao inflar


# ==============================================================================
# 🔗 CAPITAL RPC — OPÇÃO A (on-demand com timeout)
# ==============================================================================

def _mybdbook_fetch_capital_rpc(wallet: str, env: str, rpc: str = "") -> dict:
    """
    Wrapper com hard timeout NÃO-BLOQUEANTE para capital on-chain.

    Fix crítico: ThreadPoolExecutor com `with` travava o __exit__ esperando
    a thread terminar mesmo após timeout, causando gaps de blocos no vigia.
    Solução: executor sem context manager + future.cancel() explícito.
    O worker interno usa requests com timeout curto para não acumular threads.
    """
    import concurrent.futures as _cf
    _EMPTY = {"ok": False, "total_usd": 0.0, "usdt0": 0.0, "lp_fair": 0.0,
              "breakdown": {}, "ts": "", "error": "timeout"}
    _ex = _cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix="cap_rpc")
    try:
        _fut = _ex.submit(_mybdbook_fetch_capital_inner, wallet, env, rpc)
        try:
            return _fut.result(timeout=15)
        except _cf.TimeoutError:
            _fut.cancel()
            logger.warning(f"mybdBook capital timeout wallet={wallet[:10]}")
            return _EMPTY
    except Exception as _e:
        logger.warning(f"mybdBook capital erro: {_e}")
        return dict(_EMPTY, error=str(_e))
    finally:
        # shutdown(wait=False): libera imediatamente sem bloquear
        _ex.shutdown(wait=False)


def _mybdbook_fetch_capital_inner(wallet: str, env: str, rpc: str = "") -> dict:
    """Implementacao real — chamada pelo wrapper com timeout.
    Itera TODOS os envs em CONTRACTS (bd_v5 + AG_C_bd) para agregar capital real,
    igual ao _query_user_capital do worker. Evita sub-total de env único.
    """
    try:
        from webdex_config import CONTRACTS as _CONTRACTS
        w3_user = web3_for_rpc(rpc or RPC_CAPITAL, timeout=12)
        usr = Web3.to_checksum_address(wallet)

        usdt0_total = 0.0
        lp_total    = 0.0
        breakdown: dict = {}

        _BASE_LP_ADDRS = {
            ADDR_LPLPUSD.lower(): ("LP-USD", 9),
            ADDR_LPUSDT0.lower(): ("LP-V5",  6),
        }

        for env_name in _CONTRACTS:
            try:
                c   = get_contracts(env_name, w3_user)
                mgr = Web3.to_checksum_address(c["addr"]["MANAGER"])

                # LPs específicos do ambiente
                _LP_ADDRS = dict(_BASE_LP_ADDRS)
                for lp_key in ["LP_USDT", "LP_LOOP"]:
                    lp_a = (c["addr"].get(lp_key) or "").lower()
                    if lp_a and lp_a not in _LP_ADDRS:
                        _LP_ADDRS[lp_a] = (lp_key.replace("_", "-"), 6)

                subs = c["sub"].functions.getSubAccounts(mgr, usr).call()[:40]

                for s in subs:
                    sid = s[0]
                    try:
                        strats = c["sub"].functions.getStrategies(mgr, usr, sid).call()[:25]
                    except Exception:
                        continue

                    seen_coins: set = set()  # dedup por sub — evita N× inflação por estratégia
                    for st in strats:
                        try:
                            bals = c["sub"].functions.getBalances(mgr, usr, sid, st).call()
                        except Exception:
                            continue

                        for b in bals:
                            try:
                                addr_raw = str(b[1]).lower()
                                if addr_raw in seen_coins:
                                    continue
                                bal_raw = int(b[0])
                                dec_raw = int(b[2])
                                if bal_raw <= 0:
                                    continue

                                if addr_raw == ADDR_USDT0.lower():
                                    val = bal_raw / (10 ** dec_raw)
                                    usdt0_total += val
                                    breakdown["USDT"] = breakdown.get("USDT", 0.0) + val
                                    seen_coins.add(addr_raw)

                                elif addr_raw in _LP_ADDRS:
                                    sym, lp_dec = _LP_ADDRS[addr_raw]
                                    lp_bal = bal_raw / (10 ** lp_dec)
                                    lp_usd = _lp_fair_value_usd(str(b[1]), lp_bal, lp_dec, w3_user)
                                    lp_total += lp_usd
                                    breakdown[sym] = breakdown.get(sym, 0.0) + lp_usd
                                    seen_coins.add(addr_raw)

                            except Exception:
                                continue
            except Exception:
                continue

        total_usd = usdt0_total + lp_total
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "ok": True, "total_usd": total_usd,
            "usdt0": usdt0_total, "lp_fair": lp_total,
            "breakdown": breakdown, "ts": ts, "error": None
        }

    except Exception as exc:
        return {"ok": False, "total_usd": 0.0, "usdt0": 0.0, "lp_fair": 0.0,
                "breakdown": {}, "ts": "", "error": str(exc)}


# ==============================================================================
# 💾 CAPITAL SNAPSHOTS — OPÇÃO B
# ==============================================================================

def _mybdbook_save_snapshot(chat_id: int, wallet: str, env: str,
                             usdt0: float, lp_usd: float, total: float):
    """Salva snapshot de capital do usuário para o gráfico de crescimento."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with DB_LOCK:
            conn.execute(
                "INSERT INTO user_capital_snapshots"
                "(chat_id, wallet, env, ts, usdt0_usd, lp_usd, total_usd) "
                "VALUES (?,?,?,?,?,?,?)",
                (chat_id, wallet.lower(), env, ts, usdt0, lp_usd, total)
            )
            conn.commit()
    except Exception as _e:
        logger.error("[mybdbook] save_snapshot failed (chat_id=%s wallet=%s): %s", chat_id, wallet, _e)


def _mybdbook_get_capital_series(wallet: str, limit: int = 60) -> list:
    """
    Opção B: Recupera série histórica de capital do usuário.
    Retorna lista de (ts, total_usd) ordenada por data.
    """
    try:
        with DB_LOCK:
            rows = conn.execute(
                "SELECT ts, total_usd FROM user_capital_snapshots "
                "WHERE LOWER(wallet)=? ORDER BY ts ASC LIMIT ?",
                (wallet.lower(), limit)
            ).fetchall()
        return [(r[0], float(r[1])) for r in rows if float(r[1] or 0) > 0]
    except Exception as _e:
        logger.error("[mybdbook] get_capital_series failed (wallet=%s): %s", wallet, _e)
        return []


# ==============================================================================
# 📊 MYBDBOOK CHART
# ==============================================================================

def _mybdbook_generate_chart_png(
        wallet: str, wallet_label: str, capital_series: list,
        equity_series: list, label: str = "") -> bytes | None:
    """
    Gera gráfico PNG com matplotlib (sem display):
    - Linha azul: capital total ao longo do tempo (snapshots)
    - Linha verde/vermelha: equity curve de P&L do período
    Retorna bytes do PNG ou None se falhar.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # sem display
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.patches import FancyBboxPatch
        import io as _io

        fig, axes = plt.subplots(
            1 + (1 if equity_series else 0),
            1, figsize=(10, 6 if equity_series else 4),
            facecolor="#0d1117"
        )
        if not hasattr(axes, "__len__"):
            axes = [axes]

        # ── Painel 1: Capital total (snapshots) ──────────────────────────────
        ax1 = axes[0]
        ax1.set_facecolor("#0d1117")
        ax1.tick_params(colors="#8b949e", labelsize=9)
        ax1.spines[:].set_color("#21262d")

        if capital_series:
            import datetime as _dt
            xs = [_dt.datetime.strptime(t, "%Y-%m-%d %H:%M:%S") for t, _ in capital_series]
            ys = [v for _, v in capital_series]
            color = "#58a6ff"
            ax1.fill_between(xs, ys, alpha=0.15, color=color)
            ax1.plot(xs, ys, color=color, linewidth=2, marker="o",
                     markersize=4, markerfacecolor=color)
            ax1.set_ylabel("Capital USD", color="#8b949e", fontsize=9)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=8)
            # Anotar último valor
            if ys:
                ax1.annotate(f"${ys[-1]:,.2f}",
                             xy=(xs[-1], ys[-1]),
                             xytext=(8, 4), textcoords="offset points",
                             color="#f0f6fc", fontsize=9, fontweight="bold")
        else:
            ax1.text(0.5, 0.5,
                     "Sem snapshots de capital\n(abra mybdBook algumas vezes para acumular)",
                     ha="center", va="center", transform=ax1.transAxes,
                     color="#8b949e", fontsize=10)

        title = f"mybdBook WEbdEX | {wallet_label}"
        if label:
            title += f"  |  {label}"
        ax1.set_title(title, color="#f0f6fc", fontsize=11, fontweight="bold", pad=10)

        # ── Painel 2: Equity curve P&L ────────────────────────────────────────
        if equity_series and len(axes) > 1:
            ax2 = axes[1]
            ax2.set_facecolor("#0d1117")
            ax2.tick_params(colors="#8b949e", labelsize=9)
            ax2.spines[:].set_color("#21262d")

            ys2 = list(equity_series)
            xs2  = list(range(len(ys2)))
            pos  = [max(0, v) for v in ys2]
            neg  = [min(0, v) for v in ys2]

            ax2.fill_between(xs2, pos, alpha=0.25, color="#3fb950", label="Positivo")
            ax2.fill_between(xs2, neg, alpha=0.25, color="#f85149", label="Negativo")
            ax2.plot(xs2, ys2,
                     color="#3fb950" if ys2[-1] >= 0 else "#f85149",
                     linewidth=1.5)
            ax2.axhline(0, color="#21262d", linewidth=1, linestyle="--")
            ax2.set_ylabel("P&L USD", color="#8b949e", fontsize=9)
            ax2.set_xlabel("Trades", color="#8b949e", fontsize=9)

            liq_final = ys2[-1]
            ax2.annotate(f"{liq_final:+.2f}",
                         xy=(xs2[-1], liq_final),
                         xytext=(6, 4), textcoords="offset points",
                         color="#f0f6fc", fontsize=9, fontweight="bold")

        plt.tight_layout(pad=1.5)

        buf = _io.BytesIO()
        fig.savefig(buf, format="png", dpi=120,
                    bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    except Exception as exc:
        logger.warning(f"mybdBook chart error: {exc}")
        return None


# ==============================================================================
# 📈 MYBDBOOK DATA — USUÁRIO & ADM
# ==============================================================================

def _myfxbook_user_data(wallet: str, periodo: str = "ciclo",
                        chat_id: int = 0, env: str = "", rpc: str = "") -> dict:
    """
    Coleta dados de performance do usuário para o mybdBook.
    Capital: Opção A (RPC real on-demand) com fallback para cache.
    Histórico: Opção B (user_capital_snapshots por wallet).
    """
    since  = _period_since(periodo)
    label  = _period_label(periodo)

    with DB_LOCK:
        _c = conn.cursor()

        # Trades do período (filtrado por wallet)
        rows = _c.execute("""
            SELECT o.data_hora, o.valor, o.gas_usd, o.sub_conta, o.ambiente
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=?
            ORDER BY o.data_hora ASC
        """, (since, wallet)).fetchall()

        # Último capital no cache (fallback rápido)
        cap_row = _c.execute(
            "SELECT total_usd, breakdown_json, env FROM capital_cache WHERE chat_id="
            "(SELECT chat_id FROM users WHERE LOWER(wallet)=? LIMIT 1)",
            (wallet.lower(),)
        ).fetchone()

        # Série histórica de capital POR WALLET (para gráfico de crescimento)
        cap_series_rows = _c.execute(
            "SELECT ts, total_usd FROM user_capital_snapshots "
            "WHERE LOWER(wallet)=? ORDER BY ts ASC LIMIT 90",
            (wallet.lower(),)
        ).fetchall()

        # env e chat_id do usuário se não passados
        if not env or not chat_id:
            u_row = _c.execute(
                "SELECT chat_id, env, rpc FROM users WHERE LOWER(wallet)=? LIMIT 1",
                (wallet.lower(),)
            ).fetchone()
            if u_row:
                chat_id = chat_id or int(u_row[0] or 0)
                env     = env or str(u_row[1] or "")
                rpc     = rpc or str(u_row[2] or "")

    # ── Capital: usa cache do worker (atualizado a cada 30min via _capital_snapshot_worker)
    # O fetch on-demand foi removido: _mybdbook_fetch_capital_inner usa cálculo diferente
    # do worker (_val_balance vs dec_raw direto) e retorna valores incorretos para LP.
    # O worker agrega TODOS os envs corretamente — é a fonte de verdade para capital.
    capital   = 0.0
    cap_usdt0 = 0.0
    cap_lp    = 0.0
    cap_source = "cache"

    if cap_row:
        try:
            import json as _jc
            _cached = float(cap_row[0] or 0)
            _bdj    = _jc.loads(cap_row[1] or "{}")
            _bdj_sum = sum(float(v) for v in _bdj.values() if float(v or 0) > 0)
            # Usa o maior entre total_usd e soma do breakdown (proteção contra corrupção)
            capital   = max(_cached, _bdj_sum)
            cap_usdt0 = float(_bdj.get("USDT", _bdj.get("USDT0", 0.0)))
            cap_lp    = float(_bdj.get("LP-USD", _bdj.get("LP-V5", 0.0)))
            if capital <= 0:
                capital = cap_usdt0 + cap_lp
            cap_source = "cache"
        except Exception as _e:
            logger.error("[mybdbook] capital_cache read failed: %s", _e)

    # Série histórica de capital (para gráfico)
    cap_series = [(r[0], float(r[1])) for r in cap_series_rows if float(r[1] or 0) > 0]
    snaps = []  # mantido por compatibilidade

    if not rows:
        return {"ok": False, "label": label, "since": since, "capital": capital}

    valores   = [float(r[1] or 0) for r in rows]
    gases     = [float(r[2] or 0) for r in rows]
    liquidos  = [v - g for v, g in zip(valores, gases)]

    bruto      = sum(valores)
    gas_total  = sum(gases)
    liq_total  = sum(liquidos)
    wins       = sum(1 for x in liquidos if x > 0)
    losses     = sum(1 for x in liquidos if x < 0)
    total_t    = len(liquidos)
    winrate    = wins / total_t * 100 if total_t else 0
    expectancy = liq_total / total_t if total_t else 0

    # MDD na equity curve
    equity, acc = [], 0.0
    for liq in liquidos:
        acc += liq
        equity.append(acc)
    mdd = _max_drawdown(equity) if equity else 0.0

    # Profit factor
    g_sum = sum(x for x in liquidos if x > 0)
    l_sum = abs(sum(x for x in liquidos if x < 0))
    pf    = g_sum / l_sum if l_sum > 0 else float("inf")

    # ROI
    roi   = (liq_total / capital * 100) if capital > 0 else 0.0

    # Calmar Ratio — ROI anualizado / MDD%
    # Usa horas do período para anualizacao; mínimo de 5 trades para ser significativo
    _period_hours = period_to_hours(periodo) if periodo != "ciclo" else 21
    _roi_annual   = roi * (8760.0 / _period_hours) if _period_hours > 0 else 0.0
    _mdd_pct      = (mdd / capital * 100) if (capital > 0 and mdd > 0) else 0.0
    calmar        = _roi_annual / _mdd_pct if (_mdd_pct > 0 and total_t >= 5) else 0.0

    # Melhor / pior trade
    best  = max(liquidos)
    worst = min(liquidos)

    # Subs distintas
    subs = len(set(r[3] for r in rows))

    # Por ambiente
    by_env: dict = {}
    for dh, v, g, sub, amb in rows:
        k = str(amb or "?")
        if k not in by_env:
            by_env[k] = {"trades": 0, "liq": 0.0}
        by_env[k]["trades"] += 1
        by_env[k]["liq"]    += float(v or 0) - float(g or 0)

    return {
        "ok": True, "label": label, "since": since,
        "total_t": total_t, "wins": wins, "losses": losses,
        "winrate": winrate, "bruto": bruto, "gas": gas_total,
        "liq": liq_total, "roi": roi, "capital": capital,
        "cap_usdt0": cap_usdt0, "cap_lp": cap_lp, "cap_source": cap_source,
        "calmar": calmar, "mdd": mdd, "pf": pf, "expectancy": expectancy,
        "best": best, "worst": worst, "subs": subs,
        "by_env": by_env, "equity": equity, "snaps": snaps,
        "cap_series": cap_series,   # série histórica por wallet para gráfico
        "_raw_rows": rows,
        "_wallet": wallet, "_env": env, "_chat_id": chat_id,
    }


def _myfxbook_adm_data(periodo: str = "ciclo") -> dict:
    """
    Coleta dados de performance do protocolo inteiro (ADM).
    Por ambiente. Usa apenas DB — zero RPC.
    """
    since = _period_since(periodo)
    label = _period_label(periodo)

    with DB_LOCK:
        _c = conn.cursor()

        # Por ambiente (nomes raw: bd_v5, AG_C_bd)
        env_rows = _c.execute("""
            SELECT
              COALESCE(ambiente, 'UNKNOWN') AS amb,
              COUNT(*)           AS trades,
              SUM(valor)         AS bruto,
              SUM(gas_usd)       AS gas,
              SUM(valor)-SUM(gas_usd) AS liq,
              COUNT(CASE WHEN valor > 0 THEN 1 END) AS wins,
              COUNT(DISTINCT sub_conta)              AS subs
            FROM operacoes
            WHERE tipo='Trade' AND data_hora>=?
            GROUP BY amb
        """, (since,)).fetchall()
        # bd_v5 sempre primeiro
        env_rows = sorted(env_rows, key=lambda r: (0 if "v5" in str(r[0]).lower() else 1, -float(r[4] or 0)))

        # Serie diaria (ultimos 30 dias, com filtro de data para performance)
        since_30d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        daily = _c.execute("""
            SELECT DATE(data_hora) as dia,
                   SUM(valor)-SUM(gas_usd) as liq,
                   COUNT(*) as trades
            FROM operacoes
            WHERE tipo='Trade' AND data_hora >= ?
            GROUP BY dia ORDER BY dia DESC LIMIT 30
        """, (since_30d,)).fetchall()

        # Snapshots para capital total
        snaps = _c.execute("""
            SELECT env, ts, liq_usdt, liq_loop, total_usd
            FROM fl_snapshots ORDER BY id DESC LIMIT 60
        """).fetchall()

        total_users = int(_c.execute("SELECT COUNT(*) FROM users WHERE COALESCE(wallet,'')!=''").fetchone()[0] or 0)

    total_trades = sum(int(r[1] or 0) for r in env_rows)
    total_bruto  = sum(float(r[2] or 0) for r in env_rows)
    total_gas    = sum(float(r[3] or 0) for r in env_rows)
    total_liq    = sum(float(r[4] or 0) for r in env_rows)
    total_wins   = sum(int(r[5] or 0) for r in env_rows)
    total_subs   = sum(int(r[6] or 0) for r in env_rows)
    winrate      = total_wins / total_trades * 100 if total_trades else 0

    # Capital total: usa adm_capital_stats (calculado sobre capital_cache dos usuários)
    # É a fonte mais confiável — não infla com LOOP
    cap_by_env: dict = {}
    capital_total = 0.0
    try:
        _stat = conn.execute(
            "SELECT capital_total, cap_v5, cap_agbd FROM adm_capital_stats ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if _stat and float(_stat[0] or 0) > 0:
            capital_total = float(_stat[0])
            cap_by_env["bd_v5"]   = float(_stat[1] or 0)
            cap_by_env["AG_C_bd"] = float(_stat[2] or 0)
    except Exception as _e:
        logger.error("[mybdbook_adm] adm_capital_stats query failed: %s", _e)
    # Fallback: soma capital_cache de todos os usuários
    if capital_total <= 0:
        try:
            _rows_cc = conn.execute(
                "SELECT COALESCE(total_usd,0) FROM capital_cache WHERE total_usd > 0"
            ).fetchall()
            capital_total = sum(float(r[0]) for r in _rows_cc)
        except Exception as _e:
            logger.error("[mybdbook_adm] capital_cache fallback query failed: %s", _e)
    roi_total = (total_liq / capital_total * 100) if capital_total > 0 else 0.0

    # MDD global (série diária)
    daily_liq = [float(r[1] or 0) for r in reversed(daily)]
    eq, acc = [], 0.0
    for x in daily_liq:
        acc += x; eq.append(acc)
    mdd = _max_drawdown(eq) if eq else 0.0

    g_sum = sum(float(r[4] or 0) for r in env_rows if float(r[4] or 0) > 0)
    l_sum = abs(sum(float(r[4] or 0) for r in env_rows if float(r[4] or 0) < 0))
    pf    = g_sum / l_sum if l_sum > 0 else float("inf")

    return {
        "ok": True, "label": label, "since": since,
        "total_trades": total_trades, "total_liq": total_liq,
        "total_bruto": total_bruto, "total_gas": total_gas,
        "total_wins": total_wins, "total_subs": total_subs,
        "winrate": winrate, "roi": roi_total, "capital": capital_total,
        "mdd": mdd, "pf": pf, "total_users": total_users,
        "envs": env_rows, "daily": list(daily), "cap_by_env": cap_by_env,
    }


# ==============================================================================
# 📉 ASCII CHART & SPARKLINE
# ==============================================================================

def _ascii_chart(values: list, width: int = 20, height: int = 5, label: str = "") -> str:
    """
    Gera um mini gráfico ASCII de linha com eixo Y.
    values: lista de floats (série temporal)
    Retorna string formatada para Telegram (dentro de <code>).
    """
    if not values or len(values) < 2:
        return "<code>(dados insuficientes para gráfico)</code>"

    import math

    # Reduz para 'width' pontos por amostragem
    n = len(values)
    if n > width:
        step = n / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = list(values)
        width = len(sampled)

    mn = min(sampled)
    mx = max(sampled)
    rng = mx - mn if mx != mn else 1e-9

    rows = []
    for row in range(height - 1, -1, -1):
        threshold = mn + (row / (height - 1)) * rng
        line = ""
        for j, v in enumerate(sampled):
            above = v >= threshold
            if above:
                # Preenche com bloco se este ponto >= threshold
                # Determina se é o topo deste ponto
                is_top = (row == round((v - mn) / rng * (height - 1)))
                line += "●" if is_top else "│"
            else:
                line += " "
        # Adiciona label do eixo Y nos extremos
        if row == height - 1:
            rows.append(f"{mx:+.3f} │{line}")
        elif row == 0:
            rows.append(f"{mn:+.3f} │{line}")
        else:
            rows.append(f"       │{line}")

    # Linha de base
    base = "       └" + "─" * width
    rows.append(base)
    if label:
        rows.append(f"        {label}")

    return "<code>" + "\n".join(rows) + "</code>"


def _sparkline(values: list, width: int = 16) -> str:
    """Sparkline de barras: ▁▂▃▄▅▆▇█"""
    if not values or len(values) < 2:
        return "—"
    bars = " ▁▂▃▄▅▆▇█"
    n = len(values)
    if n > width:
        step = n / width
        pts = [values[int(i * step)] for i in range(width)]
    else:
        pts = list(values)
    mn, mx = min(pts), max(pts)
    rng = mx - mn if mx != mn else 1e-9
    return "".join(bars[min(8, int((v - mn) / rng * 8))] for v in pts)


# ==============================================================================
# 📊 MYBDBOOK REPORTS
# ==============================================================================

def _myfxbook_user_report(wallet: str, periodo: str = "ciclo", chat_id: int = 0, env: str = "", rpc: str = "") -> str:
    """Monta o relatório mybdBook do usuário em HTML para Telegram."""
    d = _myfxbook_user_data(wallet, periodo, chat_id=chat_id, env=env, rpc=rpc)
    if not d.get("ok"):
        return (
            f"📊 <b>mybdBook — WEbdEX</b>\n"
            f"🗓️ <i>{esc(d['label'])}</i>\n\n"
            f"⚠️ Sem trades no período.\n"
            f"💰 Capital (USDT0): <b>{d['capital']:,.2f} USD</b>"
        )

    pf_str   = f"{d['pf']:.2f}" if d['pf'] != float("inf") else "∞"
    roi_icon = "🟢" if d["roi"] >= 0 else "🔴"
    liq_icon = "🟢" if d["liq"] >= 0 else "🔴"
    bar      = barra_progresso(d["wins"], d["total_t"])

    # ── Gráfico de equity curve ASCII ─────────────────────────────────────
    eq = d["equity"]
    grafico = ""
    if len(eq) >= 4:
        grafico = _ascii_chart(eq, width=18, height=5, label=f"← {d['label']} →")
    spark = _sparkline(eq, width=16) if len(eq) >= 2 else "—"

    # ── Variação diária (série de resultados por dia) ──────────────────────
    from collections import defaultdict as _dd
    daily_acc = _dd(float)
    for row in d.get("_raw_rows", []):
        try:
            dia = str(row[0])[:10]
            daily_acc[dia] += float(row[1] or 0) - float(row[2] or 0)
        except Exception:
            pass
    daily_vals = [daily_acc[k] for k in sorted(daily_acc.keys())]
    spark_daily = _sparkline(daily_vals, width=14) if len(daily_vals) >= 2 else ""

    # ── Por ambiente ───────────────────────────────────────────────────────
    env_lines = []
    for env_k, env_v in d["by_env"].items():
        ic = "🔷" if "v5" in env_k.lower() or "beta" in env_k.lower() else ("🔶" if "ag" in env_k.lower() else "⚫")
        sg = "🟢" if env_v["liq"] >= 0 else "🔴"
        env_lines.append(f"  {ic} {esc(env_k[:14])}: {sg} <b>{env_v['liq']:+.4f}</b> | {env_v['trades']} trades")

    # ── Montar mensagem ────────────────────────────────────────────────────
    # Linha de capital com detalhe USDT0 vs LP (valor justo)
    cap_lp    = d.get("cap_lp", 0.0)
    cap_usdt  = d.get("cap_usdt0", 0.0)
    cap_src   = d.get("cap_source", "cache")
    src_icon  = "🔗" if cap_src == "on-chain" else "💾"
    if cap_usdt > 0 and cap_lp > 0:
        cap_line = (f"  💰 Capital {src_icon}: <b>{d['capital']:,.2f} USD</b>\n"
                    f"     ├ USDT0: <b>{cap_usdt:,.2f}</b>  LP (fair): <b>{cap_lp:,.2f}</b>\n")
    elif d['capital'] > 0:
        cap_label = "USDT0 real" if cap_usdt > 0 else ("on-chain" if cap_src=="on-chain" else "cache")
        cap_line = f"  💰 Capital {src_icon} <i>({cap_label})</i>: <b>{d['capital']:,.2f} USD</b>\n"
    else:
        cap_line = f"  💰 Capital: <b>—</b> <i>(sem dados — tente novamente)</i>\n"

    msg  = f"📊 <b>mybdBook — WEbdEX</b>\n"
    msg += f"🗓️ <i>{esc(d['label'])}</i>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    msg += f"💼 <b>CAPITAL &amp; ROI</b>\n"
    msg += cap_line
    if d['capital'] > 0:
        msg += f"  {roi_icon} ROI Período: <b>{d['roi']:+.3f}%</b>\n\n"
    else:
        msg += f"  ℹ️ <i>Capital não disponível — ROI calculado sobre resultado líquido</i>\n\n"

    msg += f"📈 <b>PERFORMANCE</b>\n"
    msg += f"  📊 Trades: <b>{d['total_t']:,}</b> | Subs: <b>{d['subs']}</b>\n"
    msg += f"  {liq_icon} Líquido:  <b>{d['liq']:+.4f} USD</b>\n"
    msg += f"  💰 Bruto:   <b>{d['bruto']:+.4f} USD</b>\n"
    msg += f"  ⛽ Gás:     <b>{d['gas']:.4f} USD</b>\n\n"

    msg += f"📐 <b>ESTATÍSTICAS</b>\n"
    msg += f"  🎯 WinRate: <b>{d['winrate']:.1f}%</b>  ✅{d['wins']} ❌{d['losses']}\n"
    msg += f"  {bar}\n"
    msg += f"  📏 Profit Factor: <b>{pf_str}</b>\n"
    msg += f"  💡 Expectância: <b>{d['expectancy']:+.5f} USD/trade</b>\n"
    msg += f"  📉 Max Drawdown: <b>{d['mdd']:.4f} USD</b>\n"
    if d.get("calmar", 0) > 0:
        _calmar_icon = "🟢" if d["calmar"] >= 3.0 else ("🟡" if d["calmar"] >= 1.0 else "🔴")
        msg += f"  📐 Calmar Ratio: <b>{d['calmar']:.1f}</b> {_calmar_icon}\n"
    msg += f"  🏆 Melhor trade: <b>{d['best']:+.4f} USD</b>\n"
    msg += f"  ⚠️ Pior trade:   <b>{d['worst']:+.4f} USD</b>\n\n"

    # Gráfico de crescimento da equity
    if grafico:
        msg += f"📈 <b>CURVA DE CRESCIMENTO</b>\n{grafico}\n"
        msg += f"  Sparkline: {spark}\n\n"
    elif spark != "—":
        msg += f"📡 <b>EQUITY</b>: {spark}\n\n"

    if spark_daily:
        msg += f"📅 <b>DIA A DIA</b>: {spark_daily}\n\n"

    if env_lines:
        msg += f"🌐 <b>POR AMBIENTE</b>\n" + "\n".join(env_lines) + "\n"

    return msg


def _myfxbook_adm_report(periodo: str = "ciclo") -> str:
    """Monta o relatório mybdBook ADM do protocolo completo."""
    d = _myfxbook_adm_data(periodo)
    if not d.get("ok"):
        return "📊 <b>mybdBook ADM</b>\n\n⚠️ Sem dados."

    sep      = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    pf_str   = f"{d['pf']:.2f}" if d['pf'] != float("inf") else "∞"
    roi_icon = "🟢" if d["roi"] >= 0 else "🔴"
    liq_icon = "🟢" if d["total_liq"] >= 0 else "🔴"
    bar      = barra_progresso(d["total_wins"], d["total_trades"])
    lpt_g    = d["total_liq"] / d["total_trades"] if d["total_trades"] else 0

    lines = [
        "📊 <b>mybdBook ADM — WEbdEX</b>",
        f"🗓️ <i>{esc(d['label'])}</i>",
        sep,
        "",
        "🌐 <b>CONSOLIDADO GLOBAL</b>",
        f"  ├─ 👥 Usuários: <b>{d['total_users']}</b>  🧮 Subcontas: <b>{d['total_subs']:,}</b>",
        f"  ├─ 📊 Trades:   <b>{d['total_trades']:,}</b>  (WR: <b>{d['winrate']:.1f}%</b>  PF: <b>{pf_str}</b>)",
        f"  ├─ 💰 Bruto:    <b>{d['total_bruto']:+.2f} USD</b>  ⛽ Gás: <b>{d['total_gas']:.2f} USD</b>",
        f"  └─ {liq_icon} Líquido: <b>{d['total_liq']:+.2f} USD</b>  (<b>{lpt_g:+.4f}/trade</b>)",
    ]

    # Capital
    lines += ["", sep, "", "💼 <b>CAPITAL &amp; ROI</b>"]
    if d["capital"] > 0:
        cap_by_env_sorted = sorted(d["cap_by_env"].items(), key=lambda kv: (0 if "v5" in kv[0].lower() else 1))
        cap_items = [f"  ├─ 💰 Capital Total: <b>${d['capital']:,.2f} USD</b>"]
        for i, (env_k, cap_v) in enumerate(cap_by_env_sorted):
            ic = "🔵" if "v5" in env_k.lower() else "🟠"
            pfx = "  └─" if i == len(cap_by_env_sorted) - 1 else "  ├─"
            cap_items.append(f"     {pfx} {ic} <b>{esc(env_k)}</b>: <b>${cap_v:,.2f}</b>")
        lines += cap_items
        lines.append(f"  └─ {roi_icon} ROI Período: <b>{d['roi']:+.3f}%</b>")
    else:
        lines += [
            f"  ├─ 💰 Capital Total: <b>—</b>  <i>(chame mybdBook para atualizar)</i>",
            f"  └─ {roi_icon} ROI Período: <b>{d['roi']:+.3f}%</b>",
        ]

    # Estatísticas
    lines += [
        "", sep, "",
        "📐 <b>ESTATÍSTICAS</b>",
        f"  ├─ 🎯 WinRate: <b>{d['winrate']:.1f}%</b>  {bar}",
        f"  ├─ 📏 Profit Factor: <b>{pf_str}</b>",
        f"  └─ 📉 Max Drawdown: <b>{d['mdd']:.4f} USD</b>",
    ]

    # Por ambiente
    if d["envs"]:
        lines += ["", sep]
        for amb, trades, bruto, gas, liq, wins, subs in d["envs"]:
            wr  = wins / trades * 100 if trades else 0
            ic  = "🔵" if "v5" in str(amb).lower() else "🟠"
            sg  = "🟢" if float(liq or 0) >= 0 else "🔴"
            lpt = float(liq or 0) / trades if trades else 0
            lines += [
                "",
                f"{ic} <b>{esc(str(amb))}</b>",
                f"  ├─ 🧮 Subcontas: <b>{int(subs or 0):,}</b>  📊 Trades: <b>{int(trades or 0):,}</b>  WR: <b>{wr:.1f}%</b>",
                f"  ├─ 💰 Bruto: <b>{float(bruto or 0):+.2f}</b>  ⛽ Gás: <b>{float(gas or 0):.2f}</b>",
                f"  └─ {sg} Líquido: <b>{float(liq or 0):+.2f} USD</b>  (<b>{lpt:+.4f}/trade</b>)",
            ]

    # Série diária (últimos 7)
    daily7 = d["daily"][:7]
    if daily7:
        lines += ["", sep, "", "📅 <b>ÚLTIMOS 7 DIAS</b>"]
        for dia, liq_d, tr in daily7:
            ic = "🟢" if float(liq_d or 0) >= 0 else "🔴"
            lines.append(f"  {ic} {dia}  <b>{float(liq_d or 0):+.2f} USD</b>  ({int(tr or 0):,}t)")

    # Sparkline / gráfico ASCII dos últimos 30 dias
    daily_all     = d.get("daily", [])
    daily_liq_vals = [float(r[1] or 0) for r in reversed(daily_all[:30])]
    if len(daily_liq_vals) >= 3:
        grafico = _ascii_chart(daily_liq_vals, width=18, height=4, label="← 30 dias →")
        spark   = _sparkline(daily_liq_vals, width=20)
        lines  += [
            "", sep, "",
            "📈 <b>PROGRESSÃO 30 DIAS (Líquido/dia)</b>",
            grafico,
            f"  Spark: {spark}",
        ]

    return "\n".join(lines)


def _myfxbook_ai_comment(data: dict, mode: str = "user") -> str:
    """
    Análise IA leve e rápida do mybdBook.
    Roda em background — não bloqueia o Telegram.
    Usa regras internas (sem chamada API) para ser instantâneo.
    """
    lines = []
    if mode == "user":
        wr  = data.get("winrate", 0)
        pf  = data.get("pf", 0)
        roi = data.get("roi", 0)
        liq = data.get("liq", 0)
        mdd = data.get("mdd", 0)
        total = data.get("total_t", 0)

        if total < 5:
            return "🧠 <i>Poucos trades — aguarde mais dados para análise confiável.</i>"

        # WinRate
        if wr >= 76:
            lines.append(f"✅ WinRate <b>{wr:.1f}%</b> acima da média histórica (76%). Consistência excelente.")
        elif wr >= 60:
            lines.append(f"🟡 WinRate <b>{wr:.1f}%</b> abaixo do histórico (76%). Acompanhe a tendência.")
        else:
            lines.append(f"⚠️ WinRate <b>{wr:.1f}%</b> bem abaixo do histórico. Verifique liquidez e Manager.")

        # Profit Factor
        if pf == float("inf") or pf > 2:
            lines.append("📏 Profit Factor excelente — os ganhos superam amplamente as perdas.")
        elif pf >= 1:
            lines.append(f"📏 Profit Factor <b>{pf:.2f}</b> — lucrativo, mas com espaço para melhora.")
        else:
            lines.append(f"📏 Profit Factor <b>{pf:.2f}</b> abaixo de 1.0 — resultado negativo no período.")

        # ROI
        if roi > 0:
            lines.append(f"📈 ROI positivo de <b>{roi:+.3f}%</b> no ciclo. Capital trabalhando.")
        else:
            lines.append(f"📉 ROI de <b>{roi:+.3f}%</b>. Resultado negativo — avalie gas vs retorno.")

        # Drawdown
        if mdd > 0 and liq != 0:
            mdd_ratio = mdd / abs(liq) * 100 if liq != 0 else 0
            if mdd_ratio < 20:
                lines.append("📉 Drawdown controlado em relação ao resultado.")
            else:
                lines.append(f"⚠️ Drawdown relevante. Mantenha o ciclo e não aja por impulso.")

    else:  # ADM
        wr     = data.get("winrate", 0)
        roi    = data.get("roi", 0)
        cap    = data.get("capital", 0)
        trades = data.get("total_trades", 0)
        pf     = data.get("pf", 0)

        if trades < 10:
            return "🧠 <i>Poucos dados globais — aguarde mais operações.</i>"

        lines.append(f"🏛️ Protocolo com <b>{trades:,}</b> trades no período.")
        if wr >= 70:
            lines.append(f"✅ WinRate global <b>{wr:.1f}%</b> — protocolo operando acima do break-even.")
        else:
            lines.append(f"⚠️ WinRate global <b>{wr:.1f}%</b> — monitorar se persiste abaixo de 70%.")
        if roi > 0:
            lines.append(f"📈 ROI do protocolo: <b>{roi:+.3f}%</b> sobre capital de <b>{cap:,.0f} USD</b>.")
        else:
            lines.append(f"📉 ROI negativo: <b>{roi:+.3f}%</b>. Analise ambientes separadamente.")
        if pf >= 1.5:
            lines.append("📏 Profit Factor saudável — ecossistema sustentável no ciclo atual.")

    if not lines:
        return ""
    return "🧠 <b>Análise IA:</b>\n" + "\n".join(f"  • {l}" for l in lines)


# ==============================================================================
# 🤖 BOT HANDLERS — PUBLIC ENTRY POINTS (chamados de user.py via lazy import)
# ==============================================================================

def _handle_myfxbook_user(m, u: dict):
    """Entry point: relatório mybdBook do usuário. Chamado de user.py."""
    bot.send_chat_action(m.chat.id, "typing")
    wallet  = (u.get("wallet") or "").lower()
    periodo = u.get("periodo") or "ciclo"
    env     = u.get("env") or ""
    rpc     = u.get("rpc") or ""

    if not wallet:
        return send_html(m.chat.id, "⚠️ Carteira não configurada. Use <b>Conectar</b> primeiro.")

    report = _myfxbook_user_report(wallet, periodo, chat_id=m.chat.id, env=env, rpc=rpc)
    send_html(m.chat.id, report)

    # IA comment em background
    def _ai_bg():
        try:
            d = _myfxbook_user_data(wallet, periodo, chat_id=m.chat.id, env=env, rpc=rpc)
            if d.get("ok") and d.get("total_t", 0) >= 5:
                comment = _myfxbook_ai_comment(d, mode="user")
                if comment:
                    send_html(m.chat.id, comment)
        except Exception as _e:
            logger.error("[mybdbook_user] AI background comment failed: %s", _e)
    threading.Thread(target=_ai_bg, daemon=True).start()


def _handle_myfxbook_user_chart(m, u: dict):
    """Entry point: gráfico PNG mybdBook do usuário. Chamado de user.py."""
    bot.send_chat_action(m.chat.id, "typing")
    wallet  = (u.get("wallet") or "").lower()
    periodo = u.get("periodo") or "ciclo"
    env     = u.get("env") or ""
    rpc     = u.get("rpc") or ""

    if not wallet:
        return send_html(m.chat.id, "⚠️ Carteira não configurada. Use <b>Conectar</b> primeiro.")

    d = _myfxbook_user_data(wallet, periodo, chat_id=m.chat.id, env=env, rpc=rpc)

    cap_series = d.get("cap_series", [])
    equity     = d.get("equity", [])
    label      = d.get("label", periodo.upper())

    wallet_label = wallet[:6] + "..." + wallet[-4:]
    png = _mybdbook_generate_chart_png(wallet, wallet_label, cap_series, equity, label)

    if png:
        try:
            import io as _io
            bot.send_photo(
                m.chat.id,
                _io.BytesIO(png),
                caption=f"📊 mybdBook WEbdEX | {wallet_label} | {label}"
            )
        except Exception as e:
            send_html(m.chat.id, f"⚠️ Erro ao enviar gráfico: {esc(str(e))}")
    else:
        send_html(m.chat.id, "⚠️ Não foi possível gerar o gráfico. Sem snapshots de capital suficientes.")


def _mybdbook_adm_kb(periodo: str = "ciclo") -> _tg_types.InlineKeyboardMarkup:
    periodos = [("Ciclo", "ciclo"), ("24h", "24h"), ("7d", "7d"), ("30d", "30d"), ("All", "all")]
    kb = _tg_types.InlineKeyboardMarkup()
    row = []
    for label_p, p in periodos:
        mark = f"✅ {label_p}" if p == periodo else label_p
        row.append(_tg_types.InlineKeyboardButton(mark, callback_data=f"mybdadm_{p}"))
    kb.row(*row)
    kb.row(_tg_types.InlineKeyboardButton("✅ Fechar", callback_data="mybdadm_close"))
    return kb


@bot.callback_query_handler(func=lambda c: (c.data or "").startswith("mybdadm_"))
def _mybdbook_adm_callback(c):
    from webdex_handlers.admin import _is_admin
    if not _is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "⛔ Acesso negado.")
    if c.data == "mybdadm_close":
        bot.delete_message(c.message.chat.id, c.message.message_id)
        return bot.answer_callback_query(c.id)
    periodo = c.data.replace("mybdadm_", "")
    bot.answer_callback_query(c.id, f"Carregando {periodo.upper()}...")
    try:
        txt = _myfxbook_adm_report(periodo)
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                              parse_mode="HTML", reply_markup=_mybdbook_adm_kb(periodo))
    except Exception as e:
        logger.error("[handler] %s", e)


def _handle_myfxbook_adm(m):
    """Entry point: relatório mybdBook ADM. Chamado de admin.py."""
    bot.send_chat_action(m.chat.id, "typing")
    periodo = "ciclo"
    report = _myfxbook_adm_report(periodo)
    bot.send_message(m.chat.id, report, parse_mode="HTML", reply_markup=_mybdbook_adm_kb(periodo))

    # IA comment ADM em background
    def _ai_bg():
        try:
            d = _myfxbook_adm_data(periodo)
            if d.get("ok") and d.get("total_trades", 0) >= 10:
                comment = _myfxbook_ai_comment(d, mode="adm")
                if comment:
                    send_html(m.chat.id, comment)
        except Exception as _e:
            logger.error("[mybdbook_adm] AI background comment failed: %s", _e)
    threading.Thread(target=_ai_bg, daemon=True).start()
