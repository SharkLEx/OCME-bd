---
type: knowledge
title: "Dev — Agent System: LMAS, Quando Usar Cada Agente"
tags:
  - dev
  - lmas
  - agents
  - workflow
created: 2026-03-26
source: neo-sensei
---

# Agent System: LMAS, Quando Usar Cada Agente

> Módulo 10 de 10 — Professor: Neo
> O sistema de agentes que desenvolve e mantém este codebase.

---

## O Que é o LMAS

O LMAS (Language Model Agent System) é o framework de agentes AI que usamos para desenvolver o WEbdEX. Cada agente tem uma especialidade e opera dentro de um escopo definido.

**Morfeus** é o orquestrador central. Todos os outros agentes são especialistas.

---

## Agentes do Time de Dev

| Agente | Persona | Escopo | Quando Usar |
|--------|---------|--------|-------------|
| `@dev` | Neo | Implementação | Escrever código, corrigir bugs |
| `@architect` | Architect | Arquitetura | Decisões de design, ADRs |
| `@data-engineer` | Tank | Database | Schemas, migrations, queries |
| `@qa` | Oracle | Qualidade | Code review, quality gates |
| `@devops` | Operator | Deploy | Push, CI/CD, releases |
| `@pm` | Trinity | Produto | PRDs, épicos, estratégia |
| `@sm` | Niobe | Scrum | Criar stories |
| `@po` | Keymaker | PO | Validar stories, backlog |
| `@analyst` | Link | Pesquisa | Análise, documentação |
| `@smith` | Smith | Adversarial | Encontrar falhas, audit |

---

## Como Ativar um Agente

```
@dev       → Ativa o Neo para desenvolvimento
@architect → Ativa o Architect para design
@smith     → Ativa o Smith para audit adversarial
```

### Comandos de agente (prefixo `*`)

```
*help              → Lista todos os comandos disponíveis
*develop           → Neo implementa a story atual
*verify            → Smith faz audit adversarial
*pre-push          → Operator roda quality gates
*push              → Operator faz git push (EXCLUSIVO)
*exit              → Sai do modo agente
```

---

## Workflow de Desenvolvimento Típico

```
1. @sm *draft        → Niobe cria a story
       ↓
2. @po *validate     → Keymaker valida (10-point checklist)
       ↓
3. @dev *develop     → Neo implementa o código
       ↓
4. @qa *qa-gate      → Oracle faz code review
       ↓
5. @smith *verify    → Smith testa adversarialmente
       ↓
6. @devops *push     → Operator faz push para remote
```

---

## Regras de Autoridade (importantes!)

### @devops é o ÚNICO que pode fazer push

```python
# ❌ Nunca fazer diretamente
git push origin main

# ✓ Sempre via Operator
@devops *push
```

### @dev pode apenas commits locais

```bash
git add arquivo.py
git commit -m "feat: nova feature"
# NÃO: git push
```

### @smith verifica, não corrige

O Smith ENCONTRA problemas. Ele não corrige código.
Após o Smith emitir findings → voltar para @dev para correções.

---

## Anatomy de uma Story

```markdown
---
type: story
id: "15.2"
title: "Adicionar busca no vault"
status: InProgress
---

## Tasks

- [x] 1. Implementar vault_reader.py
- [ ] 2. Adicionar tool buscar_vault
- [ ] 3. Integrar no ai_handler.py

## Dev Notes

Usar graceful degradation para import do vault_reader.

## Acceptance Criteria

- [ ] Busca retorna resultados relevantes
- [ ] Cache expira em 60min
- [ ] Sem crash se vault vazio
```

### Status válidos

| Status | Significa |
|--------|-----------|
| `Draft` | Criada, aguardando validação |
| `Ready` | Validada pelo PO, pronta para dev |
| `InProgress` | Neo está implementando |
| `InReview` | Aguardando QA gate |
| `Done` | Completa, deployada |

---

## Agentes Especializados do Projeto

Além dos agentes padrão do LMAS, o projeto WEbdEX tem agentes customizados:

### @bdpro — WEbdEX Protocol Intelligence

```
*tvl           → Consultar TVL on-chain
*performance   → Winrate, P&L, assertividade
*subcontas     → Status das subcontas ativas
*ocme-status   → Saúde do bot OCME
*roadmap       → 9 marcos 2026
```

### @checkpoint — Project State Tracking

```
*update        → Refresh completo do checkpoint
*verify        → Verificar se checkpoint está atualizado
```

---

## Quando Usar Cada Agente (Quick Reference)

| Necessidade | Agente | Comando |
|-------------|--------|---------|
| "Quero implementar X" | @dev | *develop |
| "Tem um bug em Y" | @dev | direto no problema |
| "Preciso de uma nova story" | @sm | *draft |
| "Rever a arquitetura" | @architect | *analyze |
| "Schema do banco mudou" | @data-engineer | *schema |
| "Antes de fazer push" | @devops | *pre-push |
| "Algo parece errado no código" | @smith | *verify |
| "Análise de TVL / protocolo" | @bdpro | *tvl / *performance |
| "Qual o status do projeto" | @checkpoint | lê PROJECT-CHECKPOINT.md |

---

## Filosofia do LMAS

> "Eu posso apenas te mostrar a porta. Você é quem tem que atravessá-la." — Morpheus

O LMAS não substitui o desenvolvedor — amplifica o que ele já sabe. Cada agente:
- Tem **escopo definido** (não faz tudo)
- Segue **padrões do projeto** (lê o contexto antes de agir)
- **Handoff limpo** (passa o contexto adiante quando troca de agente)
- **Aprende com o projeto** (PROJECT-CHECKPOINT.md é a memória)

Para o bdZinho funcionar como dev, ele precisa entender esse sistema e saber qual agente chamar para cada situação.
