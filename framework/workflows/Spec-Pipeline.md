---
type: workflow
id: spec-pipeline
title: "Spec-Pipeline — Requisitos para Spec Executável"
domain: software-dev
tags:
  - workflow
  - software-dev
  - spec
  - requirements
  - pre-implementation
---

# 📋 Spec-Pipeline — Requisitos para Spec Executável

Transforma requisitos informais ("quero uma feature de X") em especificação técnica executável antes de escrever uma linha de código. Elimina retrabalho caro por ambiguidade. Para features SIMPLE, executa em 3 fases. Para COMPLEX, 6 fases + revisão.

## Fases
| Fase | Agente | Output | Skip Se |
|------|--------|--------|---------|
| 1. Gather | [[Trinity — PM]] | `requirements.json` | Nunca |
| 2. Assess | [[Aria — Architect]] | `complexity.json` | Nunca |
| 3. Research | [[Atlas — Analyst]] | `research.json` | Classe SIMPLE |
| 4. Write Spec | [[Trinity — PM]] | `spec.md` | Nunca |
| 5. Critique | [[Oracle — QA]] | `critique.json` | Nunca |
| 6. Plan | [[Aria — Architect]] | `implementation.yaml` | Se APPROVED |

## Classes de Complexidade
| Score | Classe | Fases Executadas |
|-------|--------|-----------------|
| ≤ 8 | **SIMPLE** | 1 → 4 → 5 (3 fases) |
| 9–15 | **STANDARD** | Todas as 6 fases |
| ≥ 16 | **COMPLEX** | 6 fases + ciclo de revisão |

## 5 Dimensões de Complexidade (score 1–5 cada)
| Dimensão | O que avalia |
|----------|-------------|
| **Scope** | Quantos arquivos/módulos afetados |
| **Integration** | APIs externas envolvidas |
| **Infrastructure** | Mudanças de infra necessárias |
| **Knowledge** | Familiaridade do time com o domínio |
| **Risk** | Nível de criticidade e impacto |

## Verditos do Critique (Fase 5)
| Verdito | Score Médio | Próximo |
|---------|------------|---------|
| APPROVED | ≥ 4.0 | Fase 6 (Plan) |
| NEEDS_REVISION | 3.0–3.9 | Fase 5b (Revisão) |
| BLOCKED | < 3.0 | Escalar para [[Aria — Architect]] |

## Gate Constitucional (Artigo IV — No Invention)
Todo statement em `spec.md` DEVE rastrear para `FR-*`, `NFR-*`, `CON-*` ou finding de research. Nenhuma feature pode ser inventada pelo PM.

## Gatilho
Feature complexa ou ambígua que precisa de spec antes do desenvolvimento. Inicie com `@pm *spec-pipeline {feature}`.

## Agentes
[[Trinity — PM]] → [[Aria — Architect]] → [[Atlas — Analyst]] → [[Trinity — PM]] → [[Oracle — QA]] → [[Aria — Architect]]

## Artefatos Produzidos
- `requirements.json` — Requisitos estruturados
- `complexity.json` — Score de complexidade por dimensão
- `research.json` — Evidências de mercado/técnicas (se STANDARD/COMPLEX)
- `spec.md` — Especificação executável
- `critique.json` — Review da spec com scores
- `implementation.yaml` — Plano de implementação (se aprovado)

## Workflows Relacionados
[[SDC — Story Development Cycle]] (após Spec-Pipeline aprovado, gera stories)
[[Brownfield-Discovery]] (se for feature em projeto existente)
