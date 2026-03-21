"""monitor-chain/operation_parser.py — OperationParser standalone.

Decodifica logs brutos da blockchain em dicionários de operação
para o OCME Engine (WEbdEX Protocol).

Não depende do monolito webdex_*.py.

Uso:
    from operation_parser import OperationParser

    parser = OperationParser(
        contracts=CONTRACTS,
        abi_payments=ABI_PAYMENTS,
        abi_erc20=ABI_ERC20,
        token_meta={addr: {"sym": "USDT0", "dec": 6}},
    )
    ops = parser.parse(log, "Trade")
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger("monitor-chain.operation_parser")


class OperationParser:
    """Decodifica logs brutos (dict/AttributeDict) em operações OCME.

    Parâmetros:
        contracts:    Dict {env: {PAYMENTS: addr, ...}} — endereços por ambiente
        abi_payments: ABI do contrato PAYMENTS (OpenPosition event)
        abi_erc20:    ABI ERC-20 mínimo (Transfer event)
        token_meta:   Dict {addr_lower: {"sym": str, "dec": int}}
        infer_env_fn: Callable(addr) → str (ambiente do contrato)
    """

    def __init__(
        self,
        contracts: Dict[str, Dict],
        abi_payments: list,
        abi_erc20: list,
        token_meta: Optional[Dict[str, Dict]] = None,
        infer_env_fn=None,
    ):
        from web3 import Web3
        self._Web3 = Web3
        self._contracts = contracts
        self._token_meta = token_meta or {}
        self._infer_env_fn = infer_env_fn or (lambda addr: "UNKNOWN")

        # Constrói instâncias de contrato (usando provider None — só para ABI decode)
        self._payment_abis: Dict[str, Any] = {}
        self._erc20_abi = abi_erc20

        # Para decodificar sem provider: criamos contratos mock com endereço indiferente
        _dummy_w3 = Web3()
        for env, addrs in contracts.items():
            payments_addr = addrs.get("PAYMENTS", "")
            if payments_addr:
                try:
                    self._payment_abis[env] = _dummy_w3.eth.contract(
                        address=Web3.to_checksum_address(payments_addr),
                        abi=abi_payments,
                    )
                except Exception as exc:
                    logger.warning("OperationParser contrato %s: %s", env, exc)

        self._erc20_instances: Dict[str, Any] = {}
        for addr_lower, meta in self._token_meta.items():
            try:
                self._erc20_instances[addr_lower] = _dummy_w3.eth.contract(
                    address=Web3.to_checksum_address(addr_lower),
                    abi=abi_erc20,
                )
            except Exception:
                pass

    def _get_token_meta(self, addr: str) -> Dict:
        return self._token_meta.get(addr.lower(), {"sym": "UNKNOWN", "dec": 18})

    # ── Trade (OpenPosition) ──────────────────────────────────────────────
    def parse_trade(self, log: Dict, env: str) -> Optional[Dict]:
        """Decodifica log OpenPosition → dict de operação Trade."""
        contract = self._payment_abis.get(env)
        if not contract:
            return None
        try:
            evt = contract.events.OpenPosition().process_log(log)
            args = evt["args"]
            details = args["details"]

            uw = str(args["user"]).lower().strip()
            coin_addr = str(details["coin"]).lower()
            meta = self._get_token_meta(coin_addr)
            dec = meta["dec"]
            sym = meta["sym"]

            val = float(Decimal(int(details["profit"])) / Decimal(10 ** dec))
            fee = float(Decimal(int(details.get("fee", 0))) / Decimal(10 ** 9))
            strategy_addr = str(details.get("strategy") or "").lower().strip()
            bot_id = str(details.get("botId") or "").strip()
            old_bal_raw = int(details.get("oldBalance") or 0)
            old_bal_usd = float(old_bal_raw) / (10 ** dec) if old_bal_raw > 0 else 0.0
            gas_proto_raw = int(details.get("gas") or 0)
            gas_proto = float(gas_proto_raw) / (10 ** dec) if gas_proto_raw > 0 else 0.0

            tx_hash = self._normalize_tx(str(log.get("transactionHash") or ""))

            return {
                "tipo": "Trade",
                "tx_hash": tx_hash,
                "log_index": int(log["logIndex"]),
                "bloco": int(log["blockNumber"]),
                "ambiente": env,
                "sub_conta": str(args["accountId"]),
                "owner_wallet": uw,
                "valor": val,
                "gas_usd": 0.0,       # calculado externamente (requer receipt)
                "gas_pol": 0.0,       # calculado externamente
                "token": sym,
                "fee": fee,
                "strategy_addr": strategy_addr,
                "bot_id": bot_id,
                "gas_protocol": gas_proto,
                "old_balance_usd": old_bal_usd,
                "coin_addr": coin_addr,
                "dec": dec,
            }
        except Exception as exc:
            logger.debug("parse_trade %s: %s", env, exc)
            return None

    # ── Transfer (ERC-20) ─────────────────────────────────────────────────
    def parse_transfer(self, log: Dict) -> List[Dict]:
        """Decodifica log Transfer → lista de operações (entrada/saída)."""
        ops: List[Dict] = []
        addr = str(log.get("address", "")).lower()
        contract = self._erc20_instances.get(addr)
        if not contract:
            return ops
        try:
            evt = contract.events.Transfer().process_log(log)
            args = evt["args"]
            to_w = str(args["to"]).lower()
            fr_w = str(args["from"]).lower()
            meta = self._get_token_meta(addr)
            val = float(Decimal(int(args["value"])) / Decimal(10 ** meta["dec"]))
            tx_hash = self._normalize_tx(str(log.get("transactionHash") or ""))
            bloco = int(log["blockNumber"])
            log_idx = int(log["logIndex"])
            ambiente = self._infer_env_fn(addr)

            if to_w and to_w != "0x" + "0" * 40:
                ops.append({
                    "tipo": "Transfer",
                    "tx_hash": tx_hash,
                    "log_index": log_idx,
                    "bloco": bloco,
                    "ambiente": ambiente,
                    "sub_conta": "WALLET",
                    "owner_wallet": to_w,
                    "valor": val,
                    "gas_usd": 0.0,
                    "gas_pol": 0.0,
                    "token": meta["sym"],
                    "fee": 0.0,
                    "direction": "in",
                })
            if fr_w and fr_w != "0x" + "0" * 40:
                ops.append({
                    "tipo": "Transfer",
                    "tx_hash": tx_hash,
                    "log_index": log_idx + 10000,
                    "bloco": bloco,
                    "ambiente": ambiente,
                    "sub_conta": "WALLET",
                    "owner_wallet": fr_w,
                    "valor": -val,
                    "gas_usd": 0.0,
                    "gas_pol": 0.0,
                    "token": meta["sym"],
                    "fee": 0.0,
                    "direction": "out",
                })
        except Exception as exc:
            logger.debug("parse_transfer: %s", exc)
        return ops

    # ── Helpers ───────────────────────────────────────────────────────────
    def parse(self, log: Dict, tipo: str, env: str = "") -> List[Dict]:
        """Ponto de entrada unificado. tipo: 'Trade' | 'Transfer'."""
        if tipo == "Trade":
            op = self.parse_trade(log, env)
            return [op] if op else []
        elif tipo == "Transfer":
            return self.parse_transfer(log)
        return []

    @staticmethod
    def _normalize_tx(tx: str) -> str:
        tx = tx.lower().strip()
        if isinstance(tx, bytes):
            tx = "0x" + tx.hex()
        elif not tx.startswith("0x"):
            tx = "0x" + tx
        return tx
