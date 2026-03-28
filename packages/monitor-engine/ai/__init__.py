"""
ai/ — Domínio de Inteligência Artificial do monitor-engine.

Módulos:
    vision      — Análise de imagens via Gemini/Claude Vision
    memory      — Memória de longo prazo (PostgreSQL + cache local)
    knowledge   — Base de conhecimento persistente (PostgreSQL)
    proactive   — Mensagens proativas baseadas em perfil do trader
    content     — Geração de conteúdo e copywriting
    user_profile — Perfis individuais de traders
    digest      — Digest diário/semanal do protocolo
    cycle_visual — Visualizações do ciclo 21h

Story 7.2 — módulos principais:
    chat        — Conversação + rate limiting IA (de webdex_ai.py)
    trainer     — Treinamento nightly + determinístico
    embeddings  — Busca semântica vault (nomic-embed-text-v1.5)
    image       — Geração de imagens (PIL cards branded)
    image_gen   — Geração de imagens IA (Gemini via OpenRouter)
"""
# Story 7.1 — módulos simples (sem dependências de handlers)
from ai.vision import *       # noqa: F401, F403
from ai.memory import *       # noqa: F401, F403
from ai.knowledge import *    # noqa: F401, F403
from ai.proactive import *    # noqa: F401, F403
from ai.content import *      # noqa: F401, F403
from ai.user_profile import * # noqa: F401, F403
from ai.digest import *       # noqa: F401, F403
from ai.cycle_visual import * # noqa: F401, F403

# Story 7.2 — módulos principais
from ai.chat import *         # noqa: F401, F403
from ai.trainer import *      # noqa: F401, F403
from ai.embeddings import *   # noqa: F401, F403
from ai.image import *        # noqa: F401, F403
from ai.image_gen import *    # noqa: F401, F403
