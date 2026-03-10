# ==============================================================================
# monitor_chain/block_fetcher.py — Abstração da camada Web3/RPC
# OCME bd Monitor Engine — Story 7.2
# ==============================================================================
from __future__ import annotations

import json
import logging
import time
from typing import Any

from web3 import Web3
from web3.types import LogReceipt

logger = logging.getLogger('monitor.chain.fetcher')

_POA_MW = None
try:
    from web3.middleware import geth_poa_middleware
    _POA_MW = geth_poa_middleware
except ImportError:
    try:
        from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware
        _POA_MW = ExtraDataToPOAMiddleware
    except ImportError:
        pass

# ABIs compactas
ABI_PAYMENTS = json.dumps([{
    'anonymous': False,
    'inputs': [
        {'indexed': True,  'name': 'manager',   'type': 'address'},
        {'indexed': False, 'name': 'user',       'type': 'address'},
        {'indexed': False, 'name': 'accountId',  'type': 'string'},
        {'components': [
            {'name': 'strategy',   'type': 'address'},
            {'name': 'coin',       'type': 'address'},
            {'name': 'botId',      'type': 'string'},
            {'name': 'oldBalance', 'type': 'uint256'},
            {'name': 'fee',        'type': 'uint256'},
            {'name': 'gas',        'type': 'uint256'},
            {'name': 'profit',     'type': 'int256'},
        ], 'indexed': False, 'name': 'details', 'type': 'tuple'},
    ],
    'name': 'OpenPosition',
    'type': 'event',
}])

TOPIC_OPENPOSITION = Web3.to_hex(
    Web3.keccak(text='OpenPosition(address,address,string,(address,address,string,uint256,uint256,uint256,int256))')
)
TOPIC_TRANSFER = Web3.to_hex(Web3.keccak(text='Transfer(address,address,uint256)'))


def _make_w3(rpc_url: str, timeout: int = 25) -> Web3:
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': timeout}))
    if _POA_MW:
        try:
            w3.middleware_onion.inject(_POA_MW, layer=0)
        except Exception:
            pass
    return w3


class BlockFetcher:
    '''Busca logs de blocos da blockchain com retry e fallback de RPC.'''

    def __init__(self, rpc_url: str, chunk_size: int = 25, timeout: int = 25):
        self.rpc_url = rpc_url
        self.chunk_size = chunk_size
        self.w3 = _make_w3(rpc_url, timeout)
        self._rpc_cache: dict[str, Web3] = {}

    def get_latest_block(self) -> int:
        try:
            return int(self.w3.eth.block_number)
        except Exception as exc:
            logger.warning('get_latest_block falhou: %s', exc)
            raise

    def get_block_timestamp(self, block_number: int) -> int:
        try:
            blk = self.w3.eth.get_block(block_number)
            return int(blk.get('timestamp', 0))
        except Exception as exc:
            logger.warning('get_block_timestamp(%d) falhou: %s', block_number, exc)
            return 0

    def get_logs(
        self,
        from_block: int,
        to_block: int,
        addresses: list[str],
        topics: list[str],
    ) -> list[LogReceipt]:
        '''Busca logs em chunks. Retorna lista de logs ou [] em falha.'''
        all_logs: list[LogReceipt] = []
        current = from_block

        while current <= to_block:
            end = min(current + self.chunk_size - 1, to_block)
            try:
                logs = self.w3.eth.get_logs({
                    'fromBlock': current,
                    'toBlock': end,
                    'address': addresses,
                    'topics': [topics],
                })
                all_logs.extend(logs)
                logger.debug('Logs %d-%d: %d encontrados', current, end, len(logs))
            except Exception as exc:
                err = str(exc)
                if '429' in err or 'Too Many Requests' in err:
                    logger.warning('RPC rate limit (429) — aguardando 3s')
                    time.sleep(3)
                elif 'timeout' in err.lower():
                    logger.warning('RPC timeout em bloco %d-%d — pulando', current, end)
                else:
                    logger.warning('get_logs(%d-%d) falhou: %s', current, end, exc)
            current = end + 1

        return all_logs

    def get_transaction_receipt(self, tx_hash: str) -> Any | None:
        try:
            return self.w3.eth.get_transaction_receipt(tx_hash)
        except Exception:
            return None

    def get_gas_price_gwei(self) -> float:
        try:
            return float(Web3.from_wei(self.w3.eth.gas_price, 'gwei'))
        except Exception:
            return 0.0

    def get_pol_balance(self, address: str) -> float:
        try:
            raw = self.w3.eth.get_balance(Web3.to_checksum_address(address))
            return float(Web3.from_wei(raw, 'ether'))
        except Exception:
            return 0.0
