<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Simple, deterministic tasks

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** Learning, complex decisions

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Ambiguous requirements, critical work

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: partyModeBrainstorm()
responsável: Morpheus (Orchestrator)
responsavel_type: Agente
atomic_layer: Strategy

**Entrada:**
- campo: topic
  tipo: string
  origem: User Input
  obrigatório: true
  validação: Non-empty string, minimum 20 characters

- campo: agents
  tipo: string | array
  origem: User Input
  obrigatório: false
  validação: Agent IDs (e.g., "@architect @analyst") or team name (e.g., "team-fullstack"). Default uses team-fullstack excluding dev, devops, qa

- campo: rounds
  tipo: number
  origem: User Input
  obrigatório: false
  validação: Integer >= 1, default 3

- campo: strategy
  tipo: string
  origem: User Input
  obrigatório: false
  validação: "sequential" | "conversational", default "conversational"

**Saída:**
- campo: brainstorm_report
  tipo: file
  destino: docs/party-sessions/party-{date}-{topic-slug}.md
  persistido: true

- campo: conclusions
  tipo: string
  destino: Console Output (injected back to original agent context)
  persistido: false
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Topic provided with minimum 20 characters
    tipo: pre-condition
    blocker: true
    validação: |
      Check topic is non-empty and has at least 20 characters
    error_message: "Pre-condition failed: Topic too short — provide a meaningful topic for discussion (min 20 chars)"

  - [ ] Agent persona files accessible for requested agents
    tipo: pre-condition
    blocker: false
    validação: |
      Check that persona files exist in .lmas-core/development/agents/ for each requested agent
    error_message: "Warning: Some agent persona files not found — will use default personas"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] All requested rounds completed or user interrupted
    tipo: post-condition
    blocker: false
    validação: |
      Verify brainstorming session completed (all rounds or user-initiated end)
    error_message: "Warning: Session ended before all rounds completed"

  - [ ] Conclusions synthesized and presented to user
    tipo: post-condition
    blocker: true
    validação: |
      Verify conclusions were generated with top ideas and next steps
    error_message: "Post-condition failed: No conclusions generated"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Multiple agent personas participated with distinct voices; conclusions synthesized; original flow context preserved for resumption
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert agents spoke in character, conclusions exist, and return-to-flow handoff is clear
    error_message: "Acceptance criterion not met: Party Mode did not produce actionable conclusions"
```

---

## Error Handling

**Strategy:** graceful-degradation

**Common Errors:**

1. **Error:** Agent Persona Not Found
   - **Cause:** Requested agent ID doesn't match any agent file
   - **Resolution:** Use known agent attributes (name, icon, role) as fallback
   - **Recovery:** Continue with available personas, warn user about missing ones

2. **Error:** Topic Too Vague
   - **Cause:** Topic doesn't provide enough context for meaningful discussion
   - **Resolution:** Ask user to elaborate or provide more context
   - **Recovery:** Suggest topic refinements based on current flow context

3. **Error:** No Current Flow Context
   - **Cause:** Party Mode activated without an active workflow or agent session
   - **Resolution:** Proceed as standalone brainstorm (no flow to resume)
   - **Recovery:** Skip context preservation, run as independent session

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 5-20 min (estimated, depends on rounds and user interaction)
cost_estimated: $0.010-0.030
token_usage: ~10,000-30,000 tokens
```

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - N/A
tags:
  - brainstorming
  - multi-agent
  - collaboration
  - party-mode
  - consultive
updated_at: 2026-03-13
```

---

 Powered by LMAS™ Core -->

---
tools: []
docOutputLocation: docs/party-sessions/
execution_mode: interactive
---

# party-mode-brainstorm

Multi-agent brainstorming discussion — agents collaborate and debate ideas with you, then conclusions feed back into your active flow.

## Purpose

Party Mode is a **flow-interruptible sidebar discussion** where the user pauses the current workflow, brings in multiple agent personas to discuss what's happening, and then resumes the original flow with the brainstorm conclusions injected into context. Morpheus (lmas-master) role-plays all personas — no subagent spawning, no Synapse L2 modification, no session.active_agent changes.

## Core Principles

1. **Consultive ONLY** — No agent executes actions (no git, no file writes, no PRs, no code changes)
2. **No Authority Violation** — Agents opine but don't decide outside their scope (Constitution Article II)
3. **Personalities Maintained** — Each agent uses their `communication.tone` and `vocabulary` from persona files
4. **User Controls Everything** — Can end, expand, redirect, add/remove agents at any time
5. **Flow-Aware** — Captures current context before entering, injects conclusions on exit
6. **Non-Structural** — Does NOT modify Synapse, handoff protocol, or agent authority

## Prerequisites

- Topic must be provided (minimum 20 characters)
- Agent persona files should exist in `.lmas-core/development/agents/` for requested agents
- If activated mid-flow, the current agent context will be preserved for resumption

## Agent Selection

The user chooses which agents participate. Options:

```
*party-mode "topic"                                    → default team (analyst, architect, pm, po, ux)
*party-mode "topic" --agents "@architect @data-engineer @qa"  → specific agents
*party-mode "topic" --team "team-backend"              → use squad definition
```

**Default team** (when no `--agents` or `--team` specified):
- @analyst (Sage) — Research & data perspective
- @architect (Aria) — Technical architecture perspective
- @pm (Morgan) — Project management & requirements perspective
- @po (Pax) — Product & business value perspective
- @ux-design-expert (Aurora) — User experience perspective

**Excluded from default** (but can be added explicitly):
- @dev, @devops, @qa — Execution agents, not typically strategic brainstormers
- @sm — Story mechanics, not ideation
- @data-engineer — Specialized, add when topic is DB-related

## Execution Flow

### Step 1: Capture Current Context

Before entering Party Mode, capture the active flow state:

```yaml
party_context:
  previous_agent: "{session.active_agent or null}"
  previous_command: "{last command executed or null}"
  current_story: "{active story ID or null}"
  flow_state: "{what was happening when party mode was activated}"
  topic: "{user-provided topic}"
```

If no active flow exists, set `previous_agent: null` and proceed as standalone brainstorm.

### Step 2: Setup

1. Parse the requested agents (from `--agents`, `--team`, or default)
2. For each agent, load from `.lmas-core/development/agents/{agent-id}.md`:
   - `agent.name` — Display name
   - `agent.icon` — Emoji icon
   - `agent.title` — Role title
   - `persona.role` — Role description
   - `persona.core_principles` — Decision-making basis
   - `persona_profile.communication.tone` — Communication style
   - `persona_profile.communication.vocabulary` — Preferred terms

3. Present to user:

```
🎉 **Party Mode Ativado**

**Tópico:** {topic}
**Agentes:** {icon} {name} ({title}), {icon} {name} ({title}), ...
**Rounds:** {rounds}
**Estratégia:** {strategy}

{If mid-flow: "📌 Contexto pausado: {previous_agent} executando {previous_command}"}

Quer ajustar a equipe ou iniciar?
```

4. Wait for user confirmation or adjustments.

### Step 3: Rounds de Ideação

For each round (1 to N):

**3a. Each agent generates 2-3 ideas** (role-playing the persona using their tone and vocabulary):

```
{icon} **{name}** ({title}):
- {idea_1_using_agent_vocabulary_and_tone}
- {idea_2_aligned_with_core_principles}
- {idea_3_optional}
```

**3b. After all agents speak**, present round summary and ask:

```
📊 **Round {n} completo** — {total_ideas} ideias geradas

1. Alguma ideia que quer expandir?
2. Quer que algum agente reaja a uma ideia específica?
3. Próximo round
4. Encerrar e sintetizar
```

**3c. User can:**
- Expand an idea → selected agent(s) elaborate in-character
- Direct reaction → "O que o @architect acha da ideia do @analyst?" → targeted response
- Next round → continue to round N+1
- End → jump to Step 5

### Step 4: Reações Cruzadas (if strategy = "conversational")

Between rounds or when directed by user:

- Agents react to each other's ideas **maintaining their personalities**
- Disagreements are encouraged (different perspectives = more value)
- Each agent responds using their `core_principles` as decision basis
- Format:

```
{icon} **{name}** reagindo a {other_name}:
{in-character response using agent's tone and vocabulary}
```

### Step 5: Síntese e Conclusões

When user ends the session (or all rounds complete):

**5a. Categorize all ideas by theme**

**5b. Generate conclusions:**

```markdown
## 🎉 Party Mode — Conclusões

### Tópico: {topic}
### Agentes: {list with icons}
### Rounds: {completed}/{total}

### Top 10 Ideias
1. {idea} — proposta por {icon} {name}
2. {idea} — proposta por {icon} {name}
...

### Consensos
- {points where agents agreed}

### Divergências
- {points where agents disagreed, with each position}

### Próximos Passos Acionáveis
- [ ] {action_1} — sugerido por {agent}
- [ ] {action_2} — sugerido por {agent}
...
```

**5c. Save report** to `docs/party-sessions/party-{date}-{topic-slug}.md`

### Step 6: Return to Flow

If Party Mode was activated mid-flow:

1. Present the conclusions summary
2. Show return message:

```
📌 **Retornando ao fluxo anterior**
Agente: {previous_agent.icon} {previous_agent.name}
Comando: {previous_command}
Story: {current_story}

As conclusões do brainstorm foram registradas. O agente {previous_agent.name} tem acesso ao contexto discutido.

Para continuar o fluxo, reative o agente com @{previous_agent.id}
```

3. The conclusions from Step 5 serve as context for the next agent activation — they are NOT automatically injected (the user reactivates the agent, and the conclusions are available in the conversation history)

If standalone (no previous flow):
- Just present conclusions and end

## Slug Rules

For the output file name:
- Convert topic to lowercase
- Replace spaces with hyphens
- Strip punctuation
- Truncate to 50 chars
- Example: "Como melhorar o onboarding do LMAS?" → `como-melhorar-o-onboarding-do-lmas`

## Handoff
next_agent: "{previous_agent or null}"
next_command: "{previous_command or null}"
condition: Party Mode session concluded — user returns to previous flow
alternatives:
  - agent: @lmas-master, command: *help, condition: No previous flow to return to
