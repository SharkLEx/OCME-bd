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
task: reviewContent()
responsável: Sentinel (Content Reviewer)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: content
  tipo: object
  origem: @copywriter output
  obrigatório: true
  validação: Must be a content piece ready for review (text, copy, or creative asset)

- campo: content_brief
  tipo: object
  origem: docs/marketing/briefs/{brief-slug}.md
  obrigatório: true
  validação: Must be the original brief that guided content creation

- campo: brand_guidelines
  tipo: object
  origem: Project Knowledge Base (brand-guidelines.md)
  obrigatório: true
  validação: Must contain positioning, tone-of-voice, visual identity, and legal requirements

**Saída:**
- campo: review_verdict
  tipo: string
  destino: File (docs/marketing/reviews/{content-slug}-review.md)
  persistido: true

- campo: review_scores
  tipo: object
  destino: File (docs/marketing/reviews/{content-slug}-review.md)
  persistido: true

- campo: review_feedback
  tipo: array
  destino: File (docs/marketing/reviews/{content-slug}-review.md)
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Content to review exists and is in reviewable state
    tipo: pre-condition
    blocker: true
    validação: |
      Check content input is provided and non-empty.
      Verify content is complete (not a draft or partial piece).
    error_message: "Pre-condition failed: Content must exist and be in reviewable state"

  - [ ] Brand guidelines document exists with positioning, tone-of-voice, and legal requirements
    tipo: pre-condition
    blocker: true
    validação: |
      Check brand-guidelines.md exists in project knowledge base.
      Verify it contains: positioning, tone-of-voice, visual identity, legal requirements.
    error_message: "Pre-condition failed: Brand guidelines must exist with positioning, tone-of-voice, and legal sections"

  - [ ] Content brief (reference) is available
    tipo: pre-condition
    blocker: true
    validação: |
      Check content brief file exists at docs/marketing/briefs/{brief-slug}.md.
      Verify it contains objective, audience, key messages, and CTA.
    error_message: "Pre-condition failed: Content brief must be available as review reference"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Review verdict generated (APPROVE / REVISE / REJECT) with overall score
    tipo: post-condition
    blocker: true
    validação: |
      Verify review file exists at docs/marketing/reviews/{content-slug}-review.md.
      Verify it contains a verdict (APPROVE, REVISE, or REJECT) and overall score.
    error_message: "Post-condition failed: Review must produce a verdict with overall score"

  - [ ] All three review layers executed (Brand Alignment, Legal Compliance, Content Quality)
    tipo: post-condition
    blocker: true
    validação: |
      Verify review contains scores and feedback for all three layers:
      brand alignment, legal compliance, and content quality.
    error_message: "Post-condition failed: All three review layers must be executed"

  - [ ] Actionable feedback provided for each failed or low-scoring item
    tipo: post-condition
    blocker: true
    validação: |
      Verify each item scoring below threshold has specific, actionable feedback
      explaining what needs to change and why.
    error_message: "Post-condition failed: Actionable feedback must be provided for failed/low-scoring items"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Brand alignment score (0-10) is calculated with per-item breakdown
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert brand alignment score exists (0-10 scale).
      Assert individual checklist items are scored with pass/fail per item.
    error_message: "Acceptance criterion not met: Brand alignment score must be calculated with per-item breakdown"

  - [ ] Legal compliance check has clear pass/fail per item (NON-NEGOTIABLE)
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert legal compliance checklist is fully evaluated.
      Assert any single legal fail results in immediate REJECT verdict.
      This is NON-NEGOTIABLE per Marketing Constitution MK-III.
    error_message: "Acceptance criterion not met: Legal compliance must have clear pass/fail per item (MK-III)"

  - [ ] Content quality score (0-10) is calculated with per-item breakdown
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert content quality score exists (0-10 scale).
      Assert individual quality items are scored with per-item feedback.
    error_message: "Acceptance criterion not met: Content quality score must be calculated with per-item breakdown"

  - [ ] Overall score correctly applies weighting formula: (brand × 0.35) + (legal × 0.30) + (quality × 0.35)
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert overall score is calculated using the defined formula.
      Assert legal pass counts as full score (10) and legal fail counts as 0.
    error_message: "Acceptance criterion not met: Overall score must use correct weighting formula"

  - [ ] Verdict thresholds are correctly applied: APPROVE >= 7.0 / REVISE 5.0-6.9 / REJECT < 5.0
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert verdict matches score thresholds exactly.
      Any legal fail overrides score-based verdict to REJECT.
    error_message: "Acceptance criterion not met: Verdict thresholds must be correctly applied"

  - [ ] REVISE verdict includes specific, actionable feedback for @copywriter
    tipo: acceptance-criterion
    blocker: true
    validação: |
      If verdict is REVISE, assert feedback contains specific changes needed
      with examples or references to brand guidelines.
    error_message: "Acceptance criterion not met: REVISE verdict must include actionable feedback"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** brand-alignment-checklist
  - **Purpose:** Evaluate content against brand guidelines
  - **Source:** .lmas-core/development/checklists/brand-alignment-checklist.md

- **Tool:** legal-compliance-checklist
  - **Purpose:** Evaluate content against legal requirements
  - **Source:** .lmas-core/development/checklists/legal-compliance-checklist.md

- **Tool:** content-quality-checklist
  - **Purpose:** Evaluate content quality across multiple dimensions
  - **Source:** .lmas-core/development/checklists/content-quality-checklist.md

---

## Scripts

**Agent-specific code for this task:**

- **Script:** N/A
  - **Purpose:** This task uses checklists and scoring, not scripts
  - **Language:** N/A
  - **Location:** N/A

---

## Error Handling

**Strategy:** abort-on-legal-fail

**Common Errors:**

1. **Error:** Content Brief Not Found
   - **Cause:** Content brief file does not exist at expected path
   - **Resolution:** Search for brief by content slug or ask user for brief location
   - **Recovery:** If brief truly missing, abort review — cannot review without reference

2. **Error:** Brand Guidelines Incomplete
   - **Cause:** Brand guidelines missing legal or tone-of-voice sections
   - **Resolution:** Request complete brand guidelines from @marketing-chief
   - **Recovery:** Abort review for legal compliance layer, partial review for others

3. **Error:** Legal Compliance Checklist Missing
   - **Cause:** legal-compliance-checklist.md not found
   - **Resolution:** Alert @marketing-chief — legal review is NON-NEGOTIABLE (MK-III)
   - **Recovery:** Abort review entirely — cannot publish without legal compliance check

4. **Error:** Ambiguous Scoring
   - **Cause:** Content falls between scoring categories
   - **Resolution:** Use Interactive mode for borderline cases, document reasoning
   - **Recovery:** Default to lower score (conservative approach), document rationale

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 15-30 min (estimated)
cost_estimated: $0.008-0.025
token_usage: ~6,000-15,000 tokens
```

**Optimization Notes:**
- Run brand alignment and content quality layers in parallel
- Legal compliance must run sequentially (early abort if fail)
- Cache brand guidelines and checklists for batch reviews

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - create-brief (content brief must exist)
tags:
  - marketing
  - content-review
  - quality-gate
  - legal-compliance
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research content review best practices and compliance standards
checklists:
  - brand-alignment-checklist.md
  - legal-compliance-checklist.md
  - content-quality-checklist.md
execution_mode: interactive
---

# review-content

Full content review — brand alignment, legal compliance, and quality score. Gate for publication.

## Purpose

Execute a comprehensive 3-layer content review that serves as the quality gate before content publication. The review evaluates brand alignment, legal compliance (NON-NEGOTIABLE per MK-III), and content quality, producing a scored verdict that determines whether content proceeds to publication, needs revision, or is rejected.

**Agent:** @content-reviewer (Sentinel) — EXCLUSIVE

## Prerequisites

- Content to review must exist and be in reviewable state
- Content brief must be available as review reference
- Brand guidelines must exist with positioning, tone-of-voice, and legal requirements

## Step-by-Step Execution

### Step 1: Load Content and Content Brief

Load the content piece to review and its originating content brief.

```yaml
review_context:
  content_path: "Path to content being reviewed"
  brief_path: "Path to originating content brief"
  content_type: "Blog post / Social post / Email / etc."
  target_channel: "Where this content will be published"
```

Verify content is complete and ready for review (not a draft or partial).

### Step 2: Load Brand Guidelines and Tone-of-Voice

Load brand-guidelines.md from project knowledge base. Extract:

- Brand positioning statement
- Tone-of-voice guidelines (with channel-specific adaptations)
- Visual identity requirements (if applicable)
- Legal requirements and disclaimers
- Prohibited language or claims

### Step 3: Layer 1 — Brand Alignment

Run brand-alignment-checklist against the content:

```yaml
brand_alignment:
  checklist_items:
    - item: "Content aligns with brand positioning"
      score: 0-10
      pass: true/false
      notes: "Specific feedback"
    - item: "Tone matches brand voice guidelines"
      score: 0-10
      pass: true/false
      notes: "Specific feedback"
    - item: "Key messages align with brand messaging framework"
      score: 0-10
      pass: true/false
      notes: "Specific feedback"
    - item: "Visual elements follow brand identity (if applicable)"
      score: 0-10
      pass: true/false
      notes: "Specific feedback"
  overall_score: 0-10 (average of items)
```

**Gate:** If brand alignment score < 6 --> REJECT immediately.

**Checkpoint (Interactive):** Show brand alignment score and ask to proceed to legal review.

### Step 4: Layer 2 — Legal Compliance

Run legal-compliance-checklist against the content:

```yaml
legal_compliance:
  checklist_items:
    - item: "No false or misleading claims"
      pass: true/false
      notes: "Specific feedback"
    - item: "Required disclaimers are present"
      pass: true/false
      notes: "Specific feedback"
    - item: "No copyright infringement"
      pass: true/false
      notes: "Specific feedback"
    - item: "Privacy compliance (no unauthorized personal data)"
      pass: true/false
      notes: "Specific feedback"
    - item: "Industry-specific regulations met"
      pass: true/false
      notes: "Specific feedback"
  overall_pass: true/false (ALL items must pass)
```

**Gate:** Any single legal compliance failure --> REJECT immediately (NON-NEGOTIABLE, MK-III).

This is the most critical layer. Legal failures cannot be overridden, waived, or scored on a curve.

### Step 5: Layer 3 — Content Quality

Run content-quality-checklist against the content:

```yaml
content_quality:
  checklist_items:
    - item: "Content achieves the objective stated in brief"
      score: 0-10
      pass: true/false
      notes: "Specific feedback"
    - item: "Target audience is appropriately addressed"
      score: 0-10
      pass: true/false
      notes: "Specific feedback"
    - item: "CTA is clear and compelling"
      score: 0-10
      pass: true/false
      notes: "Specific feedback"
    - item: "Grammar, spelling, and punctuation are correct"
      score: 0-10
      pass: true/false
      notes: "Specific feedback"
    - item: "Content is engaging and holds attention"
      score: 0-10
      pass: true/false
      notes: "Specific feedback"
    - item: "Format is appropriate for the target channel"
      score: 0-10
      pass: true/false
      notes: "Specific feedback"
  overall_score: 0-10 (average of items)
```

**Gate:**
- If quality score < 5 --> REJECT
- If quality score 5-6 --> REVISE with specific feedback
- If quality score >= 7 --> Pass quality gate

### Step 6: Calculate Overall Score

Apply the weighting formula:

```
overall_score = (brand_alignment × 0.35) + (legal_compliance × 0.30) + (content_quality × 0.35)
```

Where:
- `brand_alignment` = brand alignment overall score (0-10)
- `legal_compliance` = 10 if all items pass, 0 if any item fails
- `content_quality` = content quality overall score (0-10)

### Step 7: Generate Verdict

Based on overall score and layer gates:

| Overall Score | Verdict | Condition |
|--------------|---------|-----------|
| >= 7.0 | **APPROVE** | No legal failures, brand >= 6, quality >= 7 |
| 5.0 - 6.9 | **REVISE** | No legal failures, but brand or quality below threshold |
| < 5.0 | **REJECT** | Score below minimum, or any layer gate triggered |
| Any | **REJECT** | Any legal compliance failure (overrides score) |

### Step 8: Write Detailed Feedback

For each failed or low-scoring item, provide:

```yaml
feedback:
  - item: "What was evaluated"
    layer: "Brand / Legal / Quality"
    score: 0-10
    status: "pass / fail / needs-improvement"
    issue: "What's wrong"
    suggestion: "How to fix it"
    reference: "Brand guideline section or legal requirement"
    priority: "high / medium / low"
```

### Step 9: Route Based on Verdict — APPROVE

If APPROVE:
- Content is ready for @marketing-chief approval flow
- Save review document with APPROVE status
- No revisions needed

### Step 10: Route Based on Verdict — REVISE

If REVISE:
- Send back to @copywriter with actionable feedback
- List every item that needs change, prioritized by importance
- Include specific examples of what "good" looks like
- Set revision deadline

### Step 11: Route Based on Verdict — REJECT

If REJECT:
- Send back with full justification
- Clearly state which gate triggered the rejection
- If legal: emphasize NON-NEGOTIABLE nature (MK-III)
- Recommend whether to revise extensively or start over

## Output Requirements

1. **ALWAYS** create review file at: `docs/marketing/reviews/{content-slug}-review.md`
2. **ALWAYS** include all three layer scores and overall score
3. **ALWAYS** include verdict with clear justification
4. Legal failures MUST result in REJECT regardless of other scores
5. Feedback must be specific and actionable (not generic)
6. Reference specific brand guideline sections in feedback

## Severity Scale for Feedback

**FIXED VALUES - NO VARIATIONS:**

- `low`: Minor style or formatting issues
- `medium`: Content quality or brand alignment gaps that should be fixed
- `high`: Critical brand misalignment, legal issues, or factual errors

## Handoff
next_agent: @marketing-chief
next_command: *approve-content
condition: Review verdict is APPROVE
alternatives:
  - agent: @copywriter, command: *revise-content, condition: Review verdict is REVISE
  - agent: @copywriter, command: *rewrite-content, condition: Review verdict is REJECT
  - agent: @content-strategist, command: *create-brief, condition: Brief itself needs revision
