---
type: workflow
id: qa-loop
title: "QA-Loop — Ciclo Iterativo de Review"
domain: software-dev
tags:
  - workflow
  - software-dev
  - qa
  - iterative
---

# 🔁 QA-Loop — Ciclo Iterativo de Review

Quando o QA gate falha, o QA-Loop entra em ação. Ciclo automatizado de review-fix entre [[Oracle — QA]] e [[Neo — Dev]] com máximo 5 iterações antes de escalar. Evita o ping-pong manual e mantém registro de estado entre iterações.

## Fases
| Iteração | Agente | Ação | Output |
|----------|--------|------|--------|
| Review | [[Oracle — QA]] | Identifica problemas específicos | `APPROVE` / `REJECT` / `BLOCKED` |
| Fix | [[Neo — Dev]] | Corrige issues apontados | Commits com fixes |
| Re-review | [[Oracle — QA]] | Verifica se fixes resolveram | Novo verdito |
| (max 5x) | — | Repete até APPROVE ou BLOCKED | — |

## Gatilho
Quando `@qa *qa-gate` retorna FAIL. Iniciar com `@qa *qa-loop {storyId}`.

## Comandos
| Comando | Agente | Descrição |
|---------|--------|-----------|
| `*qa-loop {storyId}` | [[Oracle — QA]] | Inicia loop |
| `*qa-loop-review` | [[Oracle — QA]] | Retoma do passo review |
| `*qa-loop-fix` | [[Neo — Dev]] | Retoma do passo fix |
| `*stop-qa-loop` | Qualquer | Pausa e salva estado |
| `*resume-qa-loop` | Qualquer | Retoma do estado salvo |
| `*escalate-qa-loop` | Qualquer | Força escalação imediata |

## Verditos
| Verdito | Ação |
|---------|------|
| APPROVE | Loop encerra → [[Operator — DevOps]] *push |
| REJECT | [[Neo — Dev]] *fix → nova iteração |
| BLOCKED | Escalação imediata → [[Morpheus — LMAS Master]] |

## Gatilhos de Escalação
- `max_iterations_reached` — 5 iterações sem APPROVE
- `verdict_blocked` — problema não pode ser resolvido por @dev
- `fix_failure` — fix gerou novos problemas
- `manual_escalate` — usuário pede escalação

## Estado
Arquivo de estado: `qa/loop-status.json`
```json
{
  "story_id": "LMAS-5.2",
  "iteration": 3,
  "status": "in_review",
  "issues_open": ["Issue 1", "Issue 2"],
  "issues_resolved": ["Issue 0"]
}
```

## Agentes
[[Oracle — QA]] ↔ [[Neo — Dev]] (loop) → [[Operator — DevOps]] (APPROVE) / [[Morpheus — LMAS Master]] (BLOCKED)

## Workflows Relacionados
[[SDC — Story Development Cycle]] (QA-Loop é acionado pelo SDC quando QA falha)
