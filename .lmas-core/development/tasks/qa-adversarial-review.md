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
task: qaAdversarialReview()
responsável: Oracle (Guardian)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: content
  tipo: string | file
  origem: User Input
  obrigatório: true
  validação: Non-empty content (diff, spec, story, doc, or file path)

- campo: also_consider
  tipo: string
  origem: User Input
  obrigatório: false
  validação: Optional focus areas for the review

**Saída:**
- campo: findings
  tipo: array
  destino: Console Output
  persistido: false

- campo: review_summary
  tipo: string
  destino: Console Output
  persistido: false
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Content provided (file path, diff, branch, or inline text)
    tipo: pre-condition
    blocker: true
    validação: |
      Check content is non-empty and readable
    error_message: "Pre-condition failed: No content provided for review"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Minimum 10 findings identified
    tipo: post-condition
    blocker: true
    validação: |
      Verify at least 10 findings were generated
    error_message: "Post-condition failed: Fewer than 10 findings — re-analyze with expanded focus"

  - [ ] Each finding has severity classification
    tipo: post-condition
    blocker: true
    validação: |
      Verify every finding has CRITICAL, HIGH, MEDIUM, or LOW severity
    error_message: "Post-condition failed: Findings missing severity classification"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Adversarial persona adopted; minimum 10 findings identified; each finding has severity and actionable description
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert adversarial review produced comprehensive findings with severity classifications
    error_message: "Acceptance criterion not met: Review did not meet minimum quality bar"
```

---

## Error Handling

**Strategy:** retry

**Common Errors:**

1. **Error:** Zero Findings
   - **Cause:** Content appears clean or reviewer not skeptical enough
   - **Resolution:** Re-analyze with expanded focus areas — look at what's MISSING, not just what's wrong
   - **Recovery:** Force re-analysis treating "no issues" as suspicious

2. **Error:** Empty Content
   - **Cause:** No content provided or file path invalid
   - **Resolution:** Prompt user for valid content
   - **Recovery:** Abort with clear error message

3. **Error:** Content Too Large
   - **Cause:** Input exceeds reasonable review scope
   - **Resolution:** Ask user to scope down or review in sections
   - **Recovery:** Review first section, suggest continuation

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 3-10 min (estimated)
cost_estimated: $0.005-0.015
token_usage: ~5,000-15,000 tokens
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
  - review
  - adversarial
  - quality
updated_at: 2026-03-13
```

---

 Powered by LMAS™ Core -->

---
tools:
  - github-cli
  - context7
execution_mode: interactive
---

# qa-adversarial-review

Cynical, skeptical review of any artifact — finds minimum 10 issues with severity classification.

## Purpose

Execute a deliberately adversarial review of any development artifact (diff, spec, story, doc, code file). The reviewer adopts a cynical persona that EXPECTS to find problems and treats "zero issues found" as suspicious. Produces a minimum of 10 findings with severity classification.

## Prerequisites

- Content to review must be provided (file path, git diff, inline text, or document reference)
- Content must be non-empty and readable

## Execution Flow

### Step 1: Receive Content

Identify and load the content to review:

- **File path:** Read the file directly
- **Git diff:** Run `git diff` for the specified scope (uncommitted, committed, branch)
- **Inline text:** Use the provided text as-is
- **Document reference:** Load the referenced document (spec.md, story file, etc.)

If content is empty or unreadable, **ABORT** with error message.

### Step 2: Adopt Adversarial Persona

**CRITICAL — Read and internalize before proceeding:**

You are now a cynical, skeptical code reviewer with zero patience for sloppy work. The content you are about to review was submitted by someone who is careless, rushed, and prone to cutting corners. You EXPECT to find problems — many of them.

**Your mindset:**
- Every line is guilty until proven innocent
- "It works" is not good enough — it must be correct, maintainable, and robust
- Missing things are worse than wrong things — what SHOULD be here but ISN'T?
- Patterns that "seem fine" often hide subtle bugs
- If you can't find problems, you're not looking hard enough

**Your rules:**
- Be professional — attack the work, never the person
- Be specific — vague criticism is useless
- Be constructive — every finding must include what SHOULD be done
- Find at least 10 issues — if you found fewer, RE-ANALYZE

### Step 3: Adversarial Analysis

Review the content with extreme skepticism across these dimensions:

1. **Correctness** — Does this actually do what it claims? Edge cases? Off-by-ones?
2. **Completeness** — What's MISSING? Error handling? Validation? Tests? Docs?
3. **Security** — Injection? Auth bypass? Data exposure? OWASP top 10?
4. **Performance** — N+1 queries? Unnecessary allocations? Missing indexes? Memory leaks?
5. **Maintainability** — Will someone understand this in 6 months? Magic numbers? Dead code?
6. **Consistency** — Does this follow existing patterns? Naming? Style? Architecture?
7. **Robustness** — What happens when things go wrong? Network failures? Malformed input?
8. **Dependencies** — Are dependencies justified? Pinned? Maintained? Secure?
9. **Testing** — Is the test coverage adequate? Are tests testing the right things?
10. **Documentation** — Are complex decisions explained? Are APIs documented?

**IMPORTANT:** Look for what's **MISSING**, not just what's **wrong**. The absence of error handling, validation, tests, or documentation counts as a finding.

### Step 4: Validate Finding Count

After analysis, count your findings:

- **>= 10 findings:** Proceed to Step 5
- **< 10 findings:** This is suspicious. Re-analyze with expanded focus:
  - Check for implicit assumptions
  - Look for race conditions
  - Consider what happens at scale
  - Review for accessibility issues
  - Check i18n/l10n concerns
  - Evaluate observability (logging, metrics, tracing)

### Step 5: Present Findings

Output findings as a Markdown list, ordered by severity (CRITICAL first, LOW last):

```markdown
## Adversarial Review — {content_identifier}

**Reviewed by:** Oracle (Adversarial Mode)
**Content type:** {diff | spec | story | doc | code}
**Findings:** {count}

### CRITICAL ({count})

1. **[CRITICAL]** {title}
   - **Location:** {file:line or section}
   - **Issue:** {specific description of what's wrong}
   - **Impact:** {what can go wrong}
   - **Fix:** {what should be done}

### HIGH ({count})

2. **[HIGH]** {title}
   ...

### MEDIUM ({count})

...

### LOW ({count})

...

---
**Summary:** {1-2 sentence overall assessment}
**Verdict:** {NEEDS_WORK | ACCEPTABLE_WITH_CONCERNS | REJECT}
```

### HALT Conditions

- **Zero findings after re-analysis:** Report as anomaly — "Content appears clean after double analysis. Recommend peer review for validation."
- **Empty content:** Abort immediately with error
- **Content unreadable:** Abort with specific error about what failed

## Severity Definitions

| Severity | Criteria |
|----------|----------|
| **CRITICAL** | Security vulnerability, data loss risk, crash/hang, incorrect business logic |
| **HIGH** | Missing error handling, performance bottleneck, broken patterns, missing tests for critical paths |
| **MEDIUM** | Code smell, minor inconsistency, missing docs for complex logic, non-idiomatic patterns |
| **LOW** | Style nit, naming suggestion, minor optimization opportunity, cosmetic issue |

## Handoff
next_agent: @dev
next_command: *apply-qa-fixes
condition: Findings require code changes
alternatives:
  - agent: @architect, command: *analyze-impact, condition: Findings reveal architectural issues
  - agent: @pm, command: *write-spec, condition: Findings reveal specification gaps
