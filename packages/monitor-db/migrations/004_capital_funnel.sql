-- Migration 004: Capital cache, snapshots, funnel, sub_positions, known_wallets

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

CREATE TABLE IF NOT EXISTS capital_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet      TEXT    NOT NULL,
    pol_balance REAL    NOT NULL DEFAULT 0.0,
    usd_value   REAL    NOT NULL DEFAULT 0.0,
    pol_price   REAL    NOT NULL DEFAULT 0.0,
    ts          INTEGER NOT NULL,
    data_hora   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS user_funnel (
    chat_id       INTEGER PRIMARY KEY,
    stage         TEXT NOT NULL DEFAULT 'conectado',
    first_trade   TEXT,
    last_trade    TEXT,
    total_trades  INTEGER DEFAULT 0,
    inactive_days INTEGER DEFAULT 0,
    alerted_at    TEXT,
    updated_at    TEXT NOT NULL
);

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

CREATE TABLE IF NOT EXISTS known_wallets (
    wallet       TEXT PRIMARY KEY COLLATE NOCASE,
    env          TEXT NOT NULL DEFAULT '',
    trade_count  INTEGER DEFAULT 0,
    wins         INTEGER DEFAULT 0,
    losses       INTEGER DEFAULT 0,
    lucro_total  REAL DEFAULT 0,
    last_trade   TEXT,
    invited_by   INTEGER,
    invite_sent  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inactivity_stats (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    end_block         INTEGER,
    start_block       INTEGER,
    minutes           REAL,
    tx_count          INTEGER,
    tx_per_min        REAL,
    accounts_in_cycle INTEGER,
    cycle_est_min     REAL,
    note              TEXT,
    created_at        TEXT
);
