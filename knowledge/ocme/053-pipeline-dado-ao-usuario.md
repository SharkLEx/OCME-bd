---
type: knowledge
id: "053"
title: "Pipeline OCME — Como o Dado Chega ao Usuário"
layer: L3-ocme
tags: [ocme, pipeline, arquitectura, monitor-engine, card-server, discord]
links: ["016-protocol-ops", "040-tech-stack-ocme", "041-deploy-pattern"]
created: 2026-03-25
---

# 053 — Pipeline: Da Blockchain ao Usuário

> **Ideia central:** O dado on-chain percorre 5 camadas antes de aparecer para o usuário. Entender esse pipeline é essencial para debugar, escalar e confiar no sistema.

---

## O Pipeline Completo

```
POLYGON BLOCKCHAIN
       │
       │ eventos on-chain (logs, transações)
       ▼
MONITOR ENGINE (ocme-monitor container)
  ├── webdex_workers.py  → agendador_21h (ciclos)
  ├── webdex_listeners.py → eventos em tempo real
  └── webdex_v5_final.db  → 4.37M rows (SQLite)
       │
       │ lê o DB compartilhado
       ▼
CARD SERVER (orchestrator-discord container)
  └── card_server.py (porta 8766)
      ├── /api/data/conquistas   → data_conquistas()
      ├── /api/data/token-bd     → data_token_bd()
      ├── /api/data/operacoes    → data_operacoes()
      └── ... 8 endpoints totais
       │
       │ HTTP GET interno (localhost:8766)
       ▼
RENDER CARD (Node.js headless)
  └── render_card.js + Playwright/Chromium
      ├── Abre HTML do card
      ├── live-data.js injeta dados via data-live=""
      └── Captura screenshot → WebM animado
       │
       │ arquivo .webm
       ▼
DISCORD BOT (voice_discord.py)
  └── /card comando
      ├── Chama render_card.js
      ├── Recebe .webm gerado
      └── Posta no canal como attachment
       │
       ▼
USUÁRIO VÊ O CARD ANIMADO
```

---

## Volumes Compartilhados (chave da arquitetura)

O SQLite é o elo entre os dois containers:

```yaml
# docker-compose.yml
volumes:
  - ocme_data:/ocme_data  # shared volume

# ocme-monitor container:
OCME_DB_PATH=/ocme_data/webdex_v5_final.db

# orchestrator-discord container:
OCME_DB_PATH=/ocme_data/webdex_v5_final.db
DB_PATH=/ocme_data/webdex_v5_final.db  # passado para card_server.py
```

**Regra:** Ambos containers lêem o MESMO arquivo SQLite. `monitor-engine` escreve, `card-server` lê.

---

## Latências por Etapa

| Etapa | Latência típica | Tipo |
|-------|----------------|------|
| Blockchain → Monitor | 1-5 min | Polling (não push) |
| Monitor → SQLite | Imediato | Write direto |
| SQLite → card_server | Imediato | Query on-demand |
| card_server → render | ~3-8s | Headless Chrome |
| render → Discord | ~1s | Upload attachment |
| **Total (pior caso)** | **~15 min** | Dados 21h frescos |

---

## Pontos de Falha e Detecção

| Componente | Falha comum | Como detectar |
|-----------|-------------|---------------|
| Monitor Engine | `unhealthy` — DB não acessível | `docker ps` → `(unhealthy)` |
| card_server | Processo morto | watchdog reinicia em 60s |
| Render Node.js | Chrome travado | timeout no `/card` command |
| Volume compartilhado | Permissão negada | `docker exec ... ls /ocme_data` |

---

## Observabilidade

- **Saúde**: `curl http://localhost:9090/health` dentro do container monitor
- **Dados**: `curl http://localhost:8766/api/data/conquistas` dentro do orchestrator
- **Logs**: `docker logs ocme-monitor --tail 50`

---

## Bug Histórico: DB_PATH Override (corrigido 2026-03-25)

`bot.py` estava passando `DB_PATH` para o card_server, mas ignorava a var `OCME_DB_PATH` do container. Resultado: todos os cards abriam o SQLite local vazio em vez do volume compartilhado.

**Fix**: `bot.py:_start_card_server()` agora usa `os.environ.get("OCME_DB_PATH")` como primeira prioridade.
