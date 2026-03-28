"""
workers/ — Background workers do monitor-engine.

Todos os workers background centralizados num único namespace.
webdex_main.py usa workers.registry.THREAD_REGISTRY para iniciar e monitorar.

Módulos:
    registry      — THREAD_REGISTRY centralizado + register_worker()
    core_workers  — Workers principais (sentinela, agendador, snapshots)
    notification  — Notification engine worker
    subscription  — Subscription on-chain worker
    metrics       — Prometheus metrics worker
    media         — Creatomate video worker

Story 7.5 — Epic 7: modularização do monolito Python
"""
from workers.registry import THREAD_REGISTRY, register_worker  # noqa: F401
