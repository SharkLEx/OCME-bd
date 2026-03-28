---
type: workflow
id: sdc
title: "SDC — Story Development Cycle"
domain: software-dev
tags:
  - workflow
  - software-dev
  - primary
  - sdc
---

# 🔄 SDC — Story Development Cycle

O workflow primário de desenvolvimento. Todo trabalho de código começa e termina aqui — da story vazia ao código em produção. Quatro fases, quatro agentes, zero ambiguidade sobre quem faz o quê.

## Fases
| Fase | Agente | Output | Quando Pular |
|------|--------|--------|-------------|
| 1. Create | [[River — SM]] | `{epic}.{story}.story.md` | Nunca |
| 2. Validate | [[Keymaker — PO]] | GO / NO-GO (checklist 10 pts) | Nunca |
| 3. Implement | [[Neo — Dev]] | Código + testes + commit | Nunca |
| 4. QA Gate | [[Oracle — QA]] | PASS / FAIL / CONCERNS | Nunca |
| 5. Push | [[Operator — DevOps]] | PR + deploy | Se não há remote |

## Fluxo Visual
```
@sm *draft → @po *validate → @dev *develop → @qa *qa-gate → @devops *push
```

## Gatilho
Quando há um epic aprovado e a próxima story precisa ser desenvolvida. Inicie com `@sm *draft {epicId}`.

## Modos de Implementação (Fase 3)
| Modo | Comando | Quando Usar |
|------|---------|-------------|
| Interactive | `*develop` | Features complexas, primeira run |
| YOLO | `*yolo` | Bug fixes simples, tasks menores |
| Pre-Flight | `*pre-flight` | Checklist antes de marcar pronto |

## QA Verditos (Fase 4)
| Verdito | Ação |
|---------|------|
| PASS | → [[Operator — DevOps]] *push |
| CONCERNS | → [[Neo — Dev]] resolve ou documenta, depois push |
| FAIL | → [[Neo — Dev]] *fix, re-review (max 5 via [[QA-Loop]]) |
| WAIVED | → [[Morpheus — LMAS Master]] aprova, então push |

## Agentes
[[River — SM]] → [[Keymaker — PO]] → [[Neo — Dev]] → [[Oracle — QA]] → [[Operator — DevOps]]

## Artefatos Produzidos
- `docs/stories/{epic}.{story}.story.md` — Story com AC, tasks, File List
- Commits no git local
- PR no GitHub (opcional)

## Workflows Relacionados
[[QA-Loop]] (quando QA falha e precisa iteração)
[[Spec-Pipeline]] (quando feature é complexa e precisa spec antes)
[[Brownfield-Discovery]] (quando projeto existente precisa assessment)
