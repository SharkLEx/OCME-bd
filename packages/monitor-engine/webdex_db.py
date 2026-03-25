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

# ==============================================================================
# 🔒 Thread-local connection pool
# Cada thread recebe sua própria conexão SQLite — elimina segfault no C layer
# (_sqlite3.cpython-312.so crashes quando múltiplas threads compartilham conn)
# DB_LOCK ainda serializa escritas para evitar SQLITE_BUSY em WAL mode.
# ==============================================================================
_thread_local = threading.local()


def _make_conn() -> sqlite3.Connection:
    # check_same_thread=False: seguro porque cada thread tem sua própria conexão
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA cache_size=-8000")
    c.execute("PRAGMA temp_store=MEMORY")
    c.commit()
    return c


def _get_thread_conn() -> sqlite3.Connection:
    """Retorna (ou cria) a conexão SQLite da thread atual."""
    if not hasattr(_thread_local, 'conn') or _thread_local.conn is None:
        _thread_local.conn = _make_conn()
    return _thread_local.conn


class _ConnProxy:
    """Proxy transparente: roteia conn.execute() para a conexão da thread atual."""

    def execute(self, sql, params=()):
        return _get_thread_conn().execute(sql, params)

    def executemany(self, sql, params=()):
        return _get_thread_conn().executemany(sql, params)

    def commit(self):
        _get_thread_conn().commit()

    def cursor(self):
        return _get_thread_conn().cursor()

    def close(self):
        if hasattr(_thread_local, 'conn') and _thread_local.conn:
            _thread_local.conn.close()
            _thread_local.conn = None

    def __getattr__(self, name):
        return getattr(_get_thread_conn(), name)


class _CursorProxy:
    """Proxy de cursor thread-safe — estado armazenado em thread-local."""

    def execute(self, sql, params=()):
        cur = _get_thread_conn().execute(sql, params)
        _thread_local.cur = cur
        return cur

    def executemany(self, sql, params=()):
        cur = _get_thread_conn().executemany(sql, params)
        _thread_local.cur = cur
        return cur

    def executescript(self, sql):
        cur = _get_thread_conn().executescript(sql)
        _thread_local.cur = cur
        return cur

    def fetchone(self):
        c = getattr(_thread_local, 'cur', None)
        return c.fetchone() if c else None

    def fetchall(self):
        c = getattr(_thread_local, 'cur', None)
        return c.fetchall() if c else []

    def fetchmany(self, size=1):
        c = getattr(_thread_local, 'cur', None)
        return c.fetchmany(size) if c else []

    def __iter__(self):
        c = getattr(_thread_local, 'cur', None)
        return iter(c) if c else iter([])

    @property
    def rowcount(self):
        c = getattr(_thread_local, 'cur', None)
        return c.rowcount if c else -1

    @property
    def lastrowid(self):
        c = getattr(_thread_local, 'cur', None)
        return c.lastrowid if c else None


conn = _ConnProxy()
cursor = _CursorProxy()


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

# Colunas adicionadas em versões posteriores — garantir em DBs antigos
_ensure_col(cursor, "protocol_ops",  "gas_pol",   "REAL DEFAULT 0.0")
_ensure_col(cursor, "fl_snapshots",  "liq_usdt",  "REAL DEFAULT 0")
_ensure_col(cursor, "fl_snapshots",  "liq_loop",  "REAL DEFAULT 0")
_ensure_col(cursor, "fl_snapshots",  "pol_price", "REAL DEFAULT 0")

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
CREATE TABLE IF NOT EXISTS protocol_ops (
    hash        TEXT,
    log_index   INTEGER,
    ts          TEXT,
    bloco       INTEGER,
    env         TEXT,
    wallet      TEXT,
    sub_conta   TEXT,
    bot_id      TEXT,
    coin        TEXT,
    profit      REAL DEFAULT 0.0,
    fee_bd      REAL DEFAULT 0.0,
    gas_pol     REAL DEFAULT 0.0,
    old_balance REAL DEFAULT 0.0,
    PRIMARY KEY (hash, log_index)
)
""")

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

cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_data_hora    ON operacoes(data_hora)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_sub_conta    ON operacoes(sub_conta)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_ambiente     ON operacoes(ambiente)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_owner_wall   ON op_owner(wallet)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_fl_snap_env_ts  ON fl_snapshots(env, ts)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_tipo_data    ON operacoes(tipo, data_hora)")
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


# ==============================================================================
# 👥 USER MANAGER
# ==============================================================================
def get_user(chat_id: int):
    with DB_LOCK:
        try:
            row = cursor.execute(
                "SELECT chat_id,wallet,rpc,env,active,periodo,pending,sub_filter FROM users WHERE chat_id=?",
                (int(chat_id),)
            ).fetchone()
            if not row:
                return None
            return {
                "chat_id": row[0],
                "wallet": (row[1] or "").lower(),
                "rpc": row[2] or "",
                "env": row[3] or "AG_C_bd",
                "active": int(row[4] or 0),
                "periodo": row[5] or "24h",
                "pending": row[6] or "",
                "sub_filter": (row[7] or "").strip(),
            }
        except Exception:
            return None

def upsert_user(chat_id: int, **fields):
    with DB_LOCK:
        # Usa SELECT com colunas explícitas para não depender da ordem do schema
        row = cursor.execute(
            "SELECT wallet, rpc, env, active, periodo, pending, sub_filter, created_at "
            "FROM users WHERE chat_id=?", (int(chat_id),)
        ).fetchone()
        base = {
            "wallet": "",
            "rpc": "",
            "env": "AG_C_bd",
            "active": 0,
            "periodo": "24h",
            "pending": "",
            "sub_filter": "",
            "created_at": now_br().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if row:
            base.update({
                "wallet":     row[0] or "",
                "rpc":        row[1] or "",
                "env":        row[2] or "AG_C_bd",
                "active":     int(row[3] or 0),
                "periodo":    row[4] or "24h",
                "pending":    row[5] or "",
                "sub_filter": row[6] or "",
                "created_at": row[7] or base["created_at"],
            })

        for k, v in fields.items():
            if k in base:
                base[k] = v

        now_s = now_br().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT OR REPLACE INTO users (chat_id,wallet,rpc,env,active,periodo,pending,sub_filter,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (int(chat_id), (base["wallet"] or "").lower(), base["rpc"], base["env"], int(base["active"]),
             base["periodo"], base["pending"], base["sub_filter"], base["created_at"], now_s)
        )
        conn.commit()

def get_connected_users():
    with DB_LOCK:
        rows = cursor.execute("SELECT chat_id FROM users WHERE wallet<>''").fetchall()
    return [int(r[0]) for r in rows]


# ==============================================================================
# 🧠 FUNÇÕES DE FILTRO, CICLO E RANKINGS
# ==============================================================================
import math
from statistics import median as _median_stats

def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if p <= 0:
        return float(sorted_vals[0])
    if p >= 100:
        return float(sorted_vals[-1])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return float(sorted_vals[f])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return float(d0 + d1)

def _std(vals: List[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    v = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
    return float(math.sqrt(v))

def _dt_since(hours: int) -> str:
    return (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

def get_user_filter_clause(u: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
    sf = (u.get("sub_filter") or "").strip()
    if not sf or sf.lower() in ("all", "todas", "todas as subcontas", "todas"):
        return "", tuple()
    return " AND o.sub_conta=? ", (sf,)


# ==============================================================================
# ⏳ INATIVIDADE (Filtro/Relatório)
# ==============================================================================
def get_last_trade_by_sub(wallet: str, hours: int = 24, only_sub: str = "") -> dict:
    """
    Retorna último trade por subconta no período (para relatório de inatividade).
    """
    dt = _dt_since(hours)
    params = [dt, wallet.lower()]
    extra = ""
    if only_sub:
        extra = " AND o.sub_conta=? "
        params.append(only_sub)

    with DB_LOCK:
        rows = cursor.execute(f"""
            SELECT o.sub_conta, MAX(o.data_hora) as last_dh, COUNT(*) as n
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=? {extra}
              AND o.sub_conta IS NOT NULL AND o.sub_conta<>'' AND o.sub_conta<>'WALLET'
            GROUP BY o.sub_conta
        """, tuple(params)).fetchall()

    out = {}
    for sub, last_dh, n in rows:
        out[str(sub)] = {"last_dh": str(last_dh), "n": int(n or 0)}
    return out

def _minutes_since(dh: str) -> float:
    try:
        t = datetime.strptime(str(dh), "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - t).total_seconds() / 60.0
    except Exception:
        return 0.0

def get_subs_in_period(wallet: str, hours: int) -> List[str]:
    dt = _dt_since(hours)
    with DB_LOCK:
        rows = cursor.execute("""
            SELECT DISTINCT o.sub_conta
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=?
              AND o.sub_conta IS NOT NULL AND o.sub_conta<>'' AND o.sub_conta<>'WALLET'
            ORDER BY o.sub_conta ASC
        """, (dt, wallet.lower())).fetchall()
    return [str(r[0]) for r in rows]

def load_trade_times_by_sub(wallet: str, hours: int, only_sub: str = "") -> Dict[str, List[datetime]]:
    dt = _dt_since(hours)
    params = [dt, wallet.lower()]
    extra = ""
    if only_sub:
        extra = " AND o.sub_conta=? "
        params.append(only_sub)

    with DB_LOCK:
        rows = cursor.execute(f"""
            SELECT o.sub_conta, o.data_hora
            FROM operacoes o
            JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
            WHERE o.tipo='Trade' AND o.data_hora>=? AND ow.wallet=? {extra}
            ORDER BY o.sub_conta ASC, o.data_hora ASC
        """, tuple(params)).fetchall()

    out: Dict[str, List[datetime]] = {}
    for sub, dh in rows:
        try:
            t = datetime.strptime(str(dh), "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
        out.setdefault(str(sub), []).append(t)
    return out

def ciclo_stats(times: List[datetime]) -> Dict[str, Any]:
    if len(times) < 2:
        last = times[-1] if times else None
        return {"n_trades": len(times), "n_gaps": 0, "gaps": [], "med": 0.0, "p95": 0.0, "sd": 0.0, "last_trade": last}
    gaps = []
    for a, b in zip(times[:-1], times[1:]):
        gaps.append((b - a).total_seconds() / 60.0)
    gaps_sorted = sorted(gaps)
    medv = float(_median_stats(gaps_sorted))
    p95v = float(_percentile(gaps_sorted, 95))
    sdv = _std(gaps_sorted)
    return {"n_trades": len(times), "n_gaps": len(gaps_sorted), "gaps": gaps_sorted, "med": medv, "p95": p95v, "sd": sdv, "last_trade": times[-1]}

def consist_score(med_gap: float, p95_gap: float) -> float:
    if med_gap <= 0:
        return 0.0
    ratio = p95_gap / med_gap
    score = 100.0 * max(0.0, 2.0 - ratio)  # ratio=1 =>100; ratio=2 =>0
    return float(min(100.0, max(0.0, score)))


# ==============================================================================
# 🔧 Helpers (compat + formatos)
# ==============================================================================
def from_s(seconds: float) -> str:
    """Formata segundos em 'Xd HH:MM:SS' (ou 'HH:MM:SS')."""
    try:
        s = int(max(0, round(float(seconds))))
    except Exception:
        return "0s"
    days, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m, sec = divmod(rem, 60)
    if days > 0:
        return f"{days}d {h:02d}:{m:02d}:{sec:02d}"
    return f"{h:02d}:{m:02d}:{sec:02d}"


# ==============================================================================
# 🗂️ KNOWN WALLETS — Fase C: registro passivo das 304 wallets on-chain
# ==============================================================================
cursor.execute("""
CREATE TABLE IF NOT EXISTS known_wallets (
    wallet       TEXT PRIMARY KEY COLLATE NOCASE,
    env          TEXT NOT NULL DEFAULT '',
    trade_count  INTEGER DEFAULT 0,
    wins         INTEGER DEFAULT 0,
    losses       INTEGER DEFAULT 0,
    lucro_total  REAL DEFAULT 0,
    last_trade   TEXT,
    invited_by   INTEGER,          -- chat_id do ADM que gerou o convite
    invite_sent  INTEGER DEFAULT 0,-- 1 = link já enviado
    registered   INTEGER DEFAULT 0,-- 1 = usuário abriu o bot e se conectou
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
)
""")
try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kw_env ON known_wallets(env)")
    conn.commit()
except Exception:
    pass
conn.commit()


def populate_known_wallets() -> int:
    """Importa wallets com trades de protocol_ops (todos) + op_owner (registrados).
    Seguro para rodar múltiplas vezes (INSERT OR IGNORE + UPDATE se melhor dado).
    Retorna número de wallets novas inseridas."""
    with DB_LOCK:
        # ── Fonte 1: protocol_ops — TODOS os traders on-chain ─────────────────
        proto_rows = cursor.execute("""
            SELECT wallet,
                   env,
                   COUNT(*)                                        AS n,
                   SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END)   AS wins,
                   SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END)   AS losses,
                   ROUND(SUM(profit), 6)                          AS lucro,
                   MAX(ts)                                        AS ultimo
            FROM protocol_ops
            WHERE wallet != '' AND env != 'UNKNOWN'
            GROUP BY wallet, env
            ORDER BY n DESC
        """).fetchall()

        inserted = 0
        for wallet, env, n, wins, losses, lucro, ultimo in proto_rows:
            if not wallet:
                continue
            try:
                cursor.execute("""
                    INSERT INTO known_wallets
                        (wallet, env, trade_count, wins, losses, lucro_total, last_trade)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(wallet) DO UPDATE SET
                        trade_count = MAX(trade_count, excluded.trade_count),
                        wins        = MAX(wins,        excluded.wins),
                        losses      = MAX(losses,      excluded.losses),
                        lucro_total = excluded.lucro_total,
                        last_trade  = COALESCE(excluded.last_trade, last_trade),
                        env         = COALESCE(NULLIF(excluded.env,''), env)
                """, (wallet.lower(), env or "", n, wins or 0, losses or 0, lucro or 0, ultimo))
                if cursor.rowcount:
                    inserted += 1
            except Exception:
                pass

        # ── Fonte 2: op_owner + operacoes — retrocompatibilidade ──────────────
        old_rows = cursor.execute("""
            SELECT oo.wallet,
                   o.ambiente,
                   COUNT(*) as n,
                   SUM(CASE WHEN o.valor > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN o.valor < 0 THEN 1 ELSE 0 END) as losses,
                   ROUND(SUM(o.valor), 6) as lucro,
                   MAX(o.data_hora) as ultimo
            FROM op_owner oo
            JOIN operacoes o ON oo.hash = o.hash AND oo.log_index = o.log_index
            WHERE o.ambiente != 'UNKNOWN'
            GROUP BY oo.wallet, o.ambiente
            ORDER BY n DESC
        """).fetchall()

        for wallet, env, n, wins, losses, lucro, ultimo in old_rows:
            try:
                cursor.execute("""
                    INSERT INTO known_wallets
                        (wallet, env, trade_count, wins, losses, lucro_total, last_trade)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(wallet) DO UPDATE SET
                        trade_count = MAX(trade_count, excluded.trade_count),
                        wins        = MAX(wins,        excluded.wins),
                        losses      = MAX(losses,      excluded.losses),
                        lucro_total = excluded.lucro_total,
                        last_trade  = COALESCE(excluded.last_trade, last_trade)
                """, (wallet.lower(), env or "", n, wins or 0, losses or 0, lucro or 0, ultimo))
                if cursor.rowcount:
                    inserted += 1
            except Exception:
                pass

        conn.commit()
        return inserted


def get_known_wallet(wallet: str) -> dict | None:
    """Retorna dados da wallet conhecida ou None."""
    if not wallet:
        return None
    with DB_LOCK:
        row = cursor.execute(
            "SELECT wallet, env, trade_count, wins, losses, lucro_total, last_trade "
            "FROM known_wallets WHERE LOWER(wallet)=LOWER(?)",
            (wallet.strip(),)
        ).fetchone()
    if not row:
        return None
    return {
        "wallet": row[0], "env": row[1], "trade_count": row[2],
        "wins": row[3], "losses": row[4], "lucro_total": row[5],
        "last_trade": row[6],
    }


def mark_known_wallet_registered(wallet: str) -> None:
    """Marca wallet como registrada (usuário abriu o bot)."""
    with DB_LOCK:
        cursor.execute(
            "UPDATE known_wallets SET registered=1 WHERE LOWER(wallet)=LOWER(?)",
            (wallet.strip(),)
        )
        conn.commit()


def get_known_wallets_unregistered(limit: int = 50) -> list[dict]:
    """Retorna wallets conhecidas que ainda não abriram o bot."""
    with DB_LOCK:
        rows = cursor.execute("""
            SELECT wallet, env, trade_count, wins, losses, lucro_total, last_trade
            FROM known_wallets
            WHERE registered = 0
            ORDER BY trade_count DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [
        {"wallet": r[0], "env": r[1], "trade_count": r[2],
         "wins": r[3], "losses": r[4], "lucro": r[5], "last_trade": r[6]}
        for r in rows
    ]


# Popula known_wallets no boot (seguro — INSERT OR IGNORE)
try:
    _kw_inserted = populate_known_wallets()
    if _kw_inserted:
        logger.info(f"[known_wallets] {_kw_inserted} wallets importadas do historico on-chain.")
except Exception as _e:
    logger.warning(f"[known_wallets] Erro ao popular: {_e}")
