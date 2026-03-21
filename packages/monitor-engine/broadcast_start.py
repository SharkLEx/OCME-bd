"""broadcast_start.py — Envia mensagem de boas-vindas/reconexão para TODOS os usuários.

Uso:
    python broadcast_start.py
    python broadcast_start.py --dry-run   (simula sem enviar)

Lê o token do .env ou TELEGRAM_TOKEN.
Envia mensagem personalizada:
  - Usuários COM wallet: confirmação de que estão conectados
  - Usuários SEM wallet: prompt para conectar a carteira
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time

import requests

# Windows: reconfigurar stdout para UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Config ──────────────────────────────────────────────────────────────────

def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v


_load_env()

TOKEN   = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH") or os.getenv("OCME_DB_PATH") or os.path.join(
    os.path.dirname(__file__), "webdex_v5_final.db"
)

# ── Mensagens ────────────────────────────────────────────────────────────────

MSG_COM_WALLET = """\
🔄 <b>WEbdEX Monitor — atualização disponível</b>

Seu monitoramento foi aprimorado com novos módulos de inteligência.

✅ Sua carteira <code>{wallet_short}</code> já está conectada.

Você agora recebe:
• Contexto on-chain real nas respostas da IA
• Dashboard com KPIs atualizados em tempo real
• Alertas de inatividade, gas e RPC mais precisos

Use /start para reabrir o menu principal.\
"""

MSG_SEM_WALLET = """\
🔄 <b>WEbdEX Monitor — atualização disponível</b>

Novos módulos de inteligência foram ativados.

⚠️ <b>Sua carteira ainda não está conectada.</b>

Para receber análises personalizadas com seus dados reais (P&L, capital, subcontas), conecte sua wallet:

👉 /start → <b>Conectar Wallet</b>

Sem a wallet, a IA responde com dados gerais do protocolo.\
"""

# ── Telegram send ─────────────────────────────────────────────────────────────

def _send(chat_id: int, text: str, dry_run: bool = False) -> bool:
    if dry_run:
        print(f"  [DRY] -> {chat_id}: {text[:60].replace(chr(10),' ')}...")
        return True
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        data = resp.json()
        if data.get("ok"):
            return True
        err = data.get("description", "")
        # Usuário bloqueou o bot ou chat inexistente — desativa silenciosamente
        if "bot was blocked" in err or "chat not found" in err or "user is deactivated" in err:
            print(f"  ⚠️  {chat_id}: {err} (ignorado)")
        else:
            print(f"  ❌ {chat_id}: {err}")
        return False
    except Exception as exc:
        print(f"  ❌ {chat_id}: {exc}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Broadcast start para todos os usuários")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem enviar")
    args = parser.parse_args()

    if not TOKEN:
        print("❌ TELEGRAM_TOKEN não configurado. Verifique o .env")
        return

    conn = sqlite3.connect(DB_PATH)
    users = conn.execute(
        "SELECT chat_id, wallet, active FROM users WHERE chat_id IS NOT NULL"
    ).fetchall()
    conn.close()

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Enviando para {len(users)} usuários...")
    print(f"DB: {DB_PATH}\n")

    ok = fail = skip = 0
    for chat_id, wallet, active in users:
        has_wallet = bool(wallet and str(wallet).startswith("0x"))
        if has_wallet:
            w_short = wallet[:6] + "..." + wallet[-4:]
            text = MSG_COM_WALLET.format(wallet_short=w_short)
        else:
            text = MSG_SEM_WALLET

        status_icon = "ON" if active else "off"
        print(f"  [{status_icon}] {chat_id} | wallet={'sim' if has_wallet else 'nao'}")

        sent = _send(int(chat_id), text, dry_run=args.dry_run)
        if sent:
            ok += 1
        else:
            fail += 1

        time.sleep(0.05)  # 20 msg/s — dentro do rate limit Telegram

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Resultado: ✅ {ok} enviados | ❌ {fail} falhas | ⏭️ {skip} ignorados")


if __name__ == "__main__":
    main()
