<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Recurring weekly/monthly reports with standard format

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** First report generation, custom periods, executive presentations

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Quarterly reviews, board presentations, multi-campaign consolidated reports

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: roiReport()
responsável: Flux (Traffic Manager)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: campaign_ids
  tipo: array
  origem: User Input / Campaign Registry
  obrigatório: true
  validação: At least one campaign ID. Use "all" for all active campaigns.

- campo: reporting_period
  tipo: object
  origem: User Input
  obrigatório: true
  validação: Must include start_date and end_date in ISO-8601. Period must not exceed 90 days.

- campo: performance_data
  tipo: object
  origem: Analytics / Platform APIs
  obrigatório: true
  validação: Must contain spend, revenue, conversions, clicks, impressions per campaign per channel

- campo: comparison_period
  tipo: object
  origem: User Input
  obrigatório: false
  validação: Previous period for comparison. Default: same duration immediately preceding reporting_period.

**Saída:**
- campo: roi_report
  tipo: file
  destino: docs/marketing/reports/
  persistido: true

- campo: executive_summary
  tipo: string
  destino: Return value
  persistido: false

- campo: recommendations
  tipo: array
  destino: ROI Report
  persistido: true

- campo: forecast
  tipo: object
  destino: ROI Report
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Campaigns must have tracking enabled (UTM parameters or pixel)
    tipo: pre-condition
    blocker: true
    validação: |
      Check each campaign_id has tracking configured (utm_params or conversion pixel active)
    error_message: "Pre-condition failed: One or more campaigns lack tracking. Enable tracking before generating ROI report."

  - [ ] Reporting period must have data (not future dates, not empty)
    tipo: pre-condition
    blocker: true
    validação: |
      Check reporting_period.end_date <= today;
      performance_data contains entries within the reporting period
    error_message: "Pre-condition failed: Reporting period has no data or includes future dates."

  - [ ] Performance data available for at least one campaign in the period
    tipo: pre-condition
    blocker: true
    validação: |
      Check at least one campaign has spend > 0 and impressions > 0 in the reporting period
    error_message: "Pre-condition failed: No campaign performance data found for the reporting period."
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] ROI report complete with all required sections; calculations verified; file saved
    tipo: post-condition
    blocker: true
    validação: |
      Verify ROI report file contains: executive summary, key metrics,
      channel breakdown, top/bottom performers, period comparison,
      recommendations, forecast
    error_message: "Post-condition failed: ROI report missing required sections."

  - [ ] All financial calculations are accurate (investment matches spend, ROAS computed correctly)
    tipo: post-condition
    blocker: true
    validação: |
      Verify total_investment === sum of all campaign spends;
      ROAS === revenue / spend for each campaign and overall
    error_message: "Post-condition failed: Financial calculations contain errors."
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Key metrics calculated and presented: Investment, Revenue, ROAS, CPA, CTR, Conversion Rate
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert all six key metrics present in report with correct values
    error_message: "Acceptance criterion not met: Key metrics incomplete in ROI report."

  - [ ] Channel breakdown included (per-platform performance)
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert channel breakdown section contains metrics per platform (Meta, Google, TikTok, LinkedIn)
    error_message: "Acceptance criterion not met: Channel breakdown missing from ROI report."

  - [ ] Period comparison included (current vs previous)
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert comparison section shows delta (absolute and percentage) for key metrics
    error_message: "Acceptance criterion not met: Period comparison missing from ROI report."

  - [ ] Actionable recommendations generated from data
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert at least 3 recommendations, each backed by specific performance data
    error_message: "Acceptance criterion not met: Recommendations missing or not data-driven."
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** roi-analyzer
  - **Purpose:** Calculate ROI metrics from raw campaign data
  - **Source:** .lmas-core/domains/marketing/utils/roi-analyzer.js

- **Tool:** roi-report-template
  - **Purpose:** Standardized ROI report template
  - **Source:** .lmas-core/domains/marketing/templates/roi-report-tmpl.md

- **Tool:** forecast-engine
  - **Purpose:** Generate next period forecast based on trends
  - **Source:** .lmas-core/domains/marketing/utils/forecast-engine.js

---

## Scripts

**Agent-specific code for this task:**

- **Script:** metrics-aggregator.js
  - **Purpose:** Aggregate performance metrics across campaigns and channels
  - **Language:** JavaScript
  - **Location:** .lmas-core/domains/marketing/scripts/metrics-aggregator.js

---

## Error Handling

**Strategy:** resolve-then-continue

**Common Errors:**

1. **Error:** Missing Campaign Data
   - **Cause:** One or more campaign IDs have no data in the reporting period
   - **Resolution:** Exclude campaigns with no data, note in report as "No Data Available"
   - **Recovery:** Generate report for available campaigns, flag missing data in summary

2. **Error:** Revenue Data Unavailable
   - **Cause:** No revenue tracking configured (common for awareness/traffic campaigns)
   - **Resolution:** Calculate cost-based metrics only (CPA, CPM, CTR); omit ROAS
   - **Recovery:** Note in report that ROAS unavailable, suggest implementing revenue tracking

3. **Error:** Comparison Period Has No Data
   - **Cause:** Previous period has no campaign data (new campaigns)
   - **Resolution:** Skip comparison section, note "First period — no comparison available"
   - **Recovery:** Generate report without comparison, set baseline for future reports

4. **Error:** Data Discrepancy Between Platforms
   - **Cause:** Platform-reported data doesn't match analytics data
   - **Resolution:** Use platform data as source of truth for spend, analytics for conversions
   - **Recovery:** Note discrepancy in report, recommend attribution model review

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 10-25 min (estimated)
cost_estimated: $0.008-0.020
token_usage: ~6,000-15,000 tokens
```

**Optimization Notes:**
- Pre-aggregate metrics per campaign before generating report sections
- Cache comparison period data when generating multiple reports
- Use template pre-filling for standard report sections

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - campaign-plan
  - budget-allocation
tags:
  - marketing
  - paid-media
  - analytics
  - reporting
  - roi
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - roi-analyzer
  - roi-report-template
  - forecast-engine
checklists: []
execution_mode: interactive
---

# roi-report

Generate ROI report for paid media campaigns.

## Purpose

Produce a comprehensive ROI report covering all campaign performance for a defined period. Calculates key financial and engagement metrics, breaks down performance by channel/platform, compares against the previous period, identifies top and bottom performers, generates data-driven recommendations, and forecasts next period performance.

## Prerequisites

- Campaigns must have tracking enabled (UTM parameters or conversion pixel)
- Reporting period must have data available
- At least one campaign with performance data in the period

## Step-by-Step Execution

### Step 1: Define Reporting Period

1. Parse `reporting_period` (start_date, end_date)
2. Validate period does not exceed 90 days
3. Calculate comparison period:
   - If `comparison_period` provided, use it
   - Otherwise, use same duration immediately preceding (e.g., if period is 30 days, compare with previous 30 days)
4. Log period definitions

### Step 2: Collect Performance Data

1. For each campaign in `campaign_ids`:
   - Load spend, revenue, conversions, clicks, impressions
   - Group by day for trend analysis
   - Group by platform/channel
2. Handle missing campaigns:
   - If "all" specified, load all campaigns in period
   - If specific IDs missing data, flag and exclude with note
3. Validate data completeness

### Step 3: Calculate Key Metrics

1. **Per campaign and overall:**
   - **Investment (Spend):** Total amount spent in BRL
   - **Revenue:** Total attributed revenue in BRL
   - **ROAS:** Revenue / Spend (if revenue available)
   - **CPA:** Spend / Conversions
   - **CTR:** (Clicks / Impressions) x 100
   - **Conversion Rate:** (Conversions / Clicks) x 100
   - **CPM:** (Spend / Impressions) x 1000
   - **CPC:** Spend / Clicks
2. Handle edge cases:
   - Zero conversions → CPA = "N/A (no conversions)"
   - Zero revenue → ROAS = "N/A (no revenue tracking)"
   - Zero clicks → CTR = 0%, CPC = "N/A"

### Step 4: Generate Channel Breakdown

1. Aggregate metrics by platform:
   - **Meta (Instagram + Facebook):** Combined and individual metrics
   - **Google (Search + Display + YouTube):** Combined and individual metrics
   - **TikTok:** Metrics
   - **LinkedIn:** Metrics
2. For each channel produce:
   ```
   Channel: {name}
   Investment: R$ {spend}
   Revenue: R$ {revenue}
   ROAS: {value}x
   CPA: R$ {value}
   CTR: {value}%
   Share of Total Spend: {percentage}%
   ```
3. Rank channels by ROAS (best to worst)

### Step 5: Identify Top and Bottom Performers

1. **Top Performers** (Top 3 by ROAS):
   - Campaign name, platform, ROAS, CPA
   - Key success factors (audience, creative, timing)
   - Recommendation: scale budget
2. **Bottom Performers** (Bottom 3 by ROAS):
   - Campaign name, platform, ROAS, CPA
   - Likely causes of underperformance
   - Recommendation: optimize, restructure, or pause

### Step 6: Compare with Previous Period

1. Calculate delta for each key metric (absolute and percentage):
   ```
   Metric: {name}
   Current Period: {value}
   Previous Period: {value}
   Change: {+/-} {delta} ({percentage}%)
   Trend: {improving|declining|stable}
   ```
2. Highlight significant changes (> 15% variation)
3. If no comparison data available, note "First period — baseline established"

### Step 7: Generate Recommendations

1. Produce minimum 3 data-driven recommendations:
   - **Budget reallocation:** Based on channel/campaign performance ranking
   - **Creative optimization:** Based on CTR and engagement data
   - **Audience refinement:** Based on conversion rate variations
   - **Platform strategy:** Based on channel breakdown results
   - **Scaling opportunities:** Based on top performer headroom
2. Each recommendation must reference specific data:
   ```
   Recommendation: {action}
   Data Support: {specific metric and value}
   Expected Impact: {projected improvement}
   Priority: {high|medium|low}
   ```

### Step 8: Create Next Period Forecast

1. Based on current trends, project for next period (same duration):
   - Projected spend (if budget maintained)
   - Projected revenue (based on current ROAS trend)
   - Projected conversions (based on current CPA trend)
   - Projected ROAS (trend-adjusted)
2. Include confidence level:
   - **High confidence:** Stable trends, sufficient data
   - **Medium confidence:** Some variability, adequate data
   - **Low confidence:** High variability, limited data
3. Note key assumptions

### Step 9: Fill ROI Report Template

1. Load `roi-report-tmpl.md` template
2. Fill all sections:
   - Executive Summary
   - Key Metrics Overview
   - Channel Breakdown
   - Top & Bottom Performers
   - Period Comparison
   - Recommendations
   - Next Period Forecast
3. Save to `docs/marketing/reports/roi-report-{start_date}-to-{end_date}.md`

## Output Requirements

1. Complete ROI report file saved to `docs/marketing/reports/`
2. Executive summary (concise, suitable for stakeholder communication)
3. Minimum 3 actionable recommendations with data justification
4. Next period forecast with confidence level

## Handoff
next_agent: @marketing-chief
next_command: *review-roi
condition: Report ready for stakeholder review
alternatives:
  - agent: @traffic-manager, command: *budget-allocation, condition: Reallocation recommended based on findings
  - agent: @traffic-manager, command: *campaign-plan, condition: New campaign recommended to address gaps
  - agent: @content-strategist, command: *adjust-strategy, condition: Content strategy changes recommended
