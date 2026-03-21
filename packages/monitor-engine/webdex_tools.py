"""
webdex_tools.py — Tool Use / Function Calling para bdZinho
Story 12.2 | Epic 12 — bdZinho Intelligence v3

Tools disponíveis para OpenAI Function Calling:
  - get_protocol_metrics: TVL, volume 24h, APY do protocolo WEbdEX
  - get_user_portfolio:   Portfolio on-chain do usuário (wallet, saldo, PnL)
  - get_market_context:   Gas price, sentimento, contexto de mercado

Circuit Breaker: 3 falhas consecutivas → OPEN por 5 min
Rate limit: 20 tool calls/hora por chat_id (sliding window)
Timeout: configurável por tool (default 8s)
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ==============================================================================
# 📋 TOOL DEFINITIONS (OpenAI Function Calling format)
# ==============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_protocol_metrics",
            "description": (
                "Busca métricas em tempo real do protocolo WEbdEX: "
                "TVL (Total Value Locked), volume 24h e APY das pools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": ["tvl", "volume_24h", "apy", "all"],
                        "description": "Qual métrica buscar. Use 'all' para todas.",
                    }
                },
                "required": ["metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_portfolio",
            "description": (
                "Busca o portfolio on-chain de um usuário WEbdEX: "
                "saldo de capital, posições abertas e PnL (lucro/prejuízo)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "wallet": {
                        "type": "string",
                        "description": "Endereço Ethereum/Polygon do usuário (0x...).",
                    }
                },
                "required": ["wallet"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_context",
            "description": (
                "Busca o contexto atual do mercado: preço do gas na Polygon, "
                "preço do POL, e estado geral do bot."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

# Timeout por tool (segundos)
TOOL_TIMEOUTS: dict[str, int] = {
    "get_protocol_metrics": 8,
    "get_user_portfolio": 10,
    "get_market_context": 5,
}

# Fallback genérico quando tool falha
_FALLBACK_MSG = (
    "Não consegui buscar essa informação agora (serviço temporariamente indisponível). "
    "Posso te ajudar com outras dúvidas, ou tente novamente em alguns minutos."
)


# ==============================================================================
# ⚡ CIRCUIT BREAKER
# ==============================================================================

class _CircuitState:
    CLOSED    = "CLOSED"     # Normal — tool funcionando
    OPEN      = "OPEN"       # Desabilitada (muitas falhas)
    HALF_OPEN = "HALF_OPEN"  # Testando se voltou


class ToolCircuitBreaker:
    """
    Circuit breaker por tool name.
    - 3 falhas consecutivas → OPEN por _COOLDOWN segundos
    - Após cooldown: HALF_OPEN → testa 1 vez → fecha ou abre novamente
    """

    _THRESHOLD = 3      # falhas para abrir
    _COOLDOWN  = 300    # segundos aberto (5 min)

    def __init__(self):
        self._states:   dict[str, str]   = {}
        self._fails:    dict[str, int]   = {}
        self._open_at:  dict[str, float] = {}
        self._lock = threading.Lock()

    def is_available(self, name: str) -> bool:
        with self._lock:
            state = self._states.get(name, _CircuitState.CLOSED)
            if state == _CircuitState.CLOSED:
                return True
            if state == _CircuitState.OPEN:
                if time.time() - self._open_at.get(name, 0) >= self._COOLDOWN:
                    self._states[name] = _CircuitState.HALF_OPEN
                    logger.info("[tools] Circuit breaker HALF_OPEN para %s", name)
                    return True
                return False
            # HALF_OPEN — permite 1 tentativa
            return True

    def record_success(self, name: str) -> None:
        with self._lock:
            self._states[name] = _CircuitState.CLOSED
            self._fails[name]  = 0

    def record_failure(self, name: str) -> None:
        with self._lock:
            fails = self._fails.get(name, 0) + 1
            self._fails[name] = fails
            state = self._states.get(name, _CircuitState.CLOSED)
            if state == _CircuitState.HALF_OPEN or fails >= self._THRESHOLD:
                self._states[name] = _CircuitState.OPEN
                self._open_at[name] = time.time()
                logger.warning(
                    "[tools] Circuit breaker OPEN para %s (%d falhas — cooldown %ds)",
                    name, fails, self._COOLDOWN,
                )


_circuit = ToolCircuitBreaker()


# ==============================================================================
# ⏱️ RATE LIMITER
# ==============================================================================

_rate_data: dict[int, list[float]] = {}  # chat_id → timestamps de calls
_rate_lock = threading.Lock()
_RATE_LIMIT = 20          # max calls por hora por chat_id
_RATE_WINDOW = 3600.0     # sliding window em segundos


def _check_rate_limit(chat_id: int) -> bool:
    """Retorna True se call é permitida, False se rate limit excedido."""
    now = time.time()
    with _rate_lock:
        times = _rate_data.get(chat_id, [])
        # Remover timestamps fora da janela
        times = [t for t in times if now - t < _RATE_WINDOW]
        if len(times) >= _RATE_LIMIT:
            _rate_data[chat_id] = times
            return False
        times.append(now)
        _rate_data[chat_id] = times
        return True


# ==============================================================================
# 🔧 TOOL IMPLEMENTATIONS
# ==============================================================================

def _impl_get_protocol_metrics(metric: str) -> str:
    """Busca métricas do protocolo WEbdEX a partir do SQLite local."""
    try:
        from webdex_db import cursor, DB_LOCK

        results: dict = {}

        with DB_LOCK:
            # TVL: última snapshot total
            row = cursor.execute(
                "SELECT total_usd, ts FROM fl_snapshots ORDER BY ts DESC LIMIT 1"
            ).fetchone()
            if row and row[0]:
                results["tvl"] = f"${float(row[0]):,.2f} USD"
                results["tvl_ts"] = str(row[1])
            else:
                results["tvl"] = "dados indisponíveis"

            # Volume 24h: soma de gas_pol das operações das últimas 24h
            row_vol = cursor.execute(
                """SELECT COUNT(*) as ops, SUM(gas_pol) as gas
                   FROM protocol_ops
                   WHERE data_hora >= datetime('now', '-24 hours')"""
            ).fetchone()
            if row_vol:
                results["volume_24h_ops"] = int(row_vol[0] or 0)
                results["volume_24h_gas_pol"] = round(float(row_vol[1] or 0), 4)
            else:
                results["volume_24h_ops"] = 0

            # APY: valor configurado (ou calculado externamente)
            apy_raw = cursor.execute(
                "SELECT value FROM config WHERE key='apy_atual'"
            ).fetchone()
            results["apy"] = (apy_raw[0] if apy_raw else "N/A")

        if metric == "tvl":
            return f"TVL WEbdEX: {results.get('tvl', 'N/A')}"
        elif metric == "volume_24h":
            return (
                f"Volume 24h: {results['volume_24h_ops']} operações | "
                f"Gas: {results['volume_24h_gas_pol']} POL"
            )
        elif metric == "apy":
            return f"APY atual: {results.get('apy', 'N/A')}%"
        else:  # all
            return json.dumps(results, ensure_ascii=False)

    except Exception as e:
        logger.warning("[tools] get_protocol_metrics falhou: %s", e)
        raise


def _impl_get_user_portfolio(wallet: str) -> str:
    """Busca portfolio do usuário no banco local."""
    try:
        from webdex_db import cursor, DB_LOCK

        wallet_lower = wallet.lower().strip()

        with DB_LOCK:
            # Capital cache do usuário
            row = cursor.execute(
                "SELECT capital_usd, atualizado_em FROM capital_cache WHERE wallet=?",
                (wallet_lower,)
            ).fetchone()

            # Última snapshot de liquidez
            snap = cursor.execute(
                """SELECT total_usd, liq_usdt, liq_loop, pol_price, ts
                   FROM fl_snapshots
                   WHERE wallet=? ORDER BY ts DESC LIMIT 1""",
                (wallet_lower,)
            ).fetchone()

            # Operações recentes (últimas 24h)
            ops = cursor.execute(
                """SELECT COUNT(*) FROM protocol_ops
                   WHERE wallet=? AND data_hora >= datetime('now', '-24 hours')""",
                (wallet_lower,)
            ).fetchone()

        if not snap and not row:
            w_short = f"{wallet[:6]}...{wallet[-4:]}"
            return (
                f"Carteira {w_short} não encontrada no sistema WEbdEX. "
                "Verifique se o endereço está correto ou se está registrado."
            )

        capital_usd = float((row[0] if row and row[0] else None) or
                            (snap[0] if snap and snap[0] else 0))
        liq_usdt = float(snap[1]) if snap and snap[1] else 0
        liq_loop = float(snap[2]) if snap and snap[2] else 0
        pol_price = float(snap[3]) if snap and snap[3] else 0
        ops_24h = int(ops[0]) if ops else 0
        ts = snap[4] if snap else "desconhecido"

        w_short = f"{wallet[:6]}...{wallet[-4:]}"
        return (
            f"Portfolio {w_short}:\n"
            f"• Capital total: ${capital_usd:,.2f} USD\n"
            f"• Liquidez USDT: ${liq_usdt:,.2f}\n"
            f"• Liquidez LOOP: ${liq_loop:,.2f}\n"
            f"• Preço POL: ${pol_price:.4f}\n"
            f"• Operações últimas 24h: {ops_24h}\n"
            f"• Atualizado: {ts}"
        )

    except Exception as e:
        logger.warning("[tools] get_user_portfolio falhou: %s", e)
        raise


def _impl_get_market_context() -> str:
    """Busca contexto de mercado via RPC Polygon + dados locais."""
    try:
        from webdex_chain import web3, obter_preco_pol

        gas_wei = web3.eth.gas_price
        gwei = gas_wei / 1e9
        pol_price = obter_preco_pol()

        return (
            f"Contexto de mercado atual:\n"
            f"• Gas Polygon: {gwei:.1f} Gwei\n"
            f"• Preço POL: ${pol_price:.4f} USD\n"
            f"• Rede: Polygon Mainnet\n"
            f"• Status: operacional"
        )
    except Exception as e:
        logger.warning("[tools] get_market_context falhou: %s", e)
        raise


# ==============================================================================
# 🚀 DISPATCHER
# ==============================================================================

_IMPLEMENTATIONS: dict = {
    "get_protocol_metrics": _impl_get_protocol_metrics,
    "get_user_portfolio":   _impl_get_user_portfolio,
    "get_market_context":   _impl_get_market_context,
}


def execute_tool(name: str, args: dict, chat_id: Optional[int] = None) -> str:
    """
    Executa uma tool por nome com os args fornecidos.
    Aplica circuit breaker, rate limit e timeout.

    Args:
        name:    Nome da tool (deve estar em TOOLS)
        args:    Argumentos como dict (parsed do JSON da OpenAI)
        chat_id: ID do chat para rate limiting (None = sem rate limit)

    Returns:
        String com o resultado da tool ou mensagem de erro/fallback.
    """
    # Rate limit
    if chat_id is not None and not _check_rate_limit(chat_id):
        logger.info("[tools] Rate limit excedido para chat_id=%s", chat_id)
        return (
            "Você atingiu o limite de consultas por hora (20). "
            "Aguarde alguns minutos antes de pedir mais dados on-chain."
        )

    # Circuit breaker
    if not _circuit.is_available(name):
        logger.info("[tools] Circuit breaker OPEN — tool %s indisponível", name)
        return _FALLBACK_MSG

    impl = _IMPLEMENTATIONS.get(name)
    if impl is None:
        return f"Tool '{name}' não reconhecida."

    timeout = TOOL_TIMEOUTS.get(name, 8)
    result_container: dict = {}
    error_container:  dict = {}

    def _run():
        try:
            result_container["v"] = impl(**args)
        except Exception as e:
            error_container["e"] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        # Timeout — thread ainda rodando (daemon vai morrer com processo)
        _circuit.record_failure(name)
        logger.warning("[tools] Timeout (%ds) na tool %s", timeout, name)
        return _FALLBACK_MSG

    if "e" in error_container:
        _circuit.record_failure(name)
        logger.warning("[tools] Erro na tool %s: %s", name, error_container["e"])
        return _FALLBACK_MSG

    _circuit.record_success(name)
    return result_container.get("v", _FALLBACK_MSG)
