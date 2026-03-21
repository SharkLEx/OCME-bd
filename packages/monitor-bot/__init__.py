"""monitor-bot — Telegram UI Layer do OCME Engine.

Notifier: recebe eventos do Vigia e Sentinela, envia notificações Telegram.
Pura camada de UI — toda lógica de dados vem de monitor-db/monitor-report.

Story 7.6: Bot como UI (zero RPC direto nos handlers).

Standalone: sem dependência do monolito webdex_*.py.
"""
from .notifier import Notifier

__all__ = ["Notifier"]
