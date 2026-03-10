from __future__ import annotations
# ==============================================================================
# webdex_main.py — WEbdEX Monitor Engine — Entry Point
# Linhas fonte: ~8904-8915 (if __name__ == "__main__"), ~7381-7460 (_start_threads)
# ==============================================================================

import threading

from webdex_config import logger
from webdex_db import conn
from webdex_bot_core import bot, _notif_worker
from webdex_monitor import vigia
from webdex_chain import _chain_cache_worker
from webdex_workers import (
    sentinela,
    agendador_21h,
    _capital_snapshot_worker,
    _user_capital_refresh_worker,
    _funnel_worker,
    _inactivity_auto_loop,
)

# Importar handlers — registra os @bot.message_handler
import webdex_handlers.admin   # noqa: F401
import webdex_handlers.user    # noqa: F401
import webdex_handlers.reports # noqa: F401


def _start_threads():
    """Inicia todos os workers em background como threads daemon."""
    threads = [
        ("notif_worker",            _notif_worker),
        ("chain_cache_worker",      _chain_cache_worker),
        ("vigia",                   vigia),
        ("sentinela",               sentinela),
        ("agendador_21h",           agendador_21h),
        ("capital_snapshot_worker", _capital_snapshot_worker),
        ("user_capital_refresh",    _user_capital_refresh_worker),
        ("funnel_worker",           _funnel_worker),
        ("inactivity_auto_loop",    _inactivity_auto_loop),
    ]
    for name, target in threads:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        logger.info(f"[main] Thread iniciada: {name}")


def _polling_forever():
    """Inicia o polling do Telegram em loop com reconexão automática."""
    import time
    logger.info("[main] Bot iniciando polling...")
    while True:
        try:
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=20,
                allowed_updates=["message", "callback_query"],
                skip_pending=True,
            )
        except Exception as e:
            logger.warning(f"[main] Polling error — reconectando em 5s: {e}")
            time.sleep(5)


def sanity_check():
    """Verifica variáveis críticas antes de iniciar."""
    from webdex_config import TELEGRAM_TOKEN, RPC_URL
    issues = []
    if not TELEGRAM_TOKEN or ":" not in TELEGRAM_TOKEN:
        issues.append("TELEGRAM_TOKEN inválido ou não definido no .env")
    if not RPC_URL:
        issues.append("RPC_URL não definido no .env")
    if issues:
        for iss in issues:
            logger.error(f"[sanity] {iss}")
        raise SystemExit(f"[sanity] {len(issues)} problema(s) crítico(s). Verifique o .env.")
    logger.info("[sanity] OK — configuração válida.")


def auto_resume_notify():
    """Notifica usuários ativos sobre reinício do bot."""
    try:
        from webdex_db import DB_LOCK, cursor
        from webdex_bot_core import send_html
        with DB_LOCK:
            rows = cursor.execute(
                "SELECT chat_id FROM users WHERE active=1"
            ).fetchall()
        for (cid,) in rows[:5]:  # máximo 5 notificações de reinício
            try:
                send_html(int(cid), "🔄 <b>WEbdEX Monitor reiniciado.</b> Monitoramento ativo.")
            except Exception:
                pass
    except Exception:
        pass


if __name__ == "__main__":
    logger.info("✅ WEbdEX Monitor Engine iniciando...")
    sanity_check()
    _start_threads()
    auto_resume_notify()
    _polling_forever()
