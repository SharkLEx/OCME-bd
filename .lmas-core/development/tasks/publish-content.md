<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Routine publications with complete approval chain

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** First-time publications, new platforms, complex content

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Multi-platform campaigns, high-stakes launches

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: publishContent()
responsável: Echo (Social Media Manager)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: approved_content
  tipo: object
  origem: Content Pipeline
  obrigatório: true
  validação: Must have approval status APPROVE from @content-reviewer AND @marketing-chief (if required)

- campo: target_platform
  tipo: string
  origem: User Input
  obrigatório: true
  validação: Must be one of supported platforms (Instagram, LinkedIn, TikTok, Twitter/X, Facebook, YouTube)

- campo: schedule_datetime
  tipo: datetime
  origem: User Input
  obrigatório: false
  validação: Must be future datetime in ISO-8601 format. If null, publish immediately.

- campo: utm_params
  tipo: object
  origem: Campaign Config
  obrigatório: false
  validação: Must include source, medium, campaign. Default generated from content metadata.

**Saída:**
- campo: publication_confirmation
  tipo: object
  destino: Editorial Calendar
  persistido: true

- campo: tracking_link
  tipo: string
  destino: Return value
  persistido: true

- campo: publication_status
  tipo: string
  destino: Editorial Calendar
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Content MUST have APPROVE from @content-reviewer
    tipo: pre-condition
    blocker: true
    validação: |
      Check content approval_status === 'APPROVED' from @content-reviewer
    error_message: "Pre-condition failed: Content not approved by @content-reviewer. Submit for review first."

  - [ ] Content MUST have APPROVE from @marketing-chief (if budget > R$0 or campaign-level content)
    tipo: pre-condition
    blocker: true
    validação: |
      If content.requires_chief_approval === true, check marketing_chief_approval === 'APPROVED'
    error_message: "Pre-condition failed: Content requires @marketing-chief approval for campaign-level publication."

  - [ ] Pre-publish checklist MUST pass
    tipo: pre-condition
    blocker: true
    validação: |
      Run pre-publish-checklist: visual assets exist, copy finalized, CTA defined, hashtags set
    error_message: "Pre-condition failed: Pre-publish checklist incomplete. Review missing items."

  - [ ] Target platform credentials configured
    tipo: pre-condition
    blocker: true
    validação: |
      Platform API credentials or access tokens available for target_platform
    error_message: "Pre-condition failed: Platform credentials not configured for target platform."
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Content published or scheduled successfully; confirmation received; editorial calendar updated
    tipo: post-condition
    blocker: true
    validação: |
      Verify publication_confirmation exists with status 'published' or 'scheduled';
      editorial calendar entry updated with correct status and link
    error_message: "Post-condition failed: Publication not confirmed or editorial calendar not updated."
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Content published/scheduled on correct platform with correct format
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert content live or scheduled on target_platform; format matches platform specs;
      UTM parameters applied; tracking link generated
    error_message: "Acceptance criterion not met: Content not correctly published/scheduled on target platform."

  - [ ] Editorial calendar reflects current status
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert editorial calendar entry status matches publication outcome (published/scheduled)
    error_message: "Acceptance criterion not met: Editorial calendar not updated with publication status."
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** editorial-calendar
  - **Purpose:** Track publication schedule and status
  - **Source:** .lmas-core/domains/marketing/editorial-calendar.yaml

- **Tool:** utm-builder
  - **Purpose:** Generate UTM tracking parameters
  - **Source:** .lmas-core/domains/marketing/utils/utm-builder.js

- **Tool:** platform-adapter
  - **Purpose:** Adapt content format per platform specs
  - **Source:** .lmas-core/domains/marketing/utils/platform-adapter.js

---

## Scripts

**Agent-specific code for this task:**

- **Script:** pre-publish-checklist.js
  - **Purpose:** Validate all pre-publish requirements before publication
  - **Language:** JavaScript
  - **Location:** .lmas-core/domains/marketing/scripts/pre-publish-checklist.js

---

## Error Handling

**Strategy:** retry-then-abort

**Common Errors:**

1. **Error:** Approval Chain Incomplete
   - **Cause:** Content missing required approval from @content-reviewer or @marketing-chief
   - **Resolution:** Return content to approval pipeline with missing approver identified
   - **Recovery:** Abort publication, notify requester of missing approval

2. **Error:** Platform Format Mismatch
   - **Cause:** Content exceeds character limit or image dimensions don't match platform specs
   - **Resolution:** Auto-adapt content using platform-adapter; if auto-adapt fails, return to @copywriter
   - **Recovery:** Log format mismatch details, suggest manual adjustments

3. **Error:** Platform API Failure
   - **Cause:** Platform API unavailable or credentials expired
   - **Resolution:** Retry up to 3 times with exponential backoff; if persistent, schedule for later
   - **Recovery:** Save content as draft, log error, notify @social-media-manager

4. **Error:** UTM Parameter Generation Failed
   - **Cause:** Missing campaign metadata for UTM generation
   - **Resolution:** Use default UTM params from content strategy config
   - **Recovery:** Publish with default tracking, log warning

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 3-10 min (estimated)
cost_estimated: $0.002-0.008
token_usage: ~2,000-6,000 tokens
```

**Optimization Notes:**
- Pre-validate approval chain before loading full content to fail fast
- Cache platform specs to avoid repeated lookups
- Batch UTM generation for multi-platform publications

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - schedule-post
  - pre-publish-checklist
tags:
  - marketing
  - social-media
  - publication
  - content-pipeline
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - editorial-calendar
  - platform-adapter
checklists:
  - pre-publish-checklist.md
execution_mode: interactive
---

# publish-content

Publication pipeline — validate approval, adapt by platform, schedule or publish content.

## Purpose

Execute the full publication pipeline for approved content. Validates the approval chain is complete, adapts content format for the target platform, applies tracking parameters, and publishes or schedules the post. Updates the editorial calendar with the final status.

## Prerequisites

- Content must have APPROVE from @content-reviewer
- Content must have APPROVE from @marketing-chief (if campaign-level or paid content)
- Pre-publish checklist must pass (visual assets, copy, CTA, hashtags)
- Target platform credentials must be configured

## Step-by-Step Execution

### Step 1: Verify Approval Chain

1. Load content metadata and approval history
2. Check `approval_status` from @content-reviewer === `APPROVED`
3. If content is campaign-level or paid: check `marketing_chief_approval` === `APPROVED`
4. If any approval missing → **ABORT** with clear message identifying missing approver

### Step 2: Load Content and Target Platform

1. Load full content object (copy, visuals, CTA, hashtags, metadata)
2. Validate target_platform is supported
3. Load platform specifications (character limits, image sizes, video specs)

### Step 3: Run Pre-Publish Checklist

1. Execute pre-publish-checklist validation:
   - [ ] Visual assets exist and meet quality standards
   - [ ] Copy is finalized (no draft markers)
   - [ ] CTA is defined and actionable
   - [ ] Hashtags are set (if platform supports)
   - [ ] Links are valid and not broken
2. If checklist fails → **ABORT** with list of failed items

### Step 4: Adapt Format for Platform

1. Apply platform-specific formatting:
   - **Instagram:** Max 2,200 chars caption, 1080x1080 or 1080x1350 images, max 30 hashtags
   - **LinkedIn:** Max 3,000 chars, professional tone verification, 1200x627 images
   - **TikTok:** Max 2,200 chars caption, 9:16 video ratio
   - **Twitter/X:** Max 280 chars, 1200x675 images, max 3-5 hashtags
   - **Facebook:** Max 63,206 chars, 1200x630 images
   - **YouTube:** Title max 100 chars, description max 5,000 chars
2. Truncate or adapt copy if exceeding limits
3. Resize/validate visual assets

### Step 5: Set UTM Parameters

1. Generate UTM parameters:
   - `utm_source`: platform name (e.g., instagram, linkedin)
   - `utm_medium`: content type (e.g., organic, paid)
   - `utm_campaign`: campaign slug from content strategy
   - `utm_content`: content variant identifier
2. Apply UTM to all links in content
3. Generate shortened tracking link if needed

### Step 6: Schedule or Publish

**If schedule_datetime provided:**
1. Validate datetime is in the future
2. Schedule post for specified datetime
3. Set status to `scheduled`

**If immediate (no schedule_datetime):**
1. Publish content now
2. Verify publication confirmation from platform
3. Set status to `published`

### Step 7: Confirm Publication/Scheduling

1. Capture confirmation response (post ID, URL, timestamp)
2. Generate tracking link with UTM parameters
3. Log publication event with all metadata

### Step 8: Update Editorial Calendar

1. Update editorial calendar entry with:
   - Status: `published` or `scheduled`
   - Platform post URL
   - Tracking link
   - Publication/schedule timestamp
   - UTM parameters applied
2. Save editorial calendar file

## Output Requirements

1. Return publication confirmation object with:
   - `status`: published | scheduled
   - `platform`: target platform name
   - `post_url`: direct link to published/scheduled post
   - `tracking_link`: UTM-tagged link
   - `published_at` or `scheduled_for`: timestamp
2. Update editorial calendar with final status

## Handoff
next_agent: @traffic-manager
next_command: *campaign-report
condition: Content is part of a paid campaign
alternatives:
  - agent: @content-strategist, command: *review-performance, condition: Organic content published
  - agent: @social-media-manager, command: *schedule-post, condition: Multi-platform publication pending
