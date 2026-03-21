-- Migration 002: Garantir coluna ambiente + backfill UNKNOWN
-- Seguro em DB existente (coluna já pode existir)

-- Backfill ambiente NULL → UNKNOWN
UPDATE operacoes SET ambiente = 'UNKNOWN' WHERE ambiente IS NULL;

-- Garantir sub_filter em users (pode não existir em DBs antigos)
-- Tratado pelo migrator via ALTER TABLE se necessário
