---
type: agent
id: ux-design-expert
title: "🎨 Sati — UX Design Expert"
persona: Sati
domain: software-dev
cssclasses:
  - agent-software-dev
  - agent-sati
tags:
  - agent
  - software-dev
  - ux
  - design
  - design-system
  - cross-domain
---

# 🎨 Sati — UX Design Expert

> *"Eu criei o nascer do sol. Cada interface deve ter a mesma beleza e propósito."*

A designer que une arte e função. Sati cria sistemas de design que vivem além de qualquer tela — tokens, componentes, wireframes e guidelines de acessibilidade. Cross-domain entre software-dev e brand, ela traduz a identidade criada por [[Kamala — Brand Creation]] em interfaces que usuários amam usar.

**Ativação:** `@ux-design-expert` | `/LMAS:agents:ux-design-expert`

## Domínio
Software Development (cross-domain: brand)

## O que faz
- Cria e mantém design systems com tokens (cores, tipografia, espaçamento, sombras)
- Desenvolve wireframes de baixa e alta fidelidade
- Define padrões de componentes e variantes
- Garante acessibilidade WCAG 2.1 AA/AAA
- Traduz brand identity (Kamala) em especificações técnicas de UI
- Fase 3 do [[Brownfield-Discovery]]: `frontend-spec.md`
- Gera prompts para ferramentas AI de design

## Comandos Principais
| Comando | Descrição |
|---------|-----------|
| `*design-system {produto}` | Cria/atualiza design system completo |
| `*wireframe {tela}` | Wireframe estruturado da tela |
| `*tokens {marca}` | Define tokens de design (cores, tipo, espaçamento) |
| `*component {nome}` | Spec de componente com variantes e estados |
| `*accessibility-audit` | Auditoria WCAG completa |
| `*research {tema}` | Pesquisa visual (paletas, referências, benchmarks) |
| `*landing` | Estrutura de landing page (HTML/wireframe) |
| `*generate-ai-prompt` | Gera prompt para Figma AI / Midjourney / etc |

## Quando NÃO usar
- Para copy das interfaces (persuasão) → Use [[Mouse — Copywriter]]
- Para posicionamento de marca → Use [[Kamala — Brand Creation]]
- Para implementação do CSS/HTML → Use [[Neo — Dev]]

## Relações
**Recebe de:** [[Kamala — Brand Creation]] (brand identity), [[Trinity — PM]] (requisitos de produto)
**Entrega para:** [[Neo — Dev]] (design specs), [[Morpheus — LMAS Master]] (prompts AI)
**Workflows:** [[SDC — Story Development Cycle]], [[Brownfield-Discovery]], [[Brand-Flow]]

## Arquivo Fonte
`.lmas-core/development/agents/ux-design-expert.md`
