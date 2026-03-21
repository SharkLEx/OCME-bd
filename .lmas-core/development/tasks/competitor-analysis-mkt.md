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
task: competitorAnalysisMkt()
responsável: Scout (Content Researcher)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: competitor_list
  tipo: array
  origem: User Input / @content-strategist / @marketing-chief
  obrigatório: true
  validação: Non-empty array with 1-5 competitor names or brands

- campo: analysis_dimensions
  tipo: array
  origem: User Input
  obrigatório: false
  validação: Default dimensions if not provided — positioning, channels, content, engagement

- campo: brand_context
  tipo: object
  origem: Project Knowledge Base
  obrigatório: true
  validação: Must contain brand positioning for comparison baseline

**Saída:**
- campo: competitor_report
  tipo: object
  destino: File (docs/marketing/research/competitor-analysis-{slug}.md)
  persistido: true

- campo: comparison_matrix
  tipo: object
  destino: File (docs/marketing/research/competitor-analysis-{slug}.md)
  persistido: true

- campo: positioning_recommendations
  tipo: array
  destino: File (docs/marketing/research/competitor-analysis-{slug}.md)
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] At least 1 competitor is identified in the competitor list
    tipo: pre-condition
    blocker: true
    validação: |
      Check competitor_list input is provided and contains at least 1 entry.
      Recommended: 3-5 competitors for meaningful comparison.
    error_message: "Pre-condition failed: At least 1 competitor must be identified"

  - [ ] Brand context is available for comparison baseline
    tipo: pre-condition
    blocker: true
    validação: |
      Check brand context includes positioning, channels, and content approach.
      This serves as the baseline for competitor comparison.
    error_message: "Pre-condition failed: Brand context must be available for comparison baseline"

  - [ ] Analysis dimensions are defined or defaults accepted
    tipo: pre-condition
    blocker: false
    validação: |
      Check if analysis_dimensions parameter is provided.
      If not, use defaults: positioning, channels, content types, engagement, tone.
    error_message: "Warning: Analysis dimensions not specified, using defaults"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Competitor report generated with per-competitor analysis and comparison matrix
    tipo: post-condition
    blocker: true
    validação: |
      Verify report file exists at docs/marketing/research/competitor-analysis-{slug}.md.
      Verify it contains individual competitor profiles and comparison matrix.
    error_message: "Post-condition failed: Competitor report must include per-competitor analysis and comparison matrix"

  - [ ] Each competitor has been analyzed across all defined dimensions
    tipo: post-condition
    blocker: true
    validação: |
      Verify each competitor entry covers all analysis dimensions.
      No dimension should be empty or marked as "N/A" without explanation.
    error_message: "Post-condition failed: All competitors must be analyzed across all defined dimensions"

  - [ ] Gaps, opportunities, and positioning recommendations are documented
    tipo: post-condition
    blocker: true
    validação: |
      Verify report includes gap analysis, opportunities section,
      and positioning recommendations with rationale.
    error_message: "Post-condition failed: Report must include gaps, opportunities, and positioning recommendations"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Each competitor is profiled with positioning, channels, content types, and frequency
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert each competitor profile contains: positioning statement,
      active channels, content types, and posting frequency.
    error_message: "Acceptance criterion not met: Each competitor must be fully profiled"

  - [ ] Comparison matrix enables side-by-side evaluation across all dimensions
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert comparison matrix is a structured table with competitors as columns
      and dimensions as rows (or vice versa).
    error_message: "Acceptance criterion not met: Comparison matrix must enable side-by-side evaluation"

  - [ ] Top-performing content per competitor is identified with engagement evidence
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert each competitor has at least 1 top-performing content example
      with engagement data or qualitative evidence.
    error_message: "Acceptance criterion not met: Top-performing content must be identified per competitor"

  - [ ] Gaps and opportunities are contextualized to the brand
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert gaps and opportunities reference the brand's current positioning
      and explain how the brand can capitalize.
    error_message: "Acceptance criterion not met: Gaps and opportunities must be contextualized to the brand"

  - [ ] Positioning recommendations are actionable with clear rationale
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert at least 3 positioning recommendations exist,
      each with rationale based on competitor analysis findings.
    error_message: "Acceptance criterion not met: Positioning recommendations must be actionable with rationale"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** web-search
  - **Purpose:** Research competitor public presence, content, and positioning
  - **Source:** Web search integration

- **Tool:** research-report-tmpl
  - **Purpose:** Template for research report structure
  - **Source:** .lmas-core/development/templates/research-report-tmpl.md

---

## Scripts

**Agent-specific code for this task:**

- **Script:** N/A
  - **Purpose:** This task is research and analysis-driven
  - **Language:** N/A
  - **Location:** N/A

---

## Error Handling

**Strategy:** retry-with-fallback

**Common Errors:**

1. **Error:** Competitor Not Found
   - **Cause:** Competitor name is ambiguous or not publicly visible
   - **Resolution:** Verify competitor identity with user, try alternative names
   - **Recovery:** Skip unfindable competitor, document limitation, suggest alternatives

2. **Error:** Insufficient Public Data
   - **Cause:** Competitor has limited public content or presence
   - **Resolution:** Expand search to press coverage, review sites, social mentions
   - **Recovery:** Document limited data availability, provide qualitative assessment

3. **Error:** Too Many Competitors
   - **Cause:** More than 5 competitors provided, exceeding manageable analysis depth
   - **Resolution:** Ask user to prioritize top 3-5 for deep analysis
   - **Recovery:** Provide deep analysis for top 5, brief overview for remainder

4. **Error:** Brand Context Missing
   - **Cause:** Brand positioning not defined, cannot establish comparison baseline
   - **Resolution:** Request brand guidelines from user or @marketing-chief
   - **Recovery:** Abort with clear message about required brand context

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 25-50 min (estimated)
cost_estimated: $0.010-0.035
token_usage: ~8,000-20,000 tokens
```

**Optimization Notes:**
- Analyze competitors in parallel when possible
- Reuse market research data if available from market-research-mkt task
- Focus on publicly available data to avoid delays

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - market-research-mkt (optional, provides market context)
tags:
  - marketing
  - research
  - competitor-analysis
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research competitor analysis frameworks and methodologies
checklists: []
execution_mode: interactive
---

# competitor-analysis-mkt

Conduct a detailed competitor analysis covering positioning, channels, content frequency, strengths, and weaknesses.

## Purpose

Produce a structured competitor analysis report that maps the competitive landscape, identifies gaps and opportunities, and provides actionable positioning recommendations. This analysis informs content strategy and differentiation decisions.

**Agent:** @content-researcher (Scout)

## Prerequisites

- At least 1 competitor must be identified (recommended: 3-5)
- Brand context must be available for comparison baseline

## Step-by-Step Execution

### Step 1: Define Analysis Scope and Competitors

Document the analysis parameters:

```yaml
analysis_scope:
  competitors:
    - "Competitor 1 — brief description"
    - "Competitor 2 — brief description"
    - "Competitor 3 — brief description"
  dimensions:
    - "Positioning and messaging"
    - "Active channels and content types"
    - "Posting frequency"
    - "Tone of voice and visual identity"
    - "Top-performing content"
    - "Strengths and weaknesses"
  brand_baseline: "Our brand positioning for comparison"
```

**Checkpoint (Interactive):** Confirm competitor list and analysis dimensions with user.

### Step 2: Analyze Each Competitor

For each competitor, conduct a thorough analysis:

#### 2a. Analyze Positioning and Messaging

```yaml
positioning:
  tagline: "Their tagline or value proposition"
  key_messages: ["Message 1", "Message 2", "Message 3"]
  differentiation: "What makes them different"
  target_audience: "Who they're targeting"
```

#### 2b. Map Active Channels and Content Types

```yaml
channels:
  - name: "Channel name"
    followers: "Follower count if available"
    content_types: ["Type 1", "Type 2"]
    primary_focus: "Main purpose of this channel"
```

#### 2c. Measure Posting Frequency

```yaml
frequency:
  channel_1: "X posts per week"
  channel_2: "X posts per week"
  overall: "Total content output per week/month"
  consistency: "Regular / Irregular / Seasonal"
```

#### 2d. Evaluate Tone of Voice and Visual Identity

```yaml
brand_expression:
  tone: "Formal / Casual / Playful / Authoritative / etc."
  visual_style: "Minimalist / Colorful / Corporate / etc."
  consistency: "Consistent / Inconsistent across channels"
  notable_elements: "Distinctive brand elements"
```

#### 2e. Identify Top-Performing Content

```yaml
top_content:
  - type: "Content type"
    topic: "Topic"
    engagement: "Engagement metrics or qualitative assessment"
    why_it_works: "Analysis of success factors"
```

#### 2f. Note Strengths and Weaknesses

```yaml
strengths:
  - "Strength 1 — evidence"
  - "Strength 2 — evidence"
weaknesses:
  - "Weakness 1 — evidence"
  - "Weakness 2 — evidence"
```

### Step 3: Create Comparison Matrix

Build a structured comparison table:

| Dimension | Our Brand | Competitor 1 | Competitor 2 | Competitor 3 |
|-----------|-----------|--------------|--------------|--------------|
| Positioning | ... | ... | ... | ... |
| Primary Channel | ... | ... | ... | ... |
| Content Frequency | ... | ... | ... | ... |
| Tone of Voice | ... | ... | ... | ... |
| Engagement Level | ... | ... | ... | ... |
| Content Quality | ... | ... | ... | ... |
| Visual Identity | ... | ... | ... | ... |

### Step 4: Identify Gaps and Opportunities vs Competitors

Based on the comparison matrix:

```yaml
gaps:
  - gap: "What competitors are doing that we're not"
    competitors_doing_it: ["Competitor 1", "Competitor 3"]
    priority: "high/medium/low"
    addressable: true/false

opportunities:
  - opportunity: "Where we can differentiate or lead"
    evidence: "Data supporting this opportunity"
    effort: "high/medium/low"
    impact: "high/medium/low"
```

### Step 5: Identify Threats from Competitor Strengths

```yaml
threats:
  - threat: "Competitor advantage that threatens our position"
    competitor: "Which competitor"
    severity: "high/medium/low"
    our_response: "How we should respond"
```

### Step 6: Formulate Positioning Recommendations

Synthesize analysis into actionable positioning recommendations:

```yaml
recommendations:
  - priority: 1
    recommendation: "Positioning recommendation"
    rationale: "Based on competitor analysis finding X"
    competitors_affected: ["Competitor 1", "Competitor 2"]
    implementation: "How to implement"
    timeline: "When to implement"
```

**Rule:** Minimum 3 recommendations, ordered by priority.

### Step 7: Document in research-report-tmpl.md

Compile into `docs/marketing/research/competitor-analysis-{slug}.md`:

1. Executive Summary
2. Methodology
3. Individual Competitor Profiles
4. Comparison Matrix
5. Gaps and Opportunities
6. Threats
7. Positioning Recommendations
8. Appendix: Raw Data and Sources

**Slug rules:**
- Convert to lowercase
- Replace spaces with hyphens
- Strip punctuation
- Example: "SaaS Competitors Q1 2026" becomes "saas-competitors-q1-2026"

## Output Requirements

1. **ALWAYS** create report at: `docs/marketing/research/competitor-analysis-{slug}.md`
2. **ALWAYS** include comparison matrix as a structured table
3. Each competitor must have a complete profile across all dimensions
4. Recommendations must be prioritized and actionable
5. All claims must reference observable evidence

## Handoff
next_agent: @content-strategist
next_command: *create-content-strategy
condition: Competitor analysis is complete and ready for strategy input
alternatives:
  - agent: @content-researcher, command: *market-research, condition: Broader market context needed
  - agent: @marketing-chief, command: *review-research, condition: Analysis needs executive review
