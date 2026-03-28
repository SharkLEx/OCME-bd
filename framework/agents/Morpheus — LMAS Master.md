---
type: agent
id: lmas-master
title: "👑 Morpheus — LMAS Master"
persona: Morpheus
domain: framework
cssclasses:
  - agent-framework
tags:
  - agent
  - framework
  - lmas
  - orchestration
---

# 👑 Morpheus — LMAS Master

> *"Há uma diferença entre conhecer o caminho e trilhar o caminho — eu conheço todos os caminhos deste sistema."*

Entry point universal do LMAS. Roteia intenções para o agente/domínio correto, cria e modifica componentes do framework, orquestra workflows complexos cross-domain. Use Morpheus quando não souber qual agente acionar — ele sempre sabe.

**Ativação:** `@lmas-master` | `/LMAS:agents:lmas-master`

## Domínio
Framework (cross-domain)

## O que faz
- Roteia qualquer intenção para o agente especializado correto
- Cria e modifica agentes, tasks, workflows do framework
- Executa qualquer task diretamente sem restrições de escopo
- Medeia conflitos entre agentes e domínios
- Governa a constituição do framework (enforcement de regras)
- Executa operações quando agente especializado não está disponível

## Comandos Principais
| Comando | Descrição |
|---------|-----------|
| `*route {descrição}` | Analisa intenção e roteia para agente correto |
| `*create agent {nome}` | Cria novo agente no framework |
| `*create task {nome}` | Cria nova task executável |
| `*workflow {nome}` | Executa workflow completo |
| `*ids check {intent}` | Verifica registry antes de criar algo novo |
| `*domains` | Lista todos os domínios e agentes disponíveis |
| `*status` | Estado atual do projeto e agentes ativos |
| `*exec {task}` | Executa qualquer task diretamente |

## Quando NÃO usar
- Para código específico → Use [[Neo — Dev]]
- Para stories/sprints → Use [[River — SM]] ou [[Keymaker — PO]]
- Para copy de marketing → Use [[Mouse — Copywriter]]
- Para arquitetura técnica → Use [[Aria — Architect]]

## Relações
**Recebe de:** Qualquer agente em escalação
**Entrega para:** [[Neo — Dev]], [[Oracle — QA]], [[Aria — Architect]], [[Trinity — PM]], [[Keymaker — PO]], [[River — SM]], [[Atlas — Analyst]], [[Tank — Data Engineer]], [[Sati — UX Design]], [[Operator — DevOps]]
**Workflows:** [[SDC — Story Development Cycle]], [[Spec-Pipeline]], [[Brownfield-Discovery]]

## Arquivo Fonte
`.lmas-core/development/agents/lmas-master.md`
