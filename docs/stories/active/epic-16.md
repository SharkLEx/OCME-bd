# Epic 16 — QA Audit: Monitor Engine & Intelligence Layer

**Status:** 🟢 Ready for Review
**Criado:** 2026-03-20
**Criado por:** @sm (Niobe) | Demanda: Smith adversarial review — 4 epics sem QA gate
**Objetivo:** Criar cobertura de testes mínima para os ~15.000 linhas de código Python em produção — priorizando os módulos mais críticos e de maior risco.

---

## Contexto

4 Epics (9, 10, 11, 12) foram implementados e deployados **sem nenhum QA gate formal**. O resultado: ~15.000 linhas de código Python em produção com **0 testes automatizados**.

Smith risk assessment:
- **user.py** (3279L) — handlers de usuário + subscription + LGPD → ALTO RISCO
- **webdex_ai.py** (1826L) — AI chat layer + tool use → ALTO RISCO
- **webdex_db.py** (1009L) — database layer compartilhado por todos → CRÍTICO
- **webdex_onchain_notify.py** (1028L) — notificações financeiras on-chain → ALTO RISCO
- **subscription_worker.py** (440L) — ativa/desativa subscriptions → CRÍTICO

---

## Stories

| Story | Título | Status | Prioridade |
|-------|--------|--------|-----------|
| 16.1 | QA Audit: Core Engine (webdex_db + webdex_config + webdex_monitor) | ⏳ Backlog | MUST |
| 16.2 | QA Audit: AI Layer (webdex_ai + webdex_ai_memory + webdex_tools) | ⏳ Backlog | MUST |
| 16.3 | QA Audit: Handlers (user.py + admin.py + reports.py) | ⏳ Backlog | MUST |
| 16.4 | QA Audit: Workers (subscription_worker + notification_engine + creatomate) | ⏳ Backlog | SHOULD |
| 16.5 | QA Audit: On-chain Layer (onchain_notify + chain + discord_sync) | ⏳ Backlog | SHOULD |

---

## Estratégia de Teste

**Abordagem:** pytest com mocks para dependências externas (Telegram API, PostgreSQL, Web3)

**Coverage mínimo por story:** 40% das funções críticas identificadas

**Estrutura de diretório:**
```
packages/monitor-engine/tests/
├── test_webdex_db.py
├── test_webdex_ai.py
├── test_webdex_ai_memory.py
├── test_webdex_tools.py
├── test_user_handlers.py
├── test_subscription_worker.py
├── test_notification_engine.py
└── conftest.py (fixtures compartilhadas)
```

**Prioridade de teste por tipo:**
1. Funções com lógica financeira (subscription, on-chain)
2. Funções com escrita em banco (db, workers)
3. Edge cases em parsers e formatadores
4. Error handling (graceful degradation)
