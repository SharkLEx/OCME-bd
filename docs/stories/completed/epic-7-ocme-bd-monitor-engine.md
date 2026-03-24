# Epic 7 — OCME bd Monitor Engine

**Status:** ✅ IMPLEMENTADO — Ready for QA
**Criado por:** @pm (Morgan)
**Data:** 2026-03-10
**Projeto:** ALex Gonzaga bd / LMAS
**Referência de análise:** WEbdEX_V30_MONITOR_100_v2.py (análise completa @lmas-master)

---

## 🎯 Epic Goal

Transformar o sistema de monitoramento existente (WEbdEX — script monolítico Python) em um **Motor de Monitoramento e Informações modular, testável e CLI-first**, integrado ao ecossistema LMAS/OCME bd.

O motor deve operar **100% via CLI sem dependência do Telegram**, entregar dados em tempo real com **IA contextual**, e servir o Telegram Bot apenas como camada de UI/notificação — nunca como fonte da verdade.

---

## 📋 Contexto do Sistema Existente

| Item | Valor |
|------|-------|
| **Stack atual** | Python 3.12 · SQLite · pyTelegramBotAPI · web3.py · Matplotlib |
| **Blockchain** | Polygon Mainnet via Alchemy (`polygon-mainnet.g.alchemy.com`) |
| **RPC Principal** | Alchemy (configurável via `.env`) |
| **RPC Capital** | Alchemy dedicado para workers de capital |
| **IA atual** | OpenAI `gpt-5-nano` via `/v1/responses` |
| **DB** | `webdex_v5_final.db` (SQLite) |
| **Monitor config** | chunks=25, max=80 blocos/loop, idle=1.2s, busy=0.25s |
| **Ambientes** | `AG_C_bd` e `bd_v5` (multi-ambiente nativo) |
| **Contratos monitorados** | PAYMENTS, SUBACCOUNTS, MANAGER, TOKENPASS, LP_USDT, LP_LOOP |
| **Tokens rastreados** | USDT0 · LP-V5 · LP-USD (Polygon) |
| **Limites configurados** | GWEI=1000 · Gas POL=2 · Inatividade=30 min |
| **Usuários admin** | 4 chat_ids configurados |

---

## 🧩 Problema Central

O WEbdEX atual é um **monolito de 10.000+ linhas em 1 arquivo Python** onde:
- Toda lógica vive dentro de handlers do Telegram (violação CLI First)
- IA responde genericamente sem acesso a dados reais do usuário
- Zero testes automatizados → risco de regressão a cada mudança
- Migrations de schema espalhadas em 15+ `ALTER TABLE` sem versionamento
- Dashboard carrega em 5-12s (RPC síncrono no momento do clique)
- Contratos hardcoded → qualquer mudança exige novo deploy manual

---

## 🏗️ Solução Proposta — Arquitetura Modular

```
packages/
├── monitor-cli/       ← CLI-first (fonte da verdade) — Node.js/Python
├── monitor-core/      ← Vigia + Sentinela (EventEmitter pattern)
├── monitor-chain/     ← Web3 layer (BlockFetcher, OperationParser)
├── monitor-db/        ← Schema versionado + queries tipadas
├── monitor-ai/        ← IA com contexto on-chain real
├── monitor-bot/       ← Telegram (apenas UI/notificação)
└── monitor-report/    ← Relatórios + gráficos (Matplotlib/Chart.js)
```

**Princípio arquitetural:** Vigia emite eventos → CLI, Bot, e Dashboard escutam — zero duplicação.

---

## 📊 Stories do Epic

### Story 7.1 — CLI Foundation (monitor-cli)
**Executor:** `@dev` | **Quality Gate:** `@architect`
**Status:** ✅ DONE — 2026-03-11

**Goal:** Criar o CLI `ocme-monitor` com comandos essenciais de operação.

**Acceptance Criteria:**
- [x] `ocme-monitor status` — exibe vigia, sentinela, DB, RPC, ops do dia
- [x] `ocme-monitor report --period [24h|7d|30d] --env [AG_C_bd|bd_v5]` — relatório no terminal
- [x] `ocme-monitor alerts list` — lista alertas ativos e histórico
- [x] `ocme-monitor capital [wallet]` — capital por wallet + breakdown por ambiente
- [x] Sistema opera 100% sem Telegram iniciado (Constitution Art. I)
- [x] Configuração via `OCME_DB_PATH` env var + `--db` flag
- [x] `npm test` / `pytest` passa — testes unitários dos comandos CLI

**Executor Assignment:**
```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: [cli_design_review, pattern_validation, security_scan]
```

**Quality Gates:**
- Pre-Commit: ESLint + typecheck + unit tests
- Pre-PR: @architect valida design da CLI API

---

### Story 7.2 — Vigia Modular (monitor-core)
**Executor:** `@dev` | **Quality Gate:** `@architect`
**Status:** ✅ DONE — 2026-03-11

**Goal:** Extrair o loop de vigia do monolito Python para módulo independente com padrão EventEmitter.

**Acceptance Criteria:**
- [x] `Vigia` é uma classe com `.start()`, `.stop()`, e eventos `'operation'` e `'progress'`
- [x] Configurável via `.env`: `MONITOR_MAX_BLOCKS_PER_LOOP`, `MONITOR_FETCH_CHUNK`, `MONITOR_IDLE_SLEEP`, `MONITOR_BUSY_SLEEP`
- [x] `Sentinela` escuta eventos e dispara alertas: Gas alto, GWEI alto, inatividade
- [x] BlockFetcher usa chunks configuráveis (default: 25 blocos) em `monitor-chain/`
- [x] `BlockTimeCache.get_or_fetch()` cached em SQLite (evita RPC redundante)
- [x] Auto-restart com backoff exponencial em falha de RPC
- [x] Testes de integração: mock de RPC, verificação de eventos emitidos

**Executor Assignment:**
```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: [code_review, resilience_validation, event_pattern_check]
```

**Quality Gates:**
- Pre-Commit: Testes de resiliência (mock RPC down/429)
- Pre-PR: @architect valida EventEmitter pattern e thread-safety

---

### Story 7.3 — Schema Versionado (monitor-db)
**Executor:** `@data-engineer` | **Quality Gate:** `@dev`
**Status:** ✅ DONE — 2026-03-11

**Goal:** Substituir os 15+ `ALTER TABLE` espalhados por migrations versionadas e queries tipadas.

**Acceptance Criteria:**
- [x] Migrations numeradas: `001_initial_schema.sql` → `006_kpi_cache.sql`
- [x] `Migrator.migrate(db)` aplica apenas pendentes, idempotente
- [x] Tabelas preservadas + novas: `operacoes`, `users`, `op_owner`, `block_time_cache`, `fl_snapshots`, `sub_positions`, `user_funnel`, `capital_cache`, `inactivity_stats`, `external_status_history`, `adm_capital_stats`, `institutional_snapshots`, `config`, `kpi_cache`, `vigia_health`
- [x] Índices de performance incluídos nas migrations (003)
- [x] Backfill de `ambiente` incluído na migration 002
- [x] Zero perda de dados — DB produção migrado v4→v6 com sucesso
- [x] Testes: aplicar migrations em DB vazio e em DB com dados reais

**Executor Assignment:**
```yaml
executor: "@data-engineer"
quality_gate: "@dev"
quality_gate_tools: [schema_validation, migration_safety_check, index_review]
```

**Quality Gates:**
- Pre-Commit: Validação de SQL, teste de idempotência
- Pre-PR: @data-engineer review final + rollback test

---

### Story 7.4 — IA Contextual (monitor-ai)
**Executor:** `@dev` | **Quality Gate:** `@architect`

**Goal:** IA que responde com dados reais do usuário (capital, trades, subcontas, inatividade).

**Acceptance Criteria:**
- [x] `buildUserContext(wallet, period)` — agrega: capital total, breakdown por env, trades, lucro, melhor/pior subconta, última inatividade, gas gasto
- [x] `answer(userText, wallet)` — injeta contexto real no system prompt
- [x] Sem wallet configurada → responde modo genérico (comportamento atual preservado)
- [x] Suporte a OpenAI API e OpenRouter (conforme `.env`: `OPENROUTER_API_KEY` ou `OPENAI_API_KEY`)
- [x] Model configurável via `OPENAI_MODEL` (default: `gpt-5-nano`)
- [x] Governança preservada: `ai_global_enabled`, `ai_admin_only`, `ai_mode`
- [x] `_pretty_ai_text()` preservado para output no Telegram
- [x] Testes: mock da API, verificação de contexto injetado

**Executor Assignment:**
```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: [security_scan, context_validation, api_key_safety]
```

**Quality Gates:**
- Pre-Commit: Verificação de que nenhuma API key é logada/exposta
- Pre-PR: @architect valida context injection pattern

---

### Story 7.5 — Dashboard Cache (monitor-report)
**Executor:** `@dev` | **Quality Gate:** `@qa`

**Goal:** Dashboard que responde em < 500ms com dados pré-calculados pelo vigia.

**Acceptance Criteria:**
- [x] `DashboardCache` pré-calcula KPIs a cada ciclo do vigia (não no clique)
- [x] Cache TTL: 15s (configurável via `.env`)
- [x] Dados disponíveis: lucro 24h/7d/30d, trades count, melhor subconta, drawdown, gas médio
- [x] Gráficos gerados em background (Matplotlib headless) — não bloqueiam o bot
- [x] Cache invalidado automaticamente após nova operação processada
- [x] Fallback: se cache expirado, serve último valor com timestamp visível
- [x] Testes: latência < 500ms em 100 cliques simultâneos (mock)

**Executor Assignment:**
```yaml
executor: "@dev"
quality_gate: "@qa"
quality_gate_tools: [performance_test, cache_validation, regression_check]
```

**Quality Gates:**
- Pre-Commit: Teste de latência
- Pre-PR: @qa valida comportamento do cache + fallback

---

### Story 7.6 — Bot como UI (monitor-bot)
**Executor:** `@dev` | **Quality Gate:** `@architect`

**Goal:** Refatorar handlers do Telegram para serem apenas UI — toda lógica delegada aos módulos do motor.

**Acceptance Criteria:**
- [x] Handlers não fazem chamadas RPC diretamente — delegam para `monitor-core` ou `monitor-db`
- [x] Alertas proativos: inatividade com diagnóstico (sigma histórico + gas)
- [x] Resumo semanal automático (segunda-feira 08:00 BRT) com insights gerados pelo `monitor-ai`
- [x] Anti-flood: `NOTIF_QUEUE` (5000 itens) + debounce 2s preservados
- [x] `_tg_send_with_retry` com backoff mantido
- [x] Usuário bloqueado (403) → desativa no DB, para de tentar
- [x] Todos os ambientes (`AG_C_bd` e `bd_v5`) funcionais após refatoração
- [x] Testes: mock do bot, verificar que handlers não fazem I/O direto

**Executor Assignment:**
```yaml
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: [architecture_review, separation_of_concerns, regression_test]
```

**Quality Gates:**
- Pre-Commit: Lint + testes de handlers
- Pre-PR: @architect valida separation of concerns (UI vs logic)

---

### Story 7.7 — Observability & Deploy (monitor-devops)
**Executor:** `@devops` | **Quality Gate:** `@architect`

**Goal:** CI/CD, containerização e métricas de observabilidade para o motor.

**Acceptance Criteria:**
- [x] `Dockerfile` multi-stage: build + runtime Python slim
- [x] `.env.example` documentado com todas as variáveis (sem valores reais)
- [x] `docker-compose.yml`: serviços `monitor` + `sqlite-backup` (cron diário)
- [x] GitHub Actions: lint → test → build → push imagem
- [x] Métricas expostas via endpoint `/metrics` (Prometheus-ready): `vigia_blocks_processed`, `vigia_ops_total`, `vigia_lag_blocks`, `sentinela_alerts_total`
- [x] Log rotation preservado (5MB × 3 backups)
- [x] Health check endpoint: `GET /health` → `{ status, vigia, db, rpc }`
- [ ] `git push` apenas via `@devops` (Constitution Art. II)

**Executor Assignment:**
```yaml
executor: "@devops"
quality_gate: "@architect"
quality_gate_tools: [dockerfile_review, secrets_scan, ci_validation]
```

**Quality Gates:**
- Pre-Commit: Scan de secrets (nenhuma API key no código)
- Pre-PR: @architect valida arquitetura de containers
- Pre-Deployment: @devops valida rollback plan

---

## 🗓️ Sequência de Implementação (Waves)

```
Wave 1 (Foundation):
  Story 7.1 — CLI Foundation       ← independente, alta prioridade
  Story 7.3 — Schema Versionado    ← independente, pre-requisito das demais

Wave 2 (Core Engine):
  Story 7.2 — Vigia Modular        ← depende de 7.3 (DB layer)

Wave 3 (Intelligence):
  Story 7.4 — IA Contextual        ← depende de 7.2 (dados do vigia) + 7.3 (DB)
  Story 7.5 — Dashboard Cache      ← depende de 7.2 (eventos do vigia)

Wave 4 (UI + Ops):
  Story 7.6 — Bot como UI          ← depende de 7.2 + 7.4 + 7.5
  Story 7.7 — Observability        ← depende de todas

Estimativa total: 4-6 semanas (1 developer)
```

---

## ⚠️ Riscos e Mitigação

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Regressão no bot em produção | Alta | Alto | Feature flags — novo módulo coexiste com legado durante transição |
| Perda de dados na migration de DB | Média | Crítico | Backup obrigatório antes de migrate + teste em cópia do DB real |
| RPC Alchemy instável | Baixa | Alto | Fallback para RPCs públicos já implementado no legado — preservar |
| OpenAI API key expirada | Média | Médio | Validação na startup + mensagem clara de erro |
| Contratos movidos para novo endereço | Baixa | Alto | `.env` como única fonte de verdade — zero hardcode |

**Rollback Plan:** Cada story mantém o WEbdEX original rodando em paralelo até story 7.6 ser validada pelo @qa. Em caso de falha, desabilitar novo módulo e continuar com WEbdEX legado.

---

## ✅ Definition of Done (Epic)

- [ ] `ocme-monitor status` funciona sem Telegram (CLI First)
- [ ] IA responde com dados reais da wallet do usuário
- [ ] Dashboard carrega em < 500ms
- [ ] Todas as 7 stories com status `Done`
- [ ] `npm test` / `pytest` passam sem falhas
- [ ] `npm run lint` sem erros
- [ ] Zero secrets hardcoded no código
- [ ] DB existente migrado sem perda de dados
- [ ] `@devops` fez push e criou PR (Constitution Art. II)
- [ ] CodeRabbit sem issues CRITICAL

---

## 📁 File List (a ser atualizado conforme stories progridem)

```
docs/stories/active/epic-7-ocme-bd-monitor-engine.md   ← este arquivo
packages/monitor-cli/           ← Story 7.1
packages/monitor-core/          ← Story 7.2
packages/monitor-db/            ← Story 7.3
packages/monitor-ai/            ← Story 7.4
packages/monitor-report/        ← Story 7.5
packages/monitor-bot/           ← Story 7.6
.github/workflows/monitor-ci.yml ← Story 7.7
Dockerfile                      ← Story 7.7
docker-compose.yml              ← Story 7.7
.env.example                    ← Story 7.7
```

---

## 🔁 Handoff para @sm

> **Para o Story Manager (@sm / River):**
>
> Por favor, crie as stories detalhadas para este epic, começando pela **Wave 1**:
> - Story 7.1 (CLI Foundation) — executor `@dev`, sem dependências
> - Story 7.3 (Schema Versionado) — executor `@data-engineer`, sem dependências
>
> **Stack:** Python 3.12 (monitor-core/chain/bot/ai/report) + Node.js (monitor-cli)
> **Padrão de código:** conforme `.lmas-core/core-config.yaml` (devLoadAlwaysFiles)
> **Integration points críticos:** SQLite `webdex_v5_final.db` existente deve ser preservado
> **Compatibilidade obrigatória:** WEbdEX legado deve continuar rodando durante transição
> **Contratos e tokens:** apenas via `.env` — nunca hardcoded
>
> Cada story deve incluir: tasks sequenciais, acceptance criteria testáveis, e checkboxes de progresso.

---

*Epic criado por Morgan (Strategist) — @pm*
*Baseado em: análise WEbdEX V30 + .env OCME + revisão arquitetural @lmas-master*
*LMAS Story-Driven Development — Constitution Art. III*
