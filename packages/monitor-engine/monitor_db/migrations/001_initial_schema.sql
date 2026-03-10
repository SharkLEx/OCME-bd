-- Migration 001: Schema inicial completo
-- OCME bd Monitor Engine — Story 7.3

CREATE TABLE IF NOT EXISTS config (
  chave TEXT PRIMARY KEY,
  valor TEXT
);

CREATE TABLE IF NOT EXISTS users (
  chat_id      INTEGER PRIMARY KEY,
  ai_enabled   INTEGER DEFAULT 1,
  wallet       TEXT,
  rpc          TEXT,
  env          TEXT,
  active       INTEGER DEFAULT 1,
  periodo      TEXT DEFAULT '24h',
  pending      TEXT,
  sub_filter   TEXT,
  last_seen_ts REAL,
  username     TEXT,
  capital_hint REAL,
  created_at   TEXT,
  updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS operacoes (
  hash           TEXT,
  log_index      INTEGER,
  data_hora      TEXT,
  tipo           TEXT,
  valor          REAL,
  gas_usd        REAL,
  token          TEXT,
  sub_conta      TEXT,
  bloco          INTEGER,
  ambiente       TEXT DEFAULT 'UNKNOWN',
  fee            REAL DEFAULT 0.0,
  strategy_addr  TEXT DEFAULT '',
  bot_id         TEXT DEFAULT '',
  gas_protocol   REAL DEFAULT 0.0,
  old_balance_usd REAL DEFAULT 0.0,
  contract_address TEXT DEFAULT '',
  PRIMARY KEY (hash, log_index)
);

CREATE INDEX IF NOT EXISTS idx_op_data_hora   ON operacoes(data_hora);
CREATE INDEX IF NOT EXISTS idx_op_sub_conta   ON operacoes(sub_conta);
CREATE INDEX IF NOT EXISTS idx_op_ambiente    ON operacoes(ambiente);
CREATE INDEX IF NOT EXISTS idx_op_bot_id      ON operacoes(bot_id);
CREATE INDEX IF NOT EXISTS idx_op_strategy    ON operacoes(strategy_addr);

CREATE TABLE IF NOT EXISTS op_owner (
  hash      TEXT,
  log_index INTEGER,
  wallet    TEXT,
  PRIMARY KEY (hash, log_index)
);

CREATE INDEX IF NOT EXISTS idx_op_owner_wall ON op_owner(wallet);

CREATE TABLE IF NOT EXISTS op_blocktime (
  hash      TEXT,
  log_index INTEGER,
  block_ts  INTEGER,
  PRIMARY KEY (hash, log_index)
);

CREATE TABLE IF NOT EXISTS block_time_cache (
  bloco INTEGER PRIMARY KEY,
  ts    INTEGER
);
