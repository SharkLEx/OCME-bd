#!/usr/bin/env python3
"""
fix_notifications.py — Diagnóstico e fix de usuários com active=0
Roda DENTRO do container ocme-monitor ou diretamente no ambiente com webdex.db

Uso:
  python fix_notifications.py           # diagnóstico + fix (padrão)
  python fix_notifications.py --dry-run # só diagnóstico, não altera DB
"""
import sys
import os
import sqlite3
from datetime import datetime

DRY_RUN = "--dry-run" in sys.argv

DB_PATH = os.getenv("DB_PATH") or os.getenv("WEbdEX_DB_PATH") or "webdex_v5_final.db"
print(f"[fix_notifications] DB_PATH = {DB_PATH}")
print(f"[fix_notifications] DRY_RUN = {DRY_RUN}")
print("=" * 60)

try:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
except Exception as e:
    print(f"ERRO: não foi possível abrir o banco: {e}")
    sys.exit(1)

# ── 1. Estado atual ─────────────────────────────────────────────
total   = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
ativos  = c.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
com_w   = c.execute("SELECT COUNT(*) FROM users WHERE wallet<>'' AND wallet IS NOT NULL").fetchone()[0]
inativos_com_wallet = c.execute("""
    SELECT COUNT(*) FROM users
    WHERE active=0 AND wallet<>'' AND wallet IS NOT NULL
""").fetchone()[0]

print(f"Total de usuários:           {total}")
print(f"Ativos (active=1):           {ativos}")
print(f"Com wallet:                  {com_w}")
print(f"Inativos COM wallet (BUG):   {inativos_com_wallet}  ← estes não recebem notificações")
print()

# ── 2. Listar afetados ─────────────────────────────────────────
rows = c.execute("""
    SELECT chat_id, wallet, active, last_seen_ts
    FROM users
    WHERE wallet<>'' AND wallet IS NOT NULL
    ORDER BY active ASC, last_seen_ts DESC
""").fetchall()

print("--- Usuários com wallet (active | last_seen | chat_id | wallet) ---")
affected = []
for chat_id, wallet, active, ts in rows:
    ts_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "nunca"
    status = "OK " if active else "❌ INATIVO"
    print(f"  [{status}] active={active} | {ts_str} | chat_id={chat_id} | {str(wallet)[:20]}...")
    if not active:
        affected.append(chat_id)

print()

# ── 3. Fix ────────────────────────────────────────────────────
if not affected:
    print("✅ Nenhum usuário com wallet está inativo. Problema é outro.")
    print()
    print("Verificar:")
    print("  1. DB_PATH correto? acima deve mostrar o arquivo certo")
    print("  2. Usuários têm wallet cadastrada?")
    print("  3. Logs do container: docker logs ocme-monitor --tail=100")
else:
    print(f"⚠️  {len(affected)} usuário(s) com wallet inativo(s): {affected}")
    if DRY_RUN:
        print("DRY_RUN ativo — nenhuma alteração feita.")
        print(f"Para aplicar: python fix_notifications.py")
    else:
        for cid in affected:
            c.execute("UPDATE users SET active=1 WHERE chat_id=?", (cid,))
        conn.commit()
        print(f"✅ {len(affected)} usuário(s) reativado(s). Notificações voltarão em até 60s (cache TTL).")

print()
print("--- Verificação pós-fix ---")
ativos_agora = c.execute("SELECT COUNT(*) FROM users WHERE active=1 AND wallet<>'' AND wallet IS NOT NULL").fetchone()[0]
print(f"Usuários ativos COM wallet: {ativos_agora}")

conn.close()
print("=" * 60)
