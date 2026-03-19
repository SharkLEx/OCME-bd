<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Standard ad formats with clear campaign plan and established brand

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** New platforms, complex campaigns, or custom ad formats

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Multi-platform campaigns, large budgets, A/B testing strategies

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: adCopy()
responsável: Muse (Copywriter)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: campaign_plan_path
  tipo: string
  origem: User Input
  obrigatório: true
  validação: Must point to a valid campaign plan file

- campo: target_platform
  tipo: string
  origem: Campaign plan or User Input
  obrigatório: true
  validação: Must be one of meta_ads, google_ads, linkedin_ads, tiktok_ads

- campo: character_limits
  tipo: object
  origem: Platform defaults or User Input
  obrigatório: false
  validação: If provided, must have headline_max and description_max fields

- campo: brand_guidelines_path
  tipo: string
  origem: Knowledge Base
  obrigatório: true
  validação: Must point to brand-guidelines.md

**Saída:**
- campo: ad_copy_package
  tipo: object
  destino: File (content output directory)
  persistido: true

- campo: headline_variants
  tipo: array
  destino: Return value (within ad_copy_package)
  persistido: true

- campo: description_variants
  tipo: array
  destino: Return value (within ad_copy_package)
  persistido: true

- campo: cta_options
  tipo: array
  destino: Return value (within ad_copy_package)
  persistido: true

- campo: ad_combinations
  tipo: array
  destino: Return value (within ad_copy_package)
  persistido: true

- campo: recommended_combination
  tipo: object
  destino: Return value (within ad_copy_package)
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Campaign plan exists and specifies platform and format
    tipo: pre-condition
    blocker: true
    validação: |
      Check campaign plan file exists and contains platform and ad_format fields
    error_message: "Pre-condition failed: Campaign plan must specify platform and ad format"

  - [ ] brand-guidelines.md is accessible
    tipo: pre-condition
    blocker: true
    validação: |
      Check brand-guidelines.md exists at brand_guidelines_path
    error_message: "Pre-condition failed: brand-guidelines.md not found"

  - [ ] Target platform is supported (meta_ads, google_ads, linkedin_ads, tiktok_ads)
    tipo: pre-condition
    blocker: true
    validação: |
      Verify target_platform is one of the supported platforms
    error_message: "Pre-condition failed: Unsupported platform. Supported: meta_ads, google_ads, linkedin_ads, tiktok_ads"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Ad copy package contains headlines, descriptions, CTAs, and combinations
    tipo: post-condition
    blocker: true
    validação: |
      Verify ad_copy_package has all required sections with non-empty content
    error_message: "Post-condition failed: Ad copy package incomplete"

  - [ ] All headline variants within platform character limits
    tipo: post-condition
    blocker: true
    validação: |
      Verify every headline variant respects platform-specific character limit
    error_message: "Post-condition failed: Headline variants exceed character limits"

  - [ ] All description variants within platform character limits
    tipo: post-condition
    blocker: true
    validação: |
      Verify every description variant respects platform-specific character limit
    error_message: "Post-condition failed: Description variants exceed character limits"

  - [ ] At least 3 complete ad combinations generated
    tipo: post-condition
    blocker: true
    validação: |
      Verify ad_combinations array has at least 3 entries
    error_message: "Post-condition failed: Must have at least 3 ad combinations"

  - [ ] Recommended combination marked with rationale
    tipo: post-condition
    blocker: true
    validação: |
      Verify recommended_combination exists with headline, description, cta, and rationale
    error_message: "Post-condition failed: Recommended combination not marked"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] 5-10 headline variants generated within platform limits
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert headline_variants count is between 5 and 10, all within limits
    error_message: "Acceptance criterion not met: Must have 5-10 headline variants within limits"

  - [ ] 3-5 description variants generated within platform limits
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert description_variants count is between 3 and 5, all within limits
    error_message: "Acceptance criterion not met: Must have 3-5 description variants within limits"

  - [ ] CTA options match platform available buttons/actions
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert cta_options are valid for target platform
    error_message: "Acceptance criterion not met: CTA options not valid for target platform"

  - [ ] 3 complete ad combinations with recommended marked
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert 3 ad combinations exist and one is marked as recommended
    error_message: "Acceptance criterion not met: 3 combinations with recommendation required"

  - [ ] All copy aligns with brand guidelines
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert copy passed brand alignment self-review
    error_message: "Acceptance criterion not met: Copy does not align with brand guidelines"
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** campaign-plan-reference
  - **Purpose:** Source of campaign objectives, audience, and strategy
  - **Source:** Campaign plan file (varies per campaign)

- **Tool:** brand-guidelines
  - **Purpose:** Brand voice, positioning, and messaging framework reference
  - **Source:** knowledge-base/brand-guidelines.md

- **Tool:** platform-specs
  - **Purpose:** Character limits and format specs per ad platform
  - **Source:** Embedded in this task (see Step 2)

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

1. **Error:** Campaign Plan Missing Platform
   - **Cause:** Campaign plan does not specify target platform or ad format
   - **Resolution:** Return campaign plan to creator for platform specification
   - **Recovery:** Abort with specific missing fields listed

2. **Error:** Unsupported Platform
   - **Cause:** target_platform is not in the supported list
   - **Resolution:** Use one of: meta_ads, google_ads, linkedin_ads, tiktok_ads
   - **Recovery:** Abort with supported platform list

3. **Error:** Character Limit Exceeded
   - **Cause:** Generated copy exceeds platform character limits
   - **Resolution:** Automatically trim or rewrite to fit within limits
   - **Recovery:** Re-generate variants within limits (max 2 iterations)

4. **Error:** Brand Guidelines Not Found
   - **Cause:** brand-guidelines.md does not exist or path is incorrect
   - **Resolution:** Locate or create brand-guidelines.md
   - **Recovery:** Abort with instruction to ensure brand-guidelines.md exists

5. **Error:** Insufficient Variant Diversity
   - **Cause:** Generated variants are too similar to each other
   - **Resolution:** Re-generate with explicit diversity constraints
   - **Recovery:** Force different angles (benefit, problem, curiosity, social proof, urgency)

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 10-25 min (estimated)
cost_estimated: $0.005-0.020
token_usage: ~5,000-18,000 tokens
```

**Optimization Notes:**
- YOLO mode reduces to 5-10 min for single-platform standard formats
- Multi-platform campaigns multiply time by ~1.5x per additional platform
- Batch generation of variants is more efficient than one-by-one

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - campaign plan
  - brand-guidelines.md
tags:
  - marketing
  - ad-copy
  - paid-media
  - copywriting
  - meta-ads
  - google-ads
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - context7          # Research ad copywriting best practices and platform specs
checklists:
  - brand-alignment-checklist.md
execution_mode: interactive
---

# ad-copy

Create ad copy for paid media platforms (Meta Ads, Google Ads, LinkedIn Ads, TikTok Ads).

## Purpose

Produce platform-optimized ad copy packages with multiple variants for A/B testing. Ensures all ad copy respects platform character limits, aligns with brand guidelines, and follows paid media best practices. Delivers complete ad combinations ready for campaign setup.

## Prerequisites

- Campaign plan exists specifying platform and ad format
- brand-guidelines.md is accessible in knowledge base
- Target platform is supported (meta_ads, google_ads, linkedin_ads, tiktok_ads)

## Platform Character Limits Reference

### Meta Ads (Facebook/Instagram)
| Element | Limit |
|---------|-------|
| Headline | 40 characters |
| Description | 125 characters |
| Primary text | 125 characters (visible before "See more") |
| CTA | Platform buttons (Learn More, Shop Now, Sign Up, etc.) |

### Google Responsive Search Ads (RSA)
| Element | Limit |
|---------|-------|
| Headline | 30 characters x 15 slots |
| Description | 90 characters x 4 slots |
| Display URL path | 15 characters x 2 |
| CTA | Implied in description |

### LinkedIn Ads
| Element | Limit |
|---------|-------|
| Headline | 70 characters |
| Description | 100 characters |
| Introductory text | 150 characters (visible before expand) |
| CTA | Platform buttons (Learn More, Sign Up, Download, etc.) |

### TikTok Ads
| Element | Limit |
|---------|-------|
| Ad text | 100 characters |
| CTA | Platform buttons (Learn More, Shop Now, Sign Up, etc.) |

## Step-by-Step Instructions

### Step 1: Load Campaign Plan and Identify Ad Format

1. Read the campaign plan at `campaign_plan_path`
2. Extract key information:
   - Campaign objective (awareness, consideration, conversion)
   - Target audience
   - Key value propositions
   - Competitive positioning
   - Ad format (single image, carousel, video, responsive, etc.)
3. Identify the target platform from `target_platform`

### Step 2: Load Platform Character Limits

1. If `character_limits` provided by user, use those
2. Otherwise, use the platform defaults from the reference above:
   - **Meta Ads:** headline 40, description 125
   - **Google RSA:** headline 30 x 15 slots, description 90 x 4 slots
   - **LinkedIn Ads:** headline 70, description 100
   - **TikTok Ads:** ad text 100
3. Document active character limits for validation

### Step 3: Load Brand Guidelines

1. Read `brand-guidelines.md` from knowledge base
2. Extract brand voice attributes for ad copy:
   - Approved power words
   - Prohibited terms
   - Brand personality traits
   - Key differentiators
3. Note any platform-specific brand considerations

### Step 4: Write Headline Variants (5-10 options)

1. Generate 5-10 headline variants within platform limits
2. Use diverse approaches to maximize A/B testing value:
   - **Benefit-focused:** What the user gains
   - **Problem-focused:** Pain point addressed
   - **Curiosity-driven:** Create desire to click
   - **Social proof:** Numbers, testimonials
   - **Urgency-driven:** Time sensitivity, scarcity
   - **Question-based:** Engage through inquiry
   - **Direct value prop:** Clear offer statement
3. Verify each variant is within character limit
4. Label each variant with approach type and character count

### Step 5: Write Description Variants (3-5 options)

1. Generate 3-5 description variants within platform limits
2. Each description should:
   - Complement the headlines (not repeat them)
   - Include a secondary value proposition
   - Support the campaign objective
   - Feel natural for the platform
3. For Google RSA: write 4 descriptions (90 chars each) that work in any combination
4. Verify each variant is within character limit
5. Label each variant with character count

### Step 6: Write CTA Options

1. Generate CTA options matching platform's available buttons:
   - **Meta Ads:** Learn More, Shop Now, Sign Up, Download, Get Quote, Contact Us
   - **Google RSA:** CTAs embedded in description text
   - **LinkedIn Ads:** Learn More, Sign Up, Download, Visit Website, Apply Now
   - **TikTok Ads:** Learn More, Shop Now, Sign Up, Download, Contact Us
2. Select 2-3 CTAs most aligned with campaign objective
3. For Google RSA: write CTA phrases to embed in descriptions

### Step 7: Create 3 Complete Ad Combinations

1. Assemble 3 distinct ad combinations, each with:
   - Headline (selected from variants)
   - Description (selected from variants)
   - CTA (selected from options)
2. Each combination should have a different strategic angle:
   - **Combination 1:** Most direct/safe approach
   - **Combination 2:** Most creative/bold approach
   - **Combination 3:** Most data-driven/proof approach
3. Label each combination with its strategic angle

### Step 8: Mark Recommended Combination

1. Select the recommended combination based on:
   - Campaign objective alignment
   - Platform best practices
   - Brand voice fit
   - Historical performance patterns (if available)
2. Provide clear rationale for the recommendation
3. Suggest A/B testing strategy for the other combinations

## Output Requirements

1. **ALWAYS** deliver 5-10 headline variants with character counts
2. **ALWAYS** deliver 3-5 description variants with character counts
3. **ALWAYS** deliver 2-3 CTA options appropriate for platform
4. **ALWAYS** deliver 3 complete ad combinations
5. **ALWAYS** mark one combination as recommended with rationale
6. All copy **MUST** be within platform character limits
7. All copy **MUST** align with brand guidelines

## Ad Copy Package Format

```yaml
ad_copy_package:
  campaign_reference: "{campaign_plan_path}"
  platform: "{target_platform}"
  ad_format: "{format}"

  character_limits:
    headline_max: 40
    description_max: 125

  headlines:
    - text: "Headline text here"
      approach: "benefit-focused"
      char_count: 38
    # ... (5-10 variants)

  descriptions:
    - text: "Description text here with supporting value prop"
      char_count: 120
    # ... (3-5 variants)

  ctas:
    - text: "Learn More"
      platform_button: true
    - text: "Shop Now"
      platform_button: true
    # ... (2-3 options)

  combinations:
    - name: "Direct Approach"
      headline_index: 1
      description_index: 1
      cta_index: 1
      angle: "Most direct/safe approach"
    - name: "Bold Creative"
      headline_index: 3
      description_index: 2
      cta_index: 2
      angle: "Most creative/bold approach"
    - name: "Data-Driven"
      headline_index: 5
      description_index: 3
      cta_index: 1
      angle: "Most data-driven/proof approach"

  recommended:
    combination: 1  # index
    rationale: "Explanation of why this combination is recommended"
    ab_test_suggestion: "Test combination 2 against recommended to validate bold vs safe"

  brand_review:
    aligned: true
    notes: "All copy within brand guidelines. Power words used: [list]"
```

## Platform-Specific Best Practices

### Meta Ads
- Use emotional hooks in primary text
- Headlines should be scannable (front-load value)
- Descriptions support the headline, don't repeat
- Mobile-first: assume truncation

### Google RSA
- Headlines must make sense in any order/combination
- Include keywords naturally in headlines
- Descriptions should cover different selling points
- Pin critical headlines to position 1 if needed

### LinkedIn Ads
- Professional tone, avoid slang
- Focus on business outcomes
- Use industry-specific language
- Numbers and stats perform well

### TikTok Ads
- Keep it casual and authentic
- Front-load the hook (first 3 seconds concept)
- Use trending language/patterns when appropriate
- Short, punchy text

## Handoff
next_agent: @content-reviewer
next_command: *review-content
condition: Ad copy package complete
alternatives:
  - agent: @marketing-chief, command: *approve-campaign, condition: Ad copy is part of campaign approval flow
  - agent: @copywriter, command: *write-copy, condition: Campaign also needs organic content variants
