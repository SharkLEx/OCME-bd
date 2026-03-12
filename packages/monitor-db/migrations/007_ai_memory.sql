-- Migration 007: Memória persistente da IA
-- Armazena histórico de conversas por chat_id — sobrevive a restarts do container

CREATE TABLE IF NOT EXISTS ai_memory (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    TEXT NOT NULL,
    role       TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
    content    TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ai_memory_chat ON ai_memory(chat_id, created_at);

-- Auto-cleanup: entradas mais antigas que 7 dias são desnecessárias
-- (gerenciado pelo ai_engine via LIMIT/OFFSET, mas este índice acelera)
CREATE INDEX IF NOT EXISTS idx_ai_memory_ts ON ai_memory(created_at);
