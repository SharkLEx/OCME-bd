import sqlite3
from datetime import datetime

db = 'webdex_v5_final.db'
c = sqlite3.connect(db)

print("=" * 45)
print("  USUARIOS DO BOT — RESUMO")
print("=" * 45)

# Total geral
total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
print(f"\nTotal cadastrado:     {total}")

# Ativos (active=1)
ativos = c.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
print(f"Ativos (active=1):    {ativos}")

# Com carteira configurada
com_wallet = c.execute("SELECT COUNT(*) FROM users WHERE wallet IS NOT NULL AND wallet != ''").fetchone()[0]
print(f"Com carteira:         {com_wallet}")

# Vistos nas ultimas 24h
recentes_24h = c.execute("""
    SELECT COUNT(*) FROM users
    WHERE last_seen_ts > strftime('%s','now') - 86400
""").fetchone()[0]
print(f"Ativos ultimas 24h:   {recentes_24h}")

# Vistos nos ultimos 7 dias
recentes_7d = c.execute("""
    SELECT COUNT(*) FROM users
    WHERE last_seen_ts > strftime('%s','now') - 604800
""").fetchone()[0]
print(f"Ativos ultimos 7d:    {recentes_7d}")

# Distribuicao por ambiente
print("\n--- Por ambiente ---")
envs = c.execute("SELECT env, COUNT(*) FROM users GROUP BY env ORDER BY COUNT(*) DESC").fetchall()
for env, cnt in envs:
    print(f"  {env or 'N/A':20} {cnt}")

# Usuarios com operacoes (ja fizeram pelo menos 1 trade)
com_trades = c.execute("""
    SELECT COUNT(DISTINCT oo.wallet)
    FROM op_owner oo
""").fetchone()[0]
print(f"\nWallets com trades:   {com_trades}")

# Total de wallets distintas nas operacoes
wallets_op = c.execute("SELECT COUNT(DISTINCT wallet) FROM op_owner").fetchone()[0]
print(f"Wallets distintas:    {wallets_op}")

# Top 5 usuarios com mais operacoes
print("\n--- Top 5 subcontas (mais trades) ---")
top = c.execute("""
    SELECT sub_conta, ambiente, COUNT(*) as n
    FROM operacoes
    GROUP BY sub_conta, ambiente
    ORDER BY n DESC
    LIMIT 5
""").fetchall()
for sub, amb, n in top:
    print(f"  {sub:25} [{amb}]  {n} trades")

print("\n" + "=" * 45)
c.close()
