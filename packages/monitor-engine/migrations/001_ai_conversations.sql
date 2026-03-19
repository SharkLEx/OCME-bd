-- Migration 001 — ai_conversations
-- Story 12.1: Long-term Memory PostgreSQL para bdZinho
-- Executar em: orchestrator-postgres
-- Testar antes do deploy: psql $DATABASE_URL -f 001_ai_conversations.sql

-- Rollback seguro: DROP TABLE IF EXISTS ai_conversations;

CREATE TABLE IF NOT EXISTS ai_conversations (
    id          BIGSERIAL       PRIMARY KEY,
    chat_id     BIGINT          NOT NULL,
    platform    VARCHAR(20)     NOT NULL DEFAULT 'telegram',  -- 'telegram' | 'discord'
    role        VARCHAR(20)     NOT NULL,                      -- 'user' | 'assistant' | 'system'
    content     TEXT            NOT NULL,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    metadata    JSONB           NOT NULL DEFAULT '{}'
);

-- Índice principal: busca por chat_id ordenado por data (mais comum)
CREATE INDEX IF NOT EXISTS idx_ai_conv_chat_created
    ON ai_conversations(chat_id, created_at DESC);

-- Índice para queries de cleanup (ex: deletar msgs > 90 dias)
CREATE INDEX IF NOT EXISTS idx_ai_conv_created
    ON ai_conversations(created_at);

-- Tabela de preferências (Story 12.4 Persona Engine — schema preparado agora)
CREATE TABLE IF NOT EXISTS user_ai_preferences (
    chat_id         BIGINT      PRIMARY KEY,
    platform        VARCHAR(20) NOT NULL DEFAULT 'telegram',
    language_style  VARCHAR(20) NOT NULL DEFAULT 'casual',     -- 'casual' | 'formal'
    detail_level    VARCHAR(20) NOT NULL DEFAULT 'balanced',    -- 'concise' | 'balanced' | 'detailed'
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Comentário de versão
COMMENT ON TABLE ai_conversations IS 'Story 12.1: Long-term memory para bdZinho. Criado 2026-03-19.';
