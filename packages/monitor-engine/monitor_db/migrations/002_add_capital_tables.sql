-- Migration 002: Tabelas de capital e cache
-- OCME bd Monitor Engine — Story 7.3

CREATE TABLE IF NOT EXISTS capital_cache (
  chat_id        INTEGER PRIMARY KEY,
  env            TEXT,
  total_usd      REAL DEFAULT 0,
  breakdown_json TEXT,
  updated_ts     REAL
);

CREATE TABLE IF NOT EXISTS user_capital_snapshots (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id   INTEGER NOT NULL,
  wallet    TEXT    NOT NULL COLLATE NOCASE,
  env       TEXT    NOT NULL DEFAULT '',
  ts        TEXT    NOT NULL,
  usdt0_usd REAL    DEFAULT 0,
  lp_usd    REAL    DEFAULT 0,
  total_usd REAL    DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ucs_wallet_ts ON user_capital_snapshots(wallet, ts);

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
);

CREATE INDEX IF NOT EXISTS idx_subpos_wallet ON sub_positions(wallet);

CREATE TABLE IF NOT EXISTS adm_capital_stats (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  total_users   INTEGER,
  capital_total REAL,
  cap_v5        REAL,
  cap_agbd      REAL,
  cap_inactive  REAL,
  created_at    TEXT
);
