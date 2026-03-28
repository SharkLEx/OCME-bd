---
type: workflow
id: content-pipeline
title: "Content-Pipeline — Produção de Conteúdo"
domain: marketing
tags:
  - workflow
  - marketing
  - content
  - editorial
---

# 📝 Content-Pipeline — Produção de Conteúdo

Da ideia ao post publicado. O pipeline editorial completo de marketing de conteúdo — desde a pesquisa de audiência até a publicação no feed. Garante que cada peça tem estratégia, copy profissional, SEO, review de qualidade e aprovação antes de ir ao ar.

## Fases
| Fase | Agente | Output | Quando Pular |
|------|--------|--------|-------------|
| 1. Estratégia | [[Persephone — Content Strategist]] | Briefing + calendário | Nunca |
| 2. Research | [[Ghost — Content Researcher]] | Insights de audiência + benchmarks | Se briefing já tem research |
| 3. Copy | [[Mouse — Copywriter]] | Copy finalizada por canal | Nunca |
| 4. SEO | [[Cypher — SEO]] | Keywords + otimizações | Se conteúdo não é para orgânico |
| 5. Review | [[Seraph — Content Reviewer]] | APPROVED / REJECTED | Nunca |
| 6. Aprovação | [[Lock — Marketing Chief]] | Aprovação final | Se conteúdo menor |
| 7. Publicação | [[Sparks — Social Media Manager]] | Conteúdo publicado | Nunca |

## Fluxo Visual
```
@content-strategist → @content-researcher → @copywriter → @seo → @content-reviewer → @marketing-chief → @social-media-manager
```

## Gatilho
Quando há necessidade de conteúdo para canais owned (blog, social, email). Inicie com `@content-strategist *content-strategy {nicho}`.

## Tipos de Conteúdo Suportados
- Posts de social media (Instagram, X, LinkedIn, TikTok)
- Blog posts e artigos
- Email marketing
- Carrosséis e threads
- Conteúdo de vídeo (script)

## Agentes
[[Persephone — Content Strategist]] → [[Ghost — Content Researcher]] → [[Mouse — Copywriter]] → [[Cypher — SEO]] → [[Seraph — Content Reviewer]] → [[Lock — Marketing Chief]] → [[Sparks — Social Media Manager]]

## Artefatos Produzidos
- `content-brief.md` — Briefing editorial
- `copy-{canal}.md` — Copy finalizada por canal
- `seo-brief.md` — Keywords e otimizações
- Conteúdo publicado nos canais

## Workflows Relacionados
[[Campaign-Pipeline]] (quando conteúdo é parte de campanha paga)
