from __future__ import annotations
# ==============================================================================
# webdex_db.py — WEbdEX Monitor Engine (extraído de WEbdEX_V30_24_SPEED_PATCH_FIXED.py)
# Linhas fonte: ~527-1182
# ==============================================================================

# (imports moved to explicit re-imports below — no invalid from-import needed)

# Re-imports necessários para este módulo
import os, time, json, sqlite3, threading, logging, re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Optional

# Imports da config
from webdex_config import (
    logger, log_error, infer_env_by_address, Web3, TZ_BR,
    ADMIN_USER_IDS, OPENAI_DEFAULT_ON,
)

# ==============================================================================
# 🗃️ Cache rápido
# ==============================================================================
DASH_GRAPH_CACHE = {}
DASH_GRAPH_TTL = 15  # segundos

DB_LOCK = threading.Lock()
DB_PATH = os.getenv("DB_PATH") or os.getenv("WEbdEX_DB_PATH") or "webdex_v5_final.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA cache_size=-8000")
conn.execute("PRAGMA temp_store=MEMORY")
conn.commit()


def _ensure_operacoes_ambiente_column_and_backfill(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(operacoes)").fetchall()]
    if "ambiente" not in cols:
        cur.execute("ALTER TABLE operacoes ADD COLUMN ambiente TEXT DEFAULT 'UNKNOWN'")
        conn.commit()
    rows = cur.execute("""
        SELECT rowid, contract_address
        FROM operacoes
        WHERE (ambiente IS NULL OR TRIM(ambiente) = '' OR ambiente = 'UNKNOWN')
          AND contract_address IS NOT NULL AND TRIM(contract_address) <> ''
    """).fetchall()
    updated = 0
    for rowid, caddr in rows:
        try:
            env = infer_env_by_address(Web3.to_checksum_address(caddr))
        except Exception:
            env = "UNKNOWN"
        if env and env != "UNKNOWN":
            cur.execute("UPDATE operacoes SET ambiente=? WHERE rowid=?", (env, rowid))
            updated += 1
    if updated:
        conn.commit()
    return updated


def _db_migrate():
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_seen_ts REAL")
        conn.commit()
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
        conn.commit()
    except Exception:
        pass

_db_migrate()


def _load_float(key: str, default: float) -> float:
    try:
        return float(get_config(key, str(default)))
    except Exception:
        try:
            return float(os.getenv(key.upper(), str(default)))
        except Exception:
            return float(default)

def _set_limit(key: str, value: float):
    try:
        set_config(key, str(value))
    except Exception:
        pass

DEFAULT_LIMITE_GWEI = float(os.getenv("LIMITE_GWEI", "1000"))
DEFAULT_LIMITE_GAS_BAIXO_POL = float(os.getenv("LIMITE_GAS_BAIXO_POL", os.getenv("LIMITE_GAS_LOW_POL", os.getenv("LIMITE_SALDO_GAS", "2"))))
DEFAULT_LIMITE_INATIV_MIN = float(os.getenv("LIMITE_INATIV_MIN", os.getenv("INATIV_MIN", "60")))

LIMITE_GWEI = _load_float("limite_gwei", DEFAULT_LIMITE_GWEI)
LIMITE_GAS_BAIXO_POL = _load_float("limite_gas_baixo_pol", DEFAULT_LIMITE_GAS_BAIXO_POL)
LIMITE_INATIV_MIN = _load_float("limite_inativ_min", DEFAULT_LIMITE_INATIV_MIN)

def reload_limites():
    global LIMITE_GWEI, LIMITE_GAS_BAIXO_POL, LIMITE_INATIV_MIN
    LIMITE_GWEI = _load_float("limite_gwei", DEFAULT_LIMITE_GWEI)
    LIMITE_GAS_BAIXO_POL = _load_float("limite_gas_baixo_pol", DEFAULT_LIMITE_GAS_BAIXO_POL)
    LIMITE_INATIV_MIN = _load_float("limite_inativ_min", DEFAULT_LIMITE_INATIV_MIN)
    return LIMITE_GWEI, LIMITE_GAS_BAIXO_POL, LIMITE_INATIV_MIN


def touch_user(chat_id: int, username: str | None = None):
    try:
        cursor.execute("UPDATE users SET last_seen_ts=?, username=COALESCE(?, username) WHERE chat_id=?",
                       (time.time(), username, chat_id))
        conn.commit()
    except Exception:
        pass


def _get_username_from_db(chat_id: int) -> str | None:
    try:
        r = cursor.execute("SELECT username FROM users WHERE chat_id=?", (chat_id,)).fetchone()
        u = (r[0] if r else None)
        if u:
            u = str(u).strip().lstrip("@")
        return u or None
    except Exception:
        return None


def set_user_active(chat_id: int, active: int = 1, username: str | None = None):
    try:
        cursor.execute("UPDATE users SET active=?, last_seen_ts=?, username=COALESCE(?, username) WHERE chat_id=?",
                       (int(active), time.time(), username, chat_id))
        conn.commit()
    except Exception:
        pass


# ==============================================================================
# CREATE TABLES
# ==============================================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS operacoes (
  hash TEXT,
  log_index INTEGER,
  data_hora TEXT,
  tipo TEXT,
  valor REAL,
  gas_usd REAL,
  token TEXT,
  sub_conta TEXT,
  bloco INTEGER,
  ambiente TEXT,
  fee REAL DEFAULT 0.0,
  PRIMARY KEY (hash, log_index)
)
""")

cursor.execute("CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT)")
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
  chat_id INTEGER PRIMARY KEY,
  ai_enabled INTEGER DEFAULT 1,
  wallet TEXT,
  rpc TEXT,
  env TEXT,
  active INTEGER DEFAULT 1,
  periodo TEXT DEFAULT '24h',
  pending TEXT,
  created_at TEXT,
  updated_at TEXT
)
""")

try:
    _updated = _ensure_operacoes_ambiente_column_and_backfill(conn)
    if _updated:
        try:
            logger.info(f"🧩 Backfill ambiente: {_updated} registros atualizados.")
        except Exception:
            pass
except Exception:
    pass


def _table_has_col(cur, table: str, col: str) -> bool:
    try:
        rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
        return any((r[1] == col) for r in rows)
    except Exception:
        return False

def _ensure_col(cur, table: str, col: str, coltype: str):
    if not _table_has_col(cur, table, col):
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
        except Exception:
            pass

_ensure_col(cursor, "users", "last_seen_ts", "REAL")
_ensure_col(cursor, "users", "username", "TEXT")
_ensure_col(cursor, "users", "capital_hint", "REAL")

def _ensure_operacoes_columns(_conn):
  try:
    _cur = _conn.cursor()
    cols = [r[1] for r in _cur.execute("PRAGMA table_info(operacoes)").fetchall()]
    if "ambiente" not in cols:
      _cur.execute("ALTER TABLE operacoes ADD COLUMN ambiente TEXT DEFAULT \'UNKNOWN\'")
      _conn.commit()
    if "fee" not in cols:
      _cur.execute("ALTER TABLE operacoes ADD COLUMN fee REAL DEFAULT 0.0")
      _conn.commit()
  except Exception:
    pass

_ensure_operacoes_columns(conn)

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_funnel (
    chat_id       INTEGER PRIMARY KEY,
    stage         TEXT NOT NULL DEFAULT 'conectado',
    first_trade   TEXT,
    last_trade    TEXT,
    total_trades  INTEGER DEFAULT 0,
    inactive_days INTEGER DEFAULT 0,
    alerted_at    TEXT,
    updated_at    TEXT NOT NULL
)
""")
try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_funnel_stage ON user_funnel(stage)")
    conn.commit()
except Exception:
    pass

def _ensure_operacoes_extended_cols(_conn):
    _c = _conn.cursor()
    for col, ctype in [
        ("strategy_addr", "TEXT DEFAULT ''"),
        ("bot_id",        "TEXT DEFAULT ''"),
        ("gas_protocol",  "REAL DEFAULT 0.0"),
        ("old_balance_usd","REAL DEFAULT 0.0"),
    ]:
        try:
            _c.execute(f"ALTER TABLE operacoes ADD COLUMN {col} {ctype}")
        except Exception:
            pass
    _conn.commit()

_ensure_operacoes_extended_cols(conn)

try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_bot_id ON operacoes(bot_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_strategy ON operacoes(strategy_addr)")
    conn.commit()
except Exception:
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS capital_cache (
  chat_id INTEGER PRIMARY KEY,
  env TEXT,
  total_usd REAL DEFAULT 0,
  breakdown_json TEXT,
  updated_ts REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_capital_snapshots (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id   INTEGER NOT NULL,
  wallet    TEXT    NOT NULL COLLATE NOCASE,
  env       TEXT    NOT NULL DEFAULT '',
  ts        TEXT    NOT NULL,
  usdt0_usd REAL    DEFAULT 0,
  lp_usd    REAL    DEFAULT 0,
  total_usd REAL    DEFAULT 0
)
""")
try:
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ucs_wallet_ts "
        "ON user_capital_snapshots(wallet, ts)"
    )
    conn.commit()
except Exception:
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS inactivity_stats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  end_block INTEGER,
  start_block INTEGER,
  minutes REAL,
  tx_count INTEGER,
  tx_per_min REAL,
  accounts_in_cycle INTEGER,
  cycle_est_min REAL,
  note TEXT,
  created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS external_status_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT,
  degraded_count INTEGER,
  summary TEXT,
  raw_json TEXT,
  created_at TEXT
)
""")

conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS op_owner (
  hash TEXT,
  log_index INTEGER,
  wallet TEXT,
  PRIMARY KEY (hash, log_index)
)
""")

cursor.execute("CREATE TABLE IF NOT EXISTS op_blocktime (hash TEXT, log_index INTEGER, block_ts INTEGER, PRIMARY KEY (hash, log_index))")
cursor.execute("CREATE TABLE IF NOT EXISTS block_time_cache (bloco INTEGER PRIMARY KEY, ts INTEGER)")

cursor.execute("""
CREATE TABLE IF NOT EXISTS fl_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ts               TEXT NOT NULL,
    env              TEXT NOT NULL,
    lp_usdt_supply   REAL DEFAULT 0,
    lp_loop_supply   REAL DEFAULT 0,
    liq_usdt         REAL DEFAULT 0,
    liq_loop         REAL DEFAULT 0,
    gas_pol          REAL DEFAULT 0,
    pol_price        REAL DEFAULT 0,
    total_usd        REAL DEFAULT 0
)
""")
try:
    cursor.execute("ALTER TABLE fl_snapshots ADD COLUMN total_usd REAL DEFAULT 0")
except Exception:
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS sub_positions (
    wallet      TEXT NOT NULL,
    sub_conta   TEXT NOT NULL,
    ambiente    TEXT NOT NULL,
    saldo_usdt  REAL DEFAULT 0,
    last_trade  TEXT,
    old_balance REAL DEFAULT 0,
    trade_count INTEGER DEFAULT 0,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (wallet, sub_conta, ambiente)
)
""")
cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_subpos_wallet ON sub_positions(wallet)"
)

cursor.execute("""
CREATE TABLE IF NOT EXISTS adm_capital_stats (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    total_users   INTEGER,
    capital_total REAL,
    cap_v5        REAL,
    cap_agbd      REAL,
    cap_inactive  REAL,
    created_at    TEXT
)
""")

conn.commit()

cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_data_hora  ON operacoes(data_hora)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_sub_conta  ON operacoes(sub_conta)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_ambiente   ON operacoes(ambiente)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_owner_wall ON op_owner(wallet)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_fl_snap_env_ts ON fl_snapshots(env, ts)")
conn.commit()

try:
    cursor.execute("ALTER TABLE users ADD COLUMN sub_filter TEXT")
    conn.commit()
except Exception:
    pass

# ==============================================================================
# 🧠 UTILS DB/CONFIG
# ==============================================================================
def now_br() -> datetime:
    return datetime.now(TZ_BR) if TZ_BR else datetime.now()

def _ciclo_21h_since() -> str:
    nb = now_br()
    corte = nb.replace(hour=21, minute=0, second=0, microsecond=0)
    if nb < corte:
        corte -= timedelta(days=1)
    return corte.strftime("%Y-%m-%d %H:%M:%S")

def _ciclo_21h_label() -> str:
    nb  = now_br()
    corte = nb.replace(hour=21, minute=0, second=0, microsecond=0)
    if nb < corte:
        corte -= timedelta(days=1)
    return f"Ciclo ({corte.strftime('%d/%m %Hh')}→agora)"

def get_config(k: str, d: str = "") -> str:
    with DB_LOCK:
        try:
            r = cursor.execute("SELECT valor FROM config WHERE chave=?", (k,)).fetchone()
            return r[0] if r else d
        except Exception:
            return d

def set_config(k: str, v: str) -> None:
    with DB_LOCK:
        try:
            cursor.execute("INSERT OR REPLACE INTO config (chave, valor) VALUES (?,?)", (k, str(v)))
            conn.commit()
        except Exception:
            pass

def _config_exists(k: str) -> bool:
    with DB_LOCK:
        try:
            r = cursor.execute("SELECT 1 FROM config WHERE chave=? LIMIT 1", (k,)).fetchone()
            return bool(r)
        except Exception:
            return False

def _ensure_ai_config_defaults() -> None:
    if not _config_exists("ai_global_enabled"):
        set_config("ai_global_enabled", "1")
    if not _config_exists("ai_admin_only"):
        set_config("ai_admin_only", "0")
    if not _config_exists("ai_mode"):
        set_config("ai_mode", "community")

def ai_global_enabled() -> bool:
    return str(get_config("ai_global_enabled", "1")).strip() not in ("0", "false", "False", "no", "NO")

def ai_admin_only() -> bool:
    return str(get_config("ai_admin_only", "0")).strip() in ("1", "true", "True", "yes", "YES")

def ai_mode() -> str:
    m = str(get_config("ai_mode", "community") or "community").strip().lower()
    return "dev" if m in ("dev", "developer", "desenvolvedor") else "community"

def ai_can_use(chat_id: int) -> bool:
    from webdex_bot_core import _is_admin
    if not ai_global_enabled():
        return _is_admin(chat_id)
    if ai_admin_only() and not _is_admin(chat_id):
        return False
    return True

def _ensure_inactivity_config_defaults():
    if get_config("inactivity_auto_enabled") is None:
        set_config("inactivity_auto_enabled", "1")
    if get_config("inactivity_auto_minutes") is None:
        set_config("inactivity_auto_minutes", "10")
    if get_config("inactivity_alert_cooldown_min") is None:
        set_config("inactivity_alert_cooldown_min", "30")
    if get_config("inactivity_alert_sigma") is None:
        set_config("inactivity_alert_sigma", "2.5")
    if get_config("inactivity_alert_pct") is None:
        set_config("inactivity_alert_pct", "60")
    if get_config("inactivity_hist_window") is None:
        set_config("inactivity_hist_window", "120")
    if get_config("inactivity_last_alert_ts") is None:
        set_config("inactivity_last_alert_ts", "0")

try:
    _ensure_ai_config_defaults()
    _ensure_inactivity_config_defaults()
except Exception:
    pass

# ==============================================================================
# 🕒 BLOCK TIME CACHE
# ==============================================================================
def get_block_ts(bloco: int) -> int:
    try:
        b = int(bloco)
        if b <= 0:
            return 0
    except Exception:
        return 0
    with DB_LOCK:
        row = cursor.execute("SELECT ts FROM block_time_cache WHERE bloco=?", (b,)).fetchone()
    if row and row[0]:
        return int(row[0])
    ts = 0
    try:
        from webdex_chain import web3
        blk = web3.eth.get_block(b)
        ts = int(blk.get("timestamp") or 0)
    except Exception:
        ts = 0
    if ts > 0:
        with DB_LOCK:
            try:
                cursor.execute("INSERT OR REPLACE INTO block_time_cache (bloco, ts) VALUES (?,?)", (b, int(ts)))
                conn.commit()
            except Exception:
                pass
    return int(ts or 0)

def op_set_block_ts(tx_hash: str, log_index: int, bloco: int, ambiente: str = ""):
    try:
        ts = get_block_ts(int(bloco))
        if ts <= 0:
            return
        with DB_LOCK:
            cursor.execute(
                "INSERT OR REPLACE INTO op_blocktime (hash, log_index, block_ts) VALUES (?,?,?)",
                (normalize_txhash(tx_hash), int(log_index), int(ts))
            )
            conn.commit()
    except Exception:
        pass

# ==============================================================================
# 🏛️ INSTITUCIONAL
# ==============================================================================
def _ensure_institutional_table():
    try:
        with DB_LOCK:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS institutional_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    total_users INTEGER NOT NULL,
                    total_capital REAL NOT NULL,
                    top3_percent REAL NOT NULL,
                    env_json TEXT,
                    token_json TEXT,
                    created_at TEXT
                )
            """)
            try:
                cols = [r[1] for r in c.execute("PRAGMA table_info(institutional_snapshots)").fetchall()]
                if "created_at" not in cols:
                    c.execute("ALTER TABLE institutional_snapshots ADD COLUMN created_at TEXT")
                if "env_json" not in cols:
                    c.execute("ALTER TABLE institutional_snapshots ADD COLUMN env_json TEXT")
                if "token_json" not in cols:
                    c.execute("ALTER TABLE institutional_snapshots ADD COLUMN token_json TEXT")
            except Exception:
                pass
            try:
                c.execute("CREATE INDEX IF NOT EXISTS idx_inst_ts ON institutional_snapshots(ts)")
            except Exception:
                pass
            conn.commit()
    except Exception as e:
        logger.warning(f"Institutional table ensure warning: {e}")


def normalize_txhash(txh) -> str:
    if hasattr(txh, "hex"):
        txh = txh.hex()
    txh = str(txh).strip()
    if not txh.startswith("0x"):
        txh = "0x" + txh
    return txh.lower()

def period_to_hours(p: str) -> int:
    p = (p or "ciclo").lower().strip()
    if p == "7d":  return 24*7
    if p == "30d": return 24*30
    if p == "ciclo":
        nb = now_br()
        corte = nb.replace(hour=21, minute=0, second=0, microsecond=0)
        if nb < corte:
            corte -= timedelta(days=1)
        return max(1, int((nb - corte).total_seconds() / 3600) + 1)
    return 24

def _period_since(p: str) -> str:
    p = (p or "ciclo").lower().strip()
    if p == "ciclo":
        return _ciclo_21h_since()
    hours = period_to_hours(p)
    return (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

def _period_label(p: str) -> str:
    p = (p or "ciclo").lower().strip()
    if p == "ciclo":
        return _ciclo_21h_label()
    return p.upper()
