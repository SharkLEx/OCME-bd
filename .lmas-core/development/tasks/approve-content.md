<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Routine content approvals with clear scores

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** Brand-sensitive or institutional content

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** High-stakes content requiring multi-stakeholder alignment

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: approveContent()
responsável: Vox (Marketing Chief)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: content_path
  tipo: string
  origem: User Input
  obrigatório: true
  validação: File must exist and be readable

- campo: reviewer_verdict
  tipo: string
  origem: @content-reviewer output
  obrigatório: true
  validação: Must be one of APPROVE, REVISE, REJECT

- campo: quality_score
  tipo: number
  origem: @content-reviewer output
  obrigatório: true
  validação: Integer between 1-10

**Saída:**
- campo: approval_decision
  tipo: string (APPROVE | REVISE | REJECT)
  destino: Return value
  persistido: false

- campo: feedback
  tipo: string
  destino: Memory
  persistido: true

- campo: approval_report
  tipo: object
  destino: File (.ai/content-approvals/*.json)
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Content file exists at content_path and is readable
    tipo: pre-condition
    blocker: true
    validação: |
      Check content file exists at specified path
    error_message: "Pre-condition failed: Content file not found at specified path"

  - [ ] @content-reviewer verdict is APPROVE with quality_score >= 7
    tipo: pre-condition
    blocker: true
    validação: |
      Verify reviewer_verdict == APPROVE and quality_score >= 7
    error_message: "Pre-condition failed: Content must have APPROVE verdict from @content-reviewer with score >= 7"

  - [ ] Brand guidelines document is accessible
    tipo: pre-condition
    blocker: true
    validação: |
      Check brand-guidelines.md exists in project knowledge base
    error_message: "Pre-condition failed: brand-guidelines.md not found"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Approval decision recorded with justification
    tipo: post-condition
    blocker: true
    validação: |
      Verify approval_decision is set and feedback is non-empty
    error_message: "Post-condition failed: Approval decision must include justification"

  - [ ] Approval report persisted to .ai/content-approvals/
    tipo: post-condition
    blocker: true
    validação: |
      Verify report file created with correct schema
    error_message: "Post-condition failed: Approval report not persisted"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Content evaluated against brand alignment checklist
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert brand alignment checklist was executed and score recorded
    error_message: "Acceptance criterion not met: Brand alignment checklist not executed"

  - [ ] Decision is one of APPROVE, REVISE, or REJECT with actionable feedback
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert decision is valid enum and feedback provides clear next steps
    error_message: "Acceptance criterion not met: Invalid decision or missing actionable feedback"

  - [ ] REVISE/REJECT decisions include specific items to fix
    tipo: acceptance-criterion
    blocker: true
    validação: |
      If decision != APPROVE, assert feedback contains specific revision items
    error_message: "Acceptance criterion not met: REVISE/REJECT must list specific items to fix"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** brand-alignment-checklist
  - **Purpose:** Structured checklist for brand compliance verification
  - **Source:** .lmas-core/development/checklists/brand-alignment-checklist.md

- **Tool:** tone-of-voice reference
  - **Purpose:** Verify content matches brand tone
  - **Source:** knowledge-base/tone-of-voice.md

---

## Scripts

**Agent-specific code for this task:**

- **Script:** N/A
  - **Purpose:** This task is executed manually by @marketing-chief
  - **Language:** N/A
  - **Location:** N/A

---

## Error Handling

**Strategy:** retry-with-feedback

**Common Errors:**

1. **Error:** Content File Not Found
   - **Cause:** content_path points to non-existent file
   - **Resolution:** Verify path and re-submit with correct content_path
   - **Recovery:** Abort with clear file path error

2. **Error:** Missing Reviewer Verdict
   - **Cause:** Content was not reviewed by @content-reviewer before approval request
   - **Resolution:** Route content to @content-reviewer first
   - **Recovery:** Abort with delegation instruction to @content-reviewer

3. **Error:** Quality Score Below Threshold
   - **Cause:** @content-reviewer scored content below 7
   - **Resolution:** Return to @copywriter for revision before re-review
   - **Recovery:** Abort with score details and revision guidance

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 5-10 min (estimated)
cost_estimated: $0.002-0.008
token_usage: ~2,000-6,000 tokens
```

**Optimization Notes:**
- YOLO mode can reduce to 2-3 min for routine approvals with clear scores
- Batch multiple content approvals in a single session when possible

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - content-reviewer verdict
  - brand-guidelines.md
tags:
  - marketing
  - content-approval
  - brand-alignment
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research brand and content best practices
checklists:
  - brand-alignment-checklist.md
execution_mode: interactive
---

# approve-content

Review and approve content for publication based on @content-reviewer verdict and brand alignment.

## Purpose

Provide final approval gate for content before publication. Ensures all content meets brand standards, quality thresholds, and strategic alignment. Only content with APPROVE verdict from @content-reviewer and quality score >= 7 reaches this gate.

## Prerequisites

- Content has been reviewed by @content-reviewer
- @content-reviewer verdict is APPROVE with quality_score >= 7
- Brand guidelines document is accessible

## Step-by-Step Instructions

### Step 1: Load Content and Review Verdict

1. Read the content file at `content_path`
2. Load the @content-reviewer verdict and quality_score
3. Confirm pre-conditions are met (APPROVE verdict, score >= 7)
4. If pre-conditions fail, ABORT with specific error

### Step 2: Verify Brand Alignment

1. Load `brand-guidelines.md` from knowledge base
2. Run brand-alignment-checklist mentally against content:
   - Brand voice consistency
   - Visual identity compliance (if applicable)
   - Messaging pillars alignment
   - Target audience appropriateness
   - Value proposition clarity
3. Record brand alignment score (1-10)

### Step 3: Check Approval Level Required

1. Determine if content is **institutional** or **brand-sensitive**:
   - Institutional: official communications, press releases, investor content
   - Brand-sensitive: content that defines or redefines brand positioning
2. If institutional/brand-sensitive → requires deeper review (proceed to Step 4 with extra scrutiny)
3. If routine content → standard review (proceed to Step 4)

### Step 4: Make Approval Decision

**APPROVE** (quality_score >= 7 AND brand aligned):
- Content meets all quality and brand standards
- Ready for publication
- Record approval with brief confirmation

**REVISE** (minor issues found):
- Content quality is acceptable but has fixable issues
- List specific items to revise (max 5)
- Return to @copywriter with feedback

**REJECT** (major issues found):
- Content fails brand alignment or has critical issues
- Provide detailed justification
- Return to @copywriter for rewrite

### Step 5: Record Decision

1. Create approval report with:
   - Decision (APPROVE/REVISE/REJECT)
   - Quality score (from @content-reviewer)
   - Brand alignment score
   - Feedback/justification
   - Timestamp
2. Persist report to `.ai/content-approvals/`

## Output Requirements

1. **ALWAYS** return a clear decision: APPROVE, REVISE, or REJECT
2. **ALWAYS** include actionable feedback
3. REVISE/REJECT decisions **MUST** list specific items to fix
4. APPROVE decisions **SHOULD** include brief confirmation of brand alignment

## Decision Criteria

### APPROVE
- Quality score >= 7 (from @content-reviewer)
- Brand alignment verified
- No institutional/brand-sensitive concerns

### REVISE
- Minor brand alignment issues (fixable)
- Tone adjustments needed
- Small messaging corrections

### REJECT
- Major brand misalignment
- Content contradicts brand positioning
- Critical quality issues despite reviewer score

## Handoff
next_agent: @copywriter
next_command: *write-copy
condition: Decision is REVISE or REJECT (return for revision)
alternatives:
  - agent: @content-reviewer, command: *schedule-publication, condition: Decision is APPROVE
