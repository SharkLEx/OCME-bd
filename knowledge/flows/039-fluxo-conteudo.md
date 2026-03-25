---
type: knowledge
id: "039"
title: "Fluxo de Conteúdo — Como o WEbdEX Publica e Distribui"
layer: L5-flows
tags: [flows, conteudo, marketing, pipeline, publicacao, editorial, automacao, bdzinho]
links: ["031-content-strategy", "028-voz-da-marca-webdex", "029-copy-defi", "024-bdzinho-identidade", "030-seo-defi"]
---

# 039 — Fluxo de Conteúdo WEbdEX

> **Ideia central:** Todo conteúdo do WEbdEX nasce dos dados do ciclo 21h. bdZinho distribui automaticamente nos canais core. O time amplifica nos canais derivados. Nenhum conteúdo importante é publicado sem passar pelo quality gate.

---

## A Fonte de Todo Conteúdo: Ciclo 21h

```
21h00 — Protocolo encerra o ciclo
         ↓
21h05 — OCME coleta dados on-chain
         ↓
21h10 — bdZinho gera relatório (LLM)
         ↓
21h15 — Envio automático Telegram
         ↓
21h20 — Card visual gerado (Cycle Visual)
         ↓
21h25 — Sync Discord (embed + card)
```

**Esse fluxo é automático. 0 intervenção humana.**

---

## Pipeline Humano (Conteúdo Derivado)

Baseado no relatório do ciclo 21h, o time produz:

```
@content-strategist → plano semanal (segunda-feira)
         ↓
@content-researcher → trends DeFi + dados de mercado
         ↓
@copywriter → escrita do conteúdo
         ├── Post Instagram (carrossel)
         ├── Thread X/Twitter
         ├── Newsletter (quinta)
         └── Artigo blog SEO (quarta)
         ↓
@seo → otimização keywords + schema
         ↓
@content-reviewer → quality gate (brand, legal, tom)
         ↓
@marketing-chief → aprovação final
         ↓
@social-media-manager → publicação (EXCLUSIVO)
```

---

## Mapa de Canais e Frequência

| Canal | Responsável | Frequência | Origem |
|-------|-------------|-----------|--------|
| **Telegram bot** | bdZinho (auto) | Cada ciclo (diário) | Dados on-chain |
| **Discord** | bdZinho (auto) | Cada ciclo (diário) | Dados on-chain |
| **Instagram** | @social-media-manager | 5x/semana | Derivado do ciclo |
| **X/Twitter** | @social-media-manager | 3x/semana | Derivado + original |
| **LinkedIn** | @social-media-manager | 2x/semana | Análise institucional |
| **Blog** | @social-media-manager | 1x/semana | Artigo SEO |
| **Newsletter** | @social-media-manager | 1x/semana | Digest semanal |
| **YouTube/Reels** | @social-media-manager | 1x/mês | Explicativo |

---

## Regras de Publicação (Quality Gate)

### Antes de publicar QUALQUER conteúdo:

```
✓ Vocabulário correto (subconta, não "conta"; on-chain, não "blockchain")
✓ Sem promessas de rendimento ("assertividade histórica de X%", não "ganhe X%")
✓ Dados com fonte (on-chain verificável, ciclo de data, contrato específico)
✓ Tom correto por canal (técnico no LinkedIn, visual no Instagram)
✓ bdZinho aparece como personagem, não como "IA da empresa"
✓ Sem linguagem de hype (moon, lambo, fomo, rocket)
✓ Ciclos negativos tratados com mesma seriedade que positivos
```

### Veto automático (@content-reviewer):

❌ Qualquer comparação com "investimento seguro"
❌ Qualquer promessa de retorno futuro
❌ Qualquer dado inventado (sem fonte on-chain)
❌ Qualquer linguagem que sugira custódia

---

## bdZinho como Fonte de Conteúdo Orgânico

bdZinho gera dados que o time transforma em conteúdo:

```
Perguntas frequentes no Telegram
    → @content-researcher lista perguntas recorrentes
    → @copywriter transforma em artigo FAQ
    → @seo otimiza para keywords long-tail

Frases memoráveis de usuários
    → Capturadas pelo bdZinho (anonimizadas)
    → @copywriter usa como social proof
    → @content-reviewer verifica conformidade

Análises de ciclo do bdZinho
    → Base para posts semanais de performance
    → @copywriter expande com contexto de mercado
```

**bdZinho é a pesquisa de usuário do time de conteúdo. Gratuita. Em tempo real.**

---

## Calendário Editorial Semanal

```
SEGUNDA
├── Morning: Recap da semana anterior (dados ciclos 7d)
└── Tarde: Post educativo (conceito DeFi + protocolo)

TERÇA
├── Destaque de subconta (anonimizado)
└── Thread X: análise técnica arbitragem

QUARTA
├── Carrossel Instagram: "Como funciona X no WEbdEX"
└── Artigo blog SEO (1500-2000 palavras)

QUINTA
├── bdZinho dica do dia (Telegram broadcast)
└── LinkedIn: análise institucional

SEXTA
├── Recap do ciclo da semana
└── YouTube short / Reels explicativo

FIM DE SEMANA
├── Community engagement (responder, engajar)
└── Planejamento próxima semana
```

---

## Métricas do Fluxo

| Métrica | Meta | Ferramenta |
|---------|------|-----------|
| Telegram leitura | >60% | Analytics bot |
| Discord reactions | >50 por card | Discord |
| Instagram reach | +20% MoM | Meta Analytics |
| Blog orgânico | +30% MoM | Google Search Console |
| Newsletter open | >40% | Plataforma email |
| X impressões | +15% MoM | Twitter Analytics |

---

## Erros Comuns no Fluxo

| Erro | Consequência | Como evitar |
|------|-------------|------------|
| Publicar sem quality gate | Dano de marca | @content-reviewer obrigatório |
| Dados sem fonte | Perda de credibilidade | Todo dado = link on-chain |
| Tom errado no canal | Baixo engajamento | Checar tabela Tom por Canal |
| bdZinho como "chatbot" | Dilui identidade | bdZinho é "sistema nervoso", não chatbot |
| Ignorar ciclo negativo | Hipocrisia percebida | Reportar sempre, bom e ruim |

---

## Links

← [[031-content-strategy]] — A estratégia que guia esse fluxo
← [[028-voz-da-marca-webdex]] — O tom que todos devem seguir
← [[024-bdzinho-identidade]] — Quem é o bdZinho nesse fluxo
→ [[029-copy-defi]] — Como escrever o conteúdo
→ [[030-seo-defi]] — Como otimizar para busca
