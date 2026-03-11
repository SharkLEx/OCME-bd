from __future__ import annotations
# ==============================================================================
# webdex_chain.py — WEbdEX Monitor Engine (extraído de WEbdEX_V30_24_SPEED_PATCH_FIXED.py)
# Linhas fonte: ~1182-1320 + chain_cache (~2460-2500)
# ==============================================================================

import os, time, json, threading
from typing import Any, Dict, List

from webdex_config import (
    logger, Web3, _POA_MW, RPC_URL, RPC_CAPITAL, RPC_FALLBACK,
    CONTRACTS, ABI_PAYMENTS, ABI_SUBACCOUNTS, ABI_MANAGER,
    ABI_TOKENPASS, ABI_ERC20_TRANSFER, ABI_ERC20_META,
    TOKEN_CONFIG, TOKENS_TO_WATCH, TOKENS_MAP,
    ADMIN_USER_IDS,
)
from webdex_db import DB_LOCK, cursor

import requests
import threading as _threading
import itertools as _itertools
import time as _time

# ==============================================================================
# 🔄 RPC POOL — round-robin com failover automático (3 endpoints Alchemy)
# ==============================================================================
class RpcPool:
    """
    Pool de 3 RPCs Polygon com rotação round-robin e cooldown de 60s por falha.
    Substitui o `web3` global para chamadas eth_getLogs no vigia.
    """
    _COOLDOWN = 60.0  # segundos de pausa para endpoint com erro

    def __init__(self, rpcs: list, timeout: int = 25):
        self._lock = _threading.Lock()
        self._rpcs = rpcs
        self._timeout = timeout
        self._instances: List[Web3] = []
        self._errors: List[int] = []        # contagem de erros por índice
        self._cooldown_until: List[float] = []  # timestamp de retorno por índice
        for rpc in rpcs:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": timeout}))
            if _POA_MW:
                try:
                    w3.middleware_onion.inject(_POA_MW, layer=0)
                except Exception:
                    pass
            self._instances.append(w3)
            self._errors.append(0)
            self._cooldown_until.append(0.0)
        self._cycle = _itertools.cycle(range(len(rpcs)))
        self._primary: Web3 = self._instances[0]  # referência para compatibilidade

    def _next_healthy(self) -> tuple[int, Web3]:
        """Retorna (índice, instância) do próximo endpoint saudável."""
        now = _time.time()
        tried = 0
        while tried < len(self._instances):
            idx = next(self._cycle)
            if now >= self._cooldown_until[idx]:
                return idx, self._instances[idx]
            tried += 1
        # todos em cooldown — usa o que vai sair primeiro do cooldown
        idx = min(range(len(self._instances)), key=lambda i: self._cooldown_until[i])
        return idx, self._instances[idx]

    def mark_error(self, idx: int):
        with self._lock:
            self._errors[idx] += 1
            cd = min(180.0, self._COOLDOWN * self._errors[idx])
            self._cooldown_until[idx] = _time.time() + cd
            logger.warning(
                "[rpc_pool] Endpoint #%d com erro (%d× seguido) — cooldown %.0fs",
                idx, self._errors[idx], cd
            )

    def mark_ok(self, idx: int):
        with self._lock:
            self._errors[idx] = 0
            self._cooldown_until[idx] = 0.0

    def get_logs(self, params: dict) -> list:
        """Chama eth_getLogs usando round-robin com failover automático."""
        for attempt in range(len(self._instances)):
            idx, w3 = self._next_healthy()
            try:
                result = w3.eth.get_logs(params)
                self.mark_ok(idx)
                return result
            except Exception as e:
                if _is_429_error(e):
                    self.mark_error(idx)
                    # para 429 tenta o próximo imediatamente
                    continue
                # para outros erros re-raise (quem chama decide)
                raise
        # todos falharam com 429 — retorna vazio
        logger.error("[rpc_pool] Todos os endpoints com rate-limit. Retornando [].")
        return []

    @property
    def eth(self):
        """Proxy para compatibilidade com código que usa `web3.eth.*`."""
        _, w3 = self._next_healthy()
        return w3.eth


# Pool principal — usado pelo vigia e _safe_get_logs
rpc_pool = RpcPool([RPC_URL, RPC_CAPITAL, RPC_FALLBACK], timeout=25)

# ==============================================================================
# 🌐 WEB3 MANAGER
# ==============================================================================
# web3 mantido para compatibilidade (to_checksum_address, keccak, contratos, etc.)
web3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 25}))
if _POA_MW:
    try:
        web3.middleware_onion.inject(_POA_MW, layer=0)
    except Exception:
        pass

web3_capital = Web3(Web3.HTTPProvider(RPC_CAPITAL, request_kwargs={"timeout": 10}))
if _POA_MW:
    try:
        web3_capital.middleware_onion.inject(_POA_MW, layer=0)
    except Exception:
        pass

_web3_user_cache: Dict[str, Web3] = {}

def web3_for_rpc(rpc: str, timeout: int = 25) -> Web3:
    _cache_key = f"{rpc}:{timeout}"
    rpc = (rpc or "").strip() or RPC_URL
    if _cache_key not in _web3_user_cache:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": timeout}))
        if _POA_MW:
            try:
                w3.middleware_onion.inject(_POA_MW, layer=0)
            except Exception:
                pass
        _web3_user_cache[_cache_key] = w3
    return _web3_user_cache[_cache_key]

TOPIC_OPENPOSITION = Web3.to_hex(Web3.keccak(text="OpenPosition(address,address,string,(address,address,string,uint256,uint256,uint256,int256))"))
TOPIC_TRANSFER     = Web3.to_hex(Web3.keccak(text="Transfer(address,address,uint256)"))

def get_contracts(env_name: str, w3: Web3) -> Dict[str, Any]:
    raw = (env_name or "AG_C_bd").strip()
    aliases = {
        "beta_v5": "bd_v5",
        "bdv5": "bd_v5",
        "v5": "bd_v5",
        "agc_bd": "AG_C_bd",
        "ag_c_bd": "AG_C_bd",
        "agcbd": "AG_C_bd",
    }
    lk = raw.lower().replace(" ", "")
    env_name = aliases.get(lk, raw)
    if env_name not in CONTRACTS:
        env_name = "AG_C_bd"
    c = CONTRACTS[env_name]
    return {
        "env": env_name,
        "tag": c["TAG"],
        "addr": c,
        "payments": w3.eth.contract(address=Web3.to_checksum_address(c["PAYMENTS"]),    abi=json.loads(ABI_PAYMENTS)),
        "sub":      w3.eth.contract(address=Web3.to_checksum_address(c["SUBACCOUNTS"]), abi=json.loads(ABI_SUBACCOUNTS)),
        "mgr":      w3.eth.contract(address=Web3.to_checksum_address(c["MANAGER"]),     abi=json.loads(ABI_MANAGER)),
        "pass":     w3.eth.contract(address=Web3.to_checksum_address(c["TOKENPASS"]),   abi=json.loads(ABI_TOKENPASS)),
    }

CONTRACTS_A = get_contracts("AG_C_bd", web3)
CONTRACTS_B = get_contracts("bd_v5", web3)

_erc20_cache: Dict[str, Any] = {}
def erc20_contract(addr: str) -> Any:
    a = Web3.to_checksum_address(addr)
    key = a.lower()
    if key not in _erc20_cache:
        _erc20_cache[key] = web3.eth.contract(address=a, abi=json.loads(ABI_ERC20_TRANSFER))
    return _erc20_cache[key]

# ==============================================================================
# ⚡ CHAIN CACHE — Monitor de bloco em background
# ==============================================================================
_CHAIN_CACHE = {
    "block":     0,
    "gwei":      0.0,
    "pol_price": 0.0,
    "ts":        0.0,
    "ok":        False,
}
_CHAIN_CACHE_LOCK = threading.Lock()

def chain_block() -> int:
    with _CHAIN_CACHE_LOCK:
        return _CHAIN_CACHE["block"]

def chain_gwei() -> float:
    with _CHAIN_CACHE_LOCK:
        return _CHAIN_CACHE["gwei"]

def chain_pol_price() -> float:
    with _CHAIN_CACHE_LOCK:
        p = _CHAIN_CACHE["pol_price"]
    return p if p > 0 else obter_preco_pol()

def _chain_cache_worker():
    """Thread background: atualiza bloco, gwei e POL price a cada 12s."""
    while True:
        try:
            blk  = int(web3.eth.block_number)
            gwei = float(web3.eth.gas_price) / 1e9
            pol  = obter_preco_pol()
            with _CHAIN_CACHE_LOCK:
                _CHAIN_CACHE["block"]     = blk
                _CHAIN_CACHE["gwei"]      = gwei
                _CHAIN_CACHE["pol_price"] = pol
                _CHAIN_CACHE["ts"]        = time.time()
                _CHAIN_CACHE["ok"]        = True
        except Exception:
            pass
        time.sleep(12)

def obter_preco_pol() -> float:
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=POLUSDT", timeout=3).json()
        return float(r["price"])
    except Exception:
        return 0.50

def _is_429_error(e: Exception) -> bool:
    s = str(e).lower()
    return ("429" in s) or ("too many requests" in s) or ("rate limit" in s)

_WALLET_MAP_CACHE: Dict[str, Any] = {"ts": 0.0, "data": ({}, {})}
_WALLET_MAP_TTL = 60.0  # segundos — recarrega a cada minuto

def invalidate_wallet_map_cache():
    """Chame após registrar/atualizar wallet de usuário para forçar refresh imediato."""
    _WALLET_MAP_CACHE["ts"] = 0.0

def get_active_wallet_map(force_refresh: bool = False):
    """
    Retorna (wallet_map, meta) para processamento de eventos on-chain.
    Resultado cacheado por 60s para reduzir queries SQLite em alta frequência.
    Inclui usuários com active=0 para não perder eventos mesmo quando bot foi bloqueado.
    """
    now = time.time()
    if not force_refresh and (now - _WALLET_MAP_CACHE["ts"]) < _WALLET_MAP_TTL:
        return _WALLET_MAP_CACHE["data"]

    wallet_map: Dict[str, List[int]] = {}
    meta: Dict[int, Dict[str, Any]] = {}
    with DB_LOCK:
        try:
            rows = cursor.execute(
                "SELECT chat_id,wallet,env,periodo,active FROM users WHERE wallet<>'' AND wallet IS NOT NULL"
            ).fetchall()
            for cid, w, env, per, act in rows:
                w = (w or "").lower().strip()
                if not w:
                    continue
                wallet_map.setdefault(w, []).append(int(cid))
                meta[int(cid)] = {
                    "wallet":   w,
                    "env":      (env or "AG_C_bd"),
                    "periodo":  (per or "24h"),
                    "active":   int(act or 0),
                }
        except Exception:
            pass

    _WALLET_MAP_CACHE["data"] = (wallet_map, meta)
    _WALLET_MAP_CACHE["ts"]   = now
    return wallet_map, meta


def notify_cids_for_wallet(wallet_map: dict, uw: str) -> list:
    """Retorna apenas chat_ids ATIVOS (active=1) para notificação Telegram."""
    with DB_LOCK:
        try:
            rows = cursor.execute(
                "SELECT chat_id FROM users WHERE wallet=? AND active=1",
                (uw,)
            ).fetchall()
            return [int(r[0]) for r in rows]
        except Exception:
            return []
