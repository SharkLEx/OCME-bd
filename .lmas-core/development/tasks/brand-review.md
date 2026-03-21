<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Routine brand checks on established content formats

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** New content types, brand-sensitive material, rebranding reviews

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Major brand initiatives, institutional content, crisis communications

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: brandReview()
responsável: Vox (Marketing Chief) — EXCLUSIVE
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: review_target_path
  tipo: string
  origem: User Input
  obrigatório: true
  validação: Must point to content or campaign file to review

- campo: brand_guidelines_path
  tipo: string
  origem: Knowledge Base
  obrigatório: true
  validação: Must point to brand-guidelines.md

**Saída:**
- campo: brand_alignment_score
  tipo: number
  destino: Return value
  persistido: false

- campo: brand_alignment_report
  tipo: object
  destino: File (.ai/brand-reviews/*.json)
  persistido: true

- campo: recommendations
  tipo: array
  destino: Memory
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] brand-guidelines.md exists and is accessible
    tipo: pre-condition
    blocker: true
    validação: |
      Check brand-guidelines.md exists at brand_guidelines_path
    error_message: "Pre-condition failed: brand-guidelines.md not found"

  - [ ] Review target file exists and is readable
    tipo: pre-condition
    blocker: true
    validação: |
      Check review_target_path points to existing, readable file
    error_message: "Pre-condition failed: Review target file not found at specified path"

  - [ ] tone-of-voice.md exists and is accessible
    tipo: pre-condition
    blocker: true
    validação: |
      Check tone-of-voice.md exists in knowledge base
    error_message: "Pre-condition failed: tone-of-voice.md not found in knowledge base"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Brand alignment score calculated (1-10 scale)
    tipo: post-condition
    blocker: true
    validação: |
      Verify brand_alignment_score is set and within 1-10 range
    error_message: "Post-condition failed: Brand alignment score not calculated"

  - [ ] Brand alignment report persisted with detailed findings
    tipo: post-condition
    blocker: true
    validação: |
      Verify report file created at .ai/brand-reviews/ with all required sections
    error_message: "Post-condition failed: Brand alignment report not persisted"

  - [ ] Recommendations list generated with actionable items
    tipo: post-condition
    blocker: true
    validação: |
      Verify recommendations array is non-empty with specific actions
    error_message: "Post-condition failed: Recommendations not generated"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Each brand pillar evaluated individually with score
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert every brand pillar from brand-guidelines.md has individual assessment
    error_message: "Acceptance criterion not met: Not all brand pillars evaluated"

  - [ ] Visual identity compliance checked (if applicable)
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert visual identity check performed when content has visual elements
    error_message: "Acceptance criterion not met: Visual identity not checked"

  - [ ] Tone of voice alignment verified against tone-of-voice.md
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert tone verification performed with specific findings
    error_message: "Acceptance criterion not met: Tone of voice not verified"

  - [ ] Final score is weighted average of all pillar scores
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert final score calculation is documented and traceable
    error_message: "Acceptance criterion not met: Score calculation not documented"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** brand-guidelines
  - **Purpose:** Source of truth for brand pillars, positioning, and identity
  - **Source:** knowledge-base/brand-guidelines.md

- **Tool:** tone-of-voice
  - **Purpose:** Reference for voice, tone, and language standards
  - **Source:** knowledge-base/tone-of-voice.md

- **Tool:** brand-alignment-checklist
  - **Purpose:** Structured checklist for systematic brand compliance review
  - **Source:** .lmas-core/development/checklists/brand-alignment-checklist.md

---

## Scripts

**Agent-specific code for this task:**

- **Script:** N/A
  - **Purpose:** This task is executed manually by @marketing-chief (EXCLUSIVE)
  - **Language:** N/A
  - **Location:** N/A

---

## Error Handling

**Strategy:** retry-with-feedback

**Common Errors:**

1. **Error:** Brand Guidelines Not Found
   - **Cause:** brand-guidelines.md does not exist or path is incorrect
   - **Resolution:** Create brand guidelines or correct path in knowledge base
   - **Recovery:** Abort with instruction to create brand-guidelines.md first

2. **Error:** Tone of Voice Not Found
   - **Cause:** tone-of-voice.md does not exist in knowledge base
   - **Resolution:** Create tone-of-voice.md or locate existing document
   - **Recovery:** Proceed with brand-guidelines.md only, flag reduced accuracy

3. **Error:** Review Target Empty or Corrupt
   - **Cause:** Content file is empty or unreadable
   - **Resolution:** Verify content file and re-submit
   - **Recovery:** Abort with file status error

4. **Error:** Incomplete Brand Guidelines
   - **Cause:** brand-guidelines.md is missing required sections (pillars, positioning)
   - **Resolution:** Update brand-guidelines.md with complete information
   - **Recovery:** Proceed with available sections, flag incomplete assessment

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 10-20 min (estimated)
cost_estimated: $0.005-0.015
token_usage: ~5,000-15,000 tokens
```

**Optimization Notes:**
- YOLO mode reduces to 5-8 min for routine content against established brand
- Caching brand guidelines in session memory avoids re-reading for batch reviews

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - brand-guidelines.md
  - tone-of-voice.md
tags:
  - marketing
  - brand-review
  - brand-alignment
  - quality-assurance
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research branding best practices and standards
checklists:
  - brand-alignment-checklist.md
execution_mode: interactive
---

# brand-review

Deep review of brand alignment for content or campaigns against brand guidelines and tone of voice.

## Purpose

Provide a comprehensive brand alignment assessment for any content or campaign material. This is an EXCLUSIVE task for @marketing-chief (Vox). Evaluates content against every brand pillar, visual identity standards, messaging alignment, and tone of voice. Produces a scored report with actionable recommendations.

## Prerequisites

- brand-guidelines.md exists in knowledge base
- tone-of-voice.md exists in knowledge base
- Content or campaign material is ready for review

## Step-by-Step Instructions

### Step 1: Load Brand Guidelines

1. Read `brand-guidelines.md` from knowledge base
2. Extract brand pillars (list each pillar with its definition)
3. Extract brand positioning statement
4. Extract target audience definitions
5. Note any brand do's and don'ts

### Step 2: Load Tone of Voice

1. Read `tone-of-voice.md` from knowledge base
2. Extract voice attributes (e.g., professional, friendly, bold)
3. Extract tone variations by channel/context
4. Note language preferences and restrictions
5. Extract example phrases (do/don't examples)

### Step 3: Compare Content Against Brand Pillars

For each brand pillar identified in Step 1:

1. Read the review target content/campaign
2. Assess how well the content reflects this pillar (1-10 score)
3. Document specific evidence (quotes, sections) supporting the score
4. Note any content that contradicts the pillar
5. Record pillar score and findings

### Step 4: Check Visual Identity Compliance

**If the content has visual elements (images, design, layout):**

1. Check logo usage against brand guidelines
2. Verify color palette compliance
3. Check typography consistency
4. Verify imagery style alignment
5. Record visual compliance score (1-10)

**If text-only content:** Mark as N/A and skip to Step 5.

### Step 5: Verify Messaging Alignment

1. Identify key messages in the content
2. Compare against brand's approved messaging framework
3. Check value proposition clarity
4. Verify messaging hierarchy (primary, secondary, supporting)
5. Record messaging alignment score (1-10)

### Step 6: Run Brand Alignment Checklist

1. Load `brand-alignment-checklist.md`
2. Execute each checklist item against the content
3. Record pass/fail for each item
4. Calculate checklist completion percentage

### Step 7: Generate Brand Alignment Score and Report

1. Calculate weighted average of all pillar scores:
   - Brand pillars: 40% weight
   - Messaging alignment: 30% weight
   - Tone of voice: 20% weight
   - Visual identity: 10% weight (or redistribute if N/A)
2. Generate overall brand alignment score (1-10)
3. Compile detailed findings per category
4. Generate prioritized recommendations:
   - Critical (score < 4): Must fix before publication
   - Important (score 4-6): Should fix for quality
   - Suggested (score 7-8): Nice-to-have improvements
   - Excellent (score 9-10): Highlight as best practice

### Step 8: Persist Report

1. Create brand alignment report with:
   - Overall score
   - Per-pillar scores and findings
   - Visual identity assessment (if applicable)
   - Messaging alignment assessment
   - Tone of voice assessment
   - Checklist results
   - Prioritized recommendations
   - Timestamp
2. Persist report to `.ai/brand-reviews/`

## Output Requirements

1. **ALWAYS** return a brand alignment score (1-10)
2. **ALWAYS** include per-pillar breakdown
3. **ALWAYS** provide prioritized recommendations
4. Score calculation **MUST** be documented and traceable
5. Recommendations **MUST** be specific and actionable

## Score Interpretation

| Score Range | Interpretation | Action |
|-------------|---------------|--------|
| 9-10 | Excellent brand alignment | Approve, highlight best practices |
| 7-8 | Good alignment, minor suggestions | Approve with optional improvements |
| 4-6 | Moderate alignment, needs work | Revise before publication |
| 1-3 | Poor alignment, major issues | Reject, requires significant rework |

## Handoff
next_agent: @copywriter
next_command: *write-copy
condition: Score < 7 (content needs revision)
alternatives:
  - agent: @marketing-chief, command: *approve-content, condition: Score >= 7 (content passes brand review)
  - agent: @content-reviewer, command: *review-content, condition: Score >= 7 (route to content review pipeline)
