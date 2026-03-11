"""monitor-core — Vigia Modular do OCME Engine.

Loop principal de monitoramento on-chain com padrão EventEmitter.
Standalone: sem dependência do monolito webdex_*.py.

Uso:
    from vigia import Vigia, RpcPool, BlockTimeCache
    from sentinela import Sentinela
"""
from .vigia import Vigia, RpcPool, BlockTimeCache
from .sentinela import Sentinela

__all__ = ["Vigia", "RpcPool", "BlockTimeCache", "Sentinela"]
