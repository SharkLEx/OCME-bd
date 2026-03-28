---
type: workflow
id: business-flow
title: "Business-Flow — Estratégia de Negócio"
domain: business
tags:
  - workflow
  - business
  - strategy
  - offers
  - pricing
---

# ⚔️ Business-Flow — Estratégia de Negócio

Da dúvida estratégica ao modelo de negócio executável. Começa com o conselho de Hamann (que pergunta o que importa), passa pela visão de Mifune (que decide o que vender e como monetizar) e termina com o plano de Merovingian (que escala via tráfego). Ordem importa: sem estratégia, ads são dinheiro no lixo.

## Fases
| Fase | Agente | Output | Quando Pular |
|------|--------|--------|-------------|
| 1. Counsel | [[Hamann — Strategic Counsel]] | Veredicto estratégico + riscos | Se decisão já tomada |
| 2. Oferta | [[Mifune — Business Strategy]] | `offer-stack.md` | Nunca |
| 3. Pricing | [[Mifune — Business Strategy]] | `pricing-strategy.md` | Nunca |
| 4. Tráfego | [[Merovingian — Traffic Manager]] | `campaign-plan.yaml` | Se ainda não há oferta validada |

## Fluxo Visual
```
@hamann *seek-counsel → @mifune *create-offer → @mifune *set-pricing → @traffic-manager *campaign-plan
```

## Gatilho
Quando há decisões estratégicas de negócio a tomar (novo produto, pivot, modelo de receita). Inicie com `@hamann *seek-counsel {decisão}` ou `@mifune *create-offer {produto}` se decisão já tomada.

## Agentes
[[Hamann — Strategic Counsel]] → [[Mifune — Business Strategy]] → [[Mifune — Business Strategy]] → [[Merovingian — Traffic Manager]]

## Artefatos Produzidos
- `strategic-counsel.md` — Veredicto do board com riscos
- `offer-stack.md` — Oferta completa com stack de valor
- `pricing-strategy.md` — Estratégia de preço e tiers
- `campaign-plan.yaml` — Plano de campanha para a oferta

## Workflows Relacionados
[[Offer-to-Market]] (versão completa que inclui marca e copy)
[[Campaign-Pipeline]] (execução da campanha paga)
[[Brand-Flow]] (se marca também precisa ser criada)
