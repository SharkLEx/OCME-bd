-- Migration 003: Índices de performance

CREATE INDEX IF NOT EXISTS idx_op_data_hora    ON operacoes(data_hora);
CREATE INDEX IF NOT EXISTS idx_op_sub_conta    ON operacoes(sub_conta);
CREATE INDEX IF NOT EXISTS idx_op_ambiente     ON operacoes(ambiente);
CREATE INDEX IF NOT EXISTS idx_op_owner_wall   ON op_owner(wallet);
CREATE INDEX IF NOT EXISTS idx_op_tipo_data    ON operacoes(tipo, data_hora);
CREATE INDEX IF NOT EXISTS idx_users_wallet    ON users(wallet);
CREATE INDEX IF NOT EXISTS idx_users_active    ON users(active);
CREATE INDEX IF NOT EXISTS idx_btc_bloco       ON block_time_cache(bloco);
