from __future__ import annotations
# webdex_main.py — Entry Point (Story 7.5 — workers movidos para workers/)

import os, signal, sys, time, threading

from webdex_config import logger
from workers.registry import THREAD_REGISTRY

# Registra handlers Telegram (side-effect: @bot.message_handler)
import webdex_handlers.admin    # noqa: F401
import webdex_handlers.user     # noqa: F401
import webdex_handlers.reports  # noqa: F401
from webdex_bot_core import bot


def _start_threads():
    for name, target in THREAD_REGISTRY.items():
        threading.Thread(target=target, name=name, daemon=True).start()
        logger.info("[main] Thread iniciada: %s", name)


def _watchdog():
    logger.info("[watchdog] Monitorando %d threads.", len(THREAD_REGISTRY))
    while True:
        time.sleep(30)
        try:
            alive = {t.name for t in threading.enumerate()}
            for name, target in THREAD_REGISTRY.items():
                if name not in alive:
                    logger.warning("[watchdog] Thread '%s' morreu — reiniciando.", name)
                    try:
                        threading.Thread(target=target, name=name, daemon=True).start()
                    except Exception as e:
                        logger.error("[watchdog] Falha ao reiniciar '%s': %s", name, e)
        except Exception as e:
            logger.error("[watchdog] Erro: %s", e)


def _polling_forever():
    logger.info("[main] Bot polling iniciado.")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20,
                                 allowed_updates=["message", "callback_query"],
                                 skip_pending=True)
        except Exception as e:
            logger.warning("[main] Polling error — reconectando em 5s: %s", e)
            time.sleep(5)


def sanity_check():
    from webdex_config import TELEGRAM_TOKEN, RPC_URL
    issues = ([f"TELEGRAM_TOKEN inválido"] if not TELEGRAM_TOKEN or ":" not in TELEGRAM_TOKEN else []) + \
             ([f"RPC_URL não definido"] if not RPC_URL else [])
    if issues:
        [logger.error("[sanity] %s", i) for i in issues]
        raise SystemExit(f"[sanity] {len(issues)} problema(s). Verifique o .env.")
    logger.info("[sanity] OK — %d workers registrados.", len(THREAD_REGISTRY))


if __name__ == "__main__":
    logger.info("✅ WEbdEX Monitor Engine iniciando...")
    sanity_check()
    try:
        from ocme_integration import get_dashboard_cache, get_context_builder
        get_dashboard_cache(); get_context_builder()
    except Exception:
        pass
    _start_threads()
    try:
        from webdex_observability import ObservabilityServer
        from webdex_monitor import HEALTH as _HEALTH
        ObservabilityServer(port=int(os.environ.get("METRICS_PORT", 9090)),
                            db_path=os.environ.get("DB_PATH", "webdex_v5_final.db"),
                            health_ref=_HEALTH).start(daemon=True)
    except Exception as e:
        logger.warning("[main] Observability server não iniciado: %s", e)
    threading.Thread(target=_watchdog, name="watchdog", daemon=True).start()
    signal.signal(signal.SIGTERM, lambda s, f: (time.sleep(3), sys.exit(0)))
    _polling_forever()
