---
type: workflow
id: offer-to-market
title: "Offer-to-Market — Oferta Completa ao Mercado"
domain: business
tags:
  - workflow
  - business
  - marketing
  - cross-domain
  - launch
---

# 🚀 Offer-to-Market — Oferta Completa ao Mercado

O workflow mais completo. Da oferta criada ao anúncio no ar — atravessa os domínios de business, brand e marketing com passagem de bastão clara. Quando você quer lançar algo de verdade, esse é o caminho.

## Fases
| Fase | Agente | Output | Quando Pular |
|------|--------|--------|-------------|
| 1. Oferta | [[Mifune — Business Strategy]] | `offer-stack.md` + pricing | Nunca |
| 2. Posicionamento | [[Kamala — Brand Creation]] | `brand-positioning.md` | Se marca já existe |
| 3. Narrativa | [[Bugs — Storytelling]] | `brand-narrative.md` | Se narrativa já existe |
| 4. Copy | [[Mouse — Copywriter]] | Landing page + email + ads | Nunca |
| 5. Design | [[Sati — UX Design]] | Landing page estrutura | Se só digital sem visual |
| 6. Review | [[Seraph — Content Reviewer]] | APPROVED | Nunca |
| 7. Campanha | [[Merovingian — Traffic Manager]] | Campanha ativa | Nunca |

## Fluxo Visual
```
@mifune *create-offer → @kamala *create-positioning → @bugs *build-narrative → @copywriter *write-landing → @ux-design-expert *landing → @content-reviewer *review → @traffic-manager *campaign-plan
```

## Gatilho
Quando há uma oferta nova (produto, serviço, lançamento) que precisa ir ao mercado de forma completa. Inicie com `@mifune *create-offer {produto}`.

## Cross-Domain Authority
| Decisão | Autoridade |
|---------|-----------|
| Oferta e pricing | [[Mifune — Business Strategy]] |
| Posicionamento e tom | [[Kamala — Brand Creation]] |
| Narrativa da marca | [[Bugs — Storytelling]] |
| Copy de conversão | [[Mouse — Copywriter]] |
| Aprovação de conteúdo | [[Seraph — Content Reviewer]] → [[Lock — Marketing Chief]] |
| Budget > R$1.000 | [[Mifune — Business Strategy]] |
| Execução de campanha | [[Merovingian — Traffic Manager]] |

## Agentes
[[Mifune — Business Strategy]] → [[Kamala — Brand Creation]] → [[Bugs — Storytelling]] → [[Mouse — Copywriter]] → [[Sati — UX Design]] → [[Seraph — Content Reviewer]] → [[Merovingian — Traffic Manager]]

## Artefatos Produzidos
- `offer-stack.md` — Oferta completa
- `brand-positioning.md` — Posicionamento da oferta
- `landing-copy.md` — Copy da landing page
- `email-sequence.md` — Sequência de emails
- `ad-copy.md` — Ad copy por plataforma
- `campaign-plan.yaml` — Plano de campanha

## Workflows Relacionados
[[Brand-Flow]] (se marca precisa ser criada do zero)
[[Campaign-Pipeline]] (variação mais curta focada só na campanha)
[[Content-Pipeline]] (conteúdo orgânico paralelo ao lançamento)
