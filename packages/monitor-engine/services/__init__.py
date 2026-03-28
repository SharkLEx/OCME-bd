"""
services/ — Camada de lógica de negócio do monitor-engine.

Esta camada NÃO existia antes do Epic 7. É onde a lógica extraída
dos handlers será consolidada progressivamente.

Regra de dependência: services/ importa de core/, ai/, monitors/.
NUNCA importa de handlers/.

Módulos novos (criados nesta camada):
    subscription  — Tier check + gate de features (desbloqueia Epic 14)

Módulos wrappados (conteúdo de arquivos raiz):
    vault         — Escrita de notas Obsidian (webdex_vault_writer)
    discord_sync  — Sync de conteúdo para Discord (webdex_discord_sync)
    discord_animate — Animações Discord (webdex_discord_animate)
    image_engine  — Engine de imagens PIL (webdex_image_engine)
    onchain_notify — Notificações on-chain Discord (webdex_onchain_notify)
    swapbook_notify — Notificações SwapBook (webdex_swapbook_notify)
    milestones    — Conquistas e notificações de engajamento
    creatomate    — Geração de vídeos via Creatomate API

Story 7.4 — Epic 7: modularização do monolito Python
"""
# Módulo novo — interface para Epic 14
from services.subscription import (  # noqa: F401
    get_user_tier,
    can_use_feature,
    get_rate_limit_config,
    is_subscription_active,
    get_subscription_expiry,
)

# Módulos wrappados (conteúdo movido)
from services.vault import *          # noqa: F401, F403
from services.discord_sync import *   # noqa: F401, F403
from services.image_engine import *   # noqa: F401, F403
from services.onchain_notify import * # noqa: F401, F403
from services.milestones import *     # noqa: F401, F403
from services.creatomate import *     # noqa: F401, F403
