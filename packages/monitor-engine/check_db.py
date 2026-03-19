import sqlite3
from datetime import datetime, timedelta, timezone

db = 'data/webdex_v5_final.db'
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=3)

print("=== TVL POR AMBIENTE ===")
tvl = c.execute(
    """SELECT env, total_usd, ts FROM fl_snapshots
       WHERE (env, ts) IN (SELECT env, MAX(ts) FROM fl_snapshots GROUP BY env)
       ORDER BY env"""
).fetchall()
for r in tvl:
    print(r)

print("\n=== OPERACOES CICLO ATUAL ===")
now_br = datetime.now(timezone.utc) - timedelta(hours=3)
cutoff_br = now_br.replace(hour=21, minute=0, second=0, microsecond=0)
if now_br < cutoff_br:
    cutoff_br -= timedelta(days=1)
cutoff_utc = (cutoff_br + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
ops = c.execute(
    "SELECT COUNT(*), COALESCE(SUM(profit),0) FROM protocol_ops WHERE ts > ?",
    (cutoff_utc,)
).fetchone()
print(f"ops desde 21h BR: {ops[0]}, profit: {ops[1]:.4f}")

print("\n=== CAPITAL USUARIOS ===")
cap = c.execute(
    "SELECT COUNT(*), COALESCE(SUM(total_usd),0) FROM capital_cache WHERE total_usd > 1"
).fetchone()
print(f"carteiras: {cap[0]}, total: ${cap[1]:,.0f}")

c.close()
print("\n=== DB OK ===")
