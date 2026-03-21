"""ocme-monitor report — relatório por período e ambiente."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Optional


def _period_since(period: str) -> str:
    mapping = {"24h": 24, "7d": 168, "30d": 720, "ciclo": 24}
    hours = mapping.get(period.lower(), 24)
    return (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


def _col(text: str, code: str) -> str:
    codes = {"green": "32", "red": "31", "yellow": "33", "cyan": "36",
             "bold": "1", "blue": "34", "reset": "0"}
    return f"\033[{codes.get(code, '0')}m{text}\033[0m"


def _bar(value: float, max_val: float = 100, width: int = 10) -> str:
    filled = max(0, min(width, int(round(value / max_val * width))))
    return "█" * filled + "░" * (width - filled)


def run(db_path: str, period: str = "24h", env: Optional[str] = None,
        limit: int = 10, json_output: bool = False):
    """
    ocme-monitor report --period [24h|7d|30d] --env [AG_C_bd|bd_v5]

    Relatório completo no terminal. Opera sem Telegram (CLI First).
    """
    conn = sqlite3.connect(db_path)
    since = _period_since(period)

    # ── global ───────────────────────────────────────────────────────────────
    env_filter = "AND ambiente=?" if env else ""
    params_g   = [since, env] if env else [since]

    row = conn.execute(f"""
        SELECT COUNT(*),
               COALESCE(SUM(CAST(valor AS REAL)),0),
               COALESCE(SUM(CAST(gas_usd AS REAL)),0),
               COALESCE(SUM(CAST(valor AS REAL))-SUM(CAST(gas_usd AS REAL)),0),
               COUNT(CASE WHEN CAST(valor AS REAL)-CAST(gas_usd AS REAL)>0 THEN 1 END),
               COUNT(DISTINCT sub_conta)
        FROM operacoes
        WHERE tipo='Trade' AND data_hora>=? {env_filter}
    """, params_g).fetchone()

    trades = int(row[0] or 0)
    bruto  = float(row[1] or 0)
    gas    = float(row[2] or 0)
    liq    = float(row[3] or 0)
    wins   = int(row[4] or 0)
    subs   = int(row[5] or 0)
    losses = trades - wins
    wr     = (wins / trades * 100) if trades > 0 else 0.0
    pf     = (wins / losses) if losses > 0 else float("inf")
    pf_str = f"{pf:.2f}" if pf != float("inf") else "∞"

    # ── por ambiente ─────────────────────────────────────────────────────────
    env_rows = conn.execute(f"""
        SELECT COALESCE(ambiente,'UNKNOWN'),
               COUNT(*), ROUND(SUM(valor),4), ROUND(SUM(gas_usd),4),
               ROUND(SUM(valor)-SUM(gas_usd),4),
               COUNT(CASE WHEN valor-gas_usd>0 THEN 1 END)
        FROM operacoes
        WHERE tipo='Trade' AND data_hora>=? {env_filter}
        GROUP BY 1 ORDER BY 5 DESC
    """, params_g).fetchall()

    # ── top subcontas ─────────────────────────────────────────────────────────
    top_subs = conn.execute(f"""
        SELECT sub_conta, COALESCE(ambiente,'?'),
               COUNT(*), ROUND(SUM(valor)-SUM(gas_usd),4),
               COUNT(CASE WHEN valor>0 THEN 1 END)
        FROM operacoes
        WHERE tipo='Trade' AND data_hora>=? {env_filter}
        GROUP BY sub_conta, ambiente
        ORDER BY 4 DESC
        LIMIT ?
    """, ([since, env, limit] if env else [since, limit])).fetchall()

    # ── diário (últimos 7 dias) ───────────────────────────────────────────────
    daily = conn.execute(f"""
        SELECT DATE(data_hora), COUNT(*), ROUND(SUM(valor)-SUM(gas_usd),4)
        FROM operacoes
        WHERE tipo='Trade' AND data_hora>=? {env_filter}
        GROUP BY 1 ORDER BY 1 DESC LIMIT 7
    """, params_g).fetchall()

    conn.close()

    if json_output:
        import json
        print(json.dumps({
            "period": period, "env": env or "all", "since": since,
            "global": {"trades": trades, "bruto": bruto, "gas": gas,
                       "liquido": liq, "wins": wins, "winrate": wr, "pf": pf_str},
            "by_env": [{"env": r[0], "trades": r[1], "bruto": r[2],
                        "gas": r[3], "liquido": r[4], "wins": r[5]} for r in env_rows],
            "top_subs": [{"sub": r[0], "env": r[1], "trades": r[2],
                          "liquido": r[3], "wins": r[4]} for r in top_subs],
        }, indent=2))
        return

    # ── output ────────────────────────────────────────────────────────────────
    env_label = f" [{env}]" if env else ""
    sign = "+" if liq >= 0 else ""
    w_ic = "🟢" if wr >= 55 else ("🟡" if wr >= 40 else "🔴")
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    print()
    print(_col(f"📊 RELATÓRIO — {period.upper()}{env_label}", "bold"))
    print(_col(f"   Desde: {since}", "cyan"))
    print(_col("━" * 48, "cyan"))

    print()
    print(_col("💼 GLOBAL", "bold"))
    print(f"   Trades:   {_col(str(trades), 'bold')}  ({subs} subcontas únicas)")
    print(f"   WinRate:  {w_ic} {_col(f'{wr:.1f}%', 'bold')}  {_bar(wr)}")
    print(f"   PF:       {pf_str}")
    print(f"   Bruto:    {bruto:+.4f} USD")
    print(f"   Gás:      {gas:.4f} USD")
    print(f"   {_col('Líquido:', 'bold')}  {_col(f'{sign}${liq:.4f}', 'green' if liq >= 0 else 'red')}")

    if env_rows:
        print()
        print(_col("🌐 POR AMBIENTE", "bold"))
        for amb, t, b, g, l, w in env_rows:
            env_wr = (w / t * 100) if t > 0 else 0
            ew_ic  = "🟢" if env_wr >= 55 else ("🟡" if env_wr >= 40 else "🔴")
            icon   = "🔵" if "v5" in str(amb).lower() else "🟠"
            ls     = "+" if (l or 0) >= 0 else ""
            print(f"   {icon} {amb}")
            print(f"      Trades: {t}  WR: {ew_ic} {env_wr:.1f}%  {_bar(env_wr)}")
            print(f"      Bruto: {(b or 0):+.4f}  Gás: {(g or 0):.4f}  Líquido: {ls}${(l or 0):.4f}")

    if top_subs:
        print()
        print(_col(f"🏆 TOP {limit} SUBCONTAS", "bold"))
        for i, (sub, amb, t, l, w) in enumerate(top_subs, 1):
            med  = medals.get(i, f"{i:02d}")
            wr_s = (w / t * 100) if t > 0 else 0
            sg   = "🟢" if (l or 0) >= 0 else "🔴"
            sub_s = (str(sub or "?")[:20] + "…") if len(str(sub or "")) > 20 else str(sub or "?")
            print(f"   {med} {sg} {sub_s}  ({amb})")
            print(f"      {t} trades  WR: {wr_s:.1f}%  Líq: {(l or 0):+.4f}")

    if daily:
        print()
        print(_col("📅 DIÁRIO", "bold"))
        for dia, t, l in daily:
            sg = "🟢" if (l or 0) >= 0 else "🔴"
            print(f"   {dia}  {sg} ${(l or 0):+.4f}  ({t} trades)")

    print()
    print(_col("━" * 48, "cyan"))
    print()
