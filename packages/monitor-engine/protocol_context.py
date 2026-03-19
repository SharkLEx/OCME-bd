"""
Lê dados reais do OCME SQLite (read-only, sem interferir no bot Telegram).
Injeta contexto do protocolo no prompt da IA.
"""
import sqlite3
import os
from datetime import datetime, timedelta, timezone

# Path do DB dentro do container Discord
# Montado como volume read-only a partir do host
_DB_PATH = os.environ.get("OCME_DB_PATH", "/app/data/webdex_v5_final.db")

_ENV_LABELS = {"AG_C_bd": "🟠 AG_C_bd", "bd_v5": "🔵 bd_v5"}


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True,
                           timeout=3, check_same_thread=False)


def _ciclo_cutoff_utc() -> str:
    """Retorna o timestamp UTC do início do ciclo 21h BR mais recente."""
    now_br = datetime.now(timezone.utc) - timedelta(hours=3)  # BR = UTC-3
    cutoff_br = now_br.replace(hour=21, minute=0, second=0, microsecond=0)
    if now_br < cutoff_br:
        cutoff_br -= timedelta(days=1)
    cutoff_utc = cutoff_br + timedelta(hours=3)
    return cutoff_utc.strftime("%Y-%m-%d %H:%M:%S")


def get_protocol_context() -> str:
    """
    Retorna string formatada com dados reais do protocolo para injetar no prompt.
    Em caso de erro, retorna string vazia (não quebra o bot).
    """
    try:
        conn = _conn()
        lines = ["=== DADOS REAIS DO PROTOCOLO WEbdEX (agora) ==="]

        # ── TVL por ambiente ──────────────────────────────
        tvl_rows = conn.execute(
            """SELECT env, total_usd, ts
               FROM fl_snapshots
               WHERE (env, ts) IN (
                   SELECT env, MAX(ts) FROM fl_snapshots GROUP BY env
               )
               ORDER BY env"""
        ).fetchall()

        tvl_total = 0.0
        if tvl_rows:
            lines.append("\nTVL (último snapshot):")
            for env, total, ts in tvl_rows:
                label = _ENV_LABELS.get(env, env)
                lines.append(f"  {label}: ${total:,.0f} ({ts[:16]})")
                tvl_total += total
            lines.append(f"  📊 TOTAL: ${tvl_total:,.0f}")

        # ── Operações do ciclo atual ──────────────────────
        cutoff = _ciclo_cutoff_utc()
        ops = conn.execute(
            """SELECT COUNT(*), COALESCE(SUM(profit),0), COALESCE(SUM(fee_bd),0)
               FROM protocol_ops WHERE ts > ?""",
            (cutoff,)
        ).fetchone()

        if ops:
            count, profit, fee = ops
            lines.append(f"\nCiclo atual (desde 21h BR):")
            lines.append(f"  Operações: {count}")
            lines.append(f"  Lucro acumulado: ${profit:,.4f}")
            lines.append(f"  Fee BD: ${fee:,.4f}")

        # ── Capital dos usuários ──────────────────────────
        cap = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_usd),0) FROM capital_cache WHERE total_usd > 1"
        ).fetchone()

        if cap and cap[0]:
            lines.append(f"\nCapital usuários ativos:")
            lines.append(f"  Carteiras: {cap[0]}")
            lines.append(f"  Total: ${cap[1]:,.0f}")

        # ── Posições abertas ──────────────────────────────
        pos = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(saldo_usdt),0) FROM sub_positions"
        ).fetchone()

        if pos and pos[0]:
            lines.append(f"\nPosições abertas: {pos[0]} (${pos[1]:,.0f} USDT)")

        conn.close()
        lines.append("\n=== FIM DOS DADOS ===")
        return "\n".join(lines)

    except Exception as e:
        return f"[contexto do protocolo indisponível: {e}]"


def get_status_embed_data() -> dict:
    """Retorna dict com dados para o embed do /status."""
    try:
        conn = _conn()

        tvl_rows = conn.execute(
            """SELECT env, total_usd, ts FROM fl_snapshots
               WHERE (env, ts) IN (SELECT env, MAX(ts) FROM fl_snapshots GROUP BY env)
               ORDER BY env"""
        ).fetchall()

        cutoff = _ciclo_cutoff_utc()
        ops = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(profit),0) FROM protocol_ops WHERE ts > ?",
            (cutoff,)
        ).fetchone()

        cap = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_usd),0) FROM capital_cache WHERE total_usd > 1"
        ).fetchone()

        conn.close()
        return {
            "tvl_rows": tvl_rows or [],
            "tvl_total": sum(r[1] for r in tvl_rows) if tvl_rows else 0,
            "ops_count": ops[0] if ops else 0,
            "ops_profit": ops[1] if ops else 0,
            "cap_wallets": cap[0] if cap else 0,
            "cap_total": cap[1] if cap else 0,
        }
    except Exception:
        return {}
