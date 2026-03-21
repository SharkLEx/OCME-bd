"""monitor-core/vigia.py — Vigia Modular do OCME Engine.

Loop principal de monitoramento on-chain com padrão EventEmitter.
100% standalone: sem dependência de webdex_config / webdex_db / webdex_chain.

Uso básico:
    from vigia import Vigia, Sentinela

    vigia = Vigia(
        db_path="webdex_v5_final.db",
        rpc_urls=[RPC1, RPC2, RPC3],
        contracts=CONTRACTS,
        tokens_to_watch=[...],
        wallet_map_fn=lambda: {...},
    )
    vigia.on("operation", lambda op: print(op))
    vigia.on("progress",  lambda p: print(p))
    vigia.start()
    # ... (blocks ou thread secundária)
    vigia.stop()
"""

from __future__ import annotations

import itertools
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("monitor-core.vigia")

# ── Configuração via env (com defaults) ──────────────────────────────────────
def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default

def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


# ── POA Middleware ────────────────────────────────────────────────────────────
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


def _is_429_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "rate" in s or "limit" in s or "too many" in s


# ── RpcPool ────────────────────────────────────────────────────────────────────
class RpcPool:
    """Pool de RPCs com round-robin e cooldown automático por falha."""

    _COOLDOWN_BASE = 60.0

    def __init__(self, rpc_urls: List[str], timeout: int = 25):
        from web3 import Web3
        self._Web3 = Web3
        poa_mw = _get_poa_mw()
        self._lock = threading.Lock()
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
        self.primary: Any = self._instances[0]

    def _next_healthy(self) -> Tuple[int, Any]:
        now = time.time()
        for _ in range(len(self._instances)):
            idx = next(self._cycle)
            if now >= self._cooldown_until[idx]:
                return idx, self._instances[idx]
        idx = min(range(len(self._instances)), key=lambda i: self._cooldown_until[i])
        return idx, self._instances[idx]

    def mark_error(self, idx: int):
        with self._lock:
            self._errors[idx] += 1
            cd = min(300.0, self._COOLDOWN_BASE * self._errors[idx])
            self._cooldown_until[idx] = time.time() + cd
            logger.warning("[rpc_pool] endpoint #%d erro #%d — cooldown %.0fs", idx, self._errors[idx], cd)

    def mark_ok(self, idx: int):
        with self._lock:
            self._errors[idx] = 0
            self._cooldown_until[idx] = 0.0

    def get_logs(self, params: dict) -> list:
        for attempt in range(len(self._instances)):
            idx, w3 = self._next_healthy()
            try:
                result = w3.eth.get_logs(params)
                self.mark_ok(idx)
                return result
            except Exception as exc:
                if _is_429_error(exc):
                    self.mark_error(idx)
                    continue
                raise
        logger.error("[rpc_pool] todos endpoints com rate-limit — retornando []")
        return []

    def block_number(self) -> int:
        for attempt in range(len(self._instances)):
            idx, w3 = self._next_healthy()
            try:
                result = int(w3.eth.block_number)
                self.mark_ok(idx)
                return result
            except Exception as exc:
                if _is_429_error(exc):
                    self.mark_error(idx)
                    continue
                raise
        raise RuntimeError("todos RPCs indisponíveis")

    def get_transaction(self, tx_hash: str) -> Optional[Any]:
        idx, w3 = self._next_healthy()
        try:
            return w3.eth.get_transaction(tx_hash)
        except Exception:
            return None

    def get_receipt(self, tx_hash: str) -> Optional[Any]:
        idx, w3 = self._next_healthy()
        try:
            return w3.eth.get_transaction_receipt(tx_hash)
        except Exception:
            return None


# ── BlockTimeCache ──────────────────────────────────────────────────────────
class BlockTimeCache:
    """Cache SQLite para timestamps de bloco (evita RPC redundante)."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()

    def get(self, block_number: int) -> Optional[float]:
        with self._lock:
            try:
                c = sqlite3.connect(self._db_path)
                row = c.execute(
                    "SELECT block_ts FROM block_time_cache WHERE bloco=?", (block_number,)
                ).fetchone()
                c.close()
                return float(row[0]) if row else None
            except Exception:
                return None

    def set(self, block_number: int, ts: float):
        with self._lock:
            try:
                c = sqlite3.connect(self._db_path)
                c.execute(
                    "INSERT OR REPLACE INTO block_time_cache (bloco, block_ts) VALUES (?,?)",
                    (block_number, ts),
                )
                c.commit()
                c.close()
            except Exception:
                pass

    def get_or_fetch(self, block_number: int, rpc_pool: RpcPool) -> Optional[float]:
        ts = self.get(block_number)
        if ts:
            return ts
        try:
            idx, w3 = rpc_pool._next_healthy()
            block = w3.eth.get_block(block_number)
            ts = float(block["timestamp"])
            self.set(block_number, ts)
            return ts
        except Exception:
            return None


# ── DB helpers ──────────────────────────────────────────────────────────────
def _db_get_config(db_path: str, key: str, default: str = "") -> str:
    try:
        c = sqlite3.connect(db_path)
        row = c.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        c.close()
        return str(row[0]) if row else default
    except Exception:
        return default


def _db_set_config(db_path: str, key: str, value: str):
    try:
        c = sqlite3.connect(db_path)
        c.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?,?)", (key, value))
        c.commit()
        c.close()
    except Exception:
        pass


def _db_op_exists(db_path: str, tx_hash: str, log_index: int) -> bool:
    try:
        c = sqlite3.connect(db_path)
        row = c.execute(
            "SELECT 1 FROM operacoes WHERE hash=? AND log_index=?", (tx_hash, log_index)
        ).fetchone()
        c.close()
        return row is not None
    except Exception:
        return False


def _db_insert_op(db_path: str, op: Dict) -> bool:
    """Insere operação + op_owner. Retorna True se foi nova."""
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tx = op["tx_hash"]
    log_idx = int(op["log_index"])
    try:
        c = sqlite3.connect(db_path)
        # idempotente
        if c.execute("SELECT 1 FROM operacoes WHERE hash=? AND log_index=?", (tx, log_idx)).fetchone():
            c.close()
            return False
        try:
            c.execute(
                "INSERT OR IGNORE INTO operacoes "
                "(hash,log_index,data_hora,tipo,valor,gas_usd,token,sub_conta,bloco,ambiente,fee,"
                " strategy_addr,bot_id,gas_protocol,old_balance_usd) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tx, log_idx, dt,
                    op.get("tipo", "Trade"), float(op.get("valor", 0)),
                    float(op.get("gas_usd", 0)), op.get("token", ""),
                    op.get("sub_conta", ""), int(op.get("bloco", 0)),
                    op.get("ambiente", "UNKNOWN"), float(op.get("fee", 0)),
                    op.get("strategy_addr", ""), op.get("bot_id", ""),
                    float(op.get("gas_protocol", 0)), float(op.get("old_balance_usd", 0)),
                ),
            )
        except Exception:
            # fallback para schema sem colunas extras
            c.execute(
                "INSERT OR IGNORE INTO operacoes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (tx, log_idx, dt, op.get("tipo", "Trade"), float(op.get("valor", 0)),
                 float(op.get("gas_usd", 0)), op.get("token", ""),
                 op.get("sub_conta", ""), int(op.get("bloco", 0)),
                 op.get("ambiente", "UNKNOWN"), float(op.get("fee", 0))),
            )
        c.execute(
            "INSERT OR REPLACE INTO op_owner (hash, log_index, wallet) VALUES (?,?,?)",
            (tx, log_idx, str(op.get("owner_wallet", "")).lower()),
        )
        c.commit()
        c.close()
        return True
    except Exception as exc:
        logger.warning("_db_insert_op: %s", exc)
        return False


def _db_upsert_vigia_health(db_path: str, health: Dict):
    """Atualiza vigia_health singleton (id=1). Silencia erros."""
    try:
        c = sqlite3.connect(db_path)
        c.execute("""
            INSERT INTO vigia_health
                (id, last_block, loops_total, ops_total, rpc_errors,
                 capture_rate, last_error, started_at, updated_at)
            VALUES (1,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                last_block   = excluded.last_block,
                loops_total  = excluded.loops_total,
                ops_total    = excluded.ops_total,
                rpc_errors   = excluded.rpc_errors,
                capture_rate = excluded.capture_rate,
                last_error   = excluded.last_error,
                updated_at   = excluded.updated_at
        """, (
            int(health.get("last_block", 0)),
            int(health.get("loops_total", 0)),
            int(health.get("ops_total", 0)),
            int(health.get("rpc_errors", 0)),
            float(health.get("capture_rate", 100.0)),
            str(health.get("last_error", "") or "")[:500],
            float(health.get("started_at", time.time())),
            float(time.time()),
        ))
        c.commit()
        c.close()
    except Exception:
        pass


# ── EventBus simples ──────────────────────────────────────────────────────────
class _EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def on(self, event: str, callback: Callable):
        self._listeners.setdefault(event, []).append(callback)
        return self  # fluent

    def emit(self, event: str, *args, **kwargs):
        for cb in self._listeners.get(event, []):
            try:
                cb(*args, **kwargs)
            except Exception as exc:
                logger.warning("EventBus.emit(%s) callback error: %s", event, exc)


# ── Vigia ─────────────────────────────────────────────────────────────────────
class Vigia:
    """Loop principal de monitoramento on-chain.

    Eventos emitidos:
        'operation'  → dict com todos os campos da operação detectada
        'progress'   → dict com estado do loop (bloco atual, lag, etc.)
        'error'      → str com mensagem de erro
        'idle'       → None (nenhum bloco novo no ciclo)
    """

    def __init__(
        self,
        *,
        db_path: str,
        rpc_urls: List[str],
        contracts: Dict,
        tokens_to_watch: List[str],
        topic_openposition: str,
        topic_transfer: str,
        abi_payments: list,
        abi_erc20: list,
        wallet_map_fn: Callable[[], Dict[str, List[int]]],
        infer_env_fn: Optional[Callable[[str], str]] = None,
        # parâmetros de tuning
        max_blocks_per_loop: Optional[int] = None,
        fetch_chunk: Optional[int] = None,
        idle_sleep: Optional[float] = None,
        busy_sleep: Optional[float] = None,
        backlog_warn_at: Optional[int] = None,
        # callbacks de preço
        pol_price_fn: Optional[Callable[[], float]] = None,
    ):
        self._db_path = db_path
        self._rpc_pool = RpcPool(rpc_urls)
        self._contracts = contracts
        self._tokens_to_watch = [t.lower() for t in tokens_to_watch]
        self._topic_openposition = topic_openposition
        self._topic_transfer = topic_transfer
        self._abi_payments = abi_payments
        self._abi_erc20 = abi_erc20
        self._wallet_map_fn = wallet_map_fn
        self._infer_env_fn = infer_env_fn or (lambda addr: "UNKNOWN")
        self._pol_price_fn = pol_price_fn or (lambda: 0.0)

        # tuning via env > constructor > defaults
        self._max_blocks = max_blocks_per_loop or _env_int("MONITOR_MAX_BLOCKS_PER_LOOP", 80)
        self._chunk = fetch_chunk or _env_int("MONITOR_FETCH_CHUNK", 25)
        self._idle_sleep = idle_sleep or _env_float("MONITOR_IDLE_SLEEP", 1.2)
        self._busy_sleep = busy_sleep or _env_float("MONITOR_BUSY_SLEEP", 0.25)
        self._backlog_warn = backlog_warn_at or _env_int("MONITOR_BACKLOG_WARN_AT", 100)

        self._bus = _EventBus()
        self._block_cache = BlockTimeCache(db_path)

        # estado interno
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._health = {
            "started_at": time.time(),
            "last_block": 0,
            "loops_total": 0,
            "ops_total": 0,
            "rpc_errors": 0,
            "capture_rate": 100.0,
            "last_error": "",
            "blocks_processed": 0,
            "blocks_skipped": 0,
        }
        self._tx_cache_ts: Dict[str, float] = {}  # dedup de tx+receipt

        # contratos Web3 compilados
        from web3 import Web3
        self._Web3 = Web3
        self._payment_contracts: Dict[str, Any] = {}
        self._erc20_contracts: Dict[str, Any] = {}
        self._build_contracts()

    # ── Construção de contratos ────────────────────────────────────────────
    def _build_contracts(self):
        W3 = self._rpc_pool.primary
        from web3 import Web3
        for env, addrs in self._contracts.items():
            payments_addr = addrs.get("PAYMENTS", "")
            if payments_addr:
                try:
                    self._payment_contracts[env] = W3.eth.contract(
                        address=Web3.to_checksum_address(payments_addr),
                        abi=self._abi_payments,
                    )
                except Exception as exc:
                    logger.warning("_build_contracts %s: %s", env, exc)

        for addr in self._tokens_to_watch:
            try:
                self._erc20_contracts[addr] = W3.eth.contract(
                    address=Web3.to_checksum_address(addr),
                    abi=self._abi_erc20,
                )
            except Exception as exc:
                logger.warning("_build_contracts token %s: %s", addr, exc)

    # ── EventEmitter API ──────────────────────────────────────────────────
    def on(self, event: str, callback: Callable) -> "Vigia":
        self._bus.on(event, callback)
        return self

    # ── Lifecycle ─────────────────────────────────────────────────────────
    def start(self, daemon: bool = True) -> "Vigia":
        """Inicia o loop em thread separada."""
        if self._running:
            logger.warning("Vigia.start() chamado mas já está rodando")
            return self
        self._running = True
        self._health["started_at"] = time.time()
        self._thread = threading.Thread(target=self._loop, name="vigia-loop", daemon=daemon)
        self._thread.start()
        logger.info("👀 Vigia iniciada (thread=%s)", self._thread.name)
        return self

    def stop(self, timeout: float = 10.0):
        """Para o loop graciosamente."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info("👀 Vigia parada.")

    @property
    def is_running(self) -> bool:
        return self._running and bool(self._thread and self._thread.is_alive())

    @property
    def health(self) -> Dict:
        return dict(self._health)

    # ── Loop principal ────────────────────────────────────────────────────
    def _loop(self):
        last = self._init_last_block()
        _err_backoff = 1

        while self._running:
            try:
                self._health["loops_total"] += 1

                # cooldown RPC
                cooldown_until = float(self._health.get("cooldown_until", 0) or 0)
                if time.time() < cooldown_until:
                    time.sleep(max(1.0, self._idle_sleep))
                    continue

                curr = self._rpc_pool.block_number()
                self._health["last_block"] = curr
                _err_backoff = 1  # reset após sucesso

                if curr > last:
                    backlog = curr - last
                    target = min(curr, last + self._max_blocks)

                    if backlog > self._backlog_warn:
                        logger.warning("⚠️ Backlog %d blocos → processando %d→%d", backlog, last + 1, target)

                    ops_count = self._fetch_range(last + 1, target)

                    self._health["blocks_processed"] += (target - last)
                    _total = self._health["blocks_processed"] + self._health["blocks_skipped"]
                    self._health["capture_rate"] = (
                        self._health["blocks_processed"] / _total * 100 if _total > 0 else 100.0
                    )

                    last = target
                    _db_set_config(self._db_path, "last_block", str(last))

                    self._bus.emit("progress", {
                        "last_block": last,
                        "current_block": curr,
                        "lag": curr - last,
                        "ops_in_cycle": ops_count,
                        "loops_total": self._health["loops_total"],
                        "capture_rate": self._health["capture_rate"],
                    })

                    if last < curr:
                        time.sleep(max(0.05, self._busy_sleep))
                        continue
                else:
                    self._bus.emit("idle", None)

                time.sleep(max(0.2, self._idle_sleep))

                # persiste health a cada 10 loops
                if self._health["loops_total"] % 10 == 0:
                    _db_upsert_vigia_health(self._db_path, self._health)

            except Exception as exc:
                self._health["last_error"] = str(exc)[:500]
                self._health["rpc_errors"] += 1
                self._bus.emit("error", str(exc))

                if _is_429_error(exc):
                    self._health["cooldown_until"] = time.time() + 60
                    time.sleep(10)
                else:
                    sleep_t = min(120, 5 * _err_backoff)
                    logger.warning("vigia loop erro (backoff %ds): %s", sleep_t, exc)
                    time.sleep(sleep_t)
                    _err_backoff = min(_err_backoff * 2, 24)

        _db_upsert_vigia_health(self._db_path, self._health)

    def _init_last_block(self) -> int:
        """Determina o bloco de início (persisted ou curr-5)."""
        try:
            curr_bn = self._rpc_pool.block_number()
        except Exception as exc:
            logger.error("_init_last_block: %s", exc)
            time.sleep(5)
            return 0
        persisted = _db_get_config(self._db_path, "last_block", "").strip()
        if persisted.isdigit():
            last = int(persisted)
            if last > curr_bn:
                last = max(1, curr_bn - 5)
        else:
            last = max(1, curr_bn - 5)
        self._health["last_block"] = last
        logger.info("👀 Vigia: iniciando no bloco %d (atual: %d)", last, curr_bn)
        return last

    # ── Fetch range ───────────────────────────────────────────────────────
    def _safe_get_logs(self, params: dict, depth: int = 0) -> list:
        try:
            return self._rpc_pool.get_logs(params)
        except Exception as exc:
            if _is_429_error(exc):
                self._health["last_error"] = f"get_logs 429: {exc}"
                cd = min(180, 15 * (depth + 1))
                self._health["cooldown_until"] = time.time() + cd
                time.sleep(min(10, cd))
                return []
            if depth >= 4:
                self._health["last_error"] = f"get_logs: {exc}"
                return []
            try:
                fb = int(params["fromBlock"], 16)
                tb = int(params["toBlock"], 16)
            except Exception:
                return []
            if tb <= fb:
                return []
            mid = (fb + tb) // 2
            l, r = dict(params), dict(params)
            l["toBlock"] = self._Web3.to_hex(mid)
            r["fromBlock"] = self._Web3.to_hex(mid + 1)
            return self._safe_get_logs(l, depth + 1) + self._safe_get_logs(r, depth + 1)

    def _fetch_range(self, start: int, end: int) -> int:
        """Busca logs no intervalo [start, end] e processa. Retorna qtd de ops novas."""
        ops_count = 0
        wallet_map = self._wallet_map_fn()

        chunk = max(1, self._chunk)
        cur = start
        while cur <= end:
            nxt = min(end, cur + chunk - 1)
            p_from = self._Web3.to_hex(int(cur))
            p_to   = self._Web3.to_hex(int(nxt))

            # ── Trades ────────────────────────────────────────────────────
            for env, addrs in self._contracts.items():
                try:
                    payments_addr = addrs.get("PAYMENTS", "")
                    if not payments_addr:
                        continue
                    addr_cs = self._Web3.to_checksum_address(payments_addr)
                    logs = self._safe_get_logs({
                        "fromBlock": p_from, "toBlock": p_to,
                        "address": addr_cs,
                        "topics": [self._topic_openposition],
                    })
                    for log in logs:
                        op = self._parse_trade_log(log, env, wallet_map)
                        if op and _db_insert_op(self._db_path, op):
                            self._health["ops_total"] += 1
                            ops_count += 1
                            self._bus.emit("operation", op)
                except Exception as exc:
                    self._health["last_error"] = f"fetch trade {env}: {exc}"

            # ── Transfers ─────────────────────────────────────────────────
            try:
                token_addrs = [
                    self._Web3.to_checksum_address(t) for t in self._tokens_to_watch
                ]
                if token_addrs:
                    logs = self._safe_get_logs({
                        "fromBlock": p_from, "toBlock": p_to,
                        "address": token_addrs,
                        "topics": [self._topic_transfer],
                    })
                    for log in logs:
                        for op in self._parse_transfer_log(log, wallet_map):
                            if op and _db_insert_op(self._db_path, op):
                                self._health["ops_total"] += 1
                                ops_count += 1
                                self._bus.emit("operation", op)
            except Exception as exc:
                self._health["last_error"] = f"fetch transfer: {exc}"

            cur = nxt + 1

        return ops_count

    # ── Parsers ───────────────────────────────────────────────────────────
    def _get_gas(self, tx_hash: str) -> Tuple[float, float]:
        """Retorna (gas_pol, gas_usd). Cache anti-redundância."""
        now = time.time()
        if tx_hash in self._tx_cache_ts and (now - self._tx_cache_ts[tx_hash]) < 60:
            return 0.0, 0.0
        self._tx_cache_ts[tx_hash] = now
        try:
            t = self._rpc_pool.get_transaction(tx_hash)
            r = self._rpc_pool.get_receipt(tx_hash)
            if t and r:
                gas_pol = float(
                    Decimal(r["gasUsed"]) * Decimal(t["gasPrice"]) / Decimal(10 ** 18)
                )
                gas_usd = gas_pol * self._pol_price_fn()
                return gas_pol, gas_usd
        except Exception:
            pass
        return 0.0, 0.0

    def _parse_trade_log(self, log: Dict, env: str, wallet_map: Dict) -> Optional[Dict]:
        try:
            contract = self._payment_contracts.get(env)
            if not contract:
                return None
            evt = contract.events.OpenPosition().process_log(log)
            args = evt["args"]
            uw = str(args["user"]).lower().strip()
            if uw not in wallet_map:
                return None

            details = args["details"]
            coin_addr = str(details["coin"]).lower()
            # decimais padrão 6 para USDT, 18 para outros
            dec = 18
            sym = "UNKNOWN"
            # tenta resolver pelo endereço (o caller pode fornecer get_token_meta_fn)
            try:
                dec_env = self._contracts.get(env, {}).get("_TOKEN_DECIMALS", {})
                if coin_addr in dec_env:
                    dec = dec_env[coin_addr]["dec"]
                    sym = dec_env[coin_addr]["sym"]
            except Exception:
                pass

            val = float(Decimal(int(details["profit"])) / Decimal(10 ** dec))
            fee = float(Decimal(int(details.get("fee", 0))) / Decimal(10 ** 9))
            strategy_addr = str(details.get("strategy") or "").lower().strip()
            bot_id = str(details.get("botId") or "").strip()
            old_bal_raw = int(details.get("oldBalance") or 0)
            old_bal_usd = float(old_bal_raw) / (10 ** dec) if old_bal_raw > 0 else 0.0
            gas_proto_raw = int(details.get("gas") or 0)
            gas_proto = float(gas_proto_raw) / (10 ** dec) if gas_proto_raw > 0 else 0.0

            tx_hash = str(log.get("transactionHash") or "").lower().strip()
            if tx_hash.startswith("0x") is False and len(tx_hash) == 64:
                tx_hash = "0x" + tx_hash

            gas_pol, gas_usd = self._get_gas(tx_hash)

            return {
                "tipo": "Trade",
                "tx_hash": tx_hash,
                "log_index": int(log["logIndex"]),
                "bloco": int(log["blockNumber"]),
                "ambiente": env,
                "sub_conta": str(args["accountId"]),
                "owner_wallet": uw,
                "valor": val,
                "gas_usd": gas_usd,
                "gas_pol": gas_pol,
                "token": sym,
                "fee": fee,
                "strategy_addr": strategy_addr,
                "bot_id": bot_id,
                "gas_protocol": gas_proto,
                "old_balance_usd": old_bal_usd,
                "notify_cids": list(wallet_map.get(uw, [])),
            }
        except Exception as exc:
            logger.debug("_parse_trade_log: %s", exc)
            return None

    def _parse_transfer_log(self, log: Dict, wallet_map: Dict) -> List[Dict]:
        ops = []
        try:
            addr = str(log.get("address", "")).lower()
            contract = self._erc20_contracts.get(addr)
            if not contract:
                return ops
            evt = contract.events.Transfer().process_log(log)
            args = evt["args"]
            to_w = str(args["to"]).lower()
            fr_w = str(args["from"]).lower()
            if (to_w not in wallet_map) and (fr_w not in wallet_map):
                return ops

            dec = 18
            sym = "TOKEN"
            tx_hash = str(log.get("transactionHash") or "").lower().strip()
            val = float(Decimal(int(args["value"])) / Decimal(10 ** dec))
            bloco = int(log["blockNumber"])
            log_idx = int(log["logIndex"])

            if to_w in wallet_map:
                ops.append({
                    "tipo": "Transfer",
                    "tx_hash": tx_hash,
                    "log_index": log_idx,
                    "bloco": bloco,
                    "ambiente": self._infer_env_fn(str(log.get("address", ""))),
                    "sub_conta": "WALLET",
                    "owner_wallet": to_w,
                    "valor": val,
                    "gas_usd": 0.0,
                    "gas_pol": 0.0,
                    "token": sym,
                    "fee": 0.0,
                    "notify_cids": list(wallet_map.get(to_w, [])),
                })
            if fr_w in wallet_map:
                ops.append({
                    "tipo": "Transfer",
                    "tx_hash": tx_hash,
                    "log_index": log_idx + 10000,  # log_index separado para saída
                    "bloco": bloco,
                    "ambiente": self._infer_env_fn(str(log.get("address", ""))),
                    "sub_conta": "WALLET",
                    "owner_wallet": fr_w,
                    "valor": -val,
                    "gas_usd": 0.0,
                    "gas_pol": 0.0,
                    "token": sym,
                    "fee": 0.0,
                    "notify_cids": list(wallet_map.get(fr_w, [])),
                })
        except Exception as exc:
            logger.debug("_parse_transfer_log: %s", exc)
        return ops
