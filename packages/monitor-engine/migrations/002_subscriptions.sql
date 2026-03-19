-- Migration 002 — subscriptions
-- Story 14.3: Webhook On-chain Auto-ativação
-- Executar em: orchestrator-postgres
-- psql $DATABASE_URL -f 002_subscriptions.sql

CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    wallet_address VARCHAR(42) NOT NULL,
    chat_id BIGINT,
    tier VARCHAR(20) NOT NULL DEFAULT 'pro',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    tx_hash VARCHAR(66) NOT NULL,
    log_index INT NOT NULL,
    months INT NOT NULL DEFAULT 1,
    metadata JSONB DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sub_tx ON subscriptions(tx_hash, log_index);
CREATE INDEX IF NOT EXISTS idx_sub_wallet ON subscriptions(LOWER(wallet_address));
CREATE INDEX IF NOT EXISTS idx_sub_chat ON subscriptions(chat_id) WHERE chat_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sub_expires ON subscriptions(expires_at) WHERE status = 'active';
