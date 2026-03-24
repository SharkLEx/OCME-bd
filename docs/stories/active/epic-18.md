# Epic 18 — LiteLLM Diversification: Multi-Model AI Router

**Status:** ❌ Cancelada
**Criado:** 2026-03-20
**Objetivo:** Substituir a chamada direta `openai.ChatCompletion` por um LiteLLM proxy que roteia entre múltiplos modelos — redução de ~60% no custo de IA e eliminação de single-point-of-failure.

---

## Problema Atual

O bdZinho usa exclusivamente GPT-4o via OpenAI SDK direto:
- Custo: ~$5/1M tokens (gpt-4o)
- Single-point-of-failure: se OpenAI cair → bot mudo
- Sem fallback automático
- Sem controle de custo por usuário/tier

---

## Solução: LiteLLM como AI Router

```
bdZinho (webdex_ai.py)
        ↓
  LiteLLM Proxy (Docker)
   /      |       \
GPT-4o-mini  DeepSeek V3  Groq Llama
 (primary)   (fallback 1)  (fallback 2)
```

---

## Model Stack Recomendado

| Prioridade | Modelo | Custo | Uso |
|------------|--------|-------|-----|
| 1 (primary) | `openai/gpt-4o-mini` | $0.15/1M in | 90% das requests |
| 2 (premium) | `openai/gpt-4o` | $5.00/1M in | Queries complexas tier Pro |
| 3 (fallback) | `deepseek/deepseek-chat` | $0.07/1M in | Quando OpenAI falha |
| 4 (speed) | `groq/llama-3.1-8b-instant` | $0.05/1M in | Rate limit ou latência alta |

**Economia estimada:** GPT-4o ($5) → GPT-4o-mini ($0.15) = **-97% custo por token**. Com mix realista (90% mini, 10% full): ~**-60% custo total**.

---

## Stories

| Story | Título | Status | Blocker |
|-------|--------|--------|---------|
| 18.1 | LiteLLM Proxy Setup + webdex_ai.py migration | ⏳ Backlog | — |
| 18.2 | Model routing por tier (Free/Pro) | ⏳ Backlog | 18.1 |

---

## Prioridade de Implementação

1. **18.1** — Setup Docker container + migrar webdex_ai.py para LiteLLM SDK
2. **18.2** — Routing inteligente: Free → gpt-4o-mini, Pro → gpt-4o, fallbacks automáticos

---

## Nota sobre Deploy

LiteLLM roda como container `litellm-proxy` no mesmo Docker network do orchestrator.
Single env var `LITELLM_API_BASE=http://litellm-proxy:4000` substitui `OPENAI_API_BASE`.
Todos os modelos acessados via API key unificada ou por provider.
