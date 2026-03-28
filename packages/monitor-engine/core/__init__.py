"""
core/ — Infraestrutura base do monitor-engine.

Regra crítica: zero lógica de negócio. Zero imports de outros domínios do projeto.
Apenas stdlib, third-party e variáveis de ambiente.

Módulos:
    config      — Configuração de ambiente (.env), logger, constantes globais
    db          — Conexão SQLite, CRUD primitivo, migrations
    tools       — Tool Use / Function Calling para bdZinho (webdex_tools)
    observability — Prometheus metrics setup
    bot_core    — Core do bot Telegram (is_admin, etc.)

Story 7.3 — Epic 7: modularização do monolito Python
"""
from core.config import *       # noqa: F401, F403
from core.db import *           # noqa: F401, F403
from core.tools import *        # noqa: F401, F403
from core.observability import * # noqa: F401, F403
from core.bot_core import *     # noqa: F401, F403
