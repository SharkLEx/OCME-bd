import sqlite3, time

db = 'webdex_v5_final.db'
c = sqlite3.connect(db)

print("=== ULTIMAS 5 OPERACOES ===")
rows = c.execute("SELECT data_hora, tipo, valor, sub_conta, ambiente FROM operacoes ORDER BY rowid DESC LIMIT 5").fetchall()
for r in rows:
    print(r)

print("\n=== CONFIG ===")
lb = c.execute("SELECT valor FROM config WHERE chave='last_block'").fetchone()
print("last_block:", lb[0] if lb else "N/A")

tot = c.execute("SELECT COUNT(*) FROM operacoes").fetchone()
print("total operacoes:", tot[0])

print("\n=== OPERACOES ULTIMA HORA ===")
from datetime import datetime, timedelta
one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
recent = c.execute("SELECT COUNT(*) FROM operacoes WHERE data_hora >= ?", (one_hour_ago,)).fetchone()
print("operacoes ultima 1h:", recent[0])

c.close()
