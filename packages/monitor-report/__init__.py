"""monitor-report — Cache de Dashboard e Relatórios do OCME Engine.

DashboardCache: KPIs pré-calculados para resposta < 500ms.
Liga ao Vigia via eventos 'operation' e 'progress'.

Standalone: sem dependência do monolito webdex_*.py.
"""
from .dashboard_cache import DashboardCache

__all__ = ["DashboardCache"]
