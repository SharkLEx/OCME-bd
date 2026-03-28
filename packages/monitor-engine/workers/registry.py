"""
workers/registry.py — Thread Registry do monitor-engine.

Centraliza todos os workers background num único dicionário.
webdex_main.py usa este registry para iniciar e monitorar threads.

Story 7.5 — Epic 7: modularização do monolito Python
"""
from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

# ── Imports de workers via stubs (compatibilidade total) ──────────────────────
from webdex_bot_core import _notif_worker
from webdex_chain import _chain_cache_worker
from webdex_monitor import vigia
from webdex_workers import (
    sentinela,
    agendador_21h,
    agendador_horario,
    _capital_snapshot_worker,
    _user_capital_refresh_worker,
    _funnel_worker,
    _inactivity_auto_loop,
    _fl_snapshot_worker,
    _protocol_ops_sync_worker,
)
from webdex_anomaly import anomaly_worker
from subscription_worker import subscription_worker
from webdex_milestones import milestone_worker
from webdex_swapbook_notify import swapbook_notify_worker
from webdex_onchain_notify import onchain_notify_worker
from webdex_network_notify import network_notify_worker
from notification_engine import notification_engine_worker
from webdex_v4_monitor import v4_subaccount_worker
from webdex_socios_monitor import socios_monitor_worker
from webdex_network_dash import network_fees_dash_worker

# ── Registry base — workers obrigatórios ─────────────────────────────────────
THREAD_REGISTRY: dict[str, Callable] = {
    "notif_worker":             _notif_worker,
    "chain_cache_worker":       _chain_cache_worker,
    "vigia":                    vigia,
    "sentinela":                sentinela,
    "agendador_21h":            agendador_21h,
    "agendador_horario":        agendador_horario,
    "capital_snapshot_worker":  _capital_snapshot_worker,
    "user_capital_refresh":     _user_capital_refresh_worker,
    "funnel_worker":            _funnel_worker,
    "inactivity_auto_loop":     _inactivity_auto_loop,
    "fl_snapshot_worker":       _fl_snapshot_worker,
    "protocol_ops_sync":        _protocol_ops_sync_worker,
    "anomaly_worker":           anomaly_worker,
    "milestone_worker":         milestone_worker,
    "swapbook_notify_worker":   swapbook_notify_worker,
    "onchain_notify_worker":    onchain_notify_worker,
    "network_notify_worker":    network_notify_worker,
    "notification_engine_worker": notification_engine_worker,
    "subscription_worker":      subscription_worker,
    "v4_subaccount_worker":     v4_subaccount_worker,
    "socios_monitor_worker":    socios_monitor_worker,
    "network_fees_dash_worker": network_fees_dash_worker,
}

# ── Workers opcionais (graceful degradation) ─────────────────────────────────

# Story 18.x — Nightly Trainers
try:
    from webdex_deterministic_trainer import deterministic_trainer_worker
    THREAD_REGISTRY["deterministic_trainer_worker"] = deterministic_trainer_worker
    logger.info("[workers.registry] deterministic_trainer_worker: ATIVO")
except ImportError:
    logger.warning("[workers.registry] deterministic_trainer_worker: não disponível")

# Story 23.1 — Vault Embeddings Worker
try:
    from webdex_ai_vault_embeddings import vault_embeddings_worker
    THREAD_REGISTRY["vault_embeddings_worker"] = vault_embeddings_worker
    logger.info("[workers.registry] vault_embeddings_worker: ATIVO")
except ImportError:
    logger.warning("[workers.registry] vault_embeddings_worker: não disponível")

# Story 13.1 — Dashboard API Worker (Epic 13 — Dashboard Externo)
try:
    from webdex_dashboard_api import dashboard_api_worker
    THREAD_REGISTRY["dashboard_api_worker"] = dashboard_api_worker
    logger.info("[workers.registry] dashboard_api_worker: ATIVO (127.0.0.1:8765)")
except ImportError:
    logger.warning("[workers.registry] dashboard_api_worker: fastapi/uvicorn não instalados — API não iniciada")


def register_worker(name: str, target: Callable) -> None:
    """Registra um worker adicional no registry (uso pelo Epic 14 e futuros epics)."""
    THREAD_REGISTRY[name] = target
    logger.info("[workers.registry] Worker registrado: %s", name)
