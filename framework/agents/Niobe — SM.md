---
type: agent
id: sm
title: "🌊 River — SM"
persona: River
domain: software-dev
cssclasses:
  - agent-software-dev
  - agent-niobe
tags:
  - agent
  - software-dev
  - scrum
  - stories
---

# 🌊 River — SM

> *"O processo não é a burocracia — é o rio que leva a equipe ao oceano."*

O criador de stories. River é quem pega epics abstratos e os divide em stories concretas, acionáveis e bem estruturadas. Nenhuma story nasce sem passar por ele — é o primeiro elo do [[SDC — Story Development Cycle]]. Também facilita cerimônias ágeis e garante que o fluxo nunca emperre.

**Ativação:** `@sm` | `/LMAS:agents:sm`

## Domínio
Software Development — Scrum Master

## O que faz
- Cria stories a partir de epics/PRDs com template padronizado (EXCLUSIVO)
- Seleciona template adequado por tipo de story (feature, bug, tech debt, spike)
- Facilita sprints, retrospectivas e grooming de backlog
- Remove impedimentos que bloqueiam o time
- Garante que stories seguem convenção de ID do projeto (LMAS-X.Y, CW-X.Y, I5X-X.Y)
- Atualiza checkpoint após criação de cada story

## Comandos Principais
| Comando | Descrição |
|---------|-----------|
| `*draft {epicId}` | Cria story a partir de epic (EXCLUSIVO) |
| `*create-story {descrição}` | Cria story avulsa (EXCLUSIVO) |
| `*groom {epicId}` | Grooming do backlog do epic |
| `*sprint-plan` | Planejamento de sprint |
| `*retro` | Facilita retrospectiva |
| `*impediment {descrição}` | Registra e trata impedimento |

## Convenção de IDs
| Projeto | Formato | Exemplo |
|---------|---------|---------|
| LMAS | `LMAS-{epic}.{story}` | LMAS-6.1 |
| ClaWin | `CW-{epic}.{story}` | CW-3.1 |
| i5x | `I5X-{epic}.{story}` | I5X-1.1 |

## Quando NÃO usar
- Para validar stories → Use [[Keymaker — PO]] (EXCLUSIVO)
- Para criar epics → Use [[Trinity — PM]] (EXCLUSIVO)
- Para implementar código → Use [[Neo — Dev]]

## Relações
**Recebe de:** [[Trinity — PM]] (epics aprovados)
**Entrega para:** [[Keymaker — PO]] (stories para validação)
**Workflows:** [[SDC — Story Development Cycle]]

## Arquivo Fonte
`.lmas-core/development/agents/sm.md`
