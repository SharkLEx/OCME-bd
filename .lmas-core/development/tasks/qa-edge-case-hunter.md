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
task: qaEdgeCaseHunter()
responsável: Oracle (Guardian)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: content
  tipo: string | file
  origem: User Input
  obrigatório: true
  validação: Non-empty code content (diff, file, or function)

- campo: also_consider
  tipo: string
  origem: User Input
  obrigatório: false
  validação: Optional additional edge case domains to consider

**Saída:**
- campo: unhandled_paths
  tipo: array (JSON)
  destino: Console Output
  persistido: false
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Code content provided (file path, diff, or inline code)
    tipo: pre-condition
    blocker: true
    validação: |
      Check code content is non-empty and parseable
    error_message: "Pre-condition failed: No code content provided for analysis"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Analysis completed; output is valid JSON array
    tipo: post-condition
    blocker: true
    validação: |
      Verify output is a parseable JSON array (empty array [] is valid)
    error_message: "Post-condition failed: Output is not valid JSON"

  - [ ] Each finding has all required fields (location, trigger_condition, guard_snippet, potential_consequence)
    tipo: post-condition
    blocker: true
    validação: |
      Verify every item in the array has all 4 required fields
    error_message: "Post-condition failed: Findings missing required fields"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Exhaustive path enumeration completed; unhandled paths reported as structured JSON; output parseable and actionable
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert all branching paths were analyzed and unhandled ones reported with guard snippets
    error_message: "Acceptance criterion not met: Path enumeration incomplete or output malformed"
```

---

## Error Handling

**Strategy:** abort

**Common Errors:**

1. **Error:** Empty Content
   - **Cause:** No code content provided
   - **Resolution:** Return `{"error": "empty_content"}` and stop
   - **Recovery:** Prompt user for valid code content

2. **Error:** Unparseable Code
   - **Cause:** Content is not code (e.g., plain text document)
   - **Resolution:** Return `{"error": "not_code", "detail": "Content does not appear to be source code"}`
   - **Recovery:** Suggest using `*adversarial-review` for non-code content

3. **Error:** Content Too Large
   - **Cause:** File exceeds reasonable analysis scope
   - **Resolution:** Ask user to scope to specific functions or sections
   - **Recovery:** Analyze first function/class, suggest continuation

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 3-8 min (estimated)
cost_estimated: $0.003-0.010
token_usage: ~3,000-10,000 tokens
```

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - N/A
tags:
  - qa
  - edge-cases
  - path-enumeration
  - quality
updated_at: 2026-03-13
```

---

 Powered by LMAS™ Core -->

---
tools:
  - github-cli
  - context7
execution_mode: programmatic
---

# qa-edge-case-hunter

Exhaustive path enumeration — mechanically walk every branch, report unhandled edge cases as JSON.

## Purpose

Enumerate ALL branching paths in code content and report ONLY the unhandled ones. This is a mechanical, exhaustive analysis — not intuition-based. The output is a structured JSON array of unhandled paths with guard snippets showing how to close each gap. An empty array `[]` is valid output (all paths handled).

## Prerequisites

- Code content must be provided (file path, git diff, inline code, or function reference)
- Content must be source code (not documentation or specs — use `*adversarial-review` for those)

## Method

**Exhaustive path enumeration.** Mechanically walk every branching point in the code. Do NOT hunt by intuition — derive edge classes FROM the code itself, then check each one systematically.

## Execution Flow

### Step 1: Receive Content

Load code content strictly from input:

- **File path:** Read the file
- **Git diff:** Parse the diff for changed code
- **Inline code:** Use as-is
- **Function reference:** Load the specific function

If content is empty, return `{"error": "empty_content"}` and **STOP**.
If content is not code, return `{"error": "not_code"}` and **STOP**.

### Step 2: Exhaustive Path Analysis

Walk EVERY branching point in the code. For each, determine if all paths are handled.

**Branching types to check:**

#### Control Flow Paths
- `if` without `else` — what happens on the false branch?
- `switch` without `default` — what happens for unlisted values?
- `try` without specific `catch` — what exceptions are swallowed?
- Early returns — what state is left for callers?
- Loop boundaries — what if zero iterations? What if max iterations?
- Async paths — what if promise rejects? What if it never resolves?

#### Domain Boundary Paths
- **Null/undefined:** Parameters that could be null but aren't checked
- **Empty collections:** Arrays/objects that could be empty
- **Numeric boundaries:** Zero, negative, MAX_SAFE_INTEGER, NaN, Infinity
- **String boundaries:** Empty string, whitespace-only, unicode, very long strings
- **Type coercion:** Implicit conversions that could produce unexpected results
- **Concurrent access:** Race conditions between async operations
- **Timeout/retry:** Operations without timeout or with infinite retry
- **Resource exhaustion:** Unbounded allocations, memory leaks, file handle leaks

#### Integration Paths
- **Network failures:** API calls without error handling
- **Partial failures:** Batch operations where some succeed and some fail
- **Stale data:** Cache invalidation, concurrent modifications
- **Schema mismatches:** External data that doesn't match expected shape

**CRITICAL RULE:** Collect ONLY paths WITHOUT handling. Silently discard paths that ARE handled.

### Step 3: Validate Completeness

After the initial pass, revisit EACH edge class from Step 2:

- Did you check ALL `if` statements for missing `else`?
- Did you check ALL `switch` statements for missing `default`?
- Did you check ALL function parameters for null/undefined?
- Did you check ALL async operations for rejection handling?
- Did you check ALL loops for boundary conditions?
- Did you check ALL external calls for failure handling?

Add any newly discovered unhandled paths.

### Step 4: Present Findings

Output as a JSON array. **No text before or after — pure JSON only.**

```json
[
  {
    "location": "file.ts:42-45",
    "trigger_condition": "userId is null when session expires mid-request",
    "guard_snippet": "if (!userId) throw new UnauthorizedError('Session expired')",
    "potential_consequence": "TypeError crash on null property access"
  },
  {
    "location": "api.ts:120",
    "trigger_condition": "fetch rejects due to network timeout",
    "guard_snippet": "try { await fetch(...) } catch (e) { return fallbackResponse() }",
    "potential_consequence": "Unhandled promise rejection crashes process"
  }
]
```

**Field constraints:**
- `location`: `file:start-end` or `file:line` format
- `trigger_condition`: Max 15 words, one line
- `guard_snippet`: Minimal code sketch that closes the gap (pseudocode OK)
- `potential_consequence`: Max 15 words, what goes wrong without the guard

**Empty array `[]` is valid output** — it means all paths are handled. This is different from Adversarial Review which requires minimum 10 findings.

### HALT Conditions

- **Empty content:** Return `{"error": "empty_content"}` and stop
- **Not code:** Return `{"error": "not_code"}` and stop

## Output Schema

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "required": ["location", "trigger_condition", "guard_snippet", "potential_consequence"],
    "properties": {
      "location": { "type": "string" },
      "trigger_condition": { "type": "string", "maxLength": 100 },
      "guard_snippet": { "type": "string" },
      "potential_consequence": { "type": "string", "maxLength": 100 }
    }
  }
}
```

## Handoff
next_agent: @dev
next_command: *apply-qa-fixes
condition: Unhandled paths found that need guards
alternatives:
  - agent: @qa, command: *adversarial-review, condition: User wants broader review beyond edge cases
  - agent: @architect, command: *analyze-impact, condition: Edge cases reveal architectural gaps
