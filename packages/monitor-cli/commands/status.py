"""ocme-monitor status — saúde do vigia e estado do protocolo."""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime
from typing import Optional


def _col(text: str, code: str) -> str:
    """Coloração ANSI simples."""
    codes = {"green": "32", "red": "31", "yellow": "33", "cyan": "36", "bold": "1", "reset": "0"}
    return f"\033[{codes.get(code, '0')}m{text}\033[0m"


def _bar(value: float, max_val: float = 100, width: int = 10) -> str:
    filled = max(0, min(width, int(round(value / max_val * width))))
    return "█" * filled + "░" * (width - filled)


def _fmt_uptime(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h >= 1:
        return f"{h}h {m}m"
    return f"{m}m {s}s"


def _fmt_ago(ts: Optional[float]) -> str:
    if not ts:
        return "nunca"
    ago = int(time.time() - float(ts))
    if ago < 60:
        return f"{ago}s atrás"
    if ago < 3600:
        return f"{ago // 60}m atrás"
    return f"{ago // 3600}h atrás"


def run(db_path: str, env: Optional[str] = None, json_output: bool = False):
    """
    ocme-monitor status

    Exibe: vigia health, threads ativas, DB stats, RPC, ops do dia.
    Opera 100% sem Telegram — CLI First (Constitution Art. I).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # ── DB stats ─────────────────────────────────────────────────────────────
    total_ops = conn.execute("SELECT COUNT(*) FROM operacoes").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]

    dt_24h = (datetime.now() - __import__("datetime").timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    row24 = conn.execute("""
        SELECT COUNT(*),
               COALESCE(SUM(CAST(valor AS REAL))-SUM(CAST(gas_usd AS REAL)),0),
               COUNT(CASE WHEN CAST(valor AS REAL)>0 THEN 1 END)
        FROM operacoes WHERE tipo='Trade' AND data_hora>=?
    """, (dt_24h,)).fetchone()
    trades_24h = int(row24[0] or 0)
    pnl_24h    = float(row24[1] or 0)
    wins_24h   = int(row24[2] or 0)
    wr_24h     = (wins_24h / trades_24h * 100) if trades_24h > 0 else 0.0

    # Capital total (capital_cache)
    cap_row = conn.execute("SELECT COALESCE(SUM(total_usd),0) FROM capital_cache WHERE total_usd>0").fetchone()
    capital_total = float(cap_row[0] or 0)

    # Schema version
    schema_ver = conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()[0] or 0

    # Último bloco monitorado
    last_block_row = conn.execute("SELECT MAX(bloco) FROM operacoes").fetchone()
    last_block = int(last_block_row[0] or 0)

    # Última operação
    last_op = conn.execute(
        "SELECT data_hora FROM operacoes ORDER BY data_hora DESC LIMIT 1"
    ).fetchone()
    last_op_ts = last_op[0] if last_op else None

    # vigia_health (se tabela existir)
    vigia = {}
    try:
        row_v = conn.execute(
            "SELECT last_block, loops_total, ops_total, rpc_errors, capture_rate, "
            "last_error, started_at, updated_at FROM vigia_health WHERE id=1"
        ).fetchone()
        if row_v:
            vigia = dict(row_v)
    except Exception:
        pass

    conn.close()

    if json_output:
        import json
        print(json.dumps({
            "db_path": db_path, "schema_version": schema_ver,
            "total_ops": total_ops, "total_users": total_users,
            "trades_24h": trades_24h, "pnl_24h": pnl_24h, "winrate_24h": wr_24h,
            "capital_total": capital_total, "last_block": last_block,
            "vigia": vigia,
        }, indent=2))
        return

    # ── output CLI ────────────────────────────────────────────────────────────
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    w_icon  = "🟢" if wr_24h >= 55 else ("🟡" if wr_24h >= 40 else "🔴")
    p_sign  = "+" if pnl_24h >= 0 else ""

    print()
    print(_col("⚡ OCME MONITOR — STATUS", "bold"))
    print(_col(f"   {now_str}", "cyan"))
    print(_col("━" * 44, "cyan"))

    print()
    print(_col("📊 PROTOCOL (24h)", "bold"))
    print(f"   Trades:    {_col(str(trades_24h), 'bold')}")
    print(f"   WinRate:   {w_icon} {_col(f'{wr_24h:.1f}%', 'bold')}  {_bar(wr_24h)}")
    print(f"   P&L:       {_col(f'{p_sign}${pnl_24h:.4f}', 'green' if pnl_24h >= 0 else 'red')}")
    print(f"   Capital:   ${capital_total:,.2f} USD (OCME users)")

    print()
    print(_col("🗄️  DATABASE", "bold"))
    print(f"   Operações: {total_ops:,} (all time)")
    print(f"   Usuários:  {total_users} ativos")
    print(f"   Schema:    v{schema_ver}")
    print(f"   Último bloco: {last_block:,}")
    if last_op_ts:
        print(f"   Última op: {last_op_ts}")

    if vigia:
        up_secs = int(time.time() - float(vigia.get("started_at") or 0))
        uptime  = _fmt_uptime(up_secs) if up_secs > 0 else "—"
        cap_rt  = float(vigia.get("capture_rate") or 100)
        last_err = str(vigia.get("last_error") or "—")[:60]

        print()
        print(_col("👀 VIGIA HEALTH", "bold"))
        print(f"   Uptime:       {uptime}")
        print(f"   Loops:        {vigia.get('loops_total', 0):,}")
        print(f"   Ops capturadas: {vigia.get('ops_total', 0):,}")
        print(f"   RPC errors:   {vigia.get('rpc_errors', 0)}")
        print(f"   Capture rate: {cap_rt:.1f}%  {_bar(cap_rt)}")
        if last_err != "—":
            print(f"   Último erro:  {_col(last_err, 'yellow')}")
    else:
        print()
        print(_col("👀 VIGIA HEALTH", "bold"))
        print(f"   {_col('vigia_health não disponível — rode migrate primeiro', 'yellow')}")

    print()
    print(_col("━" * 44, "cyan"))
    print(_col("   CLI First · WEbdEX · New Digital Economy", "cyan"))
    print()
