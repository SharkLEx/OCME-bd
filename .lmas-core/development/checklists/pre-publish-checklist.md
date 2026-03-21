# Pre-Publish Checklist

```yaml
checklist:
  id: pre-publish
  version: 1.0.0
  created: 2026-03-14
  updated: 2026-03-14
  purpose: "Final verification before publishing any content — ensures approvals are in place, content is ready, and scheduling is optimal"
  mode: blocking  # Level 1 items are blocking; Levels 2-4 are MUST but non-blocking for urgent content
  domain: marketing
  used_by:
    - "@social-media-manager (Echo)"
  urgency_override:
    enabled: true
    affects: "Level 2-4 only"
    requires: "@marketing-chief (Vox) explicit approval"
    note: "Level 1 (Approval Status) CANNOT be overridden even for urgent content"
```

---

## Level 1: Approval Status [ALL BLOCKING]

```yaml
approval_status_checks:
  - id: content-reviewer-approved
    check: "Content has been approved by @content-reviewer (Sentinel)"
    type: blocking
    validation: |
      Verify approval exists:
        - Content Quality Checklist: APPROVE (>= 7/10)
        - Brand Alignment Checklist: PASS (>= 8/10)
        - Legal Compliance Checklist: PASS (20/20)
    veto_if_fail: "Publishing without content review approval violates marketing pipeline integrity"

  - id: marketing-chief-approved
    check: "Content has @marketing-chief (Vox) approval if required by content tier"
    type: blocking
    validation: |
      @marketing-chief approval REQUIRED for:
        - Campaign launches
        - Crisis communications
        - Brand partnership content
        - Content involving legal sensitivity
        - Budget above threshold
      NOT required for:
        - Routine social posts
        - Scheduled recurring content
        - Pre-approved template content
    veto_if_fail: "High-tier content without marketing-chief approval = unauthorized brand communication"

  - id: revision-history-clean
    check: "All review feedback has been addressed and no open revision requests remain"
    type: blocking
    validation: "No unresolved comments or change requests in the content review chain"
    veto_if_fail: "Unaddressed feedback may indicate unresolved quality or legal issues"
```

---

## Level 2: Content Ready [MUST — non-blocking for urgent]

```yaml
content_ready_checks:
  - id: copy-final
    check: "Copy is in final version — all edits incorporated, no tracked changes or comments"
    type: blocking
    validation: "Content file has no draft markers, TODO tags, or placeholder text"
    urgency_override: true

  - id: visuals-final
    check: "All visual assets are final versions in correct format and resolution"
    type: blocking
    validation: |
      For each visual asset:
        - Final approved version (not draft/WIP)
        - Correct dimensions for target platform
        - Correct file format (PNG/JPG/MP4/etc.)
        - File size within platform limits
    urgency_override: true

  - id: links-tested
    check: "All links have been tested and return correct destinations"
    type: blocking
    validation: "Each URL returns HTTP 200 and reaches the intended landing page"
    urgency_override: true

  - id: utm-parameters-set
    check: "UTM parameters are correctly configured for tracking"
    type: blocking
    validation: |
      UTM parameters present:
        - utm_source: traffic source
        - utm_medium: marketing medium
        - utm_campaign: campaign name
        - utm_content: content identifier (optional)
        - utm_term: keyword (optional, for paid)
    urgency_override: true

  - id: tracking-pixels
    check: "Required tracking pixels and analytics tags are in place"
    type: recommended
    validation: "Facebook Pixel, Google Analytics, conversion tracking configured"
    urgency_override: true
```

---

## Level 3: Platform-Specific [MUST — non-blocking for urgent]

```yaml
platform_specific_checks:
  - id: format-correct
    check: "Content format matches platform requirements (dimensions, aspect ratio, file type)"
    type: blocking
    validation: |
      Platform specs verified:
        - Instagram Feed: 1080x1080 or 1080x1350
        - Instagram Stories/Reels: 1080x1920
        - Facebook: 1200x630
        - LinkedIn: 1200x627
        - Twitter/X: 1200x675
        - TikTok: 1080x1920
        - YouTube Thumbnail: 1280x720
        - Blog: responsive, max-width 1200px
    urgency_override: true

  - id: character-limits
    check: "Text content respects platform character limits"
    type: blocking
    validation: |
      Character limits checked:
        - Instagram caption: 2200 chars (first 125 visible)
        - Twitter/X: 280 chars
        - LinkedIn post: 3000 chars (first 210 visible)
        - Facebook post: 63,206 chars (first 477 visible)
        - TikTok caption: 2200 chars
        - Meta title: 60 chars
        - Meta description: 155 chars
    urgency_override: true

  - id: hashtags-optimized
    check: "Hashtags are relevant, researched, and within platform best practices"
    type: recommended
    validation: |
      Hashtag strategy:
        - Instagram: 5-15 hashtags (mix of broad + niche)
        - Twitter/X: 1-3 hashtags
        - LinkedIn: 3-5 hashtags
        - TikTok: 3-5 hashtags
        - No banned or shadowbanned hashtags
    urgency_override: true

  - id: alt-text-present
    check: "Alt text is set for all images and visual content"
    type: recommended
    validation: "Descriptive alt text that aids accessibility and SEO"
    urgency_override: true

  - id: platform-tags
    check: "Relevant accounts, locations, and products are tagged where applicable"
    type: recommended
    validation: "Brand account, partner accounts, and location tags configured"
    urgency_override: true
```

---

## Level 4: Scheduling [MUST — non-blocking for urgent]

```yaml
scheduling_checks:
  - id: optimal-time
    check: "Content is scheduled at an optimal time for the target audience"
    type: blocking
    validation: |
      Scheduling verified against:
        - Platform-specific engagement data
        - Target audience timezone
        - Historical performance data for similar content
    urgency_override: true

  - id: no-conflicts
    check: "No scheduling conflicts with other posts, campaigns, or events"
    type: blocking
    validation: |
      Check for conflicts:
        - No overlap with other scheduled posts within 2-hour window
        - No conflict with ongoing campaigns
        - No conflict with sensitive dates or events
        - No conflict with competitor major announcements (if known)
    urgency_override: true

  - id: calendar-updated
    check: "Content calendar is updated with the scheduled post details"
    type: blocking
    validation: "Calendar entry created with: content, platform, time, status, responsible"
    urgency_override: true

  - id: notification-set
    check: "Team notifications are configured for publish time"
    type: recommended
    validation: "Relevant team members will be notified when content goes live"
    urgency_override: true
```

---

## Scoring

| Level | Type | Override |
|-------|------|---------|
| Level 1: Approval Status | ALL BLOCKING | NEVER — cannot be overridden |
| Level 2: Content Ready | MUST | Can be overridden for urgent content with @marketing-chief approval |
| Level 3: Platform-Specific | MUST | Can be overridden for urgent content with @marketing-chief approval |
| Level 4: Scheduling | MUST | Can be overridden for urgent content with @marketing-chief approval |

```yaml
scoring_rules:
  standard_publish:
    requirement: "ALL items across ALL levels must pass"
    decision: "READY TO PUBLISH"

  urgent_publish:
    requirement: "ALL Level 1 items must pass + @marketing-chief explicit approval"
    decision: "URGENT PUBLISH — Level 2-4 gaps documented for post-publish fix"
    post_publish: "Address all skipped items within 24 hours"

  blocked:
    trigger: "ANY Level 1 item fails"
    decision: "BLOCKED — cannot publish regardless of urgency"
    escalation: "Return to content pipeline"
```

---

## Validation Execution

### Manual Validation Checklist

Copy this checklist and fill in:

```markdown
## Pre-Publish Gate: {content_title}

**Platform:** ___
**Scheduled Date/Time:** ___
**Content Type:** ___
**Urgency:** [ ] Standard | [ ] Urgent (requires @marketing-chief override)

### Level 1: Approval Status [BLOCKING — NO OVERRIDE]
- [ ] @content-reviewer (Sentinel) approved
- [ ] @marketing-chief (Vox) approved (if required)
- [ ] All revision feedback addressed

### Level 2: Content Ready [MUST]
- [ ] Copy is final version
- [ ] Visuals are final and correct format
- [ ] All links tested and working
- [ ] UTM parameters configured
- [ ] Tracking pixels in place

### Level 3: Platform-Specific [MUST]
- [ ] Format matches platform specs
- [ ] Character limits respected
- [ ] Hashtags optimized
- [ ] Alt text on all images
- [ ] Accounts/locations tagged

### Level 4: Scheduling [MUST]
- [ ] Optimal time selected
- [ ] No scheduling conflicts
- [ ] Content calendar updated
- [ ] Team notifications configured

### Result

**Level 1:** ___/3 (must be 3/3)
**Level 2:** ___/5
**Level 3:** ___/5
**Level 4:** ___/4
**Decision:** [ ] READY TO PUBLISH | [ ] URGENT PUBLISH (override) | [ ] BLOCKED
**Publisher:** ___
**Date:** ___
**Notes:** ___
```

---

## Integration with Workflow

This checklist is invoked at:

```
Content Creation Pipeline
    |
[Content Quality APPROVED]
    |
[Brand Alignment PASS]
    |
[Legal Compliance PASS]
    |
[@social-media-manager *pre-publish] <-- THIS CHECKLIST
    |
    +-- READY TO PUBLISH --> Schedule/Publish content
    |
    +-- URGENT PUBLISH   --> Publish with @marketing-chief override
    |                        (fix Level 2-4 gaps within 24h)
    |
    +-- BLOCKED          --> Return to content pipeline
                             (Level 1 approval missing)
```

---

**Version:** 1.0.0
**Created:** 2026-03-14
**Updated:** 2026-03-14
**Standard:** LMAS Marketing Domain — Pre-Publish Verification
**Domain:** Marketing
