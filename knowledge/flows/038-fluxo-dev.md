---
type: knowledge
id: "038"
title: "Fluxo de Desenvolvimento — Como o OCME Evolui"
layer: L5-flows
tags: [flows, desenvolvimento, ocme, stories, epics, deploy, workflow, ciclo-dev, lmas]
links: ["040-tech-stack-ocme", "041-deploy-pattern", "025-bdzinho-capacidades", "026-bdzinho-brain"]
---

# 038 — Fluxo de Desenvolvimento OCME

> **Ideia central:** O OCME evolui através de Stories bem definidas, seguindo o Story Development Cycle (SDC). Cada feature passa por: ideação → spec → implementação → QA → deploy VPS. Nada vai para produção sem passar por esse ciclo.

---

## O Ciclo de Desenvolvimento Padrão (SDC)

```
@sm *draft                      → Story criada em docs/stories/
         ↓
@po *validate-story-draft       → 10-point checklist aprovado
         ↓
@dev *develop                   → Implementação no branch feat/*
         ↓
@qa *qa-gate                    → 7 quality checks
         ↓
@devops *push                   → Push para remoto
         ↓
Deploy VPS (manual via SCP)     → Em produção
```

---

## Estrutura de Epics do OCME

```
Epic 7 — bdZinho Intelligence v2 (✅ Done)
  └── Stories 7.x — Chat, Knowledge, Proactive

Epic 8 — Canais e Integrações (🔄 Em progresso)
  ├── Story 8.8 — Instagram (pausado, aguarda credenciais Meta)
  └── Story 8.9 — WhatsApp (pausado, aguarda credenciais Meta)

Epic 9 — bdZinho Discord IA (✅ Done)
  └── Contrato v1.1.0 deployado

Epic 10 — OCME Melhorias (✅ Done)
  └── Stories 10.x concluídas

Epic 11 — Creatomate Videos (✅ Done)
  └── Story 11.1 — vídeo MP4 1080x1920 ciclo 21h

Epic 12 — bdZinho Intelligence v3 (✅ Done, 2026-03-20)
  ├── Story 12.x — Stack completo deployed
  └── Smith hardening INFECTED→CLEAN

Epic 13 — Dashboard Externo Next.js+SIWE (planejado)
  └── Após Epic 12 estabilizar

Epic 14 — Subscription Flow v2 (planejado)
  └── Free/Pro/Institutional — após Epic 13
```

---

## Como Uma Nova Feature Entra no OCME

### Step 1: Ideação (Alex → Morpheus)

```
Alex identifica necessidade
      ↓
Morpheus verifica se já existe no registry (IDS check)
      ↓
Se novo: @sm cria story draft
Se existente: @dev extende feature existente
```

### Step 2: Spec (não-trivial)

Para features complexas (score >= 9 na Spec Pipeline):

```
@pm gather requirements
      ↓
@architect assess complexity
      ↓
@analyst pesquisa padrões existentes
      ↓
Spec.md criado com acceptance criteria claros
```

### Step 3: Implementação

Estrutura de arquivos do OCME:

```
packages/monitor-engine/
├── webdex_monitor.py        # Main orchestrator
├── webdex_workers.py        # Task workers
├── webdex_handlers/         # Handler modules
│   ├── user.py             # User commands (/start, /status, etc.)
│   ├── admin.py            # Admin commands (/broadcast, /stats)
│   └── webhook.py          # Webhook handlers
├── webdex_ai.py            # Brain core (Claude API)
├── webdex_ai_knowledge.py  # Knowledge Base
├── webdex_ai_proactive.py  # Proactive Mode
├── webdex_ai_vision.py     # Vision (chart analysis)
├── webdex_ai_cycle_visual.py # Cycle Visual card
├── webdex_ai_trainer.py    # Nightly Trainer
├── webdex_ai_content.py    # Content Engine
├── webdex_ai_image.py      # Image pipeline
├── webdex_ai_image_gen.py  # Image generation
├── webdex_ai_user_profile.py # Individual Memory
├── webdex_monitor.py       # Block monitor
├── webdex_discord_sync.py  # Discord sync
└── webdex_render_pil.py    # PIL renderer
```

### Step 4: QA Gate

Checks obrigatórios antes do deploy:

```
✓ Soft imports: todo módulo usa try/except
✓ Graceful degradation: falha silenciosa sem crash
✓ Logs: todas as operações logadas com nível adequado
✓ Error handling: exceptions capturadas e tratadas
✓ RPC pool rotation: timeout configurado
✓ Rate limits respeitados (especialmente Claude API)
```

### Step 5: Deploy VPS

```bash
# Padrão de deploy (ver 041-deploy-pattern)
scp -r packages/monitor-engine/ user@76.13.100.67:/tmp/monitor-engine/
ssh user@76.13.100.67 "docker cp /tmp/monitor-engine/ ocme-monitor:/app/"
ssh user@76.13.100.67 "docker restart ocme-monitor"
# Verificar saúde
curl http://localhost:9090/health
```

---

## Regras do Desenvolvedor (Neo's Code Standards)

```python
# ✅ Sempre: soft import
try:
    from webdex_ai_proactive import run_proactive
    _PROACTIVE_MODULE_ENABLED = True
except ImportError:
    _PROACTIVE_MODULE_ENABLED = False
    run_proactive = None

# ✅ Sempre: graceful degradation
if _PROACTIVE_MODULE_ENABLED and run_proactive:
    result = run_proactive(ctx)
else:
    result = None  # silently skip

# ✅ Sempre: log com contexto
logger.info(f"[proactive] executado para user_id={user_id}, resultado={result}")

# ❌ Nunca: import direto sem try/except para módulos opcionais
# ❌ Nunca: crash silencioso sem log
# ❌ Nunca: hardcode de credenciais
```

---

## Velocidade de Entrega

| Tipo de feature | Tempo estimado | Ciclo |
|----------------|---------------|-------|
| Bug fix simples | 1 sessão | SDC expresso |
| Nova capacidade bdZinho | 2-3 sessões | SDC completo |
| Novo canal (Instagram, WhatsApp) | 3-5 sessões | SDC + credenciais externas |
| Nova cápsula | 1-2 semanas | Spec Pipeline + SDC |

---

## Links

← [[040-tech-stack-ocme]] — A stack que o desenvolvimento usa
← [[041-deploy-pattern]] — Como o código vai para produção
← [[025-bdzinho-capacidades]] — O que bdZinho pode fazer (mapa de features)
→ [[042-error-patterns]] — O que pode dar errado e como tratar
