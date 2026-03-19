<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Simple specs with few UI components

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** Complex specs, learning UX validation

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Critical specs, large feature sets

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: uxValidateSpec()
responsável: Sati (UX Design Expert)
responsavel_type: Agente
atomic_layer: Molecule

**Entrada:**
- campo: spec_path
  tipo: string
  origem: User Input / Spec Pipeline
  obrigatório: true
  validação: Must be a valid path to a spec.md file

- campo: depth
  tipo: string
  origem: User Input
  obrigatório: false
  validação: Must be one of 'quick', 'standard', 'deep'. Default 'standard'

**Saída:**
- campo: ux_validation_report
  tipo: object
  destino: File ({qa_location}/ux-validation-{spec-name}.md)
  persistido: true

- campo: verdict
  tipo: string
  destino: Workflow state
  persistido: false
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Spec file exists at spec_path
    tipo: pre-condition
    blocker: true
    validação: |
      Check that spec file exists at the provided path.
      Verify file is a valid markdown document.
    error_message: "Pre-condition failed: Spec file not found at specified path"

  - [ ] Spec contains identifiable requirements (FR/NFR/user stories)
    tipo: pre-condition
    blocker: false
    validação: |
      Check that spec has structured requirements.
      If no requirements found, task can still run but with reduced scope.
    error_message: "Warning: Spec has no structured requirements — validation will be limited"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] UX validation report generated
    tipo: post-condition
    blocker: true
    validação: |
      Verify report file exists at {qa_location}/ux-validation-{spec-name}.md.
      Verify it contains all validation check results.
    error_message: "Post-condition failed: UX validation report must be generated"

  - [ ] Verdict is one of APPROVED, NEEDS_UX_REVISION, BLOCKED_UX_ISSUES
    tipo: post-condition
    blocker: true
    validação: |
      Verify verdict field is present and contains a valid value.
    error_message: "Post-condition failed: Verdict must be set"

  - [ ] All checks have PASS, WARN, or FAIL status
    tipo: post-condition
    blocker: true
    validação: |
      Verify every check in the report has a status assigned.
      No check should have an empty or undefined status.
    error_message: "Post-condition failed: All checks must have a status"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Report contains score and verdict
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert score is X/N format where N matches depth level.
      Assert verdict maps correctly to score thresholds.
    error_message: "Acceptance criterion not met: Report must contain score and verdict"

  - [ ] Critical issues have specific recommendations
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert every FAIL check has at least one specific, actionable recommendation.
      Recommendations must reference the spec section that needs change.
    error_message: "Acceptance criterion not met: FAIL checks must have actionable recommendations"

  - [ ] Component inventory is included (if UI components exist)
    tipo: acceptance-criterion
    blocker: false
    validação: |
      If spec contains UI components, verify component inventory section
      lists identified components with reuse assessment.
    error_message: "Acceptance criterion not met: Component inventory should be included"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** design-intelligence-csvs
  - **Purpose:** Cross-reference spec against known UI patterns and components
  - **Source:** .lmas-core/data/design-intelligence/ (components.csv, patterns.csv, responsive.csv)

- **Tool:** spec-parser
  - **Purpose:** Parse spec.md structure to identify FR/NFR/UI sections
  - **Source:** Inline parsing logic

---

## Scripts

**Agent-specific code for this task:**

- **Script:** N/A
  - **Purpose:** This task is analysis-driven using checklists
  - **Language:** N/A
  - **Location:** N/A

---

## Error Handling

**Strategy:** retry-with-guidance

**Common Errors:**

1. **Error:** Spec File Not Found
   - **Cause:** Invalid spec_path provided
   - **Resolution:** Error with path suggestion — list available specs in docs/
   - **Recovery:** Search for spec files matching partial name

2. **Error:** No UI Components in Spec
   - **Cause:** Spec is backend/API-only with no UI implications
   - **Resolution:** Quick pass — "Spec has no significant UI components, UX validation not required"
   - **Recovery:** Return quick pass verdict, skip full validation

3. **Error:** Design Intelligence CSVs Unavailable
   - **Cause:** design-intelligence directory does not exist or CSVs not generated
   - **Resolution:** Skip Step 3 (cross-reference), proceed with checklist only
   - **Recovery:** Log warning, note that recommendations may be less specific

4. **Error:** Spec Too Vague for UX Validation
   - **Cause:** Spec lacks sufficient detail about user interactions
   - **Resolution:** Flag as NEEDS_UX_REVISION with specific questions
   - **Recovery:** Generate report with WARN for interaction-related checks

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 5-15 min (estimated, depends on depth)
cost_estimated: $0.003-0.010
token_usage: ~3,000-8,000 tokens
```

**Optimization Notes:**
- Quick depth skips checks 5-10 for faster validation
- Cache design intelligence CSV data during session
- Parse spec sections in parallel for faster analysis

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - spec-pipeline (consumer workflow)
tags:
  - ux
  - spec-validation
  - quality
  - accessibility
domain: software-dev
updated_at: 2026-03-17
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research UX validation best practices
checklists: []
execution_mode: interactive
---

# ux-validate-spec

Validate a product specification (spec.md) from the UX/usability perspective before it enters the QA critique phase.

## Purpose

Ensure the spec considers user needs, interaction patterns, accessibility requirements, and design system compatibility. This task catches UX gaps early in the spec pipeline — before implementation begins — reducing costly rework.

**Agent:** @ux-design-expert (Sati)
**Consumers:** spec-pipeline workflow, @pm, @architect

## Prerequisites

- Spec file must exist at the provided path
- Spec should contain identifiable requirements (FR/NFR/user stories)
- Design intelligence CSVs are optional but enhance recommendations

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `spec_path` | YES | Path to the spec.md file to validate |
| `--depth` | NO | Validation depth: `quick` (5 checks) \| `standard` (10 checks) \| `deep` (15+ checks). Default: `standard` |

## Step-by-Step Execution

### Step 1: Read and Parse Spec

1. Read the spec file at `spec_path`
2. Identify sections: requirements (FR/NFR), user stories, UI components, interactions, constraints
3. Flag sections with UI/UX implications
4. Count UI-related requirements vs total requirements

**Checkpoint (Interactive):** Confirm spec loaded and show summary of UI-relevant sections found.

**Quick exit:** If no UI components or interactions are found, return quick pass:
> "Spec has no significant UI components, UX validation not required."

### Step 2: UX Validation Checklist

Run the validation checks based on depth level:

#### Quick Depth (5 checks)
Checks 1-4 (User-Centric) + Check 8 (WCAG)

#### Standard Depth (10 checks — DEFAULT)

**User-Centric Checks:**

1. **User Needs Alignment** — Are requirements tied to real user needs/personas? Or are they purely technical features without user context?
   - PASS: Requirements reference personas or user pain points
   - WARN: Some requirements lack user context
   - FAIL: Requirements are entirely technical with no user perspective

2. **Interaction Clarity** — Are user interactions described clearly? (clicks, inputs, flows, feedback)
   - PASS: All interactions have clear trigger → action → feedback
   - WARN: Some interactions are ambiguous
   - FAIL: Critical interactions undefined

3. **Error States** — Does the spec define error states, empty states, loading states?
   - PASS: All three state types documented for key flows
   - WARN: Some states missing
   - FAIL: No state definitions at all

4. **Edge Cases** — Are edge cases covered? (first-time user, power user, offline, slow network)
   - PASS: 3+ edge cases documented per critical flow
   - WARN: Some edge cases mentioned but not comprehensive
   - FAIL: No edge cases addressed

**Design System Checks:**

5. **Component Reuse** — Can existing components satisfy requirements? Or does the spec require new custom components?
   - PASS: 80%+ requirements covered by existing components
   - WARN: 50-79% covered, some custom work needed
   - FAIL: <50% covered, significant custom component work

6. **Token Compatibility** — Are visual requirements (colors, sizes, spacing) expressible with existing design tokens?
   - PASS: All visual specs map to existing tokens
   - WARN: Minor extensions needed
   - FAIL: Major token gaps or conflicting values

7. **Responsive Consideration** — Does the spec address mobile, tablet, and desktop behavior?
   - PASS: All three breakpoints addressed
   - WARN: Only desktop + mobile, no tablet
   - FAIL: Single breakpoint only or no responsive mention

**Accessibility Checks:**

8. **WCAG Compliance** — Can the specified interactions meet WCAG AA? (keyboard nav, screen reader, contrast)
   - PASS: All interactions are WCAG AA compatible
   - WARN: Some interactions need accessibility adjustments
   - FAIL: Critical interactions cannot meet WCAG AA

9. **Inclusive Design** — Does the spec consider users with disabilities, low bandwidth, older devices?
   - PASS: Multiple inclusion considerations documented
   - WARN: Basic accessibility mentioned
   - FAIL: No inclusion considerations

**Information Architecture:**

10. **Information Hierarchy** — Is the content/information hierarchy clear? (primary, secondary, tertiary)
    - PASS: Clear hierarchy with priorities documented
    - WARN: Hierarchy implied but not explicit
    - FAIL: No hierarchy, flat information structure

#### Deep Depth (15+ checks)
All 10 standard checks PLUS:

11. **Micro-interactions** — Are transitions, animations, and micro-feedback defined?
12. **Onboarding Flow** — Is the first-time user experience designed?
13. **Performance Perception** — Are skeleton screens, progressive loading, optimistic updates considered?
14. **Internationalization** — Does the spec account for text expansion, RTL, and locale differences?
15. **Design Consistency** — Are patterns consistent across similar flows in the spec?

**Checkpoint (Interactive):** Show check results summary and ask if deep-dive on any specific check is desired.

### Step 3: Cross-Reference with Design Intelligence

If design intelligence CSVs are available at `.lmas-core/data/design-intelligence/`:

1. **components.csv** — Check if specified UI components match known patterns
   - Identify existing components that can satisfy requirements
   - Flag custom component needs

2. **patterns.csv** — Verify interaction patterns against best practices
   - Match spec patterns to catalogued patterns
   - Recommend proven alternatives for unusual patterns

3. **responsive.csv** — Check if responsive strategy aligns with framework choice
   - Validate breakpoint strategy
   - Recommend responsive patterns for identified components

4. Add recommendations based on matches to the report

**Skip condition:** If CSVs are unavailable, log a warning and proceed without cross-reference. Report will note that recommendations may be less specific.

### Step 4: Generate Validation Report

Create the report at `{qa_location}/ux-validation-{spec-name}.md`:

```markdown
# UX Spec Validation Report

**Spec:** {spec_name}
**Validated by:** @ux-design-expert (Sati)
**Date:** {date}
**Depth:** {depth}

## Summary
- **Score:** {X}/{N} checks passed
- **Verdict:** APPROVED | NEEDS_UX_REVISION | BLOCKED_UX_ISSUES
- **Critical Issues:** {count}
- **Warnings:** {count}
- **Recommendations:** {count}

## Check Results
| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | User Needs Alignment | PASS/WARN/FAIL | {details} |
| 2 | Interaction Clarity | PASS/WARN/FAIL | {details} |
| 3 | Error States | PASS/WARN/FAIL | {details} |
| 4 | Edge Cases | PASS/WARN/FAIL | {details} |
| 5 | Component Reuse | PASS/WARN/FAIL | {details} |
| 6 | Token Compatibility | PASS/WARN/FAIL | {details} |
| 7 | Responsive Consideration | PASS/WARN/FAIL | {details} |
| 8 | WCAG Compliance | PASS/WARN/FAIL | {details} |
| 9 | Inclusive Design | PASS/WARN/FAIL | {details} |
| 10 | Information Hierarchy | PASS/WARN/FAIL | {details} |

## Critical Issues
{List any FAIL items with specific, actionable recommendations.
Each recommendation must reference the spec section that needs change.}

## Warnings
{List WARN items with suggestions for improvement.}

## Recommendations
{Design intelligence matches and general UX suggestions.}

## Component Inventory
{List of UI components identified in spec with reuse assessment:
- Component name
- Existing match (yes/no)
- Reuse assessment (direct use / extend / custom build)
- Estimated effort}
```

### Step 5: Verdict Decision

| Score | Verdict | Action |
|-------|---------|--------|
| >= 8/10 | APPROVED | Proceed to @qa critique in spec pipeline |
| 5-7/10 | NEEDS_UX_REVISION | Return to @pm with UX feedback for spec revision |
| < 5/10 | BLOCKED_UX_ISSUES | Escalate — spec needs significant UX rework before proceeding |

**Note:** FAIL on check #8 (WCAG Compliance) automatically triggers NEEDS_UX_REVISION minimum, regardless of total score. Accessibility is non-negotiable.

## Output Requirements

1. **ALWAYS** save report to: `{qa_location}/ux-validation-{spec-name}.md`
2. **ALWAYS** include score and verdict in report header
3. **ALWAYS** provide actionable recommendations for FAIL items
4. Component inventory only required if spec has UI components
5. Design intelligence cross-reference only if CSVs are available

## Examples

### Example 1: SaaS Dashboard Spec
```
Input: *ux-validate-spec docs/spec/dashboard-spec.md
Depth: standard (default)
Output: Score 7/10 — NEEDS_UX_REVISION
  - FAIL: No error states defined for API timeout scenarios
  - FAIL: Mobile layout not addressed (desktop-only spec)
  - WARN: 3 custom components could use existing Button/Card atoms
  - Recommendation: Dashboard layout matches "analytics-dashboard" pattern from layouts.csv
```

### Example 2: Backend API Spec
```
Input: *ux-validate-spec docs/spec/api-spec.md
Output: Quick pass — "Spec has no significant UI components, UX validation not required"
```

### Example 3: E-commerce Checkout Spec (Deep)
```
Input: *ux-validate-spec docs/spec/checkout-spec.md --depth deep
Output: Score 12/15 — APPROVED
  - FAIL: No internationalization considerations (text expansion for PT/ES)
  - FAIL: Onboarding flow for guest checkout not defined
  - WARN: Micro-interactions for form validation not specified
  - PASS: All WCAG AA checks passed
  - PASS: Component reuse at 90% with existing design system
```

## Handoff
next_agent: @qa
next_command: *critique-spec
condition: Verdict is APPROVED (score >= 8/10)
alternatives:
  - agent: @pm, command: *revise-spec, condition: Verdict is NEEDS_UX_REVISION
  - agent: @architect, command: *review-spec-architecture, condition: Verdict is BLOCKED_UX_ISSUES
