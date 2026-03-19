<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Minor reallocations (<10% shift) based on clear performance data

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** Significant reallocations, new budget distribution, unfamiliar campaigns

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Large budget shifts, multi-campaign rebalancing, quarterly planning

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: budgetAllocation()
responsável: Flux (Traffic Manager)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: campaign_performance_data
  tipo: array
  origem: Campaign Reports / Analytics
  obrigatório: true
  validação: Must contain at least one campaign with metrics (spend, revenue, conversions, clicks, impressions)

- campo: total_available_budget
  tipo: number
  origem: User Input
  obrigatório: true
  validação: Must be positive number in BRL (R$). Must equal or exceed current total spend.

- campo: roi_targets
  tipo: object
  origem: Campaign Plan / User Input
  obrigatório: true
  validação: Must define target ROAS and/or target CPA

- campo: reallocation_period
  tipo: string
  origem: User Input
  obrigatório: false
  validação: Period for new allocation (e.g., "next_week", "next_month"). Default: "next_week".

**Saída:**
- campo: allocation_recommendation
  tipo: object
  destino: Return value
  persistido: true

- campo: projected_impact
  tipo: object
  destino: Return value
  persistido: false

- campo: reallocation_report
  tipo: file
  destino: docs/marketing/reports/
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] At least one active campaign exists with performance data
    tipo: pre-condition
    blocker: true
    validação: |
      Check campaign_performance_data array is non-empty and contains
      at least one campaign with spend > 0 and impressions > 0
    error_message: "Pre-condition failed: No active campaigns with performance data found."

  - [ ] Performance data is recent and reliable
    tipo: pre-condition
    blocker: true
    validação: |
      Check performance data timestamp is within last 7 days;
      data includes minimum 3 days of metrics for statistical relevance
    error_message: "Pre-condition failed: Performance data is stale or insufficient for reliable allocation."

  - [ ] ROI targets are defined
    tipo: pre-condition
    blocker: true
    validação: |
      Check roi_targets contains at least target_roas or target_cpa
    error_message: "Pre-condition failed: ROI targets not defined. Set ROAS or CPA targets before allocation."
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Allocation recommendation complete; budget sums match total; justification provided
    tipo: post-condition
    blocker: true
    validação: |
      Verify sum of all campaign allocations === total_available_budget;
      each allocation has data-driven justification;
      reallocation report generated
    error_message: "Post-condition failed: Budget allocation incomplete or totals don't match."

  - [ ] High reallocation flagged for review if > 20% shift
    tipo: post-condition
    blocker: true
    validação: |
      If any single campaign reallocation > 20% of total budget, verify
      @marketing-chief review flag is set
    error_message: "Post-condition failed: Large reallocation (>20%) not flagged for @marketing-chief review."
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Each campaign allocation justified by performance data
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert every allocation increase/decrease has corresponding ROAS, CPA, or CTR data
    error_message: "Acceptance criterion not met: Allocation lacks data justification."

  - [ ] Projected impact calculated for proposed reallocation
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert projected_impact includes estimated ROAS, CPA, and revenue for new allocation
    error_message: "Acceptance criterion not met: Projected impact not calculated."

  - [ ] Underperforming campaigns identified with clear criteria
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert underperformers identified using quantifiable criteria (e.g., CPA > 2x target)
    error_message: "Acceptance criterion not met: Underperformers not identified with clear criteria."
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** budget-calculator
  - **Purpose:** Calculate optimal budget distribution
  - **Source:** .lmas-core/domains/marketing/utils/budget-calculator.js

- **Tool:** roi-analyzer
  - **Purpose:** Calculate ROAS, CPA, CTR from raw campaign data
  - **Source:** .lmas-core/domains/marketing/utils/roi-analyzer.js

---

## Scripts

**Agent-specific code for this task:**

- **Script:** campaign-ranker.js
  - **Purpose:** Rank campaigns by ROI efficiency for allocation priority
  - **Language:** JavaScript
  - **Location:** .lmas-core/domains/marketing/scripts/campaign-ranker.js

---

## Error Handling

**Strategy:** resolve-then-continue

**Common Errors:**

1. **Error:** Insufficient Performance Data
   - **Cause:** Campaign running for less than 3 days, not enough data for reliable analysis
   - **Resolution:** Extend data collection period or use broader metrics
   - **Recovery:** Flag campaigns with insufficient data, exclude from reallocation, maintain current budget

2. **Error:** All Campaigns Underperforming
   - **Cause:** No campaign meets ROI targets
   - **Resolution:** Recommend campaign restructuring instead of reallocation
   - **Recovery:** Generate diagnostic report, suggest pausing all and rebuilding strategy

3. **Error:** Budget Decrease Below Platform Minimum
   - **Cause:** Proposed reallocation would put a campaign below platform minimum spend
   - **Resolution:** Either pause campaign entirely or maintain at minimum viable spend
   - **Recovery:** Adjust allocation to respect platform minimums, redistribute excess

4. **Error:** Reallocation Exceeds Threshold
   - **Cause:** Proposed reallocation shifts > 20% of total budget
   - **Resolution:** Flag for @marketing-chief review before applying
   - **Recovery:** Save recommendation as PENDING_REVIEW, notify @marketing-chief

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 10-20 min (estimated)
cost_estimated: $0.005-0.015
token_usage: ~5,000-12,000 tokens
```

**Optimization Notes:**
- Pre-calculate all campaign metrics before ranking to avoid redundant computation
- Cache platform minimum spend thresholds
- Use incremental analysis when only a few campaigns have new data

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - campaign-plan
  - roi-report
tags:
  - marketing
  - paid-media
  - budget-management
  - optimization
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - budget-calculator
  - roi-analyzer
checklists: []
execution_mode: interactive
---

# budget-allocation

Allocate or reallocate budget between campaigns based on performance data.

## Purpose

Analyze active campaign performance data to recommend optimal budget allocation. Ranks campaigns by ROI efficiency, identifies underperformers, proposes data-driven reallocation, calculates projected impact, and flags significant shifts (>20%) for @marketing-chief review.

## Prerequisites

- At least one active campaign with performance data (minimum 3 days)
- Total available budget defined
- ROI targets defined (ROAS and/or CPA)

## Step-by-Step Execution

### Step 1: Load Active Campaigns and Performance Metrics

1. Load all campaigns from `campaign_performance_data`
2. For each campaign, extract:
   - Campaign ID and name
   - Platform
   - Total spend (period)
   - Total revenue (period)
   - Conversions
   - Clicks
   - Impressions
   - Current daily budget
3. Validate data completeness for each campaign
4. Flag campaigns with insufficient data (< 3 days)

### Step 2: Calculate Current ROAS, CPA, CTR

1. For each campaign calculate:
   - **ROAS** = Revenue / Spend
   - **CPA** = Spend / Conversions
   - **CTR** = (Clicks / Impressions) x 100
   - **Conversion Rate** = (Conversions / Clicks) x 100
   - **CPM** = (Spend / Impressions) x 1000
2. Handle edge cases:
   - Zero conversions → CPA = infinity (flag as critical underperformer)
   - Zero impressions → Exclude from analysis (campaign not delivering)

### Step 3: Rank Campaigns by ROI Efficiency

1. Create composite efficiency score:
   - ROAS weight: 40%
   - CPA efficiency (inverse CPA vs target): 30%
   - CTR vs benchmark: 20%
   - Trend direction (improving/declining): 10%
2. Rank all campaigns from highest to lowest efficiency
3. Categorize:
   - **Top Performers:** Above target ROI, positive trend
   - **Average Performers:** Near target ROI, stable
   - **Underperformers:** Below target ROI, negative trend

### Step 4: Identify Underperforming Campaigns

1. Apply underperformance criteria:
   - CPA > 1.5x target for 5+ consecutive days
   - ROAS < 70% of target for 5+ consecutive days
   - CTR < 50% of platform benchmark
   - Zero conversions in last 48 hours
2. Generate underperformance flags with specific data
3. Classify severity: `warning` (near threshold) or `critical` (far below)

### Step 5: Propose Reallocation

1. Calculate reallocation based on rankings:
   - **Top performers:** Increase budget by 15-30% (proportional to efficiency)
   - **Average performers:** Maintain current budget or minor adjustment (+/- 5%)
   - **Underperformers (warning):** Reduce budget by 20-30%
   - **Underperformers (critical):** Reduce budget by 50% or recommend pause
2. Ensure total allocation equals `total_available_budget`
3. Respect platform minimum spend thresholds
4. Document before/after for each campaign

### Step 6: Calculate Projected Impact

1. For proposed reallocation, estimate:
   - Projected total ROAS (weighted average)
   - Projected average CPA
   - Projected total conversions
   - Projected total revenue
2. Compare projected vs. current performance
3. Calculate expected improvement percentage

### Step 7: Present Recommendation

1. Generate allocation recommendation:
   ```
   Campaign: {name}
   Platform: {platform}
   Current Budget: R$ {current}
   Proposed Budget: R$ {proposed}
   Change: {+/-} R$ {delta} ({percentage}%)
   Justification: {data-driven reason}
   ```
2. Include summary metrics:
   - Total budget: R$ {total}
   - Projected ROAS: {value} (vs current {value})
   - Projected CPA: R$ {value} (vs current R$ {value})

### Step 8: Flag for Review (if applicable)

1. If any single campaign reallocation > 20% of total budget:
   - Set status to `PENDING_REVIEW`
   - Flag for @marketing-chief review
   - Include data justification for the large shift
2. If all reallocations <= 20%:
   - Set status to `RECOMMENDED`
   - Ready for immediate application

## Output Requirements

1. Allocation recommendation with per-campaign breakdown
2. Projected impact analysis with current vs. projected metrics
3. Reallocation report saved to `docs/marketing/reports/budget-allocation-{date}.md`
4. If reallocation > 20%: flagged for @marketing-chief review

## Handoff
next_agent: @marketing-chief
next_command: *approve-reallocation
condition: Reallocation > 20% of total budget requires approval
alternatives:
  - agent: @traffic-manager, command: *roi-report, condition: Generate updated ROI report after reallocation
  - agent: @traffic-manager, command: *campaign-plan, condition: New campaign needed to replace paused underperformers
