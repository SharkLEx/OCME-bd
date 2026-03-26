---
type: knowledge
title: "Dev — Mapa Completo do Codebase WEbdEX"
tags:
  - dev
  - arquitetura
  - codebase
  - onboarding
created: 2026-03-26
source: morpheus-sensei
---

# Mapa Completo do Codebase WEbdEX

> Módulo 01 de 10 — Professor: Morpheus
> Use este mapa sempre que precisar saber ONDE fica qualquer coisa.

---

## Dois Packages, Dois Containers

O WEbdEX tem dois pacotes independentes, cada um rodando em seu próprio container Docker no VPS:

| Package | Container | Função |
|---------|-----------|--------|
| `packages/orchestrator/` | `orchestrator-discord` | Bot Discord IA + API FastAPI |
| `packages/monitor-engine/` | `ocme-monitor` | Motor on-chain + workers + Telegram |

Cada container tem seu próprio filesystem. Compartilham o volume Docker `monitor-engine_monitor_data` montado em:
- `ocme-monitor`: `/app/data/` (leitura/escrita)
- `orchestrator-discord`: `/ocme_data/` (somente leitura)

---

## packages/orchestrator/discord/ — Stack Discord

```
bot.py               ← Entry point: intents, slash commands, rate limit 36 msgs/24h free
commands.py          ← /ajuda /status /grafico /card
ai_handler.py        ← Claude via OpenRouter, streaming, tool use, memória PostgreSQL
ia_buttons.py        ← Menu fixado no canal bdZinho, botões Wallet/PRO/Chat/Dev
subscription.py      ← Gate on-chain: verifica assinatura BD (Web3, contrato 0x6481d77f)
db_handler.py        ← Persiste eventos em PostgreSQL (platform_events, discord_user_profiles)
webdex_tools_discord.py ← Definições de tools: consulta_protocolo, buscar_vault, métricas
vault_reader.py      ← RAG: indexa 59+ notas Obsidian, busca por relevância
bdz_knowledge_discord.py ← Carrega bdz_knowledge do PostgreSQL (cache 1h)
webdex_ai_memory.py  ← Memória longa: lê/escreve ai_conversations PostgreSQL
voice_discord.py     ← SYSTEM_PROMPT principal + build_prompt()
embed_builder.py     ← Fábrica de embeds Discord com design system
design_tokens.py     ← Cores, ícones, footer: PRO_PURPLE, SUCCESS, WARNING, ERROR
protocol_context.py  ← get_protocol_context(): TVL, win rate, ciclos ao vivo
chart_handler.py     ← Detecta intenção de gráfico, gera charts
ia_buttons.py        ← Botão menu principal do canal bdZinho
metrics_worker.py    ← Tracking de uso (msgs, usuários ativos)
media/card_server.py ← Subprocess: HTML → PNG para /card (porta 8766, DB /ocme_data/)
```

## packages/monitor-engine/ — Stack Monitor

```
webdex_main.py          ← Entry point: inicia todos os workers em threads
webdex_config.py        ← Env vars, Web3, Telegram bot, logging, TZ_BR
webdex_db.py            ← SQLite thread-local, WAL mode, DB_LOCK, _ConnProxy
webdex_chain.py         ← Web3 RPC, contratos, cache de blocos
webdex_workers.py       ← sentinela, agendador_21h, capital_snapshot, funnel_worker
webdex_monitor.py       ← vigia(): rastreamento de operações em tempo real
webdex_ai.py            ← Claude/OpenRouter, rate limit, KB, prompt builder
webdex_ai_trainer.py    ← Nightly Trainer 00:00 BRT: 5 agentes aprendem conversas
webdex_ai_memory.py     ← ai_conversations PostgreSQL (plataform=telegram/discord)
webdex_ai_knowledge.py  ← Constrói bdz_knowledge (tabela PostgreSQL)
webdex_ai_content.py    ← Formata posts Telegram/Discord pós-ciclo
webdex_ai_image.py      ← PIL cards de ciclo, post Discord
webdex_ai_proactive.py  ← Nudges pós-ciclo (Telegram)
webdex_ai_cycle_visual.py ← Animação expressão bdZinho pós-ciclo
webdex_discord_sync.py  ← Webhooks Discord: relatório, operações, swaps, on-chain
webdex_vault_writer.py  ← Nexo escreve notas aprendidas no vault (/app/data/vault/learned/)
subscription_worker.py  ← Polling Subscribed events on-chain, atualiza subscription_expires
notification_engine.py  ← Roteador: Telegram / Discord / webhook
telegram_design_tokens.py ← Tokens de design do Telegram (HDR, SEP, emojis)
```

---

## Fluxo de uma Mensagem no Discord

```
Usuário menciona @bdZinho no canal
  ↓
bot.py — verifica rate limit free (36 msgs/24h)
  ↓
ai_handler.stream_ai_response()
  ├── get_protocol_context()      ← TVL, win rate, ciclos ao vivo
  ├── get_knowledge_context()     ← bdz_knowledge (90+ itens PostgreSQL)
  ├── vault_reader.search_vault() ← busca vault Obsidian se tool chamada
  ├── _mem_get(user_id)           ← histórico PostgreSQL
  └── OpenRouter (Claude) streaming
  ↓
Resposta enviada em chunks (streaming)
  ↓
_mem_add(user_id, 'assistant', texto)  ← salva memória
```

---

## Onde Adicionar Features

| Quero adicionar... | Arquivo |
|--------------------|---------|
| Novo slash command | `commands.py` |
| Nova tool para a IA | `webdex_tools_discord.py` |
| Novo botão no menu | `ia_buttons.py` |
| Nova nota de conhecimento | `knowledge/` vault + `inject_knowledge.py` |
| Novo worker background | `webdex_workers.py` |
| Nova notificação Telegram | `notification_engine.py` |
| Nova animação Discord | `webdex_discord_sync.py` ou `webdex_discord_animate.py` |
| Novo chart | `chart_handler.py` |
