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
task: createBrief()
responsável: Compass (Content Strategist)
responsavel_type: Agente
atomic_layer: Molecule

**Entrada:**
- campo: content_strategy
  tipo: object
  origem: docs/marketing/content-strategy.md
  obrigatório: false
  validação: If present, must contain pillars, funnel map, and channel strategy

- campo: brand_guidelines
  tipo: object
  origem: Project Knowledge Base
  obrigatório: true
  validação: Must exist and contain positioning and tone-of-voice

- campo: topic
  tipo: string
  origem: User Input / Editorial Calendar
  obrigatório: true
  validação: Non-empty string describing the content topic or campaign

- campo: target_channel
  tipo: string
  origem: User Input / Content Strategy
  obrigatório: true
  validação: Must be a valid channel from channel strategy

- campo: editorial_calendar_ref
  tipo: string
  origem: docs/marketing/editorial-calendar.md
  obrigatório: false
  validação: If present, must reference a valid calendar entry

**Saída:**
- campo: content_brief
  tipo: object
  destino: File (docs/marketing/briefs/{brief-slug}.md)
  persistido: true

- campo: brief_metadata
  tipo: object
  destino: File (docs/marketing/briefs/{brief-slug}.md)
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Content strategy or brand guidelines exist
    tipo: pre-condition
    blocker: true
    validação: |
      Check that at least brand guidelines exist. Content strategy is preferred
      but brand guidelines alone are sufficient to create a brief.
    error_message: "Pre-condition failed: At minimum, brand guidelines must exist to create a content brief"

  - [ ] Topic or campaign is clearly defined
    tipo: pre-condition
    blocker: true
    validação: |
      Check that topic input is provided and non-empty.
      Verify topic is specific enough to generate a focused brief.
    error_message: "Pre-condition failed: Topic or campaign must be clearly defined"

  - [ ] Target channel is specified
    tipo: pre-condition
    blocker: true
    validação: |
      Check that target channel is provided.
      If content strategy exists, verify channel is listed in channel strategy.
    error_message: "Pre-condition failed: Target channel must be specified"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Content brief document generated using content-brief-tmpl.md template
    tipo: post-condition
    blocker: true
    validação: |
      Verify brief file exists at docs/marketing/briefs/{brief-slug}.md.
      Verify it follows the content-brief-tmpl.md structure.
    error_message: "Post-condition failed: Content brief document must be generated from template"

  - [ ] Brief contains objective, audience, key messages, tone, format, and CTA
    tipo: post-condition
    blocker: true
    validação: |
      Verify all required brief sections are present and non-empty:
      objective, audience, key messages, tone, format, CTA.
    error_message: "Post-condition failed: Brief missing required sections"

  - [ ] Brief is actionable for @copywriter without additional context
    tipo: post-condition
    blocker: true
    validação: |
      Verify brief provides sufficient context for @copywriter to produce
      content without needing to ask clarifying questions.
    error_message: "Post-condition failed: Brief must be self-contained and actionable for @copywriter"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Brief has a clear, measurable objective
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert objective is defined with a measurable outcome
      (e.g., "increase signups by 10%" not "get more signups").
    error_message: "Acceptance criterion not met: Brief must have a clear, measurable objective"

  - [ ] Key messages are prioritized (3-5 messages)
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert key messages exist (3-5), each prioritized by importance.
      Assert messages align with brand positioning.
    error_message: "Acceptance criterion not met: Key messages must be prioritized (3-5)"

  - [ ] CTA is defined with primary and optional secondary action
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert primary CTA is defined with clear action and destination.
      Secondary CTA is optional but recommended.
    error_message: "Acceptance criterion not met: CTA must define primary action"

  - [ ] Tone and style match channel guidelines
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert tone specification matches channel-specific guidelines
      from content strategy or brand guidelines.
    error_message: "Acceptance criterion not met: Tone and style must match channel guidelines"

  - [ ] Format and platform constraints are specified
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert format (text, video, carousel, etc.) is defined.
      Assert platform-specific constraints (character limits, dimensions, etc.) are documented.
    error_message: "Acceptance criterion not met: Format and platform constraints must be specified"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** content-brief-tmpl
  - **Purpose:** Template for content brief structure
  - **Source:** .lmas-core/development/templates/content-brief-tmpl.md

- **Tool:** brand-guidelines-loader
  - **Purpose:** Load and parse brand guidelines
  - **Source:** Project knowledge base

---

## Scripts

**Agent-specific code for this task:**

- **Script:** N/A
  - **Purpose:** This task is document-driven using templates
  - **Language:** N/A
  - **Location:** N/A

---

## Error Handling

**Strategy:** retry-with-guidance

**Common Errors:**

1. **Error:** Content Strategy Not Found
   - **Cause:** Content strategy has not been created yet
   - **Resolution:** Fall back to brand guidelines for brief creation
   - **Recovery:** Log warning, create brief with brand guidelines only, note strategy gap

2. **Error:** Template Not Found
   - **Cause:** content-brief-tmpl.md does not exist
   - **Resolution:** Create brief using inline structure matching template schema
   - **Recovery:** Generate brief with standard sections, flag missing template

3. **Error:** Channel Not in Strategy
   - **Cause:** Target channel not defined in content strategy
   - **Resolution:** Use general brand tone-of-voice for the channel
   - **Recovery:** Log warning, request channel addition to content strategy

4. **Error:** Topic Too Vague
   - **Cause:** Input topic is too broad to create a focused brief
   - **Resolution:** Use Interactive mode to narrow down the topic with user
   - **Recovery:** Ask clarifying questions about audience, angle, and desired outcome

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 10-20 min (estimated)
cost_estimated: $0.005-0.015
token_usage: ~4,000-10,000 tokens
```

**Optimization Notes:**
- Load content strategy and brand guidelines in parallel
- Use template pre-filling for recurring brief types
- Cache channel-specific tone guidelines for reuse

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - create-content-strategy (optional, recommended)
tags:
  - marketing
  - content-brief
  - planning
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research content brief best practices
checklists: []
execution_mode: interactive
---

# create-brief

Create a content brief for @copywriter (Muse) using the content-brief-tmpl.md template.

## Purpose

Generate a complete, actionable content brief that provides @copywriter with all necessary context, direction, and constraints to produce high-quality content. The brief bridges strategy and execution, translating strategic decisions into specific creative direction.

**Agent:** @content-strategist (Compass)

## Prerequisites

- Content strategy must exist OR at minimum, brand guidelines must be available
- Topic or campaign must be clearly defined
- Target channel must be specified

## Step-by-Step Execution

### Step 1: Load Content Strategy or Brand Guidelines

Load the content strategy from `docs/marketing/content-strategy.md`.

- If content strategy exists: extract pillars, funnel mapping, channel strategy, personas
- If only brand guidelines exist: extract positioning, tone-of-voice, values

**Checkpoint (Interactive):** Confirm which source documents are available.

### Step 2: Identify the Content Piece Needed

Define the specific content piece:

```yaml
content_piece:
  topic: "Specific topic or campaign name"
  channel: "Target platform"
  format: "Blog post / Social post / Video / Email / etc."
  funnel_stage: "TOFU / MOFU / BOFU"
  pillar: "Content pillar this belongs to"
```

### Step 3: Define Objective

State what this content should achieve. The objective must be:
- Specific (not vague)
- Measurable (tied to a KPI)
- Aligned with funnel stage

**Example:** "Generate 50 email signups from organic Instagram traffic within 2 weeks"

### Step 4: Identify Target Audience Segment

From content strategy personas or brand guidelines:

```yaml
audience:
  persona: "Primary persona name"
  demographics: "Key demographics"
  pain_point_addressed: "Which pain point this content addresses"
  awareness_level: "Unaware / Problem-aware / Solution-aware / Product-aware"
```

### Step 5: Define Key Messages (3-5, prioritized)

List key messages in priority order:

1. **Primary message:** The one thing the audience must take away
2. **Supporting message 1:** Reinforces primary message
3. **Supporting message 2:** Addresses objection or adds credibility
4. (Optional) **Supporting message 3-5:** Additional angles

### Step 6: Set Tone and Style per Channel Guidelines

Specify tone adaptations for the target channel:

```yaml
tone:
  base: "Brand tone-of-voice"
  channel_adaptation: "How it adapts for this specific channel"
  formality: "Formal / Semi-formal / Casual / Playful"
  vocabulary: "Technical / Accessible / Mixed"
  examples:
    do: ["Example phrase that fits"]
    dont: ["Example phrase that doesn't fit"]
```

### Step 7: Specify Format and Platform Constraints

Document technical and format requirements:

```yaml
format:
  type: "Blog post / Carousel / Reel / Email / etc."
  length: "Word count or duration"
  dimensions: "Image/video dimensions if applicable"
  character_limits: "Platform character limits"
  hashtag_strategy: "Number and type of hashtags"
  link_placement: "Where and how to place links"
```

### Step 8: Define CTA (Primary and Secondary)

```yaml
cta:
  primary:
    action: "What the user should do"
    destination: "Where the action leads (URL, page, etc.)"
    urgency: "Time-sensitive element if any"
  secondary:
    action: "Alternative action"
    destination: "Where it leads"
```

### Step 9: Add References and Inspiration

Include:
- Reference content pieces (internal or competitor)
- Visual inspiration
- Data points or statistics to include
- Source material

### Step 10: Set Constraints

```yaml
constraints:
  timeline: "Deadline for content delivery"
  budget: "Budget for production if applicable"
  legal: "Legal requirements (disclaimers, disclosures, etc.)"
  brand_restrictions: "Things to avoid per brand guidelines"
```

### Step 11: Define Success Metrics

How this content piece will be measured:

```yaml
success_metrics:
  primary_kpi: "Main metric"
  target: "Specific target number"
  measurement_period: "Timeframe for measurement"
  secondary_metrics:
    - "Metric 1"
    - "Metric 2"
```

### Step 12: Fill content-brief-tmpl.md

Compile all sections into the template and save to `docs/marketing/briefs/{brief-slug}.md`.

**Slug rules:**
- Convert to lowercase
- Replace spaces with hyphens
- Strip punctuation
- Example: "Instagram Launch Campaign Q1" becomes "instagram-launch-campaign-q1"

## Output Requirements

1. **ALWAYS** create brief file at: `docs/marketing/briefs/{brief-slug}.md`
2. **ALWAYS** use content-brief-tmpl.md as the structural template
3. Brief must be self-contained and actionable for @copywriter
4. All key messages must align with brand positioning
5. CTA must have at least a primary action defined

## Handoff
next_agent: @copywriter
next_command: *write-content
condition: Brief is complete and approved by @content-strategist
alternatives:
  - agent: @content-strategist, command: *create-content-strategy, condition: Content strategy does not exist yet
  - agent: @content-researcher, command: *market-research, condition: Additional research needed for brief
