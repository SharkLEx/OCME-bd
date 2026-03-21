<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Low-budget campaigns with clear ROI

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** Medium/high-budget campaigns requiring strategic review

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Large campaigns with multiple stakeholders and high budgets

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: approveCampaign()
responsável: Vox (Marketing Chief) — EXCLUSIVE
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: campaign_plan_path
  tipo: string
  origem: User Input
  obrigatório: true
  validação: Must point to a valid campaign plan file (campaign-plan-tmpl.md format)

- campo: budget_amount
  tipo: number
  origem: Campaign plan
  obrigatório: true
  validação: Must be positive number in BRL

- campo: roi_projection
  tipo: object
  origem: Campaign plan
  obrigatório: true
  validação: Must include expected_revenue, expected_cost, and roi_percentage

**Saída:**
- campo: campaign_approval
  tipo: string (APPROVE | REVISE | REJECT)
  destino: Return value
  persistido: false

- campo: conditions
  tipo: array
  destino: Memory
  persistido: true

- campo: approval_report
  tipo: object
  destino: File (.ai/campaign-approvals/*.json)
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Campaign plan file exists and follows campaign-plan-tmpl.md format
    tipo: pre-condition
    blocker: true
    validação: |
      Check campaign plan file exists at campaign_plan_path and has required sections
    error_message: "Pre-condition failed: Campaign plan not found or invalid format"

  - [ ] Budget has ROI projection with expected_revenue, expected_cost, and roi_percentage
    tipo: pre-condition
    blocker: true
    validação: |
      Verify roi_projection contains all required fields with valid numbers
    error_message: "Pre-condition failed: ROI projection missing or incomplete"

  - [ ] @content-reviewer has reviewed creative assets
    tipo: pre-condition
    blocker: true
    validação: |
      Check that creative assets in campaign plan have @content-reviewer approval
    error_message: "Pre-condition failed: Creative assets not reviewed by @content-reviewer"

  - [ ] Budget > R$1.000 (campaigns below this threshold do not require @marketing-chief approval)
    tipo: pre-condition
    blocker: true
    validação: |
      Verify budget_amount > 1000
    error_message: "Pre-condition failed: Budget must exceed R$1.000 to require this approval"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Campaign approval decision recorded with conditions/notes
    tipo: post-condition
    blocker: true
    validação: |
      Verify campaign_approval is set and conditions array is populated
    error_message: "Post-condition failed: Approval decision must include conditions or notes"

  - [ ] Approval report persisted to .ai/campaign-approvals/
    tipo: post-condition
    blocker: true
    validação: |
      Verify report file created with correct schema and timestamp
    error_message: "Post-condition failed: Campaign approval report not persisted"

  - [ ] Budget allocation validated and documented
    tipo: post-condition
    blocker: true
    validação: |
      Verify budget breakdown is recorded in approval report
    error_message: "Post-condition failed: Budget allocation not documented"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Campaign evaluated against brand positioning and strategy alignment
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert strategy alignment check was performed and documented
    error_message: "Acceptance criterion not met: Strategy alignment not evaluated"

  - [ ] Budget validated with ROI projection review
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert budget and ROI were reviewed and assessment is documented
    error_message: "Acceptance criterion not met: Budget/ROI not validated"

  - [ ] Creative assets confirmed approved by @content-reviewer
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert all creative assets have @content-reviewer approval
    error_message: "Acceptance criterion not met: Creative assets approval not confirmed"

  - [ ] Decision includes conditions or next steps
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert decision has associated conditions, notes, or next steps
    error_message: "Acceptance criterion not met: Decision missing conditions/next steps"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** campaign-plan-template
  - **Purpose:** Reference template for campaign plan validation
  - **Source:** .lmas-core/development/templates/campaign-plan-tmpl.md

- **Tool:** brand-guidelines
  - **Purpose:** Brand positioning reference for strategy alignment
  - **Source:** knowledge-base/brand-guidelines.md

- **Tool:** roi-calculator
  - **Purpose:** Validate ROI projections and budget feasibility
  - **Source:** Manual calculation by @marketing-chief

---

## Scripts

**Agent-specific code for this task:**

- **Script:** N/A
  - **Purpose:** This task is executed manually by @marketing-chief (EXCLUSIVE)
  - **Language:** N/A
  - **Location:** N/A

---

## Error Handling

**Strategy:** abort

**Common Errors:**

1. **Error:** Campaign Plan Not Found
   - **Cause:** campaign_plan_path points to non-existent file
   - **Resolution:** Verify path and re-submit with correct campaign_plan_path
   - **Recovery:** Abort with clear file path error

2. **Error:** Missing ROI Projection
   - **Cause:** Campaign plan does not include ROI projection data
   - **Resolution:** Return campaign plan to creator for ROI calculation
   - **Recovery:** Abort with specific missing fields listed

3. **Error:** Creative Assets Not Reviewed
   - **Cause:** @content-reviewer has not reviewed campaign creative assets
   - **Resolution:** Route creative assets to @content-reviewer first
   - **Recovery:** Abort with delegation instruction to @content-reviewer

4. **Error:** Budget Below Threshold
   - **Cause:** Campaign budget is R$1.000 or less
   - **Resolution:** This task is not required for low-budget campaigns
   - **Recovery:** Skip approval, log as auto-approved

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 10-20 min (estimated)
cost_estimated: $0.005-0.015
token_usage: ~4,000-12,000 tokens
```

**Optimization Notes:**
- YOLO mode can reduce to 5-8 min for campaigns with clear ROI and standard budget
- Interactive mode recommended for campaigns > R$10.000

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - campaign-plan-tmpl.md
  - brand-guidelines.md
  - @content-reviewer creative asset approval
tags:
  - marketing
  - campaign-approval
  - budget
  - roi
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research campaign and marketing best practices
checklists:
  - brand-alignment-checklist.md
execution_mode: interactive
---

# approve-campaign

Approve campaign with budget allocation based on strategy alignment, ROI projections, and creative asset review.

## Purpose

Provide the final approval gate for marketing campaigns before execution. This is an EXCLUSIVE task for @marketing-chief (Vox). Only campaigns with budget > R$1.000 require this approval. Validates strategy alignment, budget feasibility, ROI projections, and creative asset quality.

## Prerequisites

- Campaign plan exists following campaign-plan-tmpl.md format
- Budget has ROI projection with expected_revenue, expected_cost, and roi_percentage
- @content-reviewer has reviewed and approved creative assets
- Budget exceeds R$1.000 threshold

## Step-by-Step Instructions

### Step 1: Load Campaign Plan

1. Read the campaign plan file at `campaign_plan_path`
2. Validate it follows the `campaign-plan-tmpl.md` format
3. Extract key sections: objective, target audience, channels, budget, timeline, creative assets, ROI projection
4. If plan is incomplete, ABORT with specific missing sections

### Step 2: Verify Strategy Alignment

1. Load `brand-guidelines.md` from knowledge base
2. Compare campaign objective against brand positioning
3. Verify target audience matches brand's target segments
4. Check channel selection aligns with brand presence strategy
5. Record strategy alignment assessment (ALIGNED / PARTIALLY_ALIGNED / MISALIGNED)

### Step 3: Validate Budget

1. Confirm budget_amount > R$1.000 (threshold for this approval)
2. Review budget breakdown by channel/activity
3. Check budget is proportional to campaign scope and expected reach
4. Flag any budget items that seem disproportionate or missing

### Step 4: Review ROI Projections

1. Load roi_projection from campaign plan
2. Verify expected_revenue, expected_cost, and roi_percentage are present
3. Assess reasonability of projections:
   - Is expected_revenue based on realistic conversion rates?
   - Are costs comprehensive (media, creative, tools, labor)?
   - Is roi_percentage achievable for this campaign type?
4. Record ROI assessment (REALISTIC / OPTIMISTIC / UNREALISTIC)

### Step 5: Check Target Audience Alignment

1. Verify target audience definition is specific and measurable
2. Compare against brand's established audience segments
3. Check if campaign reaches new segments (requires extra justification)
4. Record audience alignment assessment

### Step 6: Verify Creative Assets

1. Confirm @content-reviewer has reviewed all creative assets listed in campaign plan
2. Check reviewer verdicts for each asset
3. If any asset has REJECT verdict, flag as blocker
4. Record creative assets status

### Step 7: Make Approval Decision

**APPROVE:**
- Strategy aligned with brand positioning
- Budget is reasonable and justified
- ROI projections are realistic
- Target audience is well-defined and aligned
- All creative assets approved by @content-reviewer
- Record approval with any conditions

**REVISE:**
- Overall concept is sound but has fixable issues
- List specific items to revise (max 7)
- Return campaign plan for adjustment

**REJECT:**
- Fundamental strategy misalignment
- Unrealistic ROI projections
- Major budget issues
- Provide detailed justification and recommendations

### Step 8: Record Decision

1. Create approval report with:
   - Decision (APPROVE/REVISE/REJECT)
   - Strategy alignment assessment
   - Budget validation summary
   - ROI assessment
   - Conditions/notes (for APPROVE)
   - Revision items (for REVISE)
   - Rejection justification (for REJECT)
   - Timestamp
2. Persist report to `.ai/campaign-approvals/`

## Output Requirements

1. **ALWAYS** return a clear decision: APPROVE, REVISE, or REJECT
2. **ALWAYS** include conditions or notes
3. APPROVE decisions **MUST** list any conditions for execution
4. REVISE decisions **MUST** list specific items to adjust
5. REJECT decisions **MUST** provide detailed justification and alternative recommendations

## Decision Criteria

### APPROVE
- Strategy alignment: ALIGNED
- ROI assessment: REALISTIC or OPTIMISTIC with justification
- Budget: Reasonable and complete
- Creative assets: All approved
- Audience: Well-defined and aligned

### REVISE
- Strategy alignment: PARTIALLY_ALIGNED (fixable)
- ROI assessment: OPTIMISTIC without justification
- Budget: Minor adjustments needed
- Creative assets: Minor revisions pending

### REJECT
- Strategy alignment: MISALIGNED
- ROI assessment: UNREALISTIC
- Budget: Fundamentally flawed
- Creative assets: Major issues unresolved

## Handoff
next_agent: @campaign-manager
next_command: *execute-campaign
condition: Decision is APPROVE
alternatives:
  - agent: @copywriter, command: *write-copy, condition: Decision is REVISE (creative revision needed)
  - agent: @pm, command: *revise-campaign-plan, condition: Decision is REVISE (strategic revision needed)
  - agent: @marketing-chief, command: *brand-review, condition: Decision is REJECT (requires brand realignment)
