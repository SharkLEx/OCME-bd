<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Short-form copy with clear brief and established brand voice

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** Long-form content, new channels, or complex messaging

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Institutional content, multi-channel campaigns, high-stakes copy

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: writeCopy()
responsável: Muse (Copywriter)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: content_brief_path
  tipo: string
  origem: User Input
  obrigatório: true
  validação: Must point to a valid content brief file (content-brief-tmpl.md format)

- campo: brand_guidelines_path
  tipo: string
  origem: Knowledge Base
  obrigatório: true
  validação: Must point to brand-guidelines.md

- campo: tone_of_voice_path
  tipo: string
  origem: Knowledge Base
  obrigatório: true
  validação: Must point to tone-of-voice.md

**Saída:**
- campo: copy_package
  tipo: object
  destino: File (content output directory)
  persistido: true

- campo: headline_variants
  tipo: array
  destino: Return value (within copy_package)
  persistido: true

- campo: body_copy
  tipo: string
  destino: Return value (within copy_package)
  persistido: true

- campo: cta_variants
  tipo: array
  destino: Return value (within copy_package)
  persistido: true

- campo: recommended_combination
  tipo: object
  destino: Return value (within copy_package)
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Content brief exists with objective, target audience, and key messages defined
    tipo: pre-condition
    blocker: true
    validação: |
      Check content brief file exists and contains objective, target_audience, and key_messages sections
    error_message: "Pre-condition failed: Content brief missing or incomplete (requires objective, target audience, key messages)"

  - [ ] brand-guidelines.md is accessible
    tipo: pre-condition
    blocker: true
    validação: |
      Check brand-guidelines.md exists at brand_guidelines_path
    error_message: "Pre-condition failed: brand-guidelines.md not found"

  - [ ] tone-of-voice.md is accessible
    tipo: pre-condition
    blocker: true
    validação: |
      Check tone-of-voice.md exists at tone_of_voice_path
    error_message: "Pre-condition failed: tone-of-voice.md not found"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Copy package contains headlines, body, CTAs, and recommended combination
    tipo: post-condition
    blocker: true
    validação: |
      Verify copy_package has all required sections with non-empty content
    error_message: "Post-condition failed: Copy package incomplete"

  - [ ] Headline variants count is 3-5
    tipo: post-condition
    blocker: true
    validação: |
      Verify headline_variants array length is between 3 and 5
    error_message: "Post-condition failed: Must have 3-5 headline variants"

  - [ ] CTA variants count is 2-3
    tipo: post-condition
    blocker: true
    validação: |
      Verify cta_variants array length is between 2 and 3
    error_message: "Post-condition failed: Must have 2-3 CTA variants"

  - [ ] Self-review against brand guidelines completed
    tipo: post-condition
    blocker: true
    validação: |
      Verify self_review section exists in output with brand alignment notes
    error_message: "Post-condition failed: Self-review not completed"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Copy addresses the brief's objective and key messages
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert copy content addresses each key message from brief
    error_message: "Acceptance criterion not met: Copy does not address brief objective or key messages"

  - [ ] Tone matches channel requirements from brief
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert tone adaptation matches specified channel
    error_message: "Acceptance criterion not met: Tone not adapted to channel"

  - [ ] Copy is within format constraints (character limits, word counts)
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert all copy elements meet format constraints from brief
    error_message: "Acceptance criterion not met: Copy exceeds format constraints"

  - [ ] Recommended combination clearly identified with rationale
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert recommended_combination includes headline + body + CTA with explanation
    error_message: "Acceptance criterion not met: Recommended combination not identified"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** content-brief-template
  - **Purpose:** Reference template for content brief validation
  - **Source:** .lmas-core/development/templates/content-brief-tmpl.md

- **Tool:** brand-guidelines
  - **Purpose:** Brand voice, positioning, and messaging framework reference
  - **Source:** knowledge-base/brand-guidelines.md

- **Tool:** tone-of-voice
  - **Purpose:** Voice attributes and tone variations by channel
  - **Source:** knowledge-base/tone-of-voice.md

---

## Scripts

**Agent-specific code for this task:**

- **Script:** N/A
  - **Purpose:** This task is executed by @copywriter using creative writing capabilities
  - **Language:** N/A
  - **Location:** N/A

---

## Error Handling

**Strategy:** retry-with-feedback

**Common Errors:**

1. **Error:** Content Brief Incomplete
   - **Cause:** Brief missing objective, target_audience, or key_messages
   - **Resolution:** Return brief to requester with specific missing fields listed
   - **Recovery:** Abort with detailed missing fields report

2. **Error:** Brand Guidelines Not Found
   - **Cause:** brand-guidelines.md does not exist or path is incorrect
   - **Resolution:** Locate or create brand-guidelines.md
   - **Recovery:** Abort with instruction to ensure brand-guidelines.md exists

3. **Error:** Channel Format Unknown
   - **Cause:** Brief specifies a channel without known format constraints
   - **Resolution:** Research channel constraints or request clarification
   - **Recovery:** Proceed with general best practices, flag for review

4. **Error:** Tone Mismatch Detected in Self-Review
   - **Cause:** Written copy does not match tone-of-voice.md for specified channel
   - **Resolution:** Revise copy to match tone guidelines
   - **Recovery:** Automatically revise and re-run self-review (max 2 iterations)

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 10-20 min (estimated)
cost_estimated: $0.005-0.020
token_usage: ~5,000-15,000 tokens
```

**Optimization Notes:**
- YOLO mode reduces to 5-8 min for short-form copy with clear brief
- Batch headline generation improves variant quality
- Self-review adds 3-5 min but significantly reduces revision cycles

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - content-brief-tmpl.md
  - brand-guidelines.md
  - tone-of-voice.md
tags:
  - marketing
  - copywriting
  - content-creation
  - brand-voice
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research copywriting best practices and channel formats
checklists:
  - brand-alignment-checklist.md
execution_mode: interactive
---

# write-copy

Create copy from content brief following brand guidelines and tone of voice.

## Purpose

Produce a complete copy package (headlines, body copy, CTAs) from a content brief. Ensures all copy aligns with brand guidelines and tone of voice for the specified channel. Delivers multiple variants with a recommended combination for the requester or @content-reviewer.

## Prerequisites

- Content brief exists with objective, target audience, and key messages defined
- brand-guidelines.md is accessible in knowledge base
- tone-of-voice.md is accessible in knowledge base

## Step-by-Step Instructions

### Step 1: Load and Analyze Content Brief

1. Read the content brief at `content_brief_path`
2. Extract and validate required fields:
   - **Objective:** What the content aims to achieve
   - **Target audience:** Who the content is for
   - **Key messages:** Core messages to communicate (prioritized)
   - **Channel:** Where the content will be published
   - **Format:** Content format (article, social post, email, landing page, etc.)
   - **Constraints:** Character limits, word counts, format requirements
3. If any required field is missing, ABORT with specific missing fields

### Step 2: Load Brand Guidelines and Tone of Voice

1. Read `brand-guidelines.md` from knowledge base
2. Extract brand voice attributes, messaging pillars, and do's/don'ts
3. Read `tone-of-voice.md` from knowledge base
4. Identify the tone variation for the specified channel
5. Note any channel-specific language preferences

### Step 3: Identify Channel and Format Constraints

1. Map the channel to known format constraints:
   - **Blog/Article:** No strict limit, SEO considerations
   - **Email:** Subject line ~50 chars, preheader ~100 chars, body varies
   - **Social (Instagram):** Caption up to 2,200 chars, first line is hook
   - **Social (LinkedIn):** Up to 3,000 chars, professional tone
   - **Social (Twitter/X):** 280 chars per post
   - **Landing page:** Headline ~10 words, subhead ~20 words, body modular
   - **WhatsApp:** Short, conversational, under 500 chars
2. If channel has specific constraints from brief, use those instead
3. Document active constraints for self-review

### Step 4: Write Headline Variants (3-5 options)

1. Generate 3-5 headline variants based on brief objective
2. Each variant should take a different approach:
   - **Benefit-led:** Focus on what the audience gains
   - **Problem-led:** Address the pain point
   - **Curiosity-led:** Create intrigue to read more
   - **Direct:** Straightforward value proposition
   - **Social proof:** Leverage credibility or results
3. Ensure all variants fit within channel constraints
4. Label each variant with its approach type

### Step 5: Write Body Copy

1. Follow the brief's key messages in priority order
2. Structure body copy according to channel format:
   - **Blog:** Introduction → Key points → Conclusion
   - **Email:** Hook → Value → CTA
   - **Social:** Hook → Context → CTA
   - **Landing page:** Hero → Benefits → Proof → CTA
3. Incorporate brand messaging pillars naturally
4. Maintain specified tone throughout
5. Respect word count/character constraints

### Step 6: Write CTA Variants (2-3 options)

1. Generate 2-3 CTA variants aligned with brief objective
2. Each CTA should:
   - Use action verbs
   - Create sense of urgency or value
   - Match the channel's CTA conventions
3. Variants should range from conservative to bold

### Step 7: Adapt Tone to Channel Requirements

1. Review all written copy against tone-of-voice.md
2. Adjust formality level for channel:
   - LinkedIn: more professional
   - Instagram: more casual, visual language
   - Email: conversational but purposeful
   - Blog: educational, authoritative
3. Ensure brand voice is consistent across all elements

### Step 8: Self-Review Against Brand Guidelines

1. Read through all copy elements together
2. Check against brand do's and don'ts
3. Verify key messages from brief are addressed
4. Confirm tone matches channel requirements
5. Verify format constraints are met
6. If issues found, revise (max 2 self-review iterations)
7. Record self-review findings

### Step 9: Present Output with Recommended Combination

1. Compile the copy package:
   - All headline variants (labeled by approach)
   - Body copy
   - All CTA variants
   - Self-review notes
2. Select recommended combination:
   - Best headline for the objective
   - Body copy
   - Best CTA for the channel
3. Explain rationale for recommendation
4. Persist copy package to output directory

## Output Requirements

1. **ALWAYS** deliver 3-5 headline variants with approach labels
2. **ALWAYS** deliver body copy following brief structure
3. **ALWAYS** deliver 2-3 CTA variants
4. **ALWAYS** include a recommended combination with rationale
5. **ALWAYS** include self-review notes
6. All copy **MUST** respect channel format constraints

## Copy Package Format

```yaml
copy_package:
  brief_reference: "{content_brief_path}"
  channel: "{channel}"
  format: "{format}"

  headlines:
    - text: "Headline text"
      approach: "benefit-led"
      char_count: 45
    # ... (3-5 variants)

  body:
    text: "Full body copy text..."
    word_count: 250
    key_messages_covered:
      - "Message 1"
      - "Message 2"

  ctas:
    - text: "CTA text"
      style: "bold"
    # ... (2-3 variants)

  recommended:
    headline: 1  # index
    cta: 2       # index
    rationale: "Explanation of why this combination works best"

  self_review:
    brand_aligned: true
    tone_matched: true
    constraints_met: true
    notes: "Self-review findings..."
```

## Handoff
next_agent: @content-reviewer
next_command: *review-content
condition: Copy package complete
alternatives:
  - agent: @marketing-chief, command: *brand-review, condition: Self-review flags brand concerns
  - agent: @copywriter, command: *ad-copy, condition: Campaign requires paid media variants
