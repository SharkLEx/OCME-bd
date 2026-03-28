---
type: workflow
id: brownfield-discovery
title: "Brownfield-Discovery — Avaliação de Projeto Existente"
domain: software-dev
tags:
  - workflow
  - software-dev
  - brownfield
  - technical-debt
  - assessment
---

# 🏚️ Brownfield-Discovery — Avaliação de Projeto Existente

Quando você entra em um projeto que já existe — com código, dados, dívida técnica e decisões passadas que ninguém documentou. 10 fases sistemáticas para entender o que há, avaliar o que está quebrado e criar um plano de ação realista.

## Fases
| Fase | Agente | Output | Tipo |
|------|--------|--------|------|
| 1 | [[Aria — Architect]] | `system-architecture.md` | Coleta |
| 2 | [[Tank — Data Engineer]] | `SCHEMA.md` + `DB-AUDIT.md` | Coleta |
| 3 | [[Sati — UX Design]] | `frontend-spec.md` | Coleta |
| 4 | [[Aria — Architect]] | `technical-debt-DRAFT.md` | Draft |
| 5 | [[Tank — Data Engineer]] | `db-specialist-review.md` | Validação |
| 6 | [[Sati — UX Design]] | `ux-specialist-review.md` | Validação |
| 7 | [[Oracle — QA]] | `qa-review.md` → APPROVED/NEEDS WORK | QA Gate |
| 8 | [[Aria — Architect]] | `technical-debt-assessment.md` (final) | Finalização |
| 9 | [[Atlas — Analyst]] | `TECHNICAL-DEBT-REPORT.md` (executivo) | Finalização |
| 10 | [[Trinity — PM]] | Epics + stories prontos para dev | Planejamento |

## Gatilho
Quando o projeto já existe e precisa de assessment antes de novos desenvolvimentos. Inicie com `@architect *brownfield`.

## QA Gate (Fase 7)
| Verdito | Critérios | Ação |
|---------|-----------|------|
| APPROVED | Todos os débitos validados, sem gaps críticos, dependências mapeadas | → Fase 8 |
| NEEDS WORK | Gaps não endereçados, retornar à análise | → Fase 4 (re-draft) |

## Agentes
[[Aria — Architect]] + [[Tank — Data Engineer]] + [[Sati — UX Design]] → [[Oracle — QA]] → [[Atlas — Analyst]] → [[Trinity — PM]]

## Artefatos Produzidos
- `system-architecture.md` — Arquitetura atual documentada
- `SCHEMA.md` — Schema de banco de dados
- `DB-AUDIT.md` — Auditoria do banco
- `frontend-spec.md` — Spec do frontend atual
- `technical-debt-DRAFT.md` — Rascunho de débito técnico
- `technical-debt-assessment.md` — Assessment final
- `TECHNICAL-DEBT-REPORT.md` — Relatório executivo
- Epics e stories no backlog

## Workflows Relacionados
[[SDC — Story Development Cycle]] (executa os epics gerados na fase 10)
[[Spec-Pipeline]] (para features novas identificadas no assessment)
