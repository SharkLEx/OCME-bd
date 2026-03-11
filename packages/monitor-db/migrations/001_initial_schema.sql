-- Migration 001: Schema base — tabelas principais
-- Aplicar apenas em DB novo. Em DB existente o CREATE IF NOT EXISTS é seguro.

CREATE TABLE IF NOT EXISTS _schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

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
    gas_pol        REAL DEFAULT 0,
    PRIMARY KEY (hash, log_index)
);

CREATE TABLE IF NOT EXISTS op_owner (
    hash      TEXT,
    log_index INTEGER,
    wallet    TEXT,
    PRIMARY KEY (hash, log_index)
);

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
