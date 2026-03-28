---
type: moc
title: "MOC — Agentes LMAS"
cssclasses:
  - moc-note
tags:
  - moc
  - agents
  - lmas
---

# 🤖 Agentes LMAS

> Map of Content — todos os agentes do framework organizados por domínio.

---

## 🏛️ Framework / Universal

| Agente | Persona | Escopo |
|--------|---------|--------|
| [[Morpheus — LMAS Master\|Morpheus]] | LMAS Master | Entry point, roteamento, framework dev |
| [[Smith — Delivery Verifier\|Smith]] | Smith | Adversarial review de entregas (universal) |
| [[Craft — Squad Creator\|Craft]] | @squad-creator | Criação de novos squads |

---

## 💻 Software Development

| Agente | Persona | Escopo |
|--------|---------|--------|
| [[Neo — Dev\|Neo]] | @dev | Implementação de código |
| [[Oracle — QA\|Oracle]] | @qa | Testes e quality gates |
| [[Aria — Architect\|Aria]] | @architect | Arquitetura e decisões técnicas |
| [[Morgan — PM\|Trinity]] | @pm | Product Management, PRDs, epics |
| [[Keymaker — PO\|Keymaker]] | @po | Product Owner, validação de stories |
| [[Niobe — SM\|River]] | @sm | Scrum Master, criação de stories |
| [[Tank — Data Engineer\|Tank]] | @data-engineer | Database, schema, migrations, RLS |
| [[Sati — UX Design\|Sati]] | @ux-design-expert | UX/UI design, design system |
| [[Atlas — Analyst\|Atlas]] | @analyst | Pesquisa e análise (cross-domain) |
| [[Operator — DevOps\|Operator]] | @devops | CI/CD, git push (EXCLUSIVO) |

---

## 📣 Marketing

| Agente | Persona | Escopo |
|--------|---------|--------|
| [[Lock — Marketing Chief\|Lock]] | @marketing-chief | Brand guardian, aprovação de conteúdo |
| [[Mouse — Copywriter\|Mouse]] | @copywriter | Copy para todos os canais |
| [[Sparks — Social Media\|Sparks]] | @social-media-manager | Publicação de conteúdo (EXCLUSIVO) |
| [[Persephone — Content Strategist\|Persephone]] | @content-strategist | Estratégia editorial |
| [[Ghost — Content Researcher\|Ghost]] | @content-researcher | Pesquisa de mercado e audiência |
| [[Seraph — Content Reviewer\|Seraph]] | @content-reviewer | Quality gate de conteúdo |
| [[Cypher — SEO\|Cypher]] | @seo | SEO, keywords, E-E-A-T, GEO |

---

## 💼 Business

| Agente | Persona | Escopo |
|--------|---------|--------|
| [[Mifune — Business Strategy\|Mifune]] | @mifune | Ofertas, pricing, modelo de negócio |
| [[Hamann — Strategic Counsel\|Hamann]] | @hamann | Conselho estratégico, advisory board |
| [[Merovingian — Traffic Manager\|Merovingian]] | @traffic-manager | Tráfego pago, budget, ROAS (EXCLUSIVO) |

---

## 🎨 Brand

| Agente | Persona | Escopo |
|--------|---------|--------|
| [[Kamala — Brand Creation\|Kamala]] | @kamala | Posicionamento, naming, identidade |
| [[Bugs — Storytelling\|Bugs]] | @bugs | Narrativa, manifestos, movimentos |

---

## Hierarquia de Autoridade (Conflitos)

```
brand > marketing  (tom e identidade: Kamala decide)
business > marketing  (budget e ROI: Mifune decide)
software-dev > all  (viabilidade técnica: Aria decide)
conflito entre domínios → Morpheus medeia
```

---

## 🔗 Links Relacionados

- [[MOC-Squads]] — Squads instalados
- [[SDC — Story Development Cycle]] — Workflow principal de dev
- [[Content-Pipeline]] — Workflow de conteúdo
- [[Campaign-Pipeline]] — Workflow de campanha paga
- [[Brand-Flow]] — Workflow de criação de marca
- [[Business-Flow]] — Workflow de estratégia de negócio
