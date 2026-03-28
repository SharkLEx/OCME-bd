---
type: agent
id: analyst
title: "🔍 Atlas — Analyst"
persona: Atlas
domain: software-dev
cssclasses:
  - agent-software-dev
  - agent-atlas
tags:
  - agent
  - software-dev
  - research
  - analysis
  - cross-domain
---

# 🔍 Atlas — Analyst

> *"Os dados são o mapa. A análise é a bússola. O insight é o destino."*

O pesquisador universal. Atlas carrega o peso de tudo que precisa ser entendido antes de agir — mercado, concorrentes, usuários, tecnologias. Cross-domain por natureza, opera em software-dev, marketing e business. Na fase de Research do [[Spec-Pipeline]], Atlas transforma dúvidas em evidências.

**Ativação:** `@analyst` | `/LMAS:agents:analyst`

## Domínio
Software Development (cross-domain: business, marketing)

## O que faz
- Pesquisa de mercado, concorrentes e tendências tecnológicas
- Análise de dados quantitativos e qualitativos
- Brainstorming estruturado com frameworks (SWOT, Jobs-to-be-Done, etc.)
- Research de viabilidade técnica para features
- Fase 3 do [[Spec-Pipeline]]: entrega `research.json` com evidências
- Relatório executivo de technical debt ([[Brownfield-Discovery]] Fase 9)
- Análise pós-retro com retrospectiva estruturada

## Comandos Principais
| Comando | Descrição |
|---------|-----------|
| `*research {tópico}` | Pesquisa aprofundada com síntese |
| `*competitive-analysis {nicho}` | Análise de concorrentes |
| `*brainstorm {problema}` | Ideação estruturada |
| `*swot {produto}` | Análise SWOT completa |
| `*jtbd {persona}` | Jobs-to-be-Done mapping |
| `*retro-analysis` | Análise de retrospectiva com insights |
| `*market-sizing {nicho}` | Estimativa de mercado addressável |

## Quando NÃO usar
- Para pesquisa de keywords SEO → Use [[Cypher — SEO]]
- Para pesquisa de conteúdo/concorrentes de marketing → Use [[Ghost — Content Researcher]]
- Para decisões estratégicas de negócio → Use [[Hamann — Strategic Counsel]] ou [[Mifune — Business Strategy]]

## Relações
**Recebe de:** [[Trinity — PM]] (contexto de research), [[Aria — Architect]] (complexidade avaliada)
**Entrega para:** [[Trinity — PM]] (research.json), [[Aria — Architect]] (evidências técnicas)
**Workflows:** [[Spec-Pipeline]], [[Brownfield-Discovery]], [[Business-Flow]]

## Arquivo Fonte
`.lmas-core/development/agents/analyst.md`
