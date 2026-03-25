---
type: knowledge
id: "025"
title: "bdZinho — Capacidades Completas (O que ele sabe fazer)"
layer: L5-bdzinho
tags: [bdzinho, capacidades, features, ia, telegram, discord, vision, proactive]
links: ["024-bdzinho-identidade", "026-bdzinho-brain", "016-protocol-ops", "011-subcontas"]
---

# 025 — bdZinho: Capacidades Completas

> **Ideia central:** bdZinho é um sistema de IA multi-camada. Cada capacidade foi construída sobre a anterior. Conhecer cada camada é entender o que ele pode e o que não pode fazer.

---

## Stack de Capacidades (em ordem de construção)

```
CAMADA 7: Cycle Visual (imagem emocional pós-ciclo)
CAMADA 6: Proactive Mode (bdZinho ataca primeiro)
CAMADA 5: Vision (analisa screenshots do usuário)
CAMADA 4: Individual Memory (perfil por trader)
CAMADA 3: Nano Banana (geração de imagens AI)
CAMADA 2: Knowledge Base (memória do protocolo)
CAMADA 1: Brain Base (conversas, dados on-chain, relatórios)
```

---

## CAMADA 1 — Brain Base

**O que faz:** Responde perguntas sobre o protocolo em tempo real com dados reais do banco.

**Dados disponíveis no contexto:**
- TVL atual (bd_v5 + AG_C_bd)
- Últimas operações registradas
- Status das subcontas ativas
- Histórico de ciclos 21h
- P&L, WinRate, assertividade

**Modelos:** DeepSeek (padrão) / OpenAI (fallback) via OpenRouter

```python
# Fluxo básico
mensagem do usuário → brain prompt (dados + KB + perfil) → resposta personalizada
```

---

## CAMADA 2 — Knowledge Base (bdz_knowledge)

**O que faz:** Memória persistente do protocolo. Conhecimento que o Nightly Trainer extrai e injeta toda meia-noite.

**Categorias de knowledge:**
| Categoria | O que armazena |
|-----------|---------------|
| `protocol_patterns` | Padrões de win/loss, comportamentos recorrentes |
| `daily_insights` | Insights de cada ciclo 21h |
| `smith_findings` | Anomalias e gaps detectados adversarialmente |
| `user_patterns` | Comportamentos comuns dos traders |
| `webdex_mechanics` | Mecânicas técnicas do protocolo |
| `marketing_intel` | Inteligência de mercado DeFi |
| `business_strategy` | Estratégia e posicionamento |
| `faq_patterns` | Perguntas frequentes + respostas validadas |

**Atualizado:** Toda meia-noite via `webdex_ai_trainer.py` → 4 agentes (Smith, Morpheus, Analyst, Profile Updater)

→ [[026-bdzinho-brain]] — Como o knowledge é injetado no prompt

---

## CAMADA 3 — Nano Banana (Geração de Imagens)

**O que faz:** Gera imagens AI sob demanda pelo comando 🎨 Criar Imagem no Telegram.

**Motor:** Google Gemini `google/gemini-2.5-flash-image` via OpenRouter

**SCDS Prompt System:** Detecção automática de contexto → seleciona pose/estilo do bdZinho
- Palavras-chave → pose específica (celebrando, profissional, cool, etc.)
- DNA completo injetado em cada prompt (anatomy, colors, style)
- Rate limit: 30s entre gerações por usuário

**Uso:** Traders pedem imagens temáticas, celebrações, análises visuais

---

## CAMADA 4 — Individual Memory (Perfil por Trader)

**O que faz:** Mantém perfil individual de cada trader. Personaliza CADA resposta.

**Schema `bdz_user_profiles`:**
```
experience_level:  iniciante | intermediario | avancado | unknown
goals:             JSONB — objetivos declarados e inferidos
facts:             JSONB — fatos sobre o trader
summary:           texto — resumo em linguagem natural
last_seen:         timestamp
```

**Como cresce:** Toda conversa toca o perfil. Profile Updater roda toda meia-noite analisando conversas e atualizando o resumo com novos fatos observados.

**Efeito:** bdZinho que já te conhece não precisa de contexto — lembra do seu nível, seus objetivos, suas dúvidas recorrentes.

---

## CAMADA 5 — Vision (Análise de Imagens)

**O que faz:** Usuário envia screenshot → bdZinho analisa com contexto DeFi.

**Motor:** `google/gemini-2.5-flash` (multimodal) via OpenRouter

**Contexto especializado:**
- Charts de trading (candlestick, volume, RSI)
- Dashboards de portfólio
- Prints de carteiras Web3
- Resultados de transações
- Gráficos on-chain

**Rate limit:** 10s entre análises por usuário
**Limite:** 4MB por imagem
**Integração:** Perfil do usuário (camada 4) é injetado na análise

```
usuário envia foto + pergunta opcional
→ download bytes
→ base64 encode
→ Gemini Flash Vision + contexto DeFi + perfil trader
→ análise personalizada
```

---

## CAMADA 6 — Proactive Mode (bdZinho Ataca Primeiro)

**O que faz:** Após ciclo 21h, bdZinho envia mensagens proativas personalizadas para traders ativos.

**Lógica:**
1. Ciclo 21h encerra
2. Lista traders ativos (últimos 3 dias) com perfil
3. Filtra por rate limit (24h por usuário)
4. Máx 15 usuários por ciclo (controle de custo)
5. LLM gera insight personalizado: perfil + dados do ciclo
6. Fallback genérico se LLM indisponível

**Tipos de mensagem:**
- Ciclo positivo: celebração + destaque de ganho
- Ciclo negativo: contextualização + foco no longo prazo
- Inatividade: "faz um tempo que você não aparece..."

---

## CAMADA 7 — Cycle Visual (Imagem Emocional Pós-Ciclo)

**O que faz:** Posta UMA imagem do bdZinho com expressão emocional no Discord após cada ciclo 21h.

**Expressões:**
- `CELEBRANDO` → ciclo positivo (p_bruto ≥ 0): braços erguidos, confetti dourado
- `PROFISSIONAL` → ciclo negativo: braços cruzados, accent azul
- `NEUTRO` → sem trades: aceno gentil

**Canal:** Discord #relatório-diário via webhook
**Custo:** 1 imagem por ciclo (não por usuário)
**Motor:** Gemini Flash Image via OpenRouter

---

## Limitações Atuais (o que bdZinho NÃO faz)

| Limitação | Razão | Próximo passo |
|-----------|-------|---------------|
| Não executa trades | Non-custodial — capital do usuário é sagrado | Fora do escopo por design |
| Não acessa preços em tempo real | Sem feed de mercado integrado | bdPro pode complementar |
| Não está no Discord de forma interativa | Apenas webhooks (relatórios) | bdZinho 4.3 — Discord Bot |
| Não tem memória cross-platform | Perfil só via Telegram | Futuro: OCME App unifica |

---

## Links

← [[024-bdzinho-identidade]] — Quem é o bdZinho
→ [[026-bdzinho-brain]] — Como o brain é construído
→ [[027-bdzinho-expressoes]] — Guia de expressões visuais
→ [[016-protocol-ops]] — Dados que alimentam o brain
→ [[011-subcontas]] — Contexto de subconta no brain
