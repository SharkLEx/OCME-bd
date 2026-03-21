<!--
## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Autonomous decision making with logging
- Minimal user interaction
- **Best for:** Routine scheduling with clear datetime and no conflicts

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Explicit decision checkpoints
- Educational explanations
- **Best for:** First-time scheduling, conflict resolution, optimal timing suggestions

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Task analysis phase (identify all ambiguities)
- Zero ambiguity execution
- **Best for:** Batch scheduling, multi-platform editorial calendar planning

**Parameter:** `mode` (optional, default: `interactive`)

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: schedulePost()
responsável: Echo (Social Media Manager)
responsavel_type: Agente
atomic_layer: Organism

**Entrada:**
- campo: content
  tipo: object
  origem: Content Pipeline
  obrigatório: true
  validação: Must be approved content with copy, visuals, CTA, and hashtags defined

- campo: platform
  tipo: string
  origem: User Input
  obrigatório: true
  validação: Must be one of supported platforms (Instagram, LinkedIn, TikTok, Twitter/X, Facebook, YouTube)

- campo: preferred_datetime
  tipo: datetime
  origem: User Input
  obrigatório: false
  validação: Must be future datetime in ISO-8601. If null, suggest optimal time.

- campo: editorial_calendar_ref
  tipo: string
  origem: Editorial Calendar
  obrigatório: true
  validação: Path to editorial calendar file must exist

**Saída:**
- campo: updated_editorial_calendar
  tipo: file
  destino: Editorial Calendar
  persistido: true

- campo: schedule_confirmation
  tipo: object
  destino: Return value
  persistido: false

- campo: calendar_entry
  tipo: object
  destino: Editorial Calendar
  persistido: true
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

**Checklist:**

```yaml
pre-conditions:
  - [ ] Content must be approved (APPROVE status from review pipeline)
    tipo: pre-condition
    blocker: true
    validação: |
      Check content.approval_status === 'APPROVED'
    error_message: "Pre-condition failed: Content not approved. Cannot schedule unapproved content."

  - [ ] Editorial calendar file must exist at editorial_calendar_ref
    tipo: pre-condition
    blocker: true
    validação: |
      Check file exists at editorial_calendar_ref path
    error_message: "Pre-condition failed: Editorial calendar not found. Create calendar first."

  - [ ] Platform must be supported and configured
    tipo: pre-condition
    blocker: true
    validação: |
      Check platform is in supported platforms list and credentials are configured
    error_message: "Pre-condition failed: Platform not supported or not configured."
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

**Checklist:**

```yaml
post-conditions:
  - [ ] Editorial calendar updated with new post entry; no scheduling conflicts
    tipo: post-condition
    blocker: true
    validação: |
      Verify editorial calendar file contains new entry with correct datetime, platform,
      content metadata; no duplicate entries for same platform/time slot
    error_message: "Post-condition failed: Editorial calendar not properly updated or conflict detected."
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

**Checklist:**

```yaml
acceptance-criteria:
  - [ ] Post scheduled in editorial calendar with all required metadata
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert calendar entry contains: datetime, platform, copy, visual reference,
      CTA, hashtags, UTM params, status='scheduled'
    error_message: "Acceptance criterion not met: Calendar entry missing required metadata."

  - [ ] No scheduling conflicts exist for the selected time slot
    tipo: acceptance-criterion
    blocker: true
    validação: |
      Assert no other post scheduled for same platform within conflict window (default: 2 hours)
    error_message: "Acceptance criterion not met: Scheduling conflict detected for platform/time slot."
```

---

## Tools

**External/shared resources used by this task:**

- **Tool:** editorial-calendar
  - **Purpose:** Read and update the editorial calendar
  - **Source:** .lmas-core/domains/marketing/editorial-calendar.yaml

- **Tool:** optimal-timing-engine
  - **Purpose:** Suggest best posting times per platform based on best practices
  - **Source:** .lmas-core/domains/marketing/utils/optimal-timing.js

---

## Scripts

**Agent-specific code for this task:**

- **Script:** conflict-checker.js
  - **Purpose:** Detect scheduling conflicts in editorial calendar
  - **Language:** JavaScript
  - **Location:** .lmas-core/domains/marketing/scripts/conflict-checker.js

---

## Error Handling

**Strategy:** resolve-then-retry

**Common Errors:**

1. **Error:** Scheduling Conflict Detected
   - **Cause:** Another post already scheduled for same platform within conflict window
   - **Resolution:** Suggest alternative time slots (next available or optimal)
   - **Recovery:** Present conflict details and alternatives to user for decision

2. **Error:** Editorial Calendar File Corrupted
   - **Cause:** Invalid YAML/JSON structure in calendar file
   - **Resolution:** Attempt auto-repair; if fails, create backup and rebuild
   - **Recovery:** Restore from last valid backup, log corruption event

3. **Error:** Preferred Datetime in the Past
   - **Cause:** User provided a datetime that has already passed
   - **Resolution:** Suggest next available optimal time
   - **Recovery:** Reject scheduling, present suggested future times

4. **Error:** Content Format Incompatible with Platform
   - **Cause:** Content assets don't match platform specifications
   - **Resolution:** Flag format issues, delegate to platform-adapter
   - **Recovery:** Log incompatibilities, suggest format adjustments before scheduling

---

## Performance

**Expected Metrics:**

```yaml
duration_expected: 2-5 min (estimated)
cost_estimated: $0.001-0.005
token_usage: ~1,500-4,000 tokens
```

**Optimization Notes:**
- Cache editorial calendar in memory during batch scheduling operations
- Pre-compute conflict windows for fast lookups
- Batch multiple schedule operations when scheduling a full week

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - publish-content
tags:
  - marketing
  - social-media
  - scheduling
  - editorial-calendar
domain: marketing
updated_at: 2026-03-14
```

---

 Powered by LMAS™ Core -->

---
tools:
  - editorial-calendar
  - optimal-timing-engine
checklists: []
execution_mode: interactive
---

# schedule-post

Schedule post in editorial calendar with optimal timing and conflict detection.

## Purpose

Add a content post to the editorial calendar for a specific platform and datetime. Detects scheduling conflicts, suggests optimal posting times when not specified, validates content format matches platform specs, and persists the complete entry with all metadata.

## Prerequisites

- Content must be approved (APPROVE status)
- Editorial calendar file must exist
- Target platform must be supported and configured

## Step-by-Step Execution

### Step 1: Load Editorial Calendar

1. Read editorial calendar from `editorial_calendar_ref` path
2. Parse and validate calendar structure
3. Load entries for the target period (week surrounding preferred_datetime)
4. If calendar file invalid → attempt repair or **ABORT**

### Step 2: Check for Conflicts

1. Define conflict window: same platform, within 2 hours of preferred_datetime
2. Scan calendar entries for overlapping posts
3. If conflict found:
   - **Interactive mode:** Present conflict details and ask user to choose alternative
   - **YOLO mode:** Auto-select next available slot after conflict window
4. Log conflict check results

### Step 3: Suggest Optimal Posting Time

**If preferred_datetime not specified:**
1. Load platform best practices for posting times:
   - **Instagram:** Tue-Thu 10:00-14:00, Sat 09:00-11:00
   - **LinkedIn:** Tue-Wed 07:00-08:00, Thu 10:00-12:00
   - **TikTok:** Mon-Fri 18:00-21:00, weekends 12:00-15:00
   - **Twitter/X:** Mon-Fri 08:00-10:00, 12:00-13:00
   - **Facebook:** Mon-Wed 09:00-12:00
   - **YouTube:** Thu-Sun 12:00-15:00
2. Cross-reference with existing calendar to avoid conflicts
3. Present top 3 suggested times to user
4. Apply selected time

**If preferred_datetime specified:**
1. Validate it is in the future
2. Check if close to optimal window — if not, suggest better time as alternative
3. Proceed with user's preferred time

### Step 4: Verify Content Format

1. Load platform specifications for target platform
2. Validate content against specs:
   - Copy character count within limits
   - Visual asset dimensions match requirements
   - Video duration/ratio acceptable (if applicable)
   - Hashtag count within limits
3. If format issues found → flag for resolution before scheduling

### Step 5: Add Post to Calendar

1. Create calendar entry with all metadata:
   ```yaml
   entry:
     id: "{auto-generated UUID}"
     platform: "{target_platform}"
     scheduled_for: "{datetime ISO-8601}"
     status: "scheduled"
     content:
       copy: "{final copy text}"
       visual_ref: "{path to visual asset}"
       cta: "{call to action}"
       hashtags: ["{list of hashtags}"]
     tracking:
       utm_source: "{platform}"
       utm_medium: "{organic|paid}"
       utm_campaign: "{campaign_slug}"
     created_at: "{now ISO-8601}"
     created_by: "Echo"
   ```
2. Insert entry in chronological order within calendar

### Step 6: Update Editorial Calendar File

1. Write updated calendar to `editorial_calendar_ref` path
2. Validate written file is parseable
3. Log calendar update event

### Step 7: Confirm Schedule

1. Return schedule confirmation:
   - Entry ID
   - Platform
   - Scheduled datetime
   - Content summary (first 100 chars of copy)
   - Status: `scheduled`
2. Display confirmation to user

## Output Requirements

1. Updated editorial calendar file at `editorial_calendar_ref`
2. Schedule confirmation object with entry details
3. No scheduling conflicts in final calendar state

## Handoff
next_agent: @social-media-manager
next_command: *publish-content
condition: Scheduled datetime reached (automated trigger)
alternatives:
  - agent: @content-strategist, command: *review-calendar, condition: Calendar review requested
  - agent: @social-media-manager, command: *schedule-post, condition: Additional posts to schedule
