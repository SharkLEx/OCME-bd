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
task: createContentStrategy()
responsável: Compass (Content Strategist)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: brand_guidelines
  tipo: object
  origem: Project Knowledge Base
  obrigatório: true
  validação: Must exist and contain positioning, tone-of-voice, visual identity

- campo: market_research
  tipo: object
  origem: @content-researcher output (market-research-mkt)
  obrigatório: false
  validação: If present, must contain findings and recommendations

- campo: business_objectives
  tipo: array
  origem: User Input / PRD
  obrigatório: true
  validação: Non-empty array of business goals with measurable targets

**Saída:**
- campo: content_strategy
  tipo: object
  destino: File (docs/marketing/content-strategy.md)
  persistido: true

- campo: content_pillars
  tipo: array
  destino: File (docs/marketing/content-strategy.md)
  persistido: true

- campo: editorial_calendar_framework
  tipo: object
  destino: File (docs/marketing/editorial-calendar.md)
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Brand guidelines document exists and contains positioning, tone-of-voice, and visual identity
    tipo: pre-condition
    blocker: true
    validação: |
      Check brand guidelines file exists in project knowledge base.
      Verify it contains: brand positioning, tone-of-voice, visual identity.
    error_message: "Pre-condition failed: Brand guidelines must exist with positioning, tone-of-voice, and visual identity sections"

  - [ ] Business objectives are defined with measurable targets
    tipo: pre-condition
    blocker: true
    validação: |
      Check business objectives are provided as input.
      Verify each objective has a measurable KPI or target.
    error_message: "Pre-condition failed: Business objectives must be defined with measurable targets"

  - [ ] Market research from @content-researcher is available (recommended)
    tipo: pre-condition
    blocker: false
    validação: |
      Check if market research report exists from @content-researcher.
      If not available, log warning and proceed with brand guidelines only.
    error_message: "Warning: Market research not available. Strategy will be based on brand guidelines only."
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Content strategy document generated with all required sections (pillars, funnel, channels, KPIs)
    tipo: post-condition
    blocker: true
    validação: |
      Verify content-strategy.md contains: content pillars, funnel mapping,
      channel strategy, content mix, KPIs, personas, editorial calendar framework.
    error_message: "Post-condition failed: Content strategy document missing required sections"

  - [ ] Content pillars are derived from brand positioning (3-5 pillars)
    tipo: post-condition
    blocker: true
    validação: |
      Verify each content pillar traces back to brand positioning.
      Verify pillar count is between 3 and 5.
    error_message: "Post-condition failed: Content pillars must be 3-5 and derived from brand positioning"

  - [ ] KPIs are defined per channel and per funnel stage
    tipo: post-condition
    blocker: true
    validação: |
      Verify KPIs exist for each channel in channel strategy.
      Verify KPIs exist for each funnel stage (TOFU/MOFU/BOFU).
    error_message: "Post-condition failed: KPIs must be defined per channel and per funnel stage"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Strategy contains 3-5 content pillars aligned with brand positioning
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert content pillars exist (3-5), each with clear description and
      traceable link to brand positioning.
    error_message: "Acceptance criterion not met: Strategy must contain 3-5 content pillars aligned with brand positioning"

  - [ ] Funnel mapping covers TOFU, MOFU, and BOFU stages with content types
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert funnel map includes all three stages.
      Assert each stage has defined content types and objectives.
    error_message: "Acceptance criterion not met: Funnel mapping must cover TOFU, MOFU, and BOFU with content types"

  - [ ] Channel strategy specifies platforms, content types, and posting rationale
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert each channel has: platform name, content type, posting rationale,
      target audience, and frequency.
    error_message: "Acceptance criterion not met: Channel strategy must specify platforms, content types, and rationale"

  - [ ] Editorial calendar framework defines frequency and themes
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert editorial calendar defines weekly/monthly frequency per channel
      and recurring themes.
    error_message: "Acceptance criterion not met: Editorial calendar must define frequency and themes"

  - [ ] Target personas documented with content preferences
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert at least one persona is defined with demographics, pain points,
      content preferences, and preferred channels.
    error_message: "Acceptance criterion not met: Target personas must be documented with content preferences"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** brand-guidelines-loader
  - **Purpose:** Load and parse brand guidelines document
  - **Source:** Project knowledge base

- **Tool:** market-research-loader
  - **Purpose:** Load market research output from @content-researcher
  - **Source:** docs/marketing/research/

---

## Scripts

**Agent-specific code for this task:**

- **Script:** N/A
  - **Purpose:** This task is primarily strategic and document-driven
  - **Language:** N/A
  - **Location:** N/A

---

## Error Handling

**Strategy:** retry-with-fallback

**Common Errors:**

1. **Error:** Brand Guidelines Not Found
   - **Cause:** Brand guidelines document does not exist or is incomplete
   - **Resolution:** Request brand guidelines from project owner or @marketing-chief
   - **Recovery:** Abort with clear message listing required brand guideline sections

2. **Error:** Market Research Unavailable
   - **Cause:** @content-researcher has not completed market research
   - **Resolution:** Proceed without market research, using brand guidelines only
   - **Recovery:** Log warning, create strategy with note that market validation is pending

3. **Error:** Business Objectives Unclear
   - **Cause:** Business objectives are vague or not measurable
   - **Resolution:** Request clarification with specific examples of measurable objectives
   - **Recovery:** Use Interactive mode to elicit objectives from user

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 20-45 min (estimated)
cost_estimated: $0.010-0.030
token_usage: ~8,000-20,000 tokens
```

**Optimization Notes:**
- Load brand guidelines and market research in parallel
- Use templates for funnel mapping and channel strategy to reduce generation time
- Cache brand guidelines for reuse across marketing tasks

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - market-research-mkt (optional, recommended)
tags:
  - marketing
  - content-strategy
  - planning
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research content strategy best practices
checklists: []
execution_mode: interactive
---

# create-content-strategy

Create a comprehensive content strategy defining pillars, funnel mapping, channel plan, and KPIs.

## Purpose

Generate a structured content strategy document that serves as the foundation for all marketing content creation. The strategy aligns brand positioning with business objectives through defined content pillars, funnel-stage mapping, channel-specific plans, and measurable KPIs.

**Agent:** @content-strategist (Compass) — EXCLUSIVE

## Prerequisites

- Brand guidelines must exist with positioning, tone-of-voice, and visual identity
- Business objectives must be defined with measurable targets
- Market research from @content-researcher is recommended but not blocking

## Step-by-Step Execution

### Step 1: Load Brand Guidelines and Positioning

Load the brand guidelines document from the project knowledge base. Extract:
- Brand positioning statement
- Tone-of-voice guidelines
- Visual identity principles
- Core brand values

**Checkpoint (Interactive):** Confirm brand guidelines are complete and up-to-date.

### Step 2: Load Market Research (if available)

Check if @content-researcher has produced a market research report.

- If available: load findings, trends, competitor insights, and opportunities
- If not available: log warning and proceed with brand guidelines only

**Note:** Market research enriches the strategy but is not blocking.

### Step 3: Define Content Pillars (3-5)

Derive content pillars from brand positioning. Each pillar should:

1. Align directly with a brand value or positioning element
2. Address a specific audience need or pain point
3. Be broad enough to generate multiple content pieces
4. Be distinct from other pillars (no overlap)

**Format per pillar:**
```yaml
pillar:
  name: "Pillar Name"
  derived_from: "Brand positioning element"
  description: "What this pillar covers"
  audience_need: "What need it addresses"
  example_topics:
    - "Topic 1"
    - "Topic 2"
    - "Topic 3"
```

**Checkpoint (Interactive):** Confirm pillars align with brand and business objectives.

### Step 4: Map Content to Funnel Stages (TOFU/MOFU/BOFU)

For each funnel stage, define:

| Stage | Objective | Content Types | Pillar Alignment |
|-------|-----------|---------------|------------------|
| **TOFU** (Awareness) | Attract new audience | Blog posts, social media, videos, infographics | Which pillars |
| **MOFU** (Consideration) | Nurture leads | Case studies, webinars, email sequences, comparisons | Which pillars |
| **BOFU** (Decision) | Convert to customers | Demos, testimonials, pricing pages, free trials | Which pillars |

### Step 5: Define Channel Strategy

For each active channel, document:

```yaml
channel:
  name: "Channel Name"
  why: "Strategic rationale for this channel"
  audience_segment: "Primary audience on this channel"
  content_types:
    - "Type 1"
    - "Type 2"
  posting_frequency: "X times per week/month"
  tone_adaptation: "How brand tone adapts for this channel"
  funnel_stages: ["TOFU", "MOFU"]
```

### Step 6: Define Content Mix

Establish the percentage distribution of content types:

| Content Type | Percentage | Description |
|-------------|------------|-------------|
| Educational | X% | Teaching, how-tos, insights |
| Promotional | X% | Product/service promotion |
| Engagement | X% | Community, polls, UGC |
| Institutional | X% | Brand story, culture, values |

**Rule:** Educational content should be >= 40% of total mix.

### Step 7: Set KPIs per Channel and Funnel Stage

Define measurable KPIs:

**Per Channel:**
- Reach/Impressions
- Engagement rate
- Click-through rate
- Conversion rate
- Growth rate

**Per Funnel Stage:**
- TOFU: Impressions, reach, new followers, website visits
- MOFU: Email signups, content downloads, webinar registrations
- BOFU: Demo requests, free trial signups, purchase conversions

### Step 8: Define Target Personas

For each persona:

```yaml
persona:
  name: "Persona Name"
  demographics: "Age, role, industry"
  pain_points:
    - "Pain point 1"
    - "Pain point 2"
  content_preferences:
    formats: ["video", "blog", "podcast"]
    channels: ["Instagram", "LinkedIn"]
    consumption_time: "When they consume content"
  funnel_position: "Primary funnel stage"
```

### Step 9: Create Editorial Calendar Framework

Define the recurring structure:

```yaml
editorial_calendar:
  weekly_cadence:
    monday: "Content type / pillar"
    wednesday: "Content type / pillar"
    friday: "Content type / pillar"
  monthly_themes:
    week_1: "Theme focus"
    week_2: "Theme focus"
    week_3: "Theme focus"
    week_4: "Theme focus"
  seasonal_events:
    - "Event 1 — content approach"
    - "Event 2 — content approach"
```

### Step 10: Document Strategy in Structured Output

Compile all sections into `docs/marketing/content-strategy.md`:

1. Executive Summary
2. Content Pillars
3. Funnel Mapping
4. Channel Strategy
5. Content Mix
6. KPIs Dashboard
7. Target Personas
8. Editorial Calendar Framework
9. Appendix: Market Research Summary (if available)

## Output Requirements

1. **ALWAYS** create strategy document at: `docs/marketing/content-strategy.md`
2. **ALWAYS** include all 9 sections listed above
3. Keep executive summary to 1 paragraph maximum
4. All KPIs must be measurable and time-bound
5. Content pillars must trace back to brand positioning

## Handoff
next_agent: @content-strategist
next_command: *create-brief
condition: Content strategy is complete and approved
alternatives:
  - agent: @content-researcher, command: *market-research, condition: Market research needed before strategy
  - agent: @marketing-chief, command: *review-strategy, condition: Strategy needs executive approval
