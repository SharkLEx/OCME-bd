---
type: moc
title: "MOC — Squads LMAS"
cssclasses:
  - moc-note
tags:
  - moc
  - squads
  - lmas
---

# 🧩 Squads LMAS

> Map of Content — squads disponíveis no framework.
> Squads são expansões que adicionam agentes e tasks especializados aos core agents.

---

## Squads Disponíveis

| Squad | Domínio | Especialidade | Core Agent Enhanced |
|-------|---------|---------------|-------------------|
| [[Claude Code Mastery Squad]] | Framework | Claude Code, hooks, MCPs, subagents | [[Morpheus — LMAS Master\|Morpheus]] |
| [[Copy-Squad]] | Marketing | Direct response: Brunson, Chaperon, Settle, Kennedy | [[Mouse — Copywriter\|Mouse]] |
| [[Data-Squad]] | Software Dev | Analytics, BI, ML, CDO strategy | [[Tank — Data Engineer\|Tank]] |
| [[Design-Squad]] | Software Dev | Design system enterprise, motion, a11y | [[Sati — UX Design\|Sati]] |
| [[Cybersecurity-Squad]] | Software Dev | Pentest, threat modeling, incident response | [[Neo — Dev\|Neo]] + [[Operator — DevOps\|Operator]] |
| [[C-Level-Squad]] | Business | CFO, CTO, CMO, COO executivo | [[Hamann — Strategic Counsel\|Hamann]] |
| [[Movement-Squad]] | Brand | Community, cult brand, evangelism | [[Bugs — Storytelling\|Bugs]] |

---

## Como Descobrir um Squad

Via [[Morpheus — LMAS Master]]:
```
*discover {keyword}
```
Keywords: `claude-code`, `copy`, `data`, `design`, `security`, `c-level`, `movement`

---

## Como Instalar um Squad

```bash
npx lmas-core add-squad {nome-do-squad}
```

## Como Criar um Squad

Use [[Craft — Squad Creator]]:
```
@squad-creator *create-squad {nome}
```

---

## Regras de Squads

1. Squad commands NÃO colidem com core agent commands
2. Core agents têm prioridade sobre squad agents
3. Squad agents acessíveis via `@{squad}:{agent} *{command}`
4. Fallback: se squad indisponível, core agent opera com capacidade básica

---

## 🔗 Links Relacionados

- [[MOC-Agentes]] — Todos os agentes LMAS
- [[Craft — Squad Creator]] — Cria novos squads
- [[Morpheus — LMAS Master]] — Entry point para tudo
