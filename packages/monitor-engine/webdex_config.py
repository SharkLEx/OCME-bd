from __future__ import annotations
# ==============================================================================
# webdex_config.py — WEbdEX Monitor Engine (extraído de WEbdEX_V30_24_SPEED_PATCH_FIXED.py)
# Linhas fonte: ~1-527
# NUNCA hardcode credenciais aqui. Use .env
# ==============================================================================

import os
import time
import json
import sqlite3
import threading
import queue
import logging
import re
from datetime import datetime, timedelta

# --- SQLite datetime adapter (Python 3.12+ deprecation safe) ---
try:
    sqlite3.register_adapter(datetime, lambda d: d.isoformat(sep=' ', timespec='seconds'))
except Exception:
    pass

import html
import hashlib
from decimal import Decimal, getcontext
import io
from typing import Any, Dict, List, Tuple, Optional
import math
from statistics import median

import requests
import telebot
from telebot import types
from telebot import apihelper
from dotenv import load_dotenv

# ================================
# TELEGRAM PRETTY (AI TEXT)
# ================================

try:
    _MD_CLEAN_RE = re.compile(r"(\*\*|\*|`|^#{1,6}\s*)", re.M)
except Exception:
    _MD_CLEAN_RE = None

def _pretty_ai_text(s: str) -> str:
    """Converte markdown genérico em texto amigável no Telegram (sem depender de Markdown parse_mode)."""
    if not s:
        return ""
    s = s.replace("\r\n", "\n")
    if _MD_CLEAN_RE:
        s = _MD_CLEAN_RE.sub("", s)
    else:
        s = s.replace("**", "").replace("*", "").replace("`", "")
    s = re.sub(r"^\s*[-–•]\s+", "• ", s, flags=re.M)
    s = re.sub(r"^\s*(Resumo)\s*:?\s*$", "🧾 Resumo", s, flags=re.I|re.M)
    s = re.sub(r"^\s*(Como funciona)\s*:?\s*$", "🧩 Como funciona", s, flags=re.I|re.M)
    s = re.sub(r"^\s*(Por que)\s*:?\s*$", "❓ Por que", s, flags=re.I|re.M)
    s = re.sub(r"^\s*(Passo a passo)\s*:?\s*$", "🛠️ Passo a passo", s, flags=re.I|re.M)
    s = re.sub(r"^\s*(Riscos?)\s*:?\s*$", "⚠️ Riscos", s, flags=re.I|re.M)
    s = re.sub(r"^\s*(Boas práticas)\s*:?\s*$", "✅ Boas práticas", s, flags=re.I|re.M)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

# ======================================================================
# 🌐 TELEGRAM HTTP HARDENING
# ======================================================================
try:
    apihelper.RETRY_ON_ERROR = True
    _sess = requests.Session()
    _adapter = requests.adapters.HTTPAdapter(max_retries=3, pool_connections=20, pool_maxsize=20)
    _sess.mount("https://", _adapter)
    _sess.mount("http://", _adapter)
    apihelper.SESSION = _sess
    apihelper.CONNECT_TIMEOUT = 10
    apihelper.READ_TIMEOUT = 30
except Exception:
    pass

from web3 import Web3

# Matplotlib headless
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Timezone BR
try:
    from zoneinfo import ZoneInfo
    TZ_BR = ZoneInfo("America/Sao_Paulo")
except Exception:
    TZ_BR = None

# ==============================================================================
# ✅ POA Middleware
# ==============================================================================
try:
    from web3.middleware import geth_poa_middleware
    _POA_MW = geth_poa_middleware
except Exception:
    try:
        from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware
        _POA_MW = ExtraDataToPOAMiddleware
    except Exception:
        _POA_MW = None

# ==============================================================================
# 🔐 CONFIG
# ==============================================================================
from pathlib import Path
ENV_PATH = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

def _read_multiline_env_value(var_name: str) -> str:
    try:
        if not ENV_PATH.exists():
            return ""
        lines = ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{var_name}="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                j = i + 1
                while j < len(lines):
                    nxt = lines[j].strip()
                    if (not nxt) or nxt.startswith("#"):
                        j += 1
                        continue
                    if re.match(r"^[A-Z0-9_]+=", nxt):
                        break
                    val += nxt.strip()
                    j += 1
                return re.sub(r"\s+", "", val)
    except Exception:
        return ""
    return ""

getcontext().prec = 50

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or "").strip()

_RPC_PUBLICOS = [
    "https://polygon-rpc.com",
    "https://rpc.ankr.com/polygon",
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
]
RPC_URL     = (os.getenv("RPC_URL") or "").strip()     or _RPC_PUBLICOS[0]
RPC_CAPITAL = (os.getenv("RPC_CAPITAL") or "").strip() or _RPC_PUBLICOS[1]
DEFAULT_RPC = RPC_URL

def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name) or '').strip())
    except Exception:
        return int(default)

def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name) or '').strip())
    except Exception:
        return float(default)

MONITOR_MAX_BLOCKS_PER_LOOP = _env_int("MONITOR_MAX_BLOCKS_PER_LOOP", 80)
MONITOR_FETCH_CHUNK         = _env_int("MONITOR_FETCH_CHUNK", 25)
MONITOR_IDLE_SLEEP          = _env_float("MONITOR_IDLE_SLEEP", 1.2)
MONITOR_BUSY_SLEEP          = _env_float("MONITOR_BUSY_SLEEP", 0.25)
MONITOR_BACKLOG_WARN_AT     = _env_int("MONITOR_BACKLOG_WARN_AT", 20)
MONITOR_SYNC_STEP           = _env_int("MONITOR_SYNC_STEP", 800)

OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip().strip('"').strip("\'")
OPENAI_API_KEY     = (os.getenv("OPENAI_API_KEY") or "").strip().strip('"').strip("\'")
if not OPENAI_API_KEY:
    OPENAI_API_KEY = _read_multiline_env_value("OPENAI_API_KEY")

_AI_API_KEY = OPENROUTER_API_KEY or OPENAI_API_KEY
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "openai/gpt-4.1-nano").strip()
_AI_BASE_URL = (
    "https://openrouter.ai/api/v1"
    if OPENROUTER_API_KEY
    else "https://api.openai.com/v1"
)
OPENAI_DEFAULT_ON = (os.getenv("OPENAI_DEFAULT_ON") or "1").strip() not in ("0", "false", "False", "no", "NO")

if not TELEGRAM_TOKEN:
    print("❌ ERRO: Verifique seu .env (TELEGRAM_TOKEN)")
    raise SystemExit(1)

# ==============================================================================
# 📋 LOGGING
# ==============================================================================
import logging.handlers as _log_handlers

logger = logging.getLogger("WEbdEX")
logger.setLevel(logging.INFO)

if not logger.handlers:
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    _sh = logging.StreamHandler()
    _sh.setFormatter(_fmt)
    logger.addHandler(_sh)
    try:
        _fh = _log_handlers.RotatingFileHandler(
            "webdex.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        _fh.setFormatter(_fmt)
        logger.addHandler(_fh)
    except Exception as _e:
        logger.warning(f"⚠️ Não foi possível criar webdex.log: {_e}")
    logger.propagate = False

def log_error(ctx: str, exc: Exception) -> None:
    try:
        logger.warning(f"[{ctx}] {type(exc).__name__}: {exc}")
    except Exception:
        pass

logging.root.handlers = []
logging.basicConfig(handlers=[logging.NullHandler()])
logging.getLogger().addHandler(logging.StreamHandler())

# ==============================================================================
# 🧠 IA (OpenAI) — respostas em PT-BR (opcional)
# ==============================================================================
_AI_WAITING = {}  # chat_id -> bool

def _openai_extract_text(rj: dict) -> str:
    if isinstance(rj, dict):
        if isinstance(rj.get("output_text"), str) and rj["output_text"].strip():
            return rj["output_text"].strip()
        out = rj.get("output")
        if isinstance(out, list):
            chunks = []
            for item in out:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                            t = c.get("text")
                            if isinstance(t, str) and t.strip():
                                chunks.append(t.strip())
            if chunks:
                return "\n".join(chunks).strip()
    return ""

def ai_answer_ptbr(user_text: str, *, chat_id: int | None = None) -> str:
    if not OPENAI_API_KEY:
        return (
            "IA ainda não configurada.\n\n"
            "Para OpenRouter (recomendado), no .env:\n"
            "OPENROUTER_API_KEY=sk-or-SUA_CHAVE\n"
            "OPENAI_MODEL=openai/gpt-4.1-nano\n\n"
            "Para OpenAI direto:\n"
            "OPENAI_API_KEY=sk-SUA_CHAVE\n"
            "OPENAI_MODEL=gpt-4.1-nano\n\n"
            "Reinicie o bot após configurar."
        )

    system = (
        "Você é a IA oficial da WEbdEX e responde 100% em PT-BR. "
        "Seja direto, claro e técnico quando necessário. "
        "Se o usuário pedir algo fora do escopo do bot, explique como fazer dentro do bot. "
        "Nunca peça dados sensíveis (seed phrase, private key)."
    )

    try:
        import requests as _rq
        url = f"{_AI_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {_AI_API_KEY}",
            "Content-Type": "application/json",
        }
        if OPENROUTER_API_KEY:
            headers["HTTP-Referer"] = "https://webdex.app"
            headers["X-Title"] = "WEbdEX Bot"
        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user_text},
            ],
            "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
            "max_tokens":  int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1400")),
        }
        resp = _rq.post(url, headers=headers, json=payload, timeout=45)
        rj = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            err = ""
            if isinstance(rj, dict):
                e = rj.get("error")
                if isinstance(e, dict):
                    err = e.get("message") or ""
            return f"IA erro ({resp.status_code}). {err}".strip()
        try:
            text = rj["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            text = _openai_extract_text(rj)
        return text or "IA não retornou texto. Tente novamente."
    except Exception as e:
        return f"IA falhou: {e}"


def _parse_admin_ids(raw: str) -> list[int]:
    if not raw:
        return []
    parts = re.split(r"[\s,;]+", raw.strip())
    out = []
    for p in parts:
        if not p:
            continue
        try:
            out.append(int(p))
        except ValueError:
            continue
    seen = set()
    uniq = []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    return uniq


ADMIN_USER_IDS = _parse_admin_ids(
    os.getenv("ADMIN_USER_IDS", "")
    or os.getenv("ADMIN_USER_ID", "")
    or os.getenv("TELEGRAM_ADMIN_IDS", "")
    or os.getenv("TELEGRAM_ADMIN_ID", "")
    or os.getenv("TG_ADMIN_IDS", "")
    or os.getenv("TG_ADMIN_ID", "")
    or os.getenv("ADMIN_IDS", "")
    or os.getenv("ADMIN_ID", "")
    or os.getenv("ADMIN_CHAT_IDS", "")
    or os.getenv("ADM_IDS", "")
    or os.getenv("ADM_ID", "")
    or os.getenv("CREATOR_ID", "")
    or os.getenv("BOT_OWNER_ID", "")
)

_owner = (
    os.getenv("OWNER_CHAT_ID", "")
    or os.getenv("OWNER_ID", "")
    or os.getenv("BOT_OWNER_ID", "")
    or os.getenv("CREATOR_ID", "")
    or os.getenv("ADMIN_ID", "")
)
try:
    OWNER_CHAT_ID = int(_owner) if _owner else None
except ValueError:
    OWNER_CHAT_ID = None

if OWNER_CHAT_ID is not None and OWNER_CHAT_ID not in ADMIN_USER_IDS:
    ADMIN_USER_IDS.append(OWNER_CHAT_ID)
ADMIN_USER_IDS = sorted(set(int(x) for x in ADMIN_USER_IDS if str(x).strip().lstrip("-").isdigit()))

# ==============================================================================
# 🏛️ CONTRATOS
# ==============================================================================
CONTRACTS = {
    "AG_C_bd": {
        "PAYMENTS":    "0x96bF20B20de9c01D5F1f0fC74321ccC63E3f29F1",
        "SUBACCOUNTS": "0x14eEd4F2Bfcfd85E2262987Cf8cbcD97B02557ca",
        "MANAGER":     "0x685d04d62DA1Ef26529c7Aa1364da504c8ACDb1D",
        "TOKENPASS":   "0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d",
        "TAG":         "AG_C_bd",
        "LP_USDT":     "0x238966212E0446C04a225343DAAfb3c3A7D4F37C",
        "LP_LOOP":     "0xC3adC8b72B1C3F208E5d1614cDF87FdD93762812",
    },
    "bd_v5": {
        "MANAGER":     "0x9826a9727D5bB97A44Bf14Fe2E2B0B1D5a81C860",
        "PAYMENTS":    "0x48748959392e9fa8a72031c51593dcf52572e120",
        "SUBACCOUNTS": "0x6995077c49d920D8516AF7b87a38FdaC5E2c957C",
        "TOKENPASS":   "0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d",
        "TAG":         "bd_v5",
        "LP_USDT":     "0xFb2e2Ff7B51C2BcAf58619a55e7d2Ff88cFD8aCA",
        "LP_LOOP":     "0xB56032D0B576472b3f0f1e4747f488769dE2b00B",
    }
}

ADDRESS_TO_ENV = {}
for _env, _c in CONTRACTS.items():
  for _k, _addr in _c.items():
    if isinstance(_addr, str) and _addr.startswith("0x"):
      ADDRESS_TO_ENV[_addr.lower()] = _env

def infer_env_by_address(addr: str) -> str:
  if not addr:
    return "UNKNOWN"
  return ADDRESS_TO_ENV.get(str(addr).lower(), "UNKNOWN")

ADDR_LPLPUSD = "0xc4CF5093676e8a61404f51bC6Ceaec5279Ce8645"
ADDR_LPUSDT0 = "0x238966212E0446C04a225343DAAfb3c3A7D4F37C"
ADDR_USDT0   = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"

TOKENS_TO_WATCH = [
    Web3.to_checksum_address(ADDR_USDT0),
    Web3.to_checksum_address(ADDR_LPUSDT0),
    Web3.to_checksum_address(ADDR_LPLPUSD),
]

TOKEN_CONFIG = {
    Web3.to_checksum_address(ADDR_LPLPUSD): {"dec": 9, "sym": "LP-USD", "icon": "🟣"},
    Web3.to_checksum_address(ADDR_LPUSDT0): {"dec": 6, "sym": "LP-V5",  "icon": "🟣"},
    Web3.to_checksum_address(ADDR_USDT0):   {"dec": 6, "sym": "USDT0",  "icon": "🔵"},
}
TOKENS_MAP = {addr.lower(): meta for addr, meta in TOKEN_CONFIG.items()}

# ==============================================================================
# 🧩 ABIs (Minimizadas)
# ==============================================================================
ABI_PAYMENTS = json.dumps([
    {"anonymous":False,"inputs":[
        {"indexed":True,"name":"manager","type":"address"},
        {"indexed":False,"name":"user","type":"address"},
        {"indexed":False,"name":"accountId","type":"string"},
        {"components":[
            {"name":"strategy","type":"address"},
            {"name":"coin","type":"address"},
            {"name":"botId","type":"string"},
            {"name":"oldBalance","type":"uint256"},
            {"name":"fee","type":"uint256"},
            {"name":"gas","type":"uint256"},
            {"name":"profit","type":"int256"}
        ],"indexed":False,"name":"details","type":"tuple"}
    ],"name":"OpenPosition","type":"event"}
])

ABI_SUBACCOUNTS = json.dumps([
    {"inputs":[{"name":"contractAddress","type":"address"},{"name":"user","type":"address"}],
     "name":"getSubAccounts",
     "outputs":[{"components":[{"name":"id","type":"string"},{"name":"name","type":"string"}],"type":"tuple[]"}],
     "type":"function"},
    {"inputs":[{"name":"contractAddress","type":"address"},{"name":"user","type":"address"},{"name":"accountId","type":"string"},{"name":"strategyToken","type":"address"}],
     "name":"getBalances",
     "outputs":[{"components":[
         {"name":"amount","type":"uint256"},
         {"name":"coin","type":"address"},
         {"name":"decimals","type":"uint8"},
         {"name":"symbol","type":"string"},
         {"name":"name","type":"string"},
         {"name":"status","type":"bool"},
         {"name":"paused","type":"bool"}
     ],"type":"tuple[]"}],
     "type":"function"},
    {"inputs":[{"name":"contractAddress","type":"address"},{"name":"user","type":"address"},{"name":"accountId","type":"string"}],
     "name":"getStrategies",
     "outputs":[{"type":"address[]"}],
     "type":"function"}
])

ABI_MANAGER = json.dumps([{"inputs":[],"name":"gasBalance","outputs":[{"type":"uint256"}],"type":"function"}])
ABI_TOKENPASS = json.dumps([{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"type":"uint256"}],"type":"function"}])

ABI_ERC20_TRANSFER = json.dumps([
    {"anonymous":False,"inputs":[
        {"indexed":True,"name":"from","type":"address"},
        {"indexed":True,"name":"to","type":"address"},
        {"indexed":False,"name":"value","type":"uint256"}
    ],"name":"Transfer","type":"event"}
])
ABI_ERC20_META = json.dumps([
    {"inputs":[],"name":"decimals","outputs":[{"type":"uint8"}],"type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"type":"string"}],"type":"function"}
])
