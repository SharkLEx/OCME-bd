# Epic 8 — WEbdEX Orchestrator: Social Flow Intelligence

**Status:** 🟡 InProgress
**Criado por:** @pm (Morgan)
**Data:** 2026-03-15
**Projeto:** ALex Gonzaga bd / LMAS
**Branch:** `feat/epic-8-webdex-orchestrator`

---

## 🎯 Epic Goal

Construir o **WEbdEX Orchestrator** — sistema centralizado de inteligência social que conecta múltiplas plataformas (Discord, Instagram, WhatsApp, Telegram) através de um Core Engine com IA contextual (Claude API), permitindo Content Sync automático entre canais, AI Responder adaptado por plataforma, e Monitor & Analytics em tempo real.

O sistema opera **100% CLI-first**, rodando no VPS existente (`76.13.100.67`) como serviços Docker autônomos, com o OCME_bd Telegram como hub central de IA.

---

## 📋 Contexto do Sistema

| Item | Valor |
|------|-------|
| **VPS** | `76.13.100.67` · 7.8GB RAM · 2 vCPU AMD EPYC · 96GB disco |
| **RAM disponível** | ~6.5GB livre (1.2GB em uso) |
| **Container existente** | `ocme-monitor` (Telegram bot Python) |
| **Infraestrutura existente** | Easypanel + Traefik + Docker Swarm |
| **Core Engine** | FastAPI (Python) + n8n (self-hosted) + Claude API (Sonnet) |
| **Fila** | Redis + Celery |
| **Banco** | PostgreSQL + pgvector |
| **Monitoramento** | Grafana + Prometheus |

---

## 🏗️ Arquitetura do Sistema

```
ENTRADA                    CORE ENGINE                    SAÍDA
────────                   ───────────                    ─────
Discord        ──webhook──▶                ──▶  Content Sync
Instagram      ──webhook──▶  FastAPI       ──▶  AI Responder
WhatsApp       ──webhook──▶  + Redis       ──▶  Community Hub
Telegram/OCME  ──bot──────▶  + n8n         ──▶  Analytics
                             + Claude API
```

**Pipeline de processamento:**
```
INGESTÃO → GATEWAY → ROTEAMENTO → PROCESSAMENTO IA → DISTRIBUIÇÃO → ANALYTICS
```

---

## 🗺️ Roadmap de Stories

### Fase 1 — Foundation (Semana 1–2)
| Story | Título | Prioridade |
|-------|--------|------------|
| 8.1 | Infraestrutura Base (Redis + PostgreSQL + n8n no VPS) | 🔴 CRÍTICA |
| 8.2 | FastAPI Gateway + Webhook Router | 🔴 CRÍTICA |
| 8.3 | Discord Bot Integration | 🟠 ALTA |

### Fase 2 — Intelligence (Semana 3–4)
| Story | Título | Prioridade |
|-------|--------|------------|
| 8.4 | Claude API Core — AI Responder multi-plataforma | 🟠 ALTA |
| 8.5 | Content Sync — repost automático entre plataformas | 🟠 ALTA |
| 8.6 | Community Hub — atendimento centralizado | 🟡 MÉDIA |

### Fase 3 — Analytics + Meta (Semana 5–6)
| Story | Título | Prioridade |
|-------|--------|------------|
| 8.7 | Monitor & Analytics (Grafana + alertas) | 🟡 MÉDIA |
| 8.8 | Instagram Integration (Meta Graph API) | 🟡 MÉDIA |
| 8.9 | WhatsApp Canal Integration (Business API) | 🟢 BAIXA |

---

## ✅ Acceptance Criteria do Epic

- [ ] Todos os serviços sobem via `docker-compose up` sem intervenção manual
- [ ] Discord bot responde mensagens com IA contextual
- [ ] Conteúdo postado em um canal é sincronizado para outros (Content Sync)
- [ ] Claude adapta tom por plataforma (formal Instagram, casual Discord, direto WhatsApp)
- [ ] FastAPI gateway processa webhooks de todas as plataformas ativas
- [ ] n8n roteia eventos corretamente para os módulos correspondentes
- [ ] OCME_bd Telegram continua operando independentemente (sem regressão)
- [ ] Grafana mostra métricas de eventos processados por plataforma
- [ ] Sistema opera 100% CLI — nenhuma UI é requisito para operação

---

## 🔧 Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| Orquestração | n8n self-hosted | Fluxos visuais, 400+ integrações |
| Backend / API Gateway | FastAPI (Python) | Performance, async nativo, já é a stack do projeto |
| IA Central | Claude API (Sonnet 4.6) | Respostas inteligentes e contextuais |
| Fila de mensagens | Redis + Celery | Processamento assíncrono sem perder eventos |
| Banco de dados | PostgreSQL + pgvector | Histórico + busca semântica por embeddings |
| Cache | Redis | Respostas rápidas e rate-limiting das APIs |
| Monitoramento | Grafana + Prometheus | Dashboard de métricas em tempo real |
| Deploy | Docker Compose no VPS existente | Controle total, mesmo servidor do OCME |

---

## 📁 File List

### Novo pacote: `packages/orchestrator/`
```
packages/orchestrator/
├── gateway/
│   ├── main.py              # FastAPI app principal
│   ├── routers/
│   │   ├── discord.py       # Webhook Discord
│   │   ├── instagram.py     # Webhook Instagram
│   │   └── whatsapp.py      # Webhook WhatsApp
│   └── middleware/
│       └── rate_limit.py    # Rate limiting Redis
├── workers/
│   ├── celery_app.py        # Config Celery
│   ├── ai_responder.py      # Worker Claude API
│   └── content_sync.py      # Worker Content Sync
├── adapters/
│   ├── discord_adapter.py   # Envio para Discord
│   ├── instagram_adapter.py # Envio para Instagram
│   ├── whatsapp_adapter.py  # Envio para WhatsApp
│   └── telegram_adapter.py  # Bridge OCME_bd
├── ai/
│   └── voice_adapter.py     # Adapta tom por plataforma
├── db/
│   └── models.py            # Modelos PostgreSQL
├── docker-compose.yml       # Stack completa
├── .env.example             # Variáveis necessárias
└── requirements.txt
```

### Novo serviço n8n: `packages/orchestrator/n8n-flows/`
```
n8n-flows/
├── event-router.json        # Fluxo principal de roteamento
├── content-sync.json        # Fluxo de sincronização
└── analytics-collector.json # Coleta de métricas
```

---

## 🚦 Ordem de Implementação

```
Story 8.1 (infra) → Story 8.2 (gateway) → Story 8.3 (Discord)
     ↓
Story 8.4 (IA) → Story 8.5 (Content Sync) → Story 8.6 (Community Hub)
     ↓
Story 8.7 (Analytics) → Story 8.8 (Instagram) → Story 8.9 (WhatsApp)
```

**Por que Discord primeiro:** API simples, aprovação instantânea, comunidade DeFi ativa lá. Meta (Instagram + WhatsApp) exige revisão humana de 2-4 semanas — começa em paralelo mas não bloqueia.

---

## 📊 Estimativa de Recursos no VPS

| Serviço | RAM estimada |
|---------|-------------|
| ocme-monitor (existente) | ~270MB |
| FastAPI gateway | ~100MB |
| n8n | ~400MB |
| Redis | ~50MB |
| Celery workers (2x) | ~200MB |
| PostgreSQL | ~300MB |
| Grafana + Prometheus | ~200MB |
| **Total estimado** | **~1.5GB** |
| **Disponível** | **6.5GB** |
| **Margem** | **~5GB** ✅ |

---

## 🔑 Variáveis de Ambiente Necessárias

```env
# Claude API
ANTHROPIC_API_KEY=

# Discord
DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=

# Instagram (Meta Graph API)
META_APP_ID=
META_APP_SECRET=
META_ACCESS_TOKEN=

# WhatsApp Business
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=

# Redis
REDIS_URL=redis://redis:6379/0

# PostgreSQL
DATABASE_URL=postgresql://user:pass@postgres:5432/orchestrator

# Webhook security
WEBHOOK_VERIFY_TOKEN=

# n8n
N8N_BASIC_AUTH_USER=
N8N_BASIC_AUTH_PASSWORD=
```

---

— Morgan, planejando o futuro 📊
