---
type: knowledge
id: "040"
title: "Tech Stack OCME — A Arquitetura Completa do Sistema"
layer: L5-tech
tags: [tech, stack, ocme, arquitetura, python, docker, postgresql, claude-api, web3, polygon]
links: ["041-deploy-pattern", "042-error-patterns", "025-bdzinho-capacidades", "026-bdzinho-brain", "015-rpc-pool"]
---

# 040 — Tech Stack OCME

> **Ideia central:** O OCME é um sistema de múltiplos processos Python rodando em Docker no VPS. Cada processo tem responsabilidade clara. A comunicação é via PostgreSQL. O LLM é Claude API (Anthropic). Web3 acessa a blockchain via RPC pool rotativo.

---

## Arquitetura de Alto Nível

```
                    ┌─────────────────────────┐
                    │       VPS Ubuntu         │
                    │   76.13.100.67           │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
    ┌─────────▼─────────┐               ┌──────────▼────────┐
    │  ocme-monitor     │               │ orchestrator-     │
    │  (Docker)         │               │ discord (Docker)  │
    │  port: 9090       │               │                   │
    └─────────┬─────────┘               └──────────┬────────┘
              │                                     │
              └──────────────┬──────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  PostgreSQL DB  │
                    │  (shared)       │
                    └─────────────────┘
```

---

## Container: ocme-monitor

```
Runtime: Python 3.11
Bibliotecas principais:
  - web3==6.x (blockchain)
  - telebot (Telegram bot)
  - anthropic (Claude API)
  - psycopg2 (PostgreSQL)
  - Pillow (PIL image gen)
  - openai (OpenRouter/Image)

Processos rodando:
  1. Bot Telegram (polling loop)
  2. Monitor de blocos (background thread)
  3. Scheduler (ciclo 21h, nightly trainer)
  4. Health check server (:9090)
```

## Container: orchestrator-discord

```
Runtime: Python 3.11
web3==7.x (versão mais nova para Discord)
Contrato ativo: 0x6481d77f...
```

---

## Stack de Banco de Dados

```sql
-- Tabelas principais do OCME
fl_snapshots         -- TVL e estado dos pools de liquidez
cycle_reports        -- Relatórios de ciclo 21h
operations           -- Operações on-chain
user_sessions        -- Estado da conversa por usuário
user_profiles        -- Individual Memory (MATRIX 4.0)
bdz_knowledge        -- Knowledge Base treinada
contracts            -- Endereços e ABIs
```

**bdz_knowledge — tabela de aprendizado do bdZinho:**

```sql
CREATE TABLE bdz_knowledge (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50),  -- protocol_patterns, daily_insights, smith_findings, etc.
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP,
    embedding VECTOR(1536)  -- pgvector (futuro)
);

-- Categorias ativas:
-- protocol_patterns    → como o protocolo opera
-- daily_insights       → insights do ciclo de hoje
-- smith_findings       → postura adversarial para bdZinho
-- user_patterns        → o que usuários mais perguntam
-- webdex_mechanics     → como as features funcionam
-- marketing_intel      → copy, tom, mensagens validadas
-- business_strategy    → contexto de negócio
-- faq_patterns         → FAQs frequentes com respostas
```

---

## Stack de IA

```python
# Claude API (Anthropic) — Brain principal
model = "claude-opus-4-6"  # ou claude-sonnet-4-6

# System prompt em 5 camadas (ver 026-bdzinho-brain)
# Rate limits: 60 req/min (Tier 1)
# Timeout: 30s por request

# OpenRouter — Image Generation
# via openai client com base_url
OPENROUTER_URL = "https://openrouter.ai/api/v1"

# Replicate — Animation (quando ativo)
# Token em .env: REPLICATE_API_TOKEN
```

---

## Stack Blockchain

```python
# Web3.py com pool RPC rotativo
from web3 import Web3

POLYGON_RPC_POOL = [
    "https://polygon-rpc.com",
    "https://rpc.ankr.com/polygon",
    "https://polygon.llamarpc.com",
    "https://rpc-mainnet.matic.quiknode.pro",
    "https://polygon.drpc.org",
    "https://polygon.meowrpc.com",
]

# Contratos SubAccounts
AG_C_BD_SUBACCOUNTS = "0x14eEd4F2Bfcfd85E2262987Cf8cbcD97B02557ca"
BD_V5_SUBACCOUNTS   = "0x6995077c49d920D8516AF7b87a38FdaC5E2c957C"

# Token BD
TOKEN_BD_CONTRACT   = "0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d"
BD_FEE_PER_OP       = 0.00963  # BD por operação
```

---

## Variáveis de Ambiente (.env)

```bash
# Telegram
BOT_TOKEN=...
ADMIN_USER_ID=...

# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# OpenRouter
OPENROUTER_API_KEY=...

# PostgreSQL
DATABASE_URL=postgresql://...

# Creatomate
CREATOMATE_API_KEY=...

# Replicate
REPLICATE_API_TOKEN=...

# Polygon RPC (opcional override)
RPC_ENDPOINT=...
```

---

## Módulos e Responsabilidades

| Arquivo | Responsabilidade | Depende de |
|---------|-----------------|-----------|
| `webdex_monitor.py` | Entry point, scheduler | workers, handlers |
| `webdex_workers.py` | Orchestração de tasks | ai, handlers |
| `webdex_ai.py` | Brain Claude API | knowledge, profile |
| `webdex_ai_knowledge.py` | Busca bdz_knowledge | DB |
| `webdex_ai_user_profile.py` | Individual Memory | DB |
| `webdex_ai_proactive.py` | Proactive messages | ai, DB |
| `webdex_ai_vision.py` | Análise de charts | ai |
| `webdex_ai_cycle_visual.py` | Card Discord | ai, PIL |
| `webdex_ai_trainer.py` | Nightly training | ai, DB |
| `webdex_render_pil.py` | Render imagens | PIL |
| `webdex_discord_sync.py` | Sync Discord | discord.py |
| `handlers/user.py` | Comandos usuário | ai |
| `handlers/admin.py` | Comandos admin | ai, DB |

---

## Links

← [[025-bdzinho-capacidades]] — O que o stack suporta
← [[026-bdzinho-brain]] — Detalhes do módulo IA
← [[015-rpc-pool]] — Padrão de pool RPC
→ [[041-deploy-pattern]] — Como deployar esse stack
→ [[042-error-patterns]] — O que pode falhar e como tratar
