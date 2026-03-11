"""ocme-monitor capital [wallet] — capital por wallet + breakdown."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional


def _col(text: str, code: str) -> str:
    codes = {"green": "32", "red": "31", "yellow": "33", "cyan": "36",
             "bold": "1", "blue": "34"}
    return f"\033[{codes.get(code, '0')}m{text}\033[0m"


def _ago(ts: Optional[float]) -> str:
    if not ts:
        return "—"
    import time
    s = int(time.time() - float(ts))
    if s < 60: return f"{s}s atrás"
    if s < 3600: return f"{s // 60}m atrás"
    return f"{s // 3600}h atrás"


def run(db_path: str, wallet: Optional[str] = None, json_output: bool = False):
    """
    ocme-monitor capital [wallet]

    Sem wallet: mostra capital total por ambiente.
    Com wallet: detalha capital, trades e subcontas daquela wallet.
    """
    conn = sqlite3.connect(db_path)

    if wallet:
        _run_wallet(conn, wallet.lower(), json_output)
    else:
        _run_overview(conn, json_output)

    conn.close()


def _run_overview(conn: sqlite3.Connection, json_output: bool):
    rows = conn.execute("""
        SELECT COALESCE(c.env, u.env, 'AG_C_bd') AS env_final,
               COUNT(*) AS wallets,
               SUM(c.total_usd) AS capital
        FROM capital_cache c
        JOIN users u ON u.chat_id = c.chat_id
        WHERE c.total_usd > 0
        GROUP BY env_final
        ORDER BY capital DESC
    """).fetchall()

    total = sum(float(r[2] or 0) for r in rows)

    # Top 5 wallets
    top = conn.execute("""
        SELECT u.wallet, COALESCE(c.env, u.env,'?'), c.total_usd, c.updated_ts
        FROM capital_cache c
        JOIN users u ON u.chat_id = c.chat_id
        WHERE c.total_usd > 0
        ORDER BY c.total_usd DESC
        LIMIT 5
    """).fetchall()

    if json_output:
        import json
        print(json.dumps({
            "total_usd": total,
            "by_env": [{"env": r[0], "wallets": r[1], "capital": r[2]} for r in rows],
            "top5": [{"wallet": r[0], "env": r[1], "total_usd": r[2]} for r in top],
        }, indent=2))
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    print()
    print(_col("💼 CAPITAL — VISÃO GERAL (OCME users)", "bold"))
    print(_col("━" * 44, "cyan"))

    print()
    print(_col("🌐 POR AMBIENTE", "bold"))
    for env, wallets, cap in rows:
        pct  = (float(cap or 0) / total * 100) if total > 0 else 0
        icon = "🔵" if "v5" in str(env).lower() else "🟠"
        print(f"   {icon} {env}")
        print(f"      ${float(cap or 0):,.2f}  ({wallets} wallets)  {pct:.1f}%")

    print()
    print(_col(f"   TOTAL: ${total:,.2f} USD", "bold"))

    if top:
        print()
        print(_col("🏆 TOP 5 WALLETS", "bold"))
        for i, (w, env, cap, ts) in enumerate(top, 1):
            med = medals.get(i, f"{i}")
            ws  = f"{w[:6]}…{w[-4:]}" if w and len(w) > 10 else (w or "?")
            print(f"   {med} {ws}  ({env})")
            print(f"      ${float(cap or 0):,.2f}  · atualizado {_ago(ts)}")

    print()
    print(_col(f"   ⚠️  OCME cobre ~5.7% do protocolo real (~609 LP holders on-chain)", "yellow"))
    print()


def _run_wallet(conn: sqlite3.Connection, wallet: str, json_output: bool):
    # Capital cache
    cap = conn.execute("""
        SELECT c.env, c.total_usd, c.breakdown_json, c.updated_ts, u.chat_id
        FROM capital_cache c
        JOIN users u ON u.chat_id = c.chat_id
        WHERE LOWER(u.wallet) = ?
    """, (wallet,)).fetchone()

    # P&L 24h
    row_pnl = conn.execute("""
        SELECT COUNT(*), ROUND(SUM(o.valor)-SUM(o.gas_usd),4),
               COUNT(CASE WHEN o.valor>0 THEN 1 END)
        FROM operacoes o
        JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
        WHERE LOWER(ow.wallet)=?
          AND o.tipo='Trade'
          AND o.data_hora >= datetime('now','-1 day')
    """, (wallet,)).fetchone()

    # Top subcontas
    top_subs = conn.execute("""
        SELECT o.sub_conta, o.ambiente,
               COUNT(*), ROUND(SUM(o.valor)-SUM(o.gas_usd),4)
        FROM operacoes o
        JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
        WHERE LOWER(ow.wallet)=? AND o.tipo='Trade'
        GROUP BY o.sub_conta, o.ambiente
        ORDER BY 4 DESC
        LIMIT 5
    """, (wallet,)).fetchall()

    trades = int(row_pnl[0] or 0) if row_pnl else 0
    pnl    = float(row_pnl[1] or 0) if row_pnl else 0.0
    wins   = int(row_pnl[2] or 0) if row_pnl else 0
    wr     = (wins / trades * 100) if trades > 0 else 0.0

    ws = f"{wallet[:6]}…{wallet[-4:]}" if len(wallet) > 10 else wallet

    if json_output:
        import json
        print(json.dumps({
            "wallet": wallet,
            "capital": {"env": cap[0] if cap else None, "total_usd": cap[1] if cap else 0},
            "pnl_24h": {"trades": trades, "liquido": pnl, "winrate": wr},
            "top_subs": [{"sub": r[0], "env": r[1], "trades": r[2], "liquido": r[3]} for r in top_subs],
        }, indent=2))
        return

    w_ic = "🟢" if wr >= 55 else ("🟡" if wr >= 40 else "🔴")
    sign = "+" if pnl >= 0 else ""
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    print()
    print(_col(f"💼 CAPITAL — {ws}", "bold"))
    print(_col("━" * 44, "cyan"))

    if cap:
        print()
        print(_col("💰 CAPITAL ON-CHAIN (cache)", "bold"))
        print(f"   Ambiente: {cap[0] or '?'}")
        print(f"   Total:    ${float(cap[1] or 0):,.2f} USD")
        print(f"   Cache:    {_ago(cap[3])}")
    else:
        print()
        print(_col("   ⚠️  Sem dados de capital. Wallet não rastreada pelo OCME.", "yellow"))

    print()
    print(_col("📊 PERFORMANCE 24h", "bold"))
    print(f"   Trades:   {trades}")
    print(f"   WinRate:  {w_ic} {wr:.1f}%")
    print(f"   P&L:      {_col(f'{sign}${pnl:.4f}', 'green' if pnl >= 0 else 'red')}")

    if top_subs:
        print()
        print(_col("🔑 TOP SUBCONTAS", "bold"))
        for i, (sub, amb, t, l) in enumerate(top_subs, 1):
            med  = medals.get(i, f"{i}")
            sg   = "🟢" if (l or 0) >= 0 else "🔴"
            subs = (str(sub or "?")[:20] + "…") if len(str(sub or "")) > 20 else str(sub or "?")
            print(f"   {med} {sg} {subs}  ({amb})")
            print(f"      {t} trades  Líq: {(l or 0):+.4f}")

    print()
