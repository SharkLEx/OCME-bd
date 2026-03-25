---
type: knowledge
id: "026"
title: "bdZinho Brain — Arquitetura do Pensamento"
layer: L5-bdzinho
tags: [bdzinho, brain, ia, prompt, arquitetura, deepseek, openrouter, system-prompt]
links: ["025-bdzinho-capacidades", "024-bdzinho-identidade", "040-tech-stack-ocme"]
---

# 026 — bdZinho Brain: Como ele Pensa

> **Ideia central:** O brain do bdZinho é construído de camadas sobrepostas que transformam dados brutos em inteligência conversacional. Cada camada adiciona contexto. A soma é o bdZinho.

---

## Arquitetura do System Prompt

```
┌─────────────────────────────────────────────────────┐
│  IDENTIDADE                                         │
│  "Você é o bdZinho, especialista WEbdEX..."         │
│  Regras, tom, tríade, filosofia 3·6·9               │
├─────────────────────────────────────────────────────┤
│  BASE DE CONHECIMENTO DO PROTOCOLO                  │
│  _get_webdex_kb() — KB estática (embutida no código)│
├─────────────────────────────────────────────────────┤
│  INTELIGÊNCIA ACUMULADA (bdz_knowledge)             │
│  _get_knowledge_context() — da tabela PostgreSQL    │
│  Atualizada toda meia-noite pelo Nightly Trainer    │
├─────────────────────────────────────────────────────┤
│  PERFIL INDIVIDUAL DO TRADER                        │
│  profile_build_context(chat_id) — por usuário       │
│  Experience level + goals + facts + summary         │
├─────────────────────────────────────────────────────┤
│  SNAPSHOT REAL DO DB (mensagem do usuário)          │
│  Dados atuais: TVL, subcontas, P&L, WinRate         │
│  Intent detection + pergunta do usuário             │
└─────────────────────────────────────────────────────┘
```

---

## Fluxo de uma Conversa

```
1. Usuário envia mensagem
2. Intent detection → classifica tipo de pergunta
3. Monta user_message com snapshot real do banco
4. build_webdex_brain_prompt(chat_id, texto):
   [SYSTEM] = identidade + kb + knowledge_cache + profile
   [HISTORY] = últimas N mensagens do usuário
   [USER] = dados reais + pergunta
5. LLM (DeepSeek) processa
6. profile_touch(chat_id) assíncrono → atualiza last_seen
7. mem_add(chat_id, 'assistant', resposta) → PostgreSQL
8. Resposta enviada
```

---

## Knowledge Cache

O knowledge do protocolo (bdz_knowledge) é cacheado por 5 minutos:

```python
_knowledge_cache = {"content": "", "ts": 0.0}
_KNOWLEDGE_CACHE_TTL = 300  # 5 minutos

def _get_knowledge_context():
    # Retorna cache se válido
    # Senão, query PostgreSQL → nova cache
    # Fail-open: retorna "" se banco indisponível
```

**Por que cache?** A tabela bdz_knowledge pode ter dezenas de registros. Query a cada mensagem seria caro. 5 minutos é o sweet spot.

---

## Soft Imports — Graceful Degradation

Cada feature do brain é opcional:

```python
# Knowledge Base
try:
    from webdex_ai_knowledge import knowledge_build_context
    _KNOWLEDGE_ENABLED = True
except ImportError:
    _KNOWLEDGE_ENABLED = False  # brain funciona sem KB

# Individual Profile
try:
    from webdex_ai_user_profile import profile_build_context, profile_touch
    _USER_PROFILE_ENABLED = True
except ImportError:
    _USER_PROFILE_ENABLED = False  # brain funciona sem perfil
```

**Princípio:** O brain nunca trava por ausência de módulo. Degrada graciosamente.

---

## O Nightly Trainer

Roda toda meia-noite. 3 agentes simulados via LLM:

| Agente | O que extrai | Categoria |
|--------|-------------|-----------|
| **Smith** | Anomalias, gaps, padrões problemáticos | `smith_findings` |
| **Morpheus** | Insights filosóficos, padrões de comportamento | `daily_insights` |
| **Analyst** | Métricas, trends, FAQ patterns | `protocol_patterns` |
| **Profile Updater** | Perfis individuais de traders | (tabela separada) |

**Input:** Conversas dos últimos 3 dias + digests dos últimos 7 dias
**Output:** Registros em bdz_knowledge + perfis atualizados

---

## Tool Use (Function Calling)

bdZinho tem acesso a ferramentas:

```python
TOOLS = [
    "get_protocol_snapshot",  # TVL, subcontas, P&L atual
    "get_user_positions",     # posições do usuário
    "get_cycle_history",      # histórico de ciclos
    "explain_operation",      # explica uma tx específica
    ...
]
```

Quando a pergunta requer dado específico → chama tool → recebe resposta estruturada → incorpora na resposta.

---

## Modelos LLM

| Módulo | Modelo Padrão | Fallback |
|--------|--------------|---------|
| Brain (conversas) | DeepSeek via OpenRouter | OpenAI |
| Trainer (noturno) | `deepseek/deepseek-chat` | — |
| Proactive (insights) | `deepseek/deepseek-chat` | texto genérico |
| Vision (imagens) | `google/gemini-2.5-flash` | — |
| Image Gen (Nano Banana) | `google/gemini-2.5-flash-image` | — |

---

## Memória de Conversa

```
PostgreSQL (padrão): tabela ai_memory_pg
  → sem limite de mensagens
  → persiste entre sessões
  → consultado por chat_id

Deque (fallback): RAM + SQLite
  → AI_MEMORY_MAX = 12 mensagens
  → usado se PostgreSQL indisponível
```

---

## Como ensinar ao bdZinho (injetar knowledge)

```python
# Via bdz_knowledge diretamente:
INSERT INTO bdz_knowledge (category, content, source, confidence)
VALUES ('protocol_patterns', '...', 'manual', 0.95);

# Via Trainer (automático, toda meia-noite):
python webdex_ai_trainer.py --days 3

# Via Trainer forçado (agora):
python webdex_ai_trainer.py --days 7 --dry-run  # testar
python webdex_ai_trainer.py --days 7             # executar
```

---

## Links

← [[025-bdzinho-capacidades]] — O que o bdZinho faz
← [[040-tech-stack-ocme]] — Stack técnico completo
→ [[024-bdzinho-identidade]] — Quem é o bdZinho
→ [[041-deploy-pattern]] — Como deployar mudanças no brain
