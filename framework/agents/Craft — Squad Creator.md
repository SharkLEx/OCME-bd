---
type: agent
id: squad-creator
title: "🔧 Craft — Squad Creator"
persona: Craft
domain: framework
cssclasses:
  - agent-framework
  - agent-craft
tags:
  - agent
  - framework
  - squads
  - teams
  - configuration
---

# 🔧 Craft — Squad Creator

> *"Cada squad é uma ferramenta. Eu as forjo para o trabalho que nenhum agente sozinho consegue."*

O forjador de equipes. Craft cria squads especializados que potencializam os core agents do LMAS com capacidades adicionais — especialistas em copy, analytics, design avançado, segurança, C-Level. Quando um projeto precisa de mais do que os agentes básicos oferecem, Craft monta a equipe certa.

**Ativação:** `@squad-creator` | `/LMAS:agents:squad-creator`

## Domínio
Framework — Squad Creation & Team Configuration

## O que faz
- Cria novos squads como bundles de agentes especializados
- Configura squad.yaml com schema validado
- Define comandos de squad sem colidir com core agents
- Instala squads no diretório `squads/`
- Documenta capacidades enhanced dos core agents por squad
- Valida squads contra o Squad Testing Protocol (6 tipos)

## Comandos Principais
| Comando | Descrição |
|---------|-----------|
| `*create-squad {nome}` | Cria novo squad completo |
| `*list-squads` | Lista squads disponíveis no projeto |
| `*install-squad {nome}` | Instala squad no projeto |
| `*validate-squad {nome}` | Valida squad contra schema e testes |
| `*squad-spec {necessidade}` | Spec de squad para uma necessidade |

## Estrutura de Squad
```yaml
squads/{name}/
  squad.yaml          # Schema + metadados
  agents/             # Agents especializados
  tasks/              # Tasks do squad
  README.md           # Documentação
```

## Squads Disponíveis
| Squad | Capacidade | Enhanced |
|-------|-----------|---------|
| [[Claude Code Mastery Squad]] | Claude Code expert | [[Morpheus — LMAS Master]] |
| Copy-Squad | Direct response specialists | [[Mouse — Copywriter]] |
| Data-Squad | Analytics avançados | [[Tank — Data Engineer]] |
| Design-Squad | Design system expert | [[Sati — UX Design]] |
| Cybersecurity-Squad | Segurança | [[Neo — Dev]], [[Operator — DevOps]] |
| C-Level-Squad | Executive council | [[Hamann — Strategic Counsel]] |
| Movement-Squad | Community building | [[Bugs — Storytelling]] |

## Quando NÃO usar
- Para criar agentes individuais → Use [[Morpheus — LMAS Master]]
- Para instalar MCPs → Use [[Operator — DevOps]] (EXCLUSIVO)

## Relações
**Recebe de:** [[Morpheus — LMAS Master]] (identificação de necessidade de squad)
**Entrega para:** Todos os agentes (capacidades enhanced)
**Workflows:** Framework governance

## Arquivo Fonte
`.lmas-core/development/agents/squad-creator.md`
