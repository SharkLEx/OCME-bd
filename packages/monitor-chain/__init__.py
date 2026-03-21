"""monitor-chain — Camada Web3 do OCME Engine.

BlockFetcher: busca logs on-chain com chunking e failover RPC.
OperationParser: decodifica logs brutos em operações OCME.

Standalone: sem dependência do monolito webdex_*.py.
"""
from .block_fetcher import BlockFetcher
from .operation_parser import OperationParser

__all__ = ["BlockFetcher", "OperationParser"]
