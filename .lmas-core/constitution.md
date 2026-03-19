# LMAS Constitution — Base

> **Version:** 2.0.0 | **Ratified:** 2025-01-30 | **Last Amended:** 2026-03-14

Este documento define os princípios **universais** do LMAS que se aplicam a **TODOS** os domínios, times e squads. Princípios específicos de cada domínio (software, marketing, finance, etc.) são definidos em **Domain Extensions** separadas.

---

## Core Principles (Universal)

### I. CLI First (NON-NEGOTIABLE)

O CLI é a fonte da verdade onde toda inteligência, execução, e automação vivem.

**Regras:**
- MUST: Toda funcionalidade nova DEVE funcionar 100% via CLI antes de qualquer UI
- MUST: Dashboards apenas observam, NUNCA controlam ou tomam decisões
- MUST: A UI NUNCA é requisito para operação do sistema
- MUST: Ao decidir onde implementar, sempre CLI > Observability > UI

**Hierarquia:**
```
CLI (Máxima) → Observability (Secundária) → UI (Terciária)
```

**Gate:** WARN se UI criada antes de CLI funcional

---

### II. Agent Authority (NON-NEGOTIABLE)

Cada agente tem autoridades exclusivas que não podem ser violadas. As autoridades específicas são definidas pela **authority_matrix** do domínio ativo.

**Regras:**
- MUST: Cada agente opera dentro dos limites de sua autoridade exclusiva
- MUST: Agentes DEVEM delegar para o agente apropriado quando fora de seu escopo
- MUST: Nenhum agente pode assumir autoridade de outro
- MUST: A authority matrix do domínio ativo define quem pode fazer o quê

**Resolução de autoridade:**
```
Domain Extension (authority_matrix) → Define exclusividades por domínio
```

**Gate:** Implementado via definição de agentes + domain authority matrix

---

### III. Deliverable-Driven Work (MUST)

Todo trabalho começa e termina com um **deliverable rastreável**. O formato e tipo do deliverable é definido pelo domínio ativo (story, brief, requisition, etc.).

**Regras:**
- MUST: Nenhum trabalho é executado sem um deliverable associado
- MUST: Deliverables DEVEM ter critérios de aceitação claros antes de execução
- MUST: Progresso DEVE ser rastreado via checkboxes no deliverable
- MUST: Deliverables seguem o workflow definido pelo domínio ativo
- SHOULD: Deliverables seguem o fluxo: criador → executor → reviewer → publisher

**Formato do deliverable:**
```
Definido em: domains/{domain-id}/constitution.yaml → deliverable_format
```

**Gate:** BLOCK se não houver deliverable válido associado ao trabalho

---

### IV. Quality Gates (MUST)

Todo deliverable passa por quality gates antes de entrega. Os gates específicos são definidos pelo domínio ativo.

**Regras:**
- MUST: Todo deliverable passa pelos quality gates do domínio antes de ser considerado "done"
- MUST: Gates com severidade BLOCK impedem entrega até correção
- MUST: Gates com severidade WARN são registrados mas não impedem entrega
- MUST: Deliverable status deve refletir a aprovação dos gates

**Severity Levels (universais):**

| Severidade | Comportamento | Uso |
|------------|---------------|-----|
| BLOCK | Impede execução, requer correção | NON-NEGOTIABLE, MUST críticos |
| WARN | Permite continuar com alerta | MUST não-críticos |
| INFO | Apenas reporta | SHOULD |

**Definição dos gates:**
```
Definido em: domains/{domain-id}/constitution.yaml → quality_gates
Referência: domains/_base/gate-severity.yaml
```

---

## Domain Extensions

A partir da v2.0.0, a Constitution segue um modelo **Base + Extensions**:

```
constitution.md (este arquivo)     → Princípios universais (4 artigos)
  └── domains/{domain-id}/
      └── constitution.yaml        → Artigos, authority matrix, gates do domínio
```

### Domínios Registrados

| Domain ID | Nome | Artigos | Default |
|-----------|------|---------|---------|
| `software-dev` | Software Development | SD-I, SD-II, SD-III | ✅ Sim |
| `marketing` | Marketing Digital | MK-I, MK-II, MK-III, MK-IV | Não |

### Resolução de Domínio

O domínio ativo é resolvido na seguinte ordem de prioridade:

1. Campo `domain` no squad `config.yaml`
2. Campo `domain` no team bundle ativo
3. Campo `domain.active` no `project-config.yaml`
4. Fallback: `software-dev` (default)

### Registrar Novo Domínio

Ver `domains/README.md` para instruções de como criar um novo domínio.

### Migração v1.0.0 → v2.0.0

| Constitution v1.0.0 | Constitution v2.0.0 |
|---------------------|---------------------|
| Art. I: CLI First | Art. I: CLI First (inalterado) |
| Art. II: Agent Authority | Art. II: Agent Authority (genérico, matrix no domain) |
| Art. III: Story-Driven Development | Art. III: Deliverable-Driven Work (genérico) |
| Art. IV: No Invention | → `domains/software-dev/` Art. SD-I |
| Art. V: Quality First | Art. IV: Quality Gates (genérico, checks no domain) |
| Art. VI: Absolute Imports | → `domains/software-dev/` Art. SD-II |

---

## Governance

### Amendment Process

1. Proposta de mudança documentada com justificativa
2. Review por stakeholders relevantes do domínio
3. Aprovação requer consenso
4. Mudança implementada com atualização de versão
5. Propagação para domain extensions, templates e tasks dependentes

### Versioning

- **MAJOR:** Remoção ou redefinição incompatível de princípio universal
- **MINOR:** Novo princípio universal, novo domínio registrado, ou expansão significativa
- **PATCH:** Clarificações, correções de texto, refinamentos

### Compliance

- Todos os deliverables DEVEM verificar compliance com Constitution base + domain extension
- Gates automáticos BLOQUEIAM violações de princípios NON-NEGOTIABLE
- Gates automáticos ALERTAM violações de princípios MUST
- Violações de SHOULD são reportadas mas não bloqueiam

---

## References

- **Domain extensions:** `.lmas-core/domains/`
- **Domain registry:** `.lmas-core/data/domain-registry.yaml`
- **Gate severity definitions:** `.lmas-core/domains/_base/gate-severity.yaml`
- **Domain schema:** `.lmas-core/schemas/domain-constitution.schema.json`
- **Gates implementados em:** `.lmas-core/development/tasks/`

---

*LMAS Constitution v2.0.0*
*Universal Base | Domain Extensions | CLI First*
