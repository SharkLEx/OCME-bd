"""
test_relatorio_21h.py — Dispara relatorio protocolo + animação bdZinho UMA VEZ (teste manual).
Uso: docker exec ocme-monitor python scripts/test_relatorio_21h.py

Story 15.3: assinatura atualizada para nova notify_protocolo_relatorio (pós 15.2)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from webdex_db import DB_LOCK, conn, cursor, get_config, now_br, _ciclo_21h_since
from webdex_discord_sync import notify_protocolo_relatorio, _WEBHOOK_RELATORIO

try:
    from webdex_discord_animate import animate_and_post as _animate
except Exception:
    _animate = None

hoje = now_br().strftime("%Y-%m-%d")

# protocol_ops.ts é UTC — converter corte BRT→UTC (+3h)
_dt_lim_brt = _ciclo_21h_since()
dt_lim = (
    datetime.strptime(_dt_lim_brt, "%Y-%m-%d %H:%M:%S") + timedelta(hours=3)
).strftime("%Y-%m-%d %H:%M:%S")

print(f"[teste] hoje={hoje}  ciclo BRT={_dt_lim_brt}  ciclo UTC={dt_lim}")

with DB_LOCK:
    pr = cursor.execute("""
        SELECT COUNT(DISTINCT wallet),
               COUNT(CASE WHEN profit>0 THEN 1 END),
               COUNT(*),
               ROUND(SUM(fee_bd),6),
               ROUND(SUM(CASE WHEN profit>0 THEN profit ELSE 0 END),4)
        FROM protocol_ops WHERE ts>=?
    """, (dt_lim,)).fetchone()

    tvl_row = cursor.execute("""
        SELECT ROUND(SUM(total_usd),2)
        FROM fl_snapshots WHERE ts = (SELECT MAX(ts) FROM fl_snapshots)
    """).fetchone()

    top5 = cursor.execute("""
        SELECT wallet,
               ROUND(SUM(profit),4),
               ROUND(SUM(fee_bd),4)
        FROM protocol_ops WHERE ts>=?
        GROUP BY wallet ORDER BY SUM(profit) DESC LIMIT 5
    """, (dt_lim,)).fetchall()

p_traders = int(pr[0] or 0)
p_wins    = int(pr[1] or 0)
p_total   = int(pr[2] or 0)
p_bd      = float(pr[3] or 0)
p_bruto   = float(pr[4] or 0)
p_wr      = (p_wins / p_total * 100) if p_total > 0 else 0.0
tvl_usd   = float(tvl_row[0] or 0) if tvl_row else 0.0

print(f"[teste] traders={p_traders} total={p_total} wins={p_wins} wr={p_wr:.1f}% bruto={p_bruto:.2f} bd={p_bd:.4f} tvl={tvl_usd:.0f}")

if p_total == 0:
    print("[teste] ⚠️ Sem ops no ciclo atual — relatório não enviado.")
    sys.exit(0)

notify_protocolo_relatorio(
    hoje=hoje,
    tvl_usd=tvl_usd,
    bd_periodo=p_bd,
    p_traders=p_traders,
    p_wr=p_wr,
    p_bruto=p_bruto,
    top_traders=top5,
    label="Ciclo 21h",
)
print("[teste] ✅ Relatório Discord enviado!")

# Animação bdZinho
if _animate and p_total > 0:
    ev = "relatorio_win" if p_bruto >= 0 else "relatorio_loss"
    em = "🟢" if p_bruto >= 0 else "🔴"
    pl = f"+${p_bruto:.2f}" if p_bruto >= 0 else f"-${abs(p_bruto):.2f}"
    _animate(
        ev, _WEBHOOK_RELATORIO,
        title=f"{em}  RELATÓRIO NOTURNO — WEbdEX PROTOCOL",
        description=(
            f"## {em} RESULTADO DO DIA\n"
            f"💎 **TVL:** `${tvl_usd:,.0f} USD`\n"
            f"📈 **P&L Bruto:** `{pl}`  ·  🎯 **WR {p_wr:.0f}%**\n"
            f"👥 **{p_traders} traders** · 📊 **{p_total:,} trades**\n"
            f"💰 **BD coletado:** `{p_bd:.4f} BD`\n"
            f"🗓️ {hoje}"
        ),
        color=0x00FF88 if p_bruto >= 0 else 0xFF4444,
    )
    print(f"[teste] 🎬 Animação bdZinho disparada ({ev})")
else:
    print("[teste] ⚠️ Sem animação (módulo indisponível)")
