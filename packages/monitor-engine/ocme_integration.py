"""ocme_integration.py — Bridge entre o monolito webdex_*.py e os módulos Epic 7.

Inicializa os módulos modulares (DashboardCache, ContextBuilder) de forma lazy
e disponibiliza singletons seguros para uso no monolito.

Design:
- Zero crash: todos os imports são try/except — monolito continua se módulos
  não estiverem disponíveis.
- Lazy init: os singletons só são criados na primeira chamada, evitando
  overhead no boot do bot.
- Thread-safe: DashboardCache já é thread-safe internamente (threading.Lock).
"""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("ocme_integration")

# ── Adiciona packages/ ao sys.path para imports standalone ─────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_PKGS = os.path.normpath(os.path.join(_HERE, ".."))
for _p in [
    os.path.join(_PKGS, "monitor-report"),
    os.path.join(_PKGS, "monitor-ai"),
    os.path.join(_PKGS, "monitor-db"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Singletons ──────────────────────────────────────────────────────────────
_dashboard_cache = None
_context_builder = None
_DB_PATH: str = ""


def _db_path() -> str:
    global _DB_PATH
    if not _DB_PATH:
        _DB_PATH = (
            os.getenv("DB_PATH")
            or os.getenv("OCME_DB_PATH")
            or os.path.join(_HERE, "webdex_v5_final.db")
        )
    return _DB_PATH


def get_dashboard_cache():
    """Retorna o singleton DashboardCache (lazy init).

    Returns None se o módulo monitor-report não estiver disponível.
    """
    global _dashboard_cache
    if _dashboard_cache is not None:
        return _dashboard_cache
    try:
        from dashboard_cache import DashboardCache
        ttl = int(os.getenv("DASHBOARD_CACHE_TTL", "15"))
        _dashboard_cache = DashboardCache(db_path=_db_path(), ttl_seconds=ttl)
        logger.info("✅ DashboardCache inicializado (TTL=%ds, DB=%s)", ttl, _db_path())
    except Exception as exc:
        logger.warning("⚠️ DashboardCache indisponível: %s", exc)
        _dashboard_cache = None
    return _dashboard_cache


def get_context_builder():
    """Retorna o singleton ContextBuilder (lazy init).

    Returns None se o módulo monitor-ai não estiver disponível.
    """
    global _context_builder
    if _context_builder is not None:
        return _context_builder
    try:
        from context_builder import ContextBuilder
        _context_builder = ContextBuilder(db_path=_db_path())
        logger.info("✅ ContextBuilder inicializado (DB=%s)", _db_path())
    except Exception as exc:
        logger.warning("⚠️ ContextBuilder indisponível: %s", exc)
        _context_builder = None
    return _context_builder


def build_ai_context(wallet: str | None, period_h: int = 24) -> str | None:
    """Constrói contexto on-chain real para a IA via ContextBuilder.

    Args:
        wallet: endereço 0x... do usuário (ou None para contexto de protocolo).
        period_h: janela de tempo em horas (default 24).

    Returns:
        String formatada com o snapshot de dados reais, ou None se indisponível.
    """
    if not wallet:
        return None
    cb = get_context_builder()
    if cb is None:
        return None
    try:
        period_str = {1: "1h", 6: "6h", 24: "24h", 168: "7d", 720: "30d"}.get(
            period_h, f"{period_h}h"
        )
        ctx = cb.build(wallet=wallet, period=period_str)
        return cb.to_system_prompt(ctx)
    except Exception as exc:
        logger.debug("ContextBuilder.build falhou: %s", exc)
        return None


def notify_new_operation(op: dict) -> None:
    """Notifica DashboardCache de nova operação registrada.

    Chamado pelo process_log() do monolito após registrar_operacao() == True.

    Args:
        op: dicionário com dados da operação (tipo, valor, gas_usd, wallet, ambiente, ...)
    """
    cache = get_dashboard_cache()
    if cache is None:
        return
    try:
        cache.on_new_op(op)
    except Exception as exc:
        logger.debug("DashboardCache.on_new_op falhou: %s", exc)


def notify_vigia_progress(progress: dict) -> None:
    """Notifica DashboardCache do fim de um ciclo do Vigia.

    Chamado pelo vigia() do monolito após processar um range de blocos.

    Args:
        progress: dicionário com dados do loop (last_block, loops, latency_ms, ...)
    """
    cache = get_dashboard_cache()
    if cache is None:
        return
    try:
        cache.on_progress(progress)
    except Exception as exc:
        logger.debug("DashboardCache.on_progress falhou: %s", exc)
