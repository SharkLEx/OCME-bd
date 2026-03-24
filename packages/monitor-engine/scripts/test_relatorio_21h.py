"""
test_relatorio_21h.py — Dispara relatorio protocolo + animação bdZinho UMA VEZ (teste manual).

Uso:
  docker exec ocme-monitor python scripts/test_relatorio_21h.py            # envia
  docker exec ocme-monitor python scripts/test_relatorio_21h.py --dry-run  # só imprime, não envia

Story 15.3: assinatura atualizada para nova notify_protocolo_relatorio (pós 15.2)
Fix: janela do ciclo FECHADO (ontem 21h BRT → hoje 21h BRT), não ciclo aberto
"""
import sys, os
DRY_RUN = "--dry-run" in sys.argv
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
from webdex_db import DB_LOCK, conn, cursor, get_config, now_br, _ciclo_21h_since
from webdex_discord_sync import notify_protocolo_relatorio, notify_protocolo_relatorio_telegram, _WEBHOOK_RELATORIO

try:
    from webdex_render_pil import render_e_postar_relatorio as _pil_render
except Exception:
    _pil_render = None

hoje = now_br().strftime("%Y-%m-%d")

# protocol_ops.ts é UTC — ciclo FECHADO: ontem 21h BRT → hoje 21h BRT
# Mesmo cálculo do agendador_21h em webdex_workers.py
_ciclo_fim_brt = datetime.strptime(_ciclo_21h_since(), "%Y-%m-%d %H:%M:%S")
_ciclo_inicio_brt = _ciclo_fim_brt - timedelta(hours=24)
dt_lim = (_ciclo_inicio_brt + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")  # UTC
dt_fim = (_ciclo_fim_brt   + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")  # UTC

print(f"[teste] hoje={hoje}")
print(f"[teste] ciclo fechado BRT: {_ciclo_inicio_brt.strftime('%Y-%m-%d %H:%M')} → {_ciclo_fim_brt.strftime('%Y-%m-%d %H:%M')}")
print(f"[teste] janela UTC: {dt_lim} → {dt_fim}")

with DB_LOCK:
    pr = cursor.execute("""
        SELECT COUNT(DISTINCT wallet),
               COUNT(CASE WHEN profit>0 THEN 1 END),
               COUNT(*),
               ROUND(SUM(fee_bd),6),
               ROUND(SUM(CASE WHEN profit>0 THEN profit ELSE 0 END),4),
               ROUND(SUM(gas_pol),6)
        FROM protocol_ops WHERE ts>=? AND ts<?
    """, (dt_lim, dt_fim)).fetchone()

    # Per-env max — soma o snapshot mais recente de CADA ambiente
    tvl_row = cursor.execute("""
        SELECT ROUND(SUM(f.total_usd),2)
        FROM fl_snapshots f
        INNER JOIN (SELECT env, MAX(ts) AS max_ts FROM fl_snapshots GROUP BY env) latest
          ON f.env=latest.env AND f.ts=latest.max_ts
    """).fetchone()

    top5 = cursor.execute("""
        SELECT wallet,
               ROUND(SUM(profit),4),
               ROUND(SUM(fee_bd),4)
        FROM protocol_ops WHERE ts>=? AND ts<?
        GROUP BY wallet ORDER BY SUM(profit) DESC LIMIT 5
    """, (dt_lim, dt_fim)).fetchall()

p_traders = int(pr[0] or 0)
p_wins    = int(pr[1] or 0)
p_total   = int(pr[2] or 0)
p_bd      = float(pr[3] or 0)
p_bruto   = float(pr[4] or 0)
p_gas_pol = float(pr[5] or 0)
p_wr      = (p_wins / p_total * 100) if p_total > 0 else 0.0
tvl_usd   = float(tvl_row[0] or 0) if tvl_row else 0.0

print(f"[teste] traders={p_traders} total={p_total} wins={p_wins} wr={p_wr:.1f}% bruto={p_bruto:.2f} bd={p_bd:.4f} tvl={tvl_usd:.0f}")

if p_total == 0:
    print("[teste] ⚠️ Sem ops no ciclo fechado — relatório não enviado.")
    sys.exit(0)

em = "🟢" if p_bruto >= 0 else "🔴"
pl = f"+${p_bruto:.2f}" if p_bruto >= 0 else f"-${abs(p_bruto):.2f}"
print(f"\n{'='*50}")
print(f"  PREVIEW — RELATÓRIO CICLO 21H")
print(f"  {_ciclo_inicio_brt.strftime('%d/%m %Hh')} → {_ciclo_fim_brt.strftime('%d/%m %Hh')} BRT")
print(f"{'='*50}")
print(f"  {em} P&L Bruto:  {pl}")
print(f"  🎯 WinRate:   {p_wr:.1f}%  ({p_wins}/{p_total} trades)")
print(f"  👥 Traders:   {p_traders}")
print(f"  💧 Liquidez LP: ${tvl_usd:,.0f}")
print(f"  💰 BD:        {p_bd:.4f}")
print(f"  📅 Data:      {hoje}")
if top5:
    print(f"\n  Top traders:")
    for w, profit, fee in top5:
        print(f"    {w[:6]}...{w[-4:]}  P&L: ${profit:.4f}  Fee: {fee:.4f}")
print(f"{'='*50}\n")

if DRY_RUN:
    print("[teste] --dry-run: dados acima corretos? Rode sem --dry-run para enviar.")
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

# Broadcast Telegram — bot.send_message direto (síncrono) para garantir flush antes do script encerrar
try:
    from webdex_bot_core import bot as _tg_bot
    _tg_msg = notify_protocolo_relatorio_telegram(
        hoje=hoje,
        tvl_usd=tvl_usd,
        bd_periodo=p_bd,
        p_traders=p_traders,
        p_wr=p_wr,
        p_bruto=p_bruto,
        top_traders=top5,
        label="Ciclo 21h",
    )
    with DB_LOCK:
        tg_users = cursor.execute(
            "SELECT DISTINCT chat_id FROM users WHERE active=1"
        ).fetchall()
    tg_sent = 0
    for (uid,) in tg_users:
        try:
            _tg_bot.send_message(int(uid), _tg_msg, parse_mode="HTML", disable_web_page_preview=True)
            tg_sent += 1
        except Exception as _te:
            print(f"[teste] ⚠️ Telegram uid={uid}: {_te}")
    print(f"[teste] ✅ Relatório Telegram enviado para {tg_sent} usuário(s).")
except Exception as _tg_err:
    print(f"[teste] ⚠️ Broadcast Telegram falhou: {_tg_err}")

# Imagem PIL — nodo designer interno (zero APIs externas)
if _pil_render and p_total > 0:
    print("[teste] 🎨 Gerando imagem PIL branded...")
    ok = _pil_render(
        pnl     = p_bruto,
        trades  = p_total,
        wins    = p_wins,
        traders = p_traders,
        tvl_usd = tvl_usd,
        bd      = p_bd,
        data    = hoje,
    )
    print(f"[teste] {'✅ Imagem PIL postada no Discord!' if ok else '⚠️ PIL render falhou — sem imagem'}")
else:
    print("[teste] ⚠️ PIL render indisponível")
