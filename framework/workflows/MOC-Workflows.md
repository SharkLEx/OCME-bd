---
type: moc
title: "MOC — Workflows LMAS"
cssclasses:
  - moc-note
tags:
  - moc
  - workflows
  - lmas
---

# 🔄 Workflows LMAS

> Map of Content — todos os workflows do framework por domínio.

---

## 💻 Software Development

| Workflow | Agentes | Quando Usar |
|----------|---------|-------------|
| [[SDC — Story Development Cycle]] | SM → PO → Dev → QA → DevOps | Todo desenvolvimento — workflow primário |
| [[QA-Loop]] | QA ↔ Dev | Quando QA gate falha e precisa iteração |
| [[Spec-Pipeline]] | PM → Architect → Analyst → PM → QA → Architect | Feature complexa que precisa spec antes do dev |
| [[Brownfield-Discovery]] | Architect + Tank + Sati → QA → Analyst → PM | Entrar em projeto existente e mapear débito técnico |

---

## 📣 Marketing

| Workflow | Agentes | Quando Usar |
|----------|---------|-------------|
| [[Content-Pipeline]] | Strategist → Researcher → Copy → SEO → Reviewer → Chief → Social | Conteúdo orgânico para canais owned |
| [[Campaign-Pipeline]] | Strategist → SEO → Copy → Reviewer → Chief → Mifune → Traffic | Campanha paga com budget |

---

## 🎨 Brand

| Workflow | Agentes | Quando Usar |
|----------|---------|-------------|
| [[Brand-Flow]] | Kamala → Kamala → Bugs → Sati | Criar marca do zero |

---

## 💼 Business

| Workflow | Agentes | Quando Usar |
|----------|---------|-------------|
| [[Business-Flow]] | Hamann → Mifune → Mifune → Traffic | Estratégia de negócio completa |
| [[Offer-to-Market]] | Mifune → Kamala → Bugs → Copy → Sati → Reviewer → Traffic | Lançar oferta completa ao mercado |

---

## Guia de Seleção

| Situação | Workflow |
|----------|---------|
| Nova story de epic existente | [[SDC — Story Development Cycle]] |
| QA encontrou problemas, precisa iteração | [[QA-Loop]] |
| Feature complexa precisa de spec | [[Spec-Pipeline]] → depois [[SDC — Story Development Cycle]] |
| Entrar em projeto existente | [[Brownfield-Discovery]] |
| Bug fix simples | [[SDC — Story Development Cycle]] (modo YOLO) |
| Conteúdo orgânico | [[Content-Pipeline]] |
| Campanha paga | [[Campaign-Pipeline]] |
| Nova marca | [[Brand-Flow]] |
| Nova oferta + campanha | [[Offer-to-Market]] |
| Estratégia de negócio | [[Business-Flow]] |

---

## 🔗 Links Relacionados

- [[MOC-Agentes]] — Todos os agentes
- [[MOC-Squads]] — Squads disponíveis
