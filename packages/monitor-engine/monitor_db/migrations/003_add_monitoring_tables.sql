-- Migration 003: Tabelas de monitoramento (inatividade, status, funnel)
-- OCME bd Monitor Engine — Story 7.3

CREATE TABLE IF NOT EXISTS user_funnel (
  chat_id      INTEGER PRIMARY KEY,
  stage        TEXT NOT NULL DEFAULT 'conectado',
  first_trade  TEXT,
  last_trade   TEXT,
  total_trades INTEGER DEFAULT 0,
  inactive_days INTEGER DEFAULT 0,
  alerted_at   TEXT,
  updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_funnel_stage ON user_funnel(stage);

CREATE TABLE IF NOT EXISTS inactivity_stats (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  end_block          INTEGER,
  start_block        INTEGER,
  minutes            REAL,
  tx_count           INTEGER,
  tx_per_min         REAL,
  accounts_in_cycle  INTEGER,
  cycle_est_min      REAL,
  note               TEXT,
  created_at         TEXT
);

CREATE TABLE IF NOT EXISTS external_status_history (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  source         TEXT,
  degraded_count INTEGER,
  summary        TEXT,
  raw_json       TEXT,
  created_at     TEXT
);

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

CREATE INDEX IF NOT EXISTS idx_inst_ts ON institutional_snapshots(ts);
