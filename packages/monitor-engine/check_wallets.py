import sqlite3
from datetime import datetime, timedelta

db = 'webdex_v5_final.db'
c = sqlite3.connect(db)

print("=" * 50)
print("  304 WALLETS — ANALISE")
print("=" * 50)

# Total trades por wallet (top 15)
print("\n--- Top 15 wallets (mais trades) ---")
top = c.execute("""
    SELECT oo.wallet, COUNT(*) as n,
           MAX(o.data_hora) as ultimo_trade,
           SUM(CASE WHEN o.valor > 0 THEN 1 ELSE 0 END) as wins,
           SUM(CASE WHEN o.valor < 0 THEN 1 ELSE 0 END) as losses,
           ROUND(SUM(o.valor), 4) as lucro_total,
           COUNT(DISTINCT o.ambiente) as ambientes
    FROM op_owner oo
    JOIN operacoes o ON oo.hash = o.hash AND oo.log_index = o.log_index
    GROUP BY oo.wallet
    ORDER BY n DESC
    LIMIT 15
""").fetchall()

for wallet, n, ultimo, wins, losses, lucro, amb in top:
    w = wallet[:10] + "..." + wallet[-6:]
    print(f"  {w}  trades:{n:4}  W/L:{wins}/{losses}  lucro:{lucro:+.3f}  ultimo:{ultimo[:16]}")

# Quantas estao ativas hoje
hoje = datetime.now().strftime("%Y-%m-%d")
ativas_hoje = c.execute("""
    SELECT COUNT(DISTINCT oo.wallet) FROM op_owner oo
    JOIN operacoes o ON oo.hash=o.hash AND oo.log_index=o.log_index
    WHERE o.data_hora >= ?
""", (hoje + " 00:00:00",)).fetchone()[0]
print(f"\nWallets ativas HOJE:        {ativas_hoje}")

# Ativas esta semana
semana = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
ativas_semana = c.execute("""
    SELECT COUNT(DISTINCT oo.wallet) FROM op_owner oo
    JOIN operacoes o ON oo.hash=o.hash AND oo.log_index=o.log_index
    WHERE o.data_hora >= ?
""", (semana,)).fetchone()[0]
print(f"Wallets ativas esta semana: {ativas_semana}")

# Distribuicao por ambiente
print("\n--- Distribuicao por ambiente ---")
amb_dist = c.execute("""
    SELECT o.ambiente, COUNT(DISTINCT oo.wallet) as wallets, COUNT(*) as trades
    FROM op_owner oo
    JOIN operacoes o ON oo.hash=o.hash AND oo.log_index=o.log_index
    GROUP BY o.ambiente
""").fetchall()
for amb, wallets, trades in amb_dist:
    print(f"  {amb:15}  {wallets} wallets  {trades} trades")

# Ja monitoradas vs nao monitoradas pelo bot
registradas = c.execute("""
    SELECT COUNT(DISTINCT oo.wallet) FROM op_owner oo
    JOIN users u ON LOWER(u.wallet) = LOWER(oo.wallet)
""").fetchone()[0]
print(f"\nWallets com usuario no bot: {registradas}")
print(f"Wallets sem usuario no bot: {304 - registradas}  ← podem ser convidadas")

c.close()
