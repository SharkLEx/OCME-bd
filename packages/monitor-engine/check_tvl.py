#!/usr/bin/env python3
"""check_tvl.py — Diagnóstico do TVL no relatório diário"""
import sqlite3, os
db = os.getenv('DB_PATH', '/app/data/webdex_v5_final.db')
c = sqlite3.connect(db)

cols = [r[1] for r in c.execute('PRAGMA table_info(fl_snapshots)').fetchall()]
print('fl_snapshots cols:', cols)

rows = c.execute('SELECT * FROM fl_snapshots WHERE ts=(SELECT MAX(ts) FROM fl_snapshots)').fetchall()
print(f'Snapshots recentes ({len(rows)} rows):')
for r in rows:
    print(' ', r)

tvl = c.execute('SELECT ROUND(SUM(total_usd),2) FROM fl_snapshots WHERE ts=(SELECT MAX(ts) FROM fl_snapshots)').fetchone()[0]
print(f'TVL via fl_snapshots: ${tvl}')

try:
    cap = c.execute('SELECT SUM(total_usd) FROM capital_cache').fetchone()[0]
    print(f'capital_cache total: ${round(cap,2) if cap else 0}')
    rows2 = c.execute('SELECT chat_id, env, total_usd FROM capital_cache ORDER BY total_usd DESC LIMIT 10').fetchall()
    print('Top capital_cache:')
    for r in rows2:
        print(f'  chat_id={r[0]} env={r[1]} total=${r[2]:.2f}')
except Exception as e:
    print(f'capital_cache: {e}')

try:
    sub_count = c.execute("SELECT COUNT(*) FROM fl_snapshots").fetchone()[0]
    ts_range = c.execute("SELECT MIN(ts), MAX(ts) FROM fl_snapshots").fetchone()
    print(f'fl_snapshots total rows: {sub_count}, range: {ts_range}')
except Exception as e:
    print(f'fl_snapshots info: {e}')

c.close()
