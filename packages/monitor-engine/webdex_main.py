from __future__ import annotations
# ==============================================================================
# webdex_main.py — WEbdEX Monitor Engine — Entry Point
# Linhas fonte: ~8904-8915 (if __name__ == "__main__"), ~7381-7460 (_start_threads)
# ==============================================================================

import time
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

# Mapa name → factory para o watchdog poder reiniciar threads mortas
_THREAD_REGISTRY: dict[str, callable] = {
    "notif_worker":            _notif_worker,
    "chain_cache_worker":      _chain_cache_worker,
    "vigia":                   vigia,
    "sentinela":               sentinela,
    "agendador_21h":           agendador_21h,
    "capital_snapshot_worker": _capital_snapshot_worker,
    "user_capital_refresh":    _user_capital_refresh_worker,
    "funnel_worker":           _funnel_worker,
    "inactivity_auto_loop":    _inactivity_auto_loop,
}


def _start_threads():
    """Inicia todos os workers em background como threads daemon."""
    for name, target in _THREAD_REGISTRY.items():
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        logger.info(f"[main] Thread iniciada: {name}")


def _watchdog():
    """
    Monitora threads críticas a cada 30s e reinicia automaticamente as que morreram.
    Garante que o vigia e os workers nunca fiquem parados silenciosamente.
    """
    logger.info("[watchdog] Iniciado — monitorando %d threads.", len(_THREAD_REGISTRY))
    while True:
        time.sleep(30)
        try:
            alive_names = {t.name for t in threading.enumerate()}
            for name, target in _THREAD_REGISTRY.items():
                if name not in alive_names:
                    logger.warning("[watchdog] Thread '%s' morreu! Reiniciando...", name)
                    try:
                        t = threading.Thread(target=target, name=name, daemon=True)
                        t.start()
                        logger.info("[watchdog] Thread '%s' reiniciada com sucesso.", name)
                    except Exception as e:
                        logger.error("[watchdog] Falha ao reiniciar '%s': %s", name, e)
        except Exception as e:
            logger.error("[watchdog] Erro interno: %s", e)


def _polling_forever():
    """Inicia o polling do Telegram em loop com reconexão automática."""
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
    """Notifica TODOS os usuários ativos sobre reinício do bot (com rate limit seguro)."""
    try:
        from webdex_db import DB_LOCK, cursor
        from webdex_bot_core import send_html
        with DB_LOCK:
            rows = cursor.execute(
                "SELECT chat_id FROM users WHERE active=1"
            ).fetchall()
        logger.info("[main] Notificando %d usuários sobre reinício...", len(rows))
        for (cid,) in rows:
            try:
                send_html(int(cid), "🔄 <b>WEbdEX Monitor reiniciado.</b>\nMonitoramento ativo.")
                time.sleep(0.05)  # 20 msg/s — dentro do rate limit do Telegram
            except Exception:
                pass
    except Exception as e:
        logger.warning("[main] auto_resume_notify falhou: %s", e)


if __name__ == "__main__":
    logger.info("✅ WEbdEX Monitor Engine iniciando...")
    sanity_check()
    _start_threads()

    # Watchdog em thread separada (monitora e reinicia as demais)
    threading.Thread(target=_watchdog, name="watchdog", daemon=True).start()
    logger.info("[main] Watchdog iniciado.")

    auto_resume_notify()
    _polling_forever()
