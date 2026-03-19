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
task: marketResearchMkt()
responsável: Scout (Content Researcher)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: research_question
  tipo: string
  origem: User Input / @content-strategist / @marketing-chief
  obrigatório: true
  validação: Must be a clearly defined research question or topic

- campo: brand_context
  tipo: object
  origem: Project Knowledge Base
  obrigatório: true
  validação: Must contain brand positioning and industry context

- campo: scope
  tipo: string
  origem: User Input
  obrigatório: false
  validação: "broad" or "focused" (default: "broad")

**Saída:**
- campo: research_report
  tipo: object
  destino: File (docs/marketing/research/{research-slug}-report.md)
  persistido: true

- campo: key_findings
  tipo: array
  destino: File (docs/marketing/research/{research-slug}-report.md)
  persistido: true

- campo: recommendations
  tipo: array
  destino: File (docs/marketing/research/{research-slug}-report.md)
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Research question is clearly defined and scoped
    tipo: pre-condition
    blocker: true
    validação: |
      Check that research question input is provided and non-empty.
      Verify the question is specific enough to guide research methodology.
    error_message: "Pre-condition failed: Research question must be clearly defined and scoped"

  - [ ] Brand context is available for positioning research within industry
    tipo: pre-condition
    blocker: true
    validação: |
      Check brand context includes industry, target market, and current positioning.
      This is needed to contextualize findings.
    error_message: "Pre-condition failed: Brand context must be available with industry and positioning"

  - [ ] Research scope is defined (broad or focused)
    tipo: pre-condition
    blocker: false
    validação: |
      Check if scope parameter is provided.
      If not, default to "broad" and log the default.
    error_message: "Warning: Research scope not specified, defaulting to 'broad'"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Research report generated with findings, analysis, and recommendations
    tipo: post-condition
    blocker: true
    validação: |
      Verify report file exists at docs/marketing/research/{research-slug}-report.md.
      Verify it contains: methodology, findings, analysis, opportunities, recommendations.
    error_message: "Post-condition failed: Research report must contain all required sections"

  - [ ] Findings are evidence-based with cited sources
    tipo: post-condition
    blocker: true
    validação: |
      Verify each finding references a data source or methodology.
      No unsourced claims in the findings section.
    error_message: "Post-condition failed: All findings must be evidence-based with cited sources"

  - [ ] Recommendations are prioritized by impact and actionable
    tipo: post-condition
    blocker: true
    validação: |
      Verify recommendations are ordered by impact (high/medium/low).
      Verify each recommendation includes a clear action step.
    error_message: "Post-condition failed: Recommendations must be prioritized and actionable"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Research methodology is documented and appropriate for the question
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert methodology section exists with approach, sources, and limitations.
    error_message: "Acceptance criterion not met: Research methodology must be documented"

  - [ ] Market size, growth, and segmentation data is included (if broad scope)
    tipo: acceptance-criterion
    blocker: false
    validação: |
      If scope is "broad", assert market overview section exists.
      If scope is "focused", this is optional.
    error_message: "Acceptance criterion not met: Broad scope requires market size and segmentation data"

  - [ ] Competitor landscape is mapped with at least 3 competitors
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert competitor section includes at least 3 competitors
      with positioning and channel analysis.
    error_message: "Acceptance criterion not met: Competitor landscape must map at least 3 competitors"

  - [ ] Trends and patterns are identified with supporting evidence
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert trends section exists with at least 2 identified trends
      and supporting data points.
    error_message: "Acceptance criterion not met: Trends must be identified with supporting evidence"

  - [ ] Opportunities and threats are mapped for the brand
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert opportunities and threats sections exist,
      each with at least 2 items contextualized to the brand.
    error_message: "Acceptance criterion not met: Opportunities and threats must be mapped"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** web-search
  - **Purpose:** Search for industry reports, trends, and competitor data
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

1. **Error:** Research Question Too Broad
   - **Cause:** Research question is too vague to produce focused findings
   - **Resolution:** Use Interactive mode to narrow the question with user
   - **Recovery:** Break into sub-questions and address each systematically

2. **Error:** Insufficient Data Sources
   - **Cause:** Limited publicly available data for the specific market/niche
   - **Resolution:** Expand search to adjacent markets or use proxy indicators
   - **Recovery:** Document data limitations clearly, provide qualitative analysis

3. **Error:** Brand Context Incomplete
   - **Cause:** Brand context missing industry or target market information
   - **Resolution:** Request additional brand context from user or @marketing-chief
   - **Recovery:** Use available context, flag assumptions made

4. **Error:** Conflicting Data Sources
   - **Cause:** Different sources report conflicting market data
   - **Resolution:** Cross-reference with additional sources, note discrepancies
   - **Recovery:** Present range of estimates with confidence levels

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 30-60 min (estimated)
cost_estimated: $0.015-0.040
token_usage: ~10,000-25,000 tokens
```

**Optimization Notes:**
- Use parallel web searches for different research dimensions
- Cache industry data for reuse across research tasks
- Use focused scope to reduce research time when full breadth is not needed

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - N/A
tags:
  - marketing
  - research
  - market-analysis
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research market analysis methodologies and frameworks
checklists: []
execution_mode: interactive
---

# market-research-mkt

Conduct market research for marketing decisions — niche analysis, competitor landscape, trends, and opportunities.

## Purpose

Produce an evidence-based market research report that informs marketing strategy and content decisions. The research covers market size, competitor positioning, emerging trends, and actionable opportunities for the brand.

**Agent:** @content-researcher (Scout)

## Prerequisites

- Research question must be clearly defined and scoped
- Brand context must be available (industry, positioning, target market)

## Step-by-Step Execution

### Step 1: Define Research Scope and Methodology

Document the research approach:

```yaml
research_plan:
  question: "The primary research question"
  scope: "broad or focused"
  methodology:
    - "Desk research (industry reports, publications)"
    - "Social listening (platform trends, conversations)"
    - "Search trend analysis (keyword volumes, seasonal patterns)"
    - "Competitor content analysis"
  limitations:
    - "Data availability constraints"
    - "Time period covered"
```

**Checkpoint (Interactive):** Confirm research scope and methodology with user.

### Step 2: Identify Primary Sources

Locate and catalog primary data sources:

- Industry reports (market size, growth projections)
- Social media listening data (sentiment, trending topics)
- Search trends (Google Trends, keyword research)
- Platform analytics (if available)

### Step 3: Identify Secondary Sources

Locate and catalog secondary data sources:

- Competitor published content (blogs, social media, newsletters)
- Academic papers and white papers
- News articles and press releases
- Community forums and discussions

### Step 4: Collect Market Data

Gather data on:

```yaml
market_data:
  market_size: "Current market value"
  growth_rate: "YoY growth percentage"
  segments:
    - name: "Segment 1"
      size: "Percentage of market"
      growth: "Growing/Stable/Declining"
    - name: "Segment 2"
      size: "Percentage of market"
      growth: "Growing/Stable/Declining"
  key_drivers: ["Driver 1", "Driver 2"]
  key_barriers: ["Barrier 1", "Barrier 2"]
```

### Step 5: Analyze Competitor Landscape

For each major competitor (minimum 3):

```yaml
competitor:
  name: "Competitor Name"
  positioning: "How they position themselves"
  channels: ["Channel 1", "Channel 2"]
  content_frequency: "Posts per week/month"
  strengths: ["Strength 1", "Strength 2"]
  weaknesses: ["Weakness 1", "Weakness 2"]
  notable_content: "Best-performing content examples"
```

**Checkpoint (Interactive):** Confirm competitor list is comprehensive.

### Step 6: Identify Trends and Patterns

Analyze collected data for:

- Emerging content trends in the niche
- Audience behavior shifts
- Platform algorithm changes affecting reach
- Seasonal patterns
- Technology trends impacting content consumption

Document each trend with supporting evidence.

### Step 7: Map Opportunities for the Brand

Based on findings, identify:

```yaml
opportunities:
  - opportunity: "Description"
    impact: "high/medium/low"
    effort: "high/medium/low"
    evidence: "Data supporting this opportunity"
    timeframe: "short-term/medium-term/long-term"
```

### Step 8: Identify Threats and Risks

```yaml
threats:
  - threat: "Description"
    severity: "high/medium/low"
    probability: "high/medium/low"
    mitigation: "Suggested mitigation approach"
    evidence: "Data supporting this threat"
```

### Step 9: Formulate Recommendations Prioritized by Impact

Synthesize findings into actionable recommendations:

```yaml
recommendations:
  - priority: 1
    recommendation: "What to do"
    rationale: "Why (based on findings)"
    impact: "Expected impact"
    dependencies: ["What's needed"]
    timeline: "When to implement"
```

**Rule:** Recommendations must be ordered by impact (highest first).

### Step 10: Document Findings in research-report-tmpl.md

Compile all sections into `docs/marketing/research/{research-slug}-report.md`.

**Slug rules:**
- Convert to lowercase
- Replace spaces with hyphens
- Strip punctuation
- Prefix with date: `YYYY-MM-DD-{slug}`
- Example: "Q1 Social Media Trends" becomes "2026-03-14-q1-social-media-trends"

### Step 11: Present Key Findings and Actionable Insights

Create an executive summary highlighting:

1. Top 3 findings
2. Top 3 opportunities
3. Top 3 recommendations
4. Critical risks (if any)

## Output Requirements

1. **ALWAYS** create report at: `docs/marketing/research/{research-slug}-report.md`
2. **ALWAYS** include methodology, findings, analysis, opportunities, threats, and recommendations
3. All findings must cite their data source
4. Recommendations must be prioritized by impact
5. Executive summary must not exceed 1 page

## Handoff
next_agent: @content-strategist
next_command: *create-content-strategy
condition: Research report is complete and findings are ready for strategy input
alternatives:
  - agent: @content-researcher, command: *competitor-analysis, condition: Deeper competitor analysis is needed
  - agent: @marketing-chief, command: *review-research, condition: Research needs executive review
