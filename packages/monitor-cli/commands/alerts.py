"""ocme-monitor alerts — alertas ativos e histórico."""

from __future__ import annotations

import sqlite3
from typing import Optional


def _col(text: str, code: str) -> str:
    codes = {"green": "32", "red": "31", "yellow": "33", "cyan": "36",
             "bold": "1", "orange": "33"}
    return f"\033[{codes.get(code, '0')}m{text}\033[0m"


def run(db_path: str, subcommand: str = "list", limit: int = 20, json_output: bool = False):
    """
    ocme-monitor alerts list    — histórico de alertas de inatividade
    ocme-monitor alerts active  — apenas alertas recentes (< 1h)
    """
    conn = sqlite3.connect(db_path)

    if subcommand in ("list", "active"):
        _run_list(conn, subcommand == "active", limit, json_output)
    else:
        print(f"Subcomando desconhecido: {subcommand}. Use: list | active")

    conn.close()


def _run_list(conn: sqlite3.Connection, only_active: bool, limit: int, json_output: bool):
    # Alertas de inatividade
    extra = "AND created_at >= datetime('now','-1 hour')" if only_active else ""
    inact = conn.execute(f"""
        SELECT end_block, minutes, tx_count, note, created_at
        FROM inactivity_stats
        WHERE 1=1 {extra}
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()

    # Erros de vigia (se tabela existir)
    vigia_err = ""
    try:
        row = conn.execute("SELECT last_error, updated_at FROM vigia_health WHERE id=1").fetchone()
        if row and row[0]:
            vigia_err = str(row[0])
    except Exception:
        pass

    if json_output:
        import json
        print(json.dumps({
            "vigia_last_error": vigia_err,
            "inactivity": [
                {"block": r[0], "minutes": r[1], "tx_count": r[2],
                 "note": r[3], "at": r[4]}
                for r in inact
            ],
        }, indent=2))
        return

    title = "ALERTAS ATIVOS" if only_active else f"HISTÓRICO DE ALERTAS (últimos {limit})"
    print()
    print(_col(f"⚠️  {title}", "bold"))
    print(_col("━" * 44, "cyan"))

    if vigia_err:
        print()
        print(_col("🔴 VIGIA — ÚLTIMO ERRO", "bold"))
        print(f"   {_col(vigia_err[:120], 'yellow')}")

    if inact:
        print()
        print(_col("😴 INATIVIDADE DETECTADA", "bold"))
        for bloco, mins, txs, note, at in inact:
            sev = "🔴" if (mins or 0) > 60 else ("🟡" if (mins or 0) > 15 else "🟠")
            print(f"   {sev} {at or '?'}")
            print(f"      Bloco: {bloco or '?'}  Duração: {(mins or 0):.1f} min  TXs: {txs or 0}")
            if note:
                print(f"      Nota: {note[:60]}")
    else:
        txt = "Nenhum alerta ativo." if only_active else "Sem histórico de inatividade."
        print()
        print(f"   {_col('✅ ' + txt, 'green')}")

    print()
