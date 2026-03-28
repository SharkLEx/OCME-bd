"""
webdex_chain_health.py — Blockchain Status Health Gate
Consulta https://apiv5.webdex.fyi/blockchain-status/components
Cache 5min. Fail-open: assume operational se endpoint inacessível.
"""
import time
import json
import urllib.request
from webdex_config import logger

BLOCKCHAIN_STATUS_URL = 'https://apiv5.webdex.fyi/blockchain-status/components'
CACHE_TTL = 300  # 5 minutos

# Componentes críticos para o monitor engine
_CRITICAL_IDS = {
    'mt7b1lkfp47x': 'Mainnet RPC',
    '4zph5b594yyf': 'Mainnet Tendermint API',
    '7nrcwy9yyr0m': 'Mainnet Heimdall API',
}

_HEALTHY_STATUSES = {'operational'}

# Cache em memória
_cache: dict = {'ts': 0.0, 'data': None}


def fetch_chain_status(timeout: int = 5) -> dict | None:
    """Busca status dos componentes. Retorna None se endpoint inacessível."""
    now = time.time()
    if now - _cache['ts'] < CACHE_TTL and _cache['data'] is not None:
        return _cache['data']
    try:
        req = urllib.request.Request(
            BLOCKCHAIN_STATUS_URL,
            headers={'User-Agent': 'WEbdEX-Monitor/1.0'},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            _cache['ts'] = now
            _cache['data'] = data
            return data
    except Exception as exc:
        logger.warning('[chain_health] fetch falhou (fail-open): %s', exc)
        return None


def get_chain_health() -> dict:
    """
    Retorna {
      'healthy': bool,
      'degraded': list[str],   # nomes dos componentes fora do ar
      'checked_at': str|None,  # updated_at da API
    }
    Fail-open: se endpoint inacessível retorna healthy=True.
    """
    data = fetch_chain_status()
    if data is None:
        return {'healthy': True, 'degraded': [], 'checked_at': None}

    components = data.get('data', {}).get('components', [])
    degraded = []
    for comp in components:
        comp_id = comp.get('id')
        status = comp.get('status', 'operational')
        if comp_id in _CRITICAL_IDS and status not in _HEALTHY_STATUSES:
            degraded.append(f"{_CRITICAL_IDS[comp_id]} ({status})")

    return {
        'healthy': len(degraded) == 0,
        'degraded': degraded,
        'checked_at': data.get('data', {}).get('updated_at'),
    }


def is_rpc_healthy() -> bool:
    """True se Mainnet RPC está operational. Fail-open."""
    data = fetch_chain_status()
    if data is None:
        return True
    for comp in data.get('data', {}).get('components', []):
        if comp.get('id') == 'mt7b1lkfp47x':
            return comp.get('status') == 'operational'
    return True
