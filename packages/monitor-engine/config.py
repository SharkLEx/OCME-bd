# ==============================================================================
# config.py — Fonte única de verdade para todas as variáveis de ambiente
# OCME bd Monitor Engine — Story 7.1 / Epic 7
# NUNCA hardcode credenciais aqui. Use .env
# ==============================================================================
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env do diretório do script ou do diretório pai
_ENV_CANDIDATES = [
    Path(__file__).resolve().parent / '.env',
    Path(__file__).resolve().parent.parent.parent / 'Documents' / '.env',
    Path(os.getcwd()) / '.env',
]
for _p in _ENV_CANDIDATES:
    if _p.exists():
        load_dotenv(dotenv_path=_p, override=True)
        break

def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

def _list(name: str, default: list[str] | None = None) -> list[int]:
    raw = os.getenv(name, '')
    if not raw:
        return default or []
    parts = re.split(r'[\s,;]+', raw.strip())
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            pass
    return list(dict.fromkeys(result))  # dedup preserve order

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN', os.getenv('BOT_TOKEN', '')).strip()

# ── Blockchain ────────────────────────────────────────────────────────────────
_RPC_FALLBACKS = [
    'https://polygon-bor-rpc.publicnode.com',
    'https://1rpc.io/matic',
    'https://polygon.drpc.org',
    'https://polygon-rpc.com',
]
RPC_URL: str     = os.getenv('RPC_URL', _RPC_FALLBACKS[0]).strip()
RPC_CAPITAL: str = os.getenv('RPC_CAPITAL', _RPC_FALLBACKS[1]).strip()
POLYGONSCAN_API_KEY: str = os.getenv('POLYGONSCAN_API_KEY', '').strip()

# ── Tokens on Polygon ─────────────────────────────────────────────────────────
TOKEN_USDT_ADDRESS: str  = os.getenv('TOKEN_USDT_ADDRESS',  '0xc2132D05D31c914a87C6611C10748AEb04B58e8F').strip()
TOKEN_LOOP_ADDRESS: str  = os.getenv('TOKEN_LOOP_ADDRESS',  '0xc4CF5093676e8a61404f51bC6Ceaec5279Ce8645').strip()
_lp_raw = os.getenv('TOKEN_LP_ADDRESS', '0xFb2e2Ff7B51C2BcAf58619a55e7d2Ff88cFD8aCA,0xB56032D0B576472b3f0f1e4747f488769dE2b00B')
TOKEN_LP_ADDRESSES: list[str] = [a.strip() for a in _lp_raw.split(',') if a.strip()]

# ── Contratos por ambiente ────────────────────────────────────────────────────
# Carregados do .env — sem hardcode de endereços de produção
CONTRACTS: dict = {
    'AG_C_bd': {
        'PAYMENTS':    os.getenv('AG_C_BD_PAYMENTS',    '0x96bF20B20de9c01D5F1f0fC74321ccC63E3f29F1'),
        'SUBACCOUNTS': os.getenv('AG_C_BD_SUBACCOUNTS', '0x14eEd4F2Bfcfd85E2262987Cf8cbcD97B02557ca'),
        'MANAGER':     os.getenv('AG_C_BD_MANAGER',     '0x685d04d62DA1Ef26529c7Aa1364da504c8ACDb1D'),
        'TOKENPASS':   os.getenv('AG_C_BD_TOKENPASS',   '0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d'),
        'LP_USDT':     os.getenv('AG_C_BD_LP_USDT',     '0x238966212E0446C04a225343DAAfb3c3A7D4F37C'),
        'LP_LOOP':     os.getenv('AG_C_BD_LP_LOOP',     '0xC3adC8b72B1C3F208E5d1614cDF87FdD93762812'),
        'TAG': 'AG_C_bd',
    },
    'bd_v5': {
        'MANAGER':     os.getenv('BD_V5_MANAGER',     '0x9826a9727D5bB97A44Bf14Fe2E2B0B1D5a81C860'),
        'PAYMENTS':    os.getenv('BD_V5_PAYMENTS',    '0x48748959392e9fa8a72031c51593dcf52572e120'),
        'SUBACCOUNTS': os.getenv('BD_V5_SUBACCOUNTS', '0x6995077c49d920D8516AF7b87a38FdaC5E2c957C'),
        'TOKENPASS':   os.getenv('BD_V5_TOKENPASS',   '0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d'),
        'LP_USDT':     os.getenv('BD_V5_LP_USDT',     '0xFb2e2Ff7B51C2BcAf58619a55e7d2Ff88cFD8aCA'),
        'LP_LOOP':     os.getenv('BD_V5_LP_LOOP',     '0xB56032D0B576472b3f0f1e4747f488769dE2b00B'),
        'TAG': 'bd_v5',
    },
}
ENV_ALIASES: dict[str, str] = {
    'beta_v5': 'bd_v5', 'bdv5': 'bd_v5', 'v5': 'bd_v5',
    'agc_bd': 'AG_C_bd', 'ag_c_bd': 'AG_C_bd', 'agcbd': 'AG_C_bd',
}

# ── Monitor ───────────────────────────────────────────────────────────────────
MONITOR_MAX_BLOCKS_PER_LOOP: int   = _int('MONITOR_MAX_BLOCKS_PER_LOOP', 80)
MONITOR_FETCH_CHUNK: int           = _int('MONITOR_FETCH_CHUNK', 25)
MONITOR_IDLE_SLEEP: float          = _float('MONITOR_IDLE_SLEEP', 1.2)
MONITOR_BUSY_SLEEP: float          = _float('MONITOR_BUSY_SLEEP', 0.25)
MONITOR_TRANSFER_EVERY_N: int      = _int('MONITOR_TRANSFER_EVERY_N', 3)
MONITOR_BACKLOG_WARN_AT: int       = _int('MONITOR_BACKLOG_WARN_AT', 20)

# ── Limites / Sentinela ────────────────────────────────────────────────────────
LIMITE_GWEI: float         = _float('LIMITE_GWEI', 1000.0)
LIMITE_GAS_BAIXO_POL: float = _float('LIMITE_SALDO_GAS', 2.0)
LIMITE_INATIV_MIN: float   = _float('LIMITE_INATIV_MIN', 30.0)

# ── IA ────────────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv('OPENROUTER_API_KEY', '').strip().strip('"').strip("'")
OPENAI_API_KEY: str     = os.getenv('OPENAI_API_KEY', '').strip().strip('"').strip("'")
AI_API_KEY: str         = OPENROUTER_API_KEY or OPENAI_API_KEY
AI_BASE_URL: str        = 'https://openrouter.ai/api/v1' if OPENROUTER_API_KEY else 'https://api.openai.com/v1'
OPENAI_MODEL: str       = os.getenv('OPENAI_MODEL', 'gpt-4.1-nano').strip()
OPENAI_DEFAULT_ON: bool = os.getenv('OPENAI_DEFAULT_ON', '1').strip() not in ('0', 'false', 'False', 'no')

# ── Banco de dados ────────────────────────────────────────────────────────────
_DATA_DIR = '/app/data' if os.path.isdir('/app/data') else '.'
DB_PATH: str = os.getenv('DB_PATH', os.path.join(_DATA_DIR, 'webdex_v5_final.db'))

# ── Admin ─────────────────────────────────────────────────────────────────────
ADMIN_USER_IDS: list[int] = _list(
    'ADMIN_USER_IDS') or _list('ADM_IDS') or _list('ADMIN_USER_ID') or []
_owner_raw = os.getenv('OWNER_CHAT_ID', os.getenv('OWNER_ID', ''))
try:
    OWNER_CHAT_ID: int | None = int(_owner_raw) if _owner_raw else None
except ValueError:
    OWNER_CHAT_ID = None
if OWNER_CHAT_ID and OWNER_CHAT_ID not in ADMIN_USER_IDS:
    ADMIN_USER_IDS.append(OWNER_CHAT_ID)

# ── Wallet padrão ─────────────────────────────────────────────────────────────
WALLET_ADDRESS: str = os.getenv('WALLET_ADDRESS', '').strip().lower()
