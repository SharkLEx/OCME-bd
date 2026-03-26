---
type: knowledge
title: "Dev — Database Schema: PostgreSQL + SQLite"
tags:
  - dev
  - database
  - schema
  - postgresql
  - sqlite
created: 2026-03-26
source: tank-sensei
---

# Database Schema: PostgreSQL + SQLite

> Módulo 04 de 10 — Professor: Tank
> Dois bancos, papéis distintos. Nunca confundir os dois.

---

## Dois Bancos, Dois Papéis

| Banco | Container | Uso | Path |
|-------|-----------|-----|------|
| **SQLite** | `ocme-monitor` | Operações on-chain, usuários Telegram, estado dos workers | `/app/data/webdex_v5_final.db` |
| **PostgreSQL** | `orchestrator-postgres` | Memória IA, eventos Discord, assinaturas, bdz_knowledge | `orchestrator:5432/orchestrator` |

---

## PostgreSQL — Tabelas Principais

### ai_conversations — Memória longa da IA
```sql
CREATE TABLE ai_conversations (
    id SERIAL PRIMARY KEY,
    chat_id VARCHAR(100),      -- Discord user_id ou Telegram chat_id
    role VARCHAR(20),           -- 'user' ou 'assistant'
    content TEXT,
    platform VARCHAR(20),       -- 'discord' ou 'telegram'
    created_at TIMESTAMP DEFAULT NOW()
);
-- Índice para performance:
CREATE INDEX idx_ai_conv_chat ON ai_conversations(chat_id, platform, created_at DESC);
```

### bdz_knowledge — Knowledge base da IA
```sql
CREATE TABLE bdz_knowledge (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100),   -- 'protocol', 'market', 'faq', 'defi', 'tokenomia'
    title VARCHAR(255),
    content TEXT,
    priority INTEGER DEFAULT 0,  -- maior = mais relevante
    created_at TIMESTAMP DEFAULT NOW()
);
-- Carregada 1x/hora por bdz_knowledge_discord.py
-- 90+ itens ativos em produção
```

### platform_events — Todos os eventos Discord/Telegram
```sql
CREATE TABLE platform_events (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(20),    -- 'discord', 'telegram', 'whatsapp'
    event_type VARCHAR(50),  -- 'command', 'mention', 'reaction', 'button'
    sender_id VARCHAR(100),
    channel_id VARCHAR(100),
    content TEXT,
    payload JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### discord_user_profiles — Perfil de usuários Discord
```sql
CREATE TABLE discord_user_profiles (
    discord_user_id VARCHAR(100) PRIMARY KEY,
    username VARCHAR(255),
    env VARCHAR(50),           -- 'bd_v5' ou 'AG_C_bd'
    wallet_address VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### subscriptions — Assinaturas on-chain (PostgreSQL replica)
```sql
CREATE TABLE subscriptions (
    wallet_address VARCHAR(100),
    chat_id INTEGER,
    tier VARCHAR(50),          -- 'pro', 'dev'
    status VARCHAR(20),        -- 'active', 'expired'
    activated_at TIMESTAMP,
    expires_at TIMESTAMP,
    tx_hash VARCHAR(255),
    log_index INTEGER,
    months INTEGER
);
```

---

## SQLite — Tabelas Principais

### operacoes — Transações do protocolo
```sql
CREATE TABLE operacoes (
    hash TEXT,
    log_index INTEGER,
    data_hora TEXT,
    tipo TEXT,          -- 'swap', 'deposit', 'withdraw', 'rebalance'
    valor REAL,
    gas_usd REAL,
    token TEXT,
    sub_conta TEXT,     -- endereço da subconta
    bloco INTEGER,
    ambiente TEXT,      -- 'bd_v5' ou 'AG_C_bd'
    fee REAL DEFAULT 0.0,
    PRIMARY KEY (hash, log_index)
);
-- 4.37M+ rows em produção
```

### users — Usuários Telegram (+ Discord via sincronização)
```sql
CREATE TABLE users (
    chat_id INTEGER PRIMARY KEY,
    ai_enabled INTEGER DEFAULT 1,
    wallet TEXT,
    env TEXT,               -- 'bd_v5', 'AG_C_bd', 'both'
    active INTEGER DEFAULT 1,
    periodo TEXT DEFAULT '24h',
    last_seen_ts REAL,
    username TEXT,
    capital_hint REAL,
    created_at TEXT,
    subscription_expires TEXT   -- ISO 8601, atualizado pelo subscription_worker
);
```

### config — Estado dos workers
```sql
CREATE TABLE config (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
-- Exemplos de chaves:
-- 'sub_last_block': '68234512'  -- último bloco processado pelo subscription_worker
-- 'last_21h_cycle': '2026-03-25T21:00:00'  -- último ciclo executado
-- 'capital_snapshot_ts': '1743027600.0'
```

---

## Queries Frequentes

```python
# Contar operações por ambiente nas últimas 24h
SELECT ambiente, COUNT(*) as total, SUM(valor) as volume
FROM operacoes
WHERE data_hora >= datetime('now', '-24 hours')
GROUP BY ambiente;

# Usuários ativos (viram o bot nas últimas 48h)
SELECT COUNT(*) FROM users
WHERE active=1 AND last_seen_ts > (unixepoch() - 172800);

# Memória recente de um usuário (PostgreSQL)
SELECT role, content FROM ai_conversations
WHERE chat_id = $1 AND platform = $2
ORDER BY created_at DESC LIMIT 20;

# Assinatura ativa de um wallet (PostgreSQL)
SELECT status, expires_at, tier FROM subscriptions
WHERE LOWER(wallet_address) = LOWER($1)
ORDER BY expires_at DESC LIMIT 1;
```

---

## Regras de Acesso ao Banco

1. **SQLite** → acessar SEMPRE via `webdex_db.py` (`_ConnProxy`, `DB_LOCK`)
   - Nunca criar conexão direta com `sqlite3.connect()` em novos arquivos
   - Escritas: `with DB_LOCK: conn.execute(...)` obrigatório

2. **PostgreSQL** → acessar via `DATABASE_URL` env var
   - Use `psycopg2` ou `asyncpg`
   - Connection pooling recomendado para alta concorrência

3. **Nunca** acessar o SQLite do `ocme-monitor` de dentro do `orchestrator-discord`
   - O DB está em `/ocme_data/webdex_v5_final.db` (mount read-only)
   - Para leituras: usar a API HTTP (`card_server.py` porta 8766)
