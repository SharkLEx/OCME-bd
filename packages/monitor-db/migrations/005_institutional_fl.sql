-- Migration 005: Institutional snapshots, FL snapshots, external status, adm stats

CREATE TABLE IF NOT EXISTS fl_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    env            TEXT NOT NULL,
    lp_usdt_supply REAL DEFAULT 0,
    lp_loop_supply REAL DEFAULT 0,
    liq_usdt       REAL DEFAULT 0,
    liq_loop       REAL DEFAULT 0,
    gas_pol        REAL DEFAULT 0,
    pol_price      REAL DEFAULT 0,
    total_usd      REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fl_snap_env_ts ON fl_snapshots(env, ts);

CREATE TABLE IF NOT EXISTS institutional_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            INTEGER NOT NULL,
    total_users   INTEGER NOT NULL,
    total_capital REAL NOT NULL,
    top3_percent  REAL NOT NULL,
    env_json      TEXT,
    token_json    TEXT,
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS external_status_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source         TEXT,
    degraded_count INTEGER,
    summary        TEXT,
    raw_json       TEXT,
    created_at     TEXT
);

CREATE TABLE IF NOT EXISTS adm_capital_stats (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    total_users   INTEGER,
    capital_total REAL,
    cap_v5        REAL,
    cap_agbd      REAL,
    cap_inactive  REAL,
    created_at    TEXT
);
