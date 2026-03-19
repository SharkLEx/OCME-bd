<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Standard campaigns with clear objectives and familiar audiences

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** New campaign types, large budgets, unfamiliar audiences

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** High-budget campaigns, multi-platform launches, new market entry

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: campaignPlan()
responsável: Flux (Traffic Manager)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: content_strategy
  tipo: object
  origem: @content-strategist
  obrigatório: true
  validação: Must define campaign objectives, target audience, and content pillars

- campo: budget
  tipo: number
  origem: User Input
  obrigatório: true
  validação: Must be positive number in BRL (R$). Minimum R$100.

- campo: objectives
  tipo: array
  origem: Content Strategy
  obrigatório: true
  validação: At least one objective defined (awareness, traffic, leads, sales, engagement)

- campo: target_audience
  tipo: object
  origem: Content Strategy
  obrigatório: true
  validação: Must include demographics, interests, or custom audience definition

- campo: campaign_duration
  tipo: object
  origem: User Input
  obrigatório: false
  validação: Start and end dates in ISO-8601. Default: 30 days from today.

**Saída:**
- campo: campaign_plan
  tipo: file
  destino: docs/marketing/campaigns/
  persistido: true

- campo: creative_briefs
  tipo: array
  destino: Return value
  persistido: false

- campo: kpi_targets
  tipo: object
  destino: Campaign Plan
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Content strategy must define campaign objectives and target audience
    tipo: pre-condition
    blocker: true
    validação: |
      Check content_strategy contains objectives array (non-empty)
      and target_audience object with at least demographics or interests
    error_message: "Pre-condition failed: Content strategy missing objectives or target audience definition."

  - [ ] Budget must be provided and valid
    tipo: pre-condition
    blocker: true
    validação: |
      Check budget > 0 and budget >= 100 (minimum viable campaign budget in BRL)
    error_message: "Pre-condition failed: Budget not provided or below minimum (R$100)."

  - [ ] At least one platform must be viable for the objectives
    tipo: pre-condition
    blocker: true
    validação: |
      Check that objectives map to at least one supported ad platform
      (Meta Ads, Google Ads, TikTok Ads, LinkedIn Ads)
    error_message: "Pre-condition failed: No viable platform found for the specified objectives."
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Campaign plan complete with all required sections; KPI targets defined; budget allocated
    tipo: post-condition
    blocker: true
    validação: |
      Verify campaign plan file contains: SMART objectives, budget allocation per platform,
      audience definitions, ad format selection, KPI targets, timeline, A/B testing plan
    error_message: "Post-condition failed: Campaign plan missing required sections."

  - [ ] Budget allocation sums to total budget (no over/under allocation)
    tipo: post-condition
    blocker: true
    validação: |
      Sum of all platform budget allocations === total budget
    error_message: "Post-condition failed: Budget allocation does not match total budget."
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] SMART objectives defined for the campaign
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Each objective is Specific, Measurable, Achievable, Relevant, Time-bound
    error_message: "Acceptance criterion not met: Campaign objectives are not SMART."

  - [ ] Budget allocated by platform with clear justification
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Each platform allocation has percentage, absolute value, and reasoning
    error_message: "Acceptance criterion not met: Budget allocation lacks justification."

  - [ ] KPI targets set with benchmarks
    tipo: acceptance-criterion
    blocker: true
    validação: |
      CPA, ROAS, CTR targets defined with industry/historical benchmarks
    error_message: "Acceptance criterion not met: KPI targets missing or without benchmarks."

  - [ ] Submitted for @marketing-chief approval if budget > R$1.000
    tipo: acceptance-criterion
    blocker: true
    validação: |
      If budget > 1000, campaign plan has been submitted for @marketing-chief review
    error_message: "Acceptance criterion not met: High-budget campaign requires @marketing-chief approval."
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** campaign-plan-template
  - **Purpose:** Standardized campaign plan template
  - **Source:** .lmas-core/domains/marketing/templates/campaign-plan-tmpl.md

- **Tool:** audience-builder
  - **Purpose:** Define and segment target audiences
  - **Source:** .lmas-core/domains/marketing/utils/audience-builder.js

- **Tool:** budget-calculator
  - **Purpose:** Calculate budget distribution across platforms
  - **Source:** .lmas-core/domains/marketing/utils/budget-calculator.js

---

## Scripts

**Agent-specific code for this task:**

- **Script:** kpi-benchmark-loader.js
  - **Purpose:** Load industry KPI benchmarks for target comparison
  - **Language:** JavaScript
  - **Location:** .lmas-core/domains/marketing/scripts/kpi-benchmark-loader.js

---

## Error Handling

**Strategy:** resolve-then-continue

**Common Errors:**

1. **Error:** Content Strategy Incomplete
   - **Cause:** Content strategy missing required fields (objectives, audience, pillars)
   - **Resolution:** Return to @content-strategist with list of missing fields
   - **Recovery:** Abort planning, generate gap analysis for content strategy

2. **Error:** Budget Below Platform Minimums
   - **Cause:** Allocated budget per platform below minimum viable spend
   - **Resolution:** Reduce number of platforms to concentrate budget
   - **Recovery:** Suggest single-platform strategy with full budget allocation

3. **Error:** No Audience Data Available
   - **Cause:** Target audience too vague or no historical data
   - **Resolution:** Use broad targeting with discovery phase built into timeline
   - **Recovery:** Plan with wider audience, add optimization phase to narrow targeting

4. **Error:** Conflicting Objectives
   - **Cause:** Multiple objectives that require different optimization strategies
   - **Resolution:** Prioritize primary objective, set others as secondary KPIs
   - **Recovery:** Split into separate campaigns per objective if budget allows

5. **Error:** Marketing Chief Approval Required
   - **Cause:** Budget exceeds R$1.000 threshold
   - **Resolution:** Flag plan for @marketing-chief review before execution
   - **Recovery:** Save plan as PENDING_APPROVAL, notify @marketing-chief

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 15-30 min (estimated)
cost_estimated: $0.010-0.025
token_usage: ~8,000-20,000 tokens
```

**Optimization Notes:**
- Load industry benchmarks once and cache for session
- Use template pre-filling for standard campaign types
- Batch audience definition when planning multi-platform campaigns

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - content-strategy
  - budget-allocation
tags:
  - marketing
  - paid-media
  - campaign-planning
  - traffic-management
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - campaign-plan-template
  - audience-builder
  - budget-calculator
checklists: []
execution_mode: interactive
---

# campaign-plan

Plan paid media campaign from strategy to execution plan.

## Purpose

Transform a content strategy into a complete, actionable paid media campaign plan. Defines SMART objectives, allocates budget across platforms, builds target audiences, selects ad formats, sets KPI targets with benchmarks, creates a phased timeline, and establishes A/B testing and optimization rules. High-budget campaigns (> R$1.000) require @marketing-chief approval.

## Prerequisites

- Content strategy from @content-strategist with objectives and target audience
- Budget defined (minimum R$100)
- At least one viable platform for the campaign objectives

## Step-by-Step Execution

### Step 1: Load Content Strategy and Objectives

1. Load content strategy document from @content-strategist
2. Extract campaign objectives, target audience, and content pillars
3. Validate all required fields are present
4. If incomplete → **ABORT** with gap analysis

### Step 2: Define SMART Campaign Objectives

1. Transform each objective into SMART format:
   - **S**pecific: Clear, well-defined goal
   - **M**easurable: Quantifiable metric attached
   - **A**chievable: Realistic given budget and timeline
   - **R**elevant: Aligned with business goals
   - **T**ime-bound: Deadline or timeframe defined
2. Example: "Increase website traffic by 30% within 30 days via Meta and Google Ads"
3. Prioritize if multiple objectives (primary, secondary)

### Step 3: Allocate Budget by Platform

1. Analyze objectives to determine best platforms:
   - **Awareness:** Meta (Instagram/Facebook), TikTok, YouTube
   - **Traffic:** Google Ads, Meta, LinkedIn
   - **Leads:** Meta Lead Ads, Google Ads, LinkedIn
   - **Sales:** Google Shopping, Meta Catalog, Google Ads
   - **Engagement:** Meta, TikTok
2. Allocate budget based on:
   - Platform relevance to objective (40% weight)
   - Audience presence on platform (30% weight)
   - Historical performance if available (20% weight)
   - Minimum viable spend per platform (10% weight)
3. Validate no platform is below minimum viable spend
4. Document allocation with justification

### Step 4: Define Target Audiences

1. Build audience segments:
   - **Demographics:** Age, gender, location, language
   - **Interests:** Topics, behaviors, affinities
   - **Custom audiences:** Website visitors, email lists, app users
   - **Lookalike audiences:** Based on best customers or converters
2. Define audience size estimates per platform
3. Plan audience testing strategy (broad vs. narrow)

### Step 5: Select Platforms and Ad Formats

1. For each platform, select ad formats:
   - **Meta:** Stories, Reels, Feed, Carousel, Collection
   - **Google:** Search, Display, YouTube (In-stream, Shorts), Performance Max
   - **TikTok:** In-Feed, TopView, Spark Ads
   - **LinkedIn:** Sponsored Content, Message Ads, Lead Gen Forms
2. Match format to objective and creative capabilities
3. Document creative specifications per format

### Step 6: List Creative Assets Needed

1. Generate creative brief for each ad format:
   - Dimensions and specifications
   - Copy requirements (headline, description, CTA)
   - Visual requirements (image, video, carousel)
   - Variant count for A/B testing
2. Delegate creative production brief to @copywriter
3. Estimate creative production timeline

### Step 7: Set KPI Targets

1. Define targets for key metrics:
   - **CPA** (Cost Per Acquisition): Based on industry benchmarks and margin
   - **ROAS** (Return on Ad Spend): Revenue / Ad Spend target
   - **CTR** (Click-Through Rate): Platform-specific benchmarks
   - **CPM** (Cost Per Mille): Expected reach cost
   - **Conversion Rate**: Expected conversion percentage
2. Load industry benchmarks as reference
3. Adjust targets based on campaign maturity (new vs. optimized)

### Step 8: Create Timeline with Phases

1. Define campaign phases:
   - **Learning Phase** (Days 1-7): Broad targeting, algorithm learning, no major changes
   - **Optimization Phase** (Days 8-21): Narrow audiences, scale winners, pause losers
   - **Scale Phase** (Days 22+): Increase budget on top performers, expand audiences
2. Set milestone checkpoints for each phase
3. Define phase transition criteria

### Step 9: Define A/B Testing Plan

1. Identify variables to test:
   - Creative variants (headline, image, CTA)
   - Audience segments
   - Placements
   - Bidding strategies
2. Define test duration and sample size requirements
3. Set statistical significance threshold (95% confidence)
4. Plan test rotation schedule

### Step 10: Set Optimization Rules

1. Define automated rules:
   - **Pause trigger:** CPA > 2x target for 3+ consecutive days
   - **Scale trigger:** ROAS > target for 5+ consecutive days
   - **Adjust trigger:** CTR < 50% of benchmark for 48+ hours
2. Set budget reallocation thresholds
3. Define escalation criteria (when to involve @marketing-chief)

### Step 11: Fill Campaign Plan Template

1. Load `campaign-plan-tmpl.md` template
2. Fill all sections with gathered data
3. Validate all required fields are complete
4. Save to `docs/marketing/campaigns/{campaign-slug}-plan.md`

### Step 12: Submit for Approval (if required)

1. If budget > R$1.000:
   - Flag plan for @marketing-chief review
   - Set status to `PENDING_APPROVAL`
   - Notify @marketing-chief with plan summary
2. If budget <= R$1.000:
   - Set status to `APPROVED` (auto-approved)
   - Ready for execution

## Output Requirements

1. Complete campaign plan file saved to `docs/marketing/campaigns/`
2. Creative briefs generated for @copywriter
3. KPI targets with benchmarks documented
4. If budget > R$1.000: plan flagged for @marketing-chief approval

## Handoff
next_agent: @marketing-chief
next_command: *approve-campaign
condition: Budget > R$1.000 (requires approval)
alternatives:
  - agent: @traffic-manager, command: *budget-allocation, condition: Campaign approved, ready for execution
  - agent: @copywriter, command: *create-ad-copy, condition: Creative briefs ready for production
