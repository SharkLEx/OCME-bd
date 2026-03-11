"""monitor-chain/block_fetcher.py — BlockFetcher standalone.

Responsável por buscar logs de blocos via Web3 com chunking configurável
e recuperação de falhas. Não depende do monolito webdex_*.py.

Uso:
    from block_fetcher import BlockFetcher

    fetcher = BlockFetcher(rpc_urls=[...], chunk_size=25)
    logs = fetcher.get_logs_range(
        from_block=1000000, to_block=1000100,
        addresses=["0xABC..."], topics=["0xDEF..."]
    )
"""

from __future__ import annotations

import itertools
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("monitor-chain.block_fetcher")


def _is_429_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "rate" in s or "limit" in s or "too many" in s


def _get_poa_mw():
    try:
        from web3.middleware import geth_poa_middleware
        return geth_poa_middleware
    except ImportError:
        pass
    try:
        from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware
        return ExtraDataToPOAMiddleware
    except ImportError:
        return None


class BlockFetcher:
    """Busca logs on-chain com chunking, deduplicação e failover RPC.

    Parâmetros:
        rpc_urls:   Lista de endpoints RPC (round-robin + cooldown)
        chunk_size: Blocos por requisição (default: 25, configurável)
        timeout:    Timeout HTTP por chamada RPC (default: 25s)
        on_error:   Callback opcional (exc) para erros de RPC
    """

    _COOLDOWN_BASE = 60.0

    def __init__(
        self,
        rpc_urls: List[str],
        chunk_size: int = 25,
        timeout: int = 25,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        from web3 import Web3
        self._Web3 = Web3
        self._chunk_size = max(1, chunk_size)
        self._on_error = on_error
        poa_mw = _get_poa_mw()

        self._instances: List[Any] = []
        self._errors: List[int] = []
        self._cooldown_until: List[float] = []

        for url in rpc_urls:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": timeout}))
            if poa_mw:
                try:
                    w3.middleware_onion.inject(poa_mw, layer=0)
                except Exception:
                    pass
            self._instances.append(w3)
            self._errors.append(0)
            self._cooldown_until.append(0.0)

        self._cycle = itertools.cycle(range(len(rpc_urls)))

    # ── RPC management ────────────────────────────────────────────────────
    def _next_healthy(self) -> Tuple[int, Any]:
        now = time.time()
        for _ in range(len(self._instances)):
            idx = next(self._cycle)
            if now >= self._cooldown_until[idx]:
                return idx, self._instances[idx]
        idx = min(range(len(self._instances)), key=lambda i: self._cooldown_until[i])
        return idx, self._instances[idx]

    def _mark_error(self, idx: int):
        self._errors[idx] += 1
        cd = min(300.0, self._COOLDOWN_BASE * self._errors[idx])
        self._cooldown_until[idx] = time.time() + cd
        logger.warning("[block_fetcher] endpoint #%d erro #%d — cooldown %.0fs", idx, self._errors[idx], cd)

    def _mark_ok(self, idx: int):
        self._errors[idx] = 0
        self._cooldown_until[idx] = 0.0

    # ── Public API ────────────────────────────────────────────────────────
    def current_block(self) -> int:
        """Retorna o bloco mais recente da chain."""
        for _ in range(len(self._instances)):
            idx, w3 = self._next_healthy()
            try:
                result = int(w3.eth.block_number)
                self._mark_ok(idx)
                return result
            except Exception as exc:
                if _is_429_error(exc):
                    self._mark_error(idx)
                    continue
                if self._on_error:
                    self._on_error(exc)
                raise
        raise RuntimeError("BlockFetcher: todos endpoints indisponíveis")

    def get_logs_single(
        self,
        from_block: int,
        to_block: int,
        addresses: List[str],
        topics: List[str],
    ) -> List[Dict]:
        """Busca logs em um único intervalo (sem chunking)."""
        W3 = self._Web3
        params = {
            "fromBlock": W3.to_hex(from_block),
            "toBlock":   W3.to_hex(to_block),
            "address":   addresses,
            "topics":    topics,
        }
        return self._safe_get_logs(params)

    def get_logs_range(
        self,
        from_block: int,
        to_block: int,
        addresses: List[str],
        topics: List[str],
        chunk_size: Optional[int] = None,
    ) -> List[Dict]:
        """Busca logs em [from_block, to_block] com chunking automático."""
        chunk = max(1, chunk_size or self._chunk_size)
        result: List[Dict] = []
        cur = from_block
        while cur <= to_block:
            nxt = min(to_block, cur + chunk - 1)
            logs = self.get_logs_single(cur, nxt, addresses, topics)
            result.extend(logs)
            cur = nxt + 1
        return result

    def get_block_timestamp(self, block_number: int) -> Optional[float]:
        """Retorna timestamp Unix do bloco. None em falha."""
        for _ in range(len(self._instances)):
            idx, w3 = self._next_healthy()
            try:
                block = w3.eth.get_block(block_number)
                self._mark_ok(idx)
                return float(block["timestamp"])
            except Exception as exc:
                if _is_429_error(exc):
                    self._mark_error(idx)
                    continue
                logger.debug("get_block_timestamp(%d): %s", block_number, exc)
                return None
        return None

    # ── Internal ──────────────────────────────────────────────────────────
    def _safe_get_logs(self, params: dict, depth: int = 0) -> List[Dict]:
        """Chamada get_logs com retry binário em caso de overflow."""
        W3 = self._Web3
        for _ in range(len(self._instances)):
            idx, w3 = self._next_healthy()
            try:
                result = w3.eth.get_logs(params)
                self._mark_ok(idx)
                return list(result)
            except Exception as exc:
                if _is_429_error(exc):
                    self._mark_error(idx)
                    cd = min(180, 15 * (depth + 1))
                    time.sleep(min(10, cd))
                    continue
                # Overflow de range? dividir ao meio
                if depth < 4:
                    try:
                        fb = int(params["fromBlock"], 16)
                        tb = int(params["toBlock"], 16)
                        if tb > fb:
                            mid = (fb + tb) // 2
                            left = dict(params)
                            right = dict(params)
                            left["toBlock"]   = W3.to_hex(mid)
                            right["fromBlock"] = W3.to_hex(mid + 1)
                            return (
                                self._safe_get_logs(left, depth + 1)
                                + self._safe_get_logs(right, depth + 1)
                            )
                    except Exception:
                        pass
                logger.warning("_safe_get_logs profundidade=%d: %s", depth, exc)
                if self._on_error:
                    self._on_error(exc)
                return []
        return []
