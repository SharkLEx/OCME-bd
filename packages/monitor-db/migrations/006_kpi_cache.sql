-- Migration 006: KPI cache para Dashboard < 500ms (Story 7.5 prep)

CREATE TABLE IF NOT EXISTS kpi_cache (
    key        TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    computed_at REAL NOT NULL,
    ttl_seconds INTEGER NOT NULL DEFAULT 15
);

CREATE TABLE IF NOT EXISTS vigia_health (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    last_block   INTEGER DEFAULT 0,
    loops_total  INTEGER DEFAULT 0,
    ops_total    INTEGER DEFAULT 0,
    rpc_errors   INTEGER DEFAULT 0,
    capture_rate REAL DEFAULT 100.0,
    last_error   TEXT DEFAULT '',
    started_at   REAL DEFAULT 0,
    updated_at   REAL DEFAULT 0
);

-- Seed row (singleton)
INSERT OR IGNORE INTO vigia_health (id) VALUES (1);
