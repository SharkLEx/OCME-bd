"""
test_relatorio_21h.py — Dispara relatorio protocolo + animação bdZinho UMA VEZ (teste manual).
Uso: docker exec ocme-monitor python scripts/test_relatorio_21h.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from webdex_db import DB_LOCK, conn, cursor, get_config, now_br, _ciclo_21h_since
from webdex_discord_sync import notify_protocolo_relatorio, _WEBHOOK_RELATORIO
from webdex_chain import chain_pol_price

try:
    from webdex_discord_animate import animate_and_post as _animate
except Exception:
    _animate = None

hoje = now_br().strftime("%Y-%m-%d")
pol_price = chain_pol_price()
dt_lim = _ciclo_21h_since()

print(f"[teste] hoje={hoje}  pol={pol_price:.4f}  ciclo desde={dt_lim}")

with DB_LOCK:
    pr = cursor.execute("""
        SELECT COUNT(*), COUNT(DISTINCT wallet),
               ROUND(SUM(profit),4),
               COUNT(CASE WHEN profit>0 THEN 1 END),
               ROUND(SUM(fee_bd),6),
               ROUND(SUM(gas_pol),6),
               ROUND(SUM(CASE WHEN profit>0 THEN profit ELSE 0 END),4),
               ROUND(SUM(CASE WHEN profit<0 THEN profit ELSE 0 END),4)
        FROM protocol_ops WHERE ts>=?
    """, (dt_lim,)).fetchone()
    bd_all = float(cursor.execute(
        "SELECT ROUND(SUM(fee_bd),4) FROM protocol_ops WHERE fee_bd>0"
    ).fetchone()[0] or 0)
    proto_count = int(cursor.execute(
        "SELECT COUNT(*) FROM protocol_ops"
    ).fetchone()[0] or 0)
    top5 = cursor.execute("""
        SELECT wallet, ROUND(SUM(profit),4), COUNT(*),
               ROUND(SUM(fee_bd),4), ROUND(SUM(gas_pol),4)
        FROM protocol_ops WHERE ts>=?
        GROUP BY wallet ORDER BY SUM(profit) DESC LIMIT 5
    """, (dt_lim,)).fetchall()

p_trades  = int(pr[0] or 0)
p_traders = int(pr[1] or 0)
p_lucro   = float(pr[2] or 0)
p_wins    = int(pr[3] or 0)
p_bd      = float(pr[4] or 0)
p_gas_pol = float(pr[5] or 0)
p_ganhos  = float(pr[6] or 0)
p_perdas  = float(pr[7] or 0)
p_gas_usd = p_gas_pol * pol_price

print(f"[teste] trades={p_trades} traders={p_traders} lucro={p_lucro:.2f} ganhos={p_ganhos:.2f} perdas={p_perdas:.2f}")
print(f"[teste] gas_pol={p_gas_pol:.4f} bd={p_bd:.4f} bd_alltime={bd_all:.4f} proto={proto_count}")

notify_protocolo_relatorio(
    hoje=hoje,
    pol_price=pol_price,
    p_trades=p_trades,
    p_traders=p_traders,
    p_lucro=p_lucro,
    p_ganhos=p_ganhos,
    p_perdas=p_perdas,
    p_wins=p_wins,
    p_gas_pol=p_gas_pol,
    p_gas_usd=p_gas_usd,
    p_bd=p_bd,
    bd_alltime=bd_all,
    proto_count=proto_count,
    top_traders=top5,
    label="Ciclo 21h",
)
print("[teste] ✅ Relatório Discord enviado!")

# Animação bdZinho
if _animate and p_trades > 0:
    ev = "relatorio_win" if p_lucro >= 0 else "relatorio_loss"
    em = "🟢" if p_lucro >= 0 else "🔴"
    pl = f"+${p_lucro:.2f}" if p_lucro >= 0 else f"-${abs(p_lucro):.2f}"
    wr = (p_wins / p_trades * 100) if p_trades > 0 else 0.0
    _animate(
        ev, _WEBHOOK_RELATORIO,
        title=f"{em}  RELATÓRIO NOTURNO — WEbdEX PROTOCOL",
        description=(
            f"## {em} RESULTADO DO DIA\n"
            f"💎 **P&L Protocolo:** `{pl}`\n"
            f"📊 **Trades:** {p_trades:,}  |  **WR:** {wr:.1f}%\n"
            f"👥 **Traders únicos:** {p_traders}"
        ),
    )
    print(f"[teste] 🎬 Animação bdZinho disparada ({ev})")
else:
    print("[teste] ⚠️ Sem animação (sem trades ou módulo indisponível)")
