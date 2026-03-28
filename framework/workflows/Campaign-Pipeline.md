---
type: workflow
id: campaign-pipeline
title: "Campaign-Pipeline — Campanha Paga Cross-Domain"
domain: marketing
tags:
  - workflow
  - marketing
  - campaign
  - paid-traffic
  - cross-domain
---

# 📣 Campaign-Pipeline — Campanha Paga Cross-Domain

Da estratégia ao ad no feed. Pipeline para campanhas pagas que cruzam marketing e business — precisa de copy profissional, SEO de keywords, review, aprovação de marca E aprovação de budget antes de rodar. O mais completo e o que mais dinheiro move.

## Fases
| Fase | Agente | Output | Quando Pular |
|------|--------|--------|-------------|
| 1. Estratégia de Conteúdo | [[Persephone — Content Strategist]] | Briefing + posicionamento | Nunca |
| 2. Keywords & Intent | [[Cypher — SEO]] | Keyword clusters + intenção | Nunca |
| 3. Ad Copy | [[Mouse — Copywriter]] | Copy por plataforma + variações | Nunca |
| 4. Review | [[Seraph — Content Reviewer]] | APPROVED / REJECTED | Nunca |
| 5. Aprovação de Marca | [[Lock — Marketing Chief]] | GO / NO-GO | Nunca |
| 6. Aprovação de Budget | [[Mifune — Business Strategy]] | Budget aprovado | Se < R$1.000 |
| 7. Execução | [[Merovingian — Traffic Manager]] | Campanha ativa | Nunca |

## Fluxo Visual
```
@content-strategist → @seo → @copywriter → @content-reviewer → @marketing-chief → @mifune (se > R$1k) → @traffic-manager
```

## Gatilho
Quando há oferta ou produto para promover com budget. Inicie com `@content-strategist *content-strategy {campanha}` ou direto com `@traffic-manager *campaign-plan {objetivo}`.

## Aprovação de Budget
| Valor | Aprovador |
|-------|-----------|
| < R$1.000 | [[Lock — Marketing Chief]] suficiente |
| ≥ R$1.000 | [[Mifune — Business Strategy]] obrigatório |

## Plataformas Suportadas
Meta Ads (Facebook/Instagram), Google Ads, YouTube Ads, TikTok Ads, LinkedIn Ads

## Agentes
[[Persephone — Content Strategist]] → [[Cypher — SEO]] → [[Mouse — Copywriter]] → [[Seraph — Content Reviewer]] → [[Lock — Marketing Chief]] → [[Mifune — Business Strategy]] → [[Merovingian — Traffic Manager]]

## Artefatos Produzidos
- `campaign-brief.md` — Brief completo da campanha
- `ad-copy-{plataforma}.md` — Copy por plataforma
- `campaign-plan.yaml` — Plano de execução da campanha
- Campanha ativa nas plataformas

## Workflows Relacionados
[[Content-Pipeline]] (produção de conteúdo orgânico paralelo)
[[Offer-to-Market]] (quando campanha é para nova oferta)
