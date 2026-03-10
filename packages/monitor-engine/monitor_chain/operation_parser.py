# ==============================================================================
# monitor_chain/operation_parser.py — Decodifica eventos OpenPosition e Transfer
# OCME bd Monitor Engine — Story 7.2
# ==============================================================================
from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal, getcontext
from typing import Any

from web3 import Web3

from monitor_chain.block_fetcher import ABI_PAYMENTS, TOPIC_OPENPOSITION, TOPIC_TRANSFER

getcontext().prec = 50
logger = logging.getLogger('monitor.chain.parser')

_USDT_DEC  = 6
_LP_DEC    = 6
_POL_DEC   = 18


def _to_usd(raw: int, decimals: int) -> float:
    try:
        return float(Decimal(raw) / Decimal(10 ** decimals))
    except Exception:
        return 0.0


def normalize_hash(h: str) -> str:
    return (h or '').lower().strip()


class OperationParser:
    '''Decodifica logs de blockchain em operações estruturadas.'''

    def __init__(self, contracts: dict[str, dict], tokens_map: dict[str, dict]):
        '''
        contracts: { 'AG_C_bd': { 'PAYMENTS': '0x...', ... }, ... }
        tokens_map: { '0xlower...': { 'dec': 6, 'sym': 'USDT0', 'icon': '🔵' }, ... }
        '''
        self.tokens_map = {k.lower(): v for k, v in tokens_map.items()}
        self._payment_contracts: dict[str, str] = {}  # addr_lower -> env_name
        self._w3 = Web3()  # apenas para ABI decode

        for env_name, addrs in contracts.items():
            payments_addr = addrs.get('PAYMENTS', '')
            if payments_addr:
                self._payment_contracts[payments_addr.lower()] = env_name

    def parse(self, logs: list[Any]) -> list[dict]:
        '''Transforma logs brutos em lista de operações estruturadas.'''
        ops: list[dict] = []
        for log in logs:
            try:
                op = self._parse_log(log)
                if op:
                    ops.append(op)
            except Exception as exc:
                logger.debug('parse_log falhou: %s', exc)
        return ops

    def _parse_log(self, log: Any) -> dict | None:
        topic0 = (log.get('topics', [None])[0] or b'').hex()
        if not topic0.startswith('0x'):
            topic0 = '0x' + topic0

        addr = (log.get('address') or '').lower()

        if topic0.lower() == TOPIC_OPENPOSITION.lower():
            return self._parse_open_position(log, addr)

        if topic0.lower() == TOPIC_TRANSFER.lower():
            return self._parse_transfer(log, addr)

        return None

    def _parse_open_position(self, log: Any, addr: str) -> dict | None:
        env_name = self._payment_contracts.get(addr, 'UNKNOWN')

        try:
            contract = self._w3.eth.contract(abi=json.loads(ABI_PAYMENTS))
            decoded = contract.events.OpenPosition().process_log(log)
            args = decoded['args']
            details = args['details']
        except Exception as exc:
            logger.debug('Falha ao decodificar OpenPosition: %s', exc)
            return None

        coin_addr = (details.get('coin') or '').lower()
        token_info = self.tokens_map.get(coin_addr, {'dec': 6, 'sym': '?', 'icon': '⬜'})
        decimals = token_info.get('dec', 6)

        profit_raw  = int(details.get('profit', 0))
        gas_raw     = int(details.get('gas', 0))
        fee_raw     = int(details.get('fee', 0))
        old_bal_raw = int(details.get('oldBalance', 0))

        profit_usd  = _to_usd(abs(profit_raw), decimals) * (1 if profit_raw >= 0 else -1)
        gas_usd     = _to_usd(gas_raw, decimals)
        fee_usd     = _to_usd(fee_raw, decimals)
        old_bal_usd = _to_usd(old_bal_raw, decimals)

        return {
            'type':          'trade',
            'event':         'OpenPosition',
            'hash':          normalize_hash(log.get('transactionHash', b'').hex()),
            'log_index':     int(log.get('logIndex', 0)),
            'block':         int(log.get('blockNumber', 0)),
            'timestamp':     datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'env':           env_name,
            'user_wallet':   (args.get('user') or '').lower(),
            'sub_conta':     args.get('accountId') or '',
            'strategy_addr': (details.get('strategy') or '').lower(),
            'bot_id':        details.get('botId') or '',
            'coin_addr':     coin_addr,
            'token_sym':     token_info.get('sym', '?'),
            'token_icon':    token_info.get('icon', '⬜'),
            'profit_usd':    profit_usd,
            'gas_usd':       gas_usd,
            'fee_usd':       fee_usd,
            'old_balance_usd': old_bal_usd,
            'contract_address': addr,
        }

    def _parse_transfer(self, log: Any, addr: str) -> dict | None:
        token_info = self.tokens_map.get(addr)
        if not token_info:
            return None

        try:
            topics = log.get('topics', [])
            if len(topics) < 3:
                return None
            from_addr = '0x' + topics[1].hex()[-40:]
            to_addr   = '0x' + topics[2].hex()[-40:]
            value_raw = int(log.get('data', '0x0'), 16)
        except Exception:
            return None

        decimals = token_info.get('dec', 6)
        value_usd = _to_usd(value_raw, decimals)

        return {
            'type':      'transfer',
            'event':     'Transfer',
            'hash':      normalize_hash(log.get('transactionHash', b'').hex()),
            'log_index': int(log.get('logIndex', 0)),
            'block':     int(log.get('blockNumber', 0)),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'from':      from_addr.lower(),
            'to':        to_addr.lower(),
            'token_addr': addr,
            'token_sym':  token_info.get('sym', '?'),
            'token_icon': token_info.get('icon', '⬜'),
            'value_usd':  value_usd,
        }
