# Epic 12 — bdZinho Intelligence v3

**Status:** ✅ Done
**Criado:** 2026-03-19
**Objetivo:** Transformar bdZinho no melhor assistente DeFi do mundo — memória persistente, tool use on-chain, streaming, persona adaptativa.

---

## Stories

| Story | Título | Status | Prioridade |
|-------|--------|--------|-----------|
| 12.1 | Long-term Memory PostgreSQL | ✅ Done | MUST |
| 12.2 | Tool Use / Function Calling (Telegram) | ✅ Done | MUST |
| 12.2b | Tool Use Discord (port do Telegram) | ✅ Done | MUST |
| 12.3 | Streaming Responses Discord | ✅ Done | SHOULD |
| 12.4 | Persona Engine | ✅ Done | SHOULD |
| 12.5 | RAG Protocol Knowledge | ⏳ Backlog | COULD |

**Paralelo (Smith CRITICAL #1):**

| Story | Título | Status |
|-------|--------|--------|
| 14.3 | Webhook On-chain Auto-ativação | ✅ Done |

---

## Arquitetura

```
┌─────────────────────────────────────────┐
│          bdZinho Intelligence v3         │
├─────────────────────────────────────────┤
│  Layer 1: Context Management             │
│  ├── Short-term: deque(20) em memória   │
│  ├── Mid-term: PostgreSQL últimas 90d   │
│  └── Long-term: pgvector embeddings     │
├─────────────────────────────────────────┤
│  Layer 2: Tool Use Engine               │
│  ├── get_protocol_metrics()             │  ← com circuit breaker
│  ├── get_user_portfolio()               │  ← com timeout + fallback
│  ├── get_market_context()              │  ← rate limit 20/h/user
│  └── search_knowledge()               │  ← confidence >= 0.7
├─────────────────────────────────────────┤
│  Layer 3: Response Generation           │
│  ├── Streaming chunks (Discord)         │
│  ├── Persona Engine (tone adaptation)   │
│  └── RAG Context Injection             │
└─────────────────────────────────────────┘
```

## Smith CRITICAL fixes incorporados

- **12.2 AC:** Circuit breaker (3 falhas → disable 5min), timeout por tool, fallback response padronizado
- **12.1 AC:** Plano de migração com rollback, script testado com dados reais antes do deploy
- **13.3 AC (futura):** Nonce management + chainId=137 validation
- **13.2 (futura):** Métricas públicas: TVL total, ops count, uptime — sem granularidade por usuário
- **14.3:** Executar em paralelo com Epic 12 (receita não espera)
