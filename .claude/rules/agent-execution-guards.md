# Agent Execution Guards — Systemic Quality Rules

## Purpose

Three cross-agent rules that prevent silent quality degradation. These rules apply to ALL agents, ALL domains, ALL commands.

---

## Rule 1: Context-Load (Pre-Read Obrigatório)

**MUST — All Agents**

Antes de executar qualquer task principal, o agente DEVE carregar contexto do projeto:

### O que ler (em ordem de prioridade):

1. **PRD** — `docs/prd*.md` (se existir) → entender o produto, público, proposta de valor
2. **Stories concluídas** — `docs/stories/` com status Done/Ready for Review → entender o que já foi construído
3. **Architecture docs** — `docs/architecture*.md` (se existir) → entender stack e decisões técnicas
4. **Design System** — `docs/DESIGN-SYSTEM.md` ou `MASTER.md` (se existir) → tokens, componentes, brand

### Quando aplicar:

| Situação | Context-Load obrigatório? |
|----------|--------------------------|
| Primeira task do agente na sessão | SIM — ler PRD + stories relevantes |
| Tasks subsequentes na mesma sessão | NÃO — contexto já carregado |
| Mudança de domínio (dev → marketing) | SIM — recarregar com foco no novo domínio |
| Produto existente + task de design/marketing | SIM — ler código/app existente também |

### Como aplicar:

O agente NÃO precisa ler todos os arquivos. Deve:
1. Verificar se `docs/` existe e o que contém
2. Ler o PRD (se existir) — scanning rápido de features e público
3. Listar stories concluídas — entender o que foi implementado
4. Se a task envolve UI/design/marketing → verificar o que o produto já tem (rotas, telas, componentes)

### Output esperado:

Antes de iniciar a task, o agente declara em 2-3 linhas:
```
📋 Contexto carregado: [produto X] com [N features implementadas], público [Y], stack [Z].
```

Se não encontrar docs de contexto:
```
📋 Nenhum contexto de projeto encontrado. Prosseguindo com informações fornecidas.
```

---

## Rule 2: Pipeline-Suggest (Sugestão de Próximo Step)

**MUST — All Agents**

Após completar qualquer command que aparece como step em `workflow-chains.yaml`, o agente DEVE sugerir o próximo step do pipeline.

### Como funciona:

1. Agente completa command (ex: Sati completa `*landing`)
2. Agente consulta `workflow-chains.yaml` para verificar se o command faz parte de algum chain
3. Se sim → identifica o próximo step no chain
4. Sugere ao usuário (NÃO auto-executa)

### Formato da sugestão:

```
✅ [task concluída]

💡 Próximo step no pipeline [{pipeline-name}]:
   → @{agent} {command} — {descrição do output}
   Prosseguir? (sim / pular / ver pipeline completo)
```

### Regras:

- **NUNCA auto-executar** o próximo step — sempre perguntar
- **Tier-check ANTES de sugerir** — verificar se o próximo agente está disponível no tier atual:
  - Se **disponível** → sugerir normalmente
  - Se **premium indisponível** → NÃO mencionar o agente premium. Sugerir direto o workaround free (conforme graceful-degradation.md). Ex: em vez de "→ @copywriter *write-copy", sugerir "→ Você pode escrever o copy usando as guidelines acima, ou Morpheus pode ajudar"
  - Se **step marcado optional: true** no workflow E agente indisponível → pular silenciosamente para o próximo step disponível
- Se o usuário disser "pular" → perguntar se quer ver o step seguinte
- Se o usuário disser "ver pipeline" → mostrar todos os steps restantes (marcando indisponíveis com ⚠️)
- Se o command NÃO aparece em nenhum workflow → não sugerir nada (comportamento normal)
- Se o workflow tem **conditional steps** (ex: Spec Pipeline pula steps para SIMPLE class) → respeitar as condições, não sugerir steps que seriam pulados

### Exceção:

Commands utilitários (`*help`, `*status`, `*guide`, `*kb`) NUNCA acionam pipeline-suggest.

---

## Rule 3: Scope Guard (Proteção de Escopo)

**MUST — All Agents**

Quando um agente está prestes a produzir output que pertence ao escopo exclusivo de outro agente, ele DEVE parar e sugerir delegação.

### Mapa de escopo (o que cada agente PRODUZ exclusivamente):

| Output | Dono exclusivo | Outros agentes DEVEM delegar |
|--------|---------------|------------------------------|
| Copy de marketing (headlines, CTAs, body text persuasivo, landing page copy) | @copywriter | @sati, @dev, @pm, qualquer outro |
| Keywords, SEO audit, schema markup | @seo | @copywriter, @content-strategist |
| Database schemas, migrations, RLS | @data-engineer | @dev, @architect |
| Git push, PRs, releases | @devops | TODOS |
| Content strategy, editorial calendar | @content-strategist | @copywriter, @seo |
| Architecture decisions, ADRs | @architect | @dev, @pm |
| Story creation | @sm | @pm, @dev |
| Story validation | @po | @sm, @dev |

### Como funciona:

1. Agente está executando task e percebe que precisa produzir output de outro escopo
2. Agente PARA e informa:
   ```
   ⚠️ Isso é escopo do @{agent} ({persona}). Quer que eu acione?
   ```
3. Se usuário aceita → handoff com contexto
4. Se usuário recusa → agente pode produzir output básico com disclaimer:
   ```
   ⚠️ Copy gerado como placeholder — recomendo revisão pelo @copywriter para versão final.
   ```

### Quando NÃO aplicar:

- Agente premium indisponível no free tier → produzir output com disclaimer
- Morpheus executando diretamente (`*task`, `*exec`) → Morpheus pode executar qualquer recurso
- Output é trivial (ex: label de botão "Salvar") → não delegar por um botão
- Urgência explícita do usuário ("faz tudo agora, sem delegação")
- Agent Authority já cobre a operação (ex: git push já bloqueado → scope guard não precisa duplicar)

### Critério de "output não-trivial":

Se o output envolve mais de 3 linhas de texto persuasivo, estratégia de conteúdo, decisão técnica de dados, ou qualquer item listado na tabela acima → scope guard ativa.

### Distinção: Copy de Marketing vs UI Microcopy

| Tipo | Exemplos | Scope Guard? |
|------|----------|-------------|
| **Copy de marketing** | Headlines de landing page, CTAs persuasivos, body text de conversão, email copy, ad copy | SIM → @copywriter |
| **UI microcopy** | Labels de botão ("Salvar", "Cancelar"), error messages técnicas, tooltips, placeholders de input, breadcrumbs | NÃO → agente atual pode escrever |
| **Zona cinza** | Onboarding text, empty states, notification messages (> 2 linhas persuasivas) | SIM se persuasivo, NÃO se funcional |

**Regra prática:** Se o texto existe para **convencer** o usuário a agir → @copywriter. Se existe para **informar** o usuário sobre estado/ação → agente atual.

---

## Interação entre as 3 regras

```
Sessão inicia
  → Rule 1: Context-Load (ler projeto)

Agente executa command
  → Rule 3: Scope Guard (verificar se output é do meu escopo)
  → Se não → sugerir delegação

Agente completa command
  → Rule 2: Pipeline-Suggest (verificar workflow-chains.yaml)
  → Se encontrou → sugerir próximo step
```

---

## Resolução de Conflitos com Regras Existentes

### Context-Load vs Checkpoint Protocol
- **Checkpoint** atualiza docs APÓS ação (escrita)
- **Context-Load** lê docs ANTES de task (leitura)
- **Resolução:** Sem conflito real. Context-Load roda uma vez por sessão (primeira task). Checkpoint atualiza inline após cada ação. Se o mesmo agente continua na sessão, não relê.

### Scope Guard vs Agent Authority
- **Agent Authority** bloqueia OPERAÇÕES (git push, PR, releases)
- **Scope Guard** bloqueia OUTPUTS (copy, schemas, ADRs)
- **Resolução:** Complementares. Scope Guard NÃO se aplica onde Agent Authority já cobre. Não há cascata dupla — se Authority já bloqueia, Scope Guard não ativa.

### Pipeline-Suggest vs Graceful Degradation
- **Pipeline-Suggest** sugere próximo step
- **Graceful Degradation** pula steps premium silenciosamente
- **Resolução:** Pipeline-Suggest faz tier-check ANTES de sugerir. Se premium indisponível, sugere workaround free diretamente. Nunca menciona agente premium indisponível.

---

## Obrigatoriedade

Estas regras são **MUST** para todos os agentes, incluindo Morpheus. A única exceção é quando o usuário **explicitamente** pede para ignorar (ex: "faz tudo sem delegar").
