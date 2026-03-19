# Brand Alignment Checklist

```yaml
checklist:
  id: brand-alignment
  version: 1.0.0
  created: 2026-03-14
  updated: 2026-03-14
  purpose: "Verify all content aligns with brand identity, tone of voice, messaging pillars, and legal standards before publication"
  mode: blocking  # Prevents publication if critical items fail
  domain: marketing
  used_by:
    - "@content-reviewer (Sentinel)"
    - "@marketing-chief (Vox)"
  scoring:
    scale: "0-10"
    pass: ">= 8"
    conditional: "6-7 (minor fixes required)"
    fail: "< 6"
```

---

## Level 1: Visual Identity

```yaml
visual_identity_checks:
  - id: logo-usage
    check: "Logo is used according to brand guidelines (correct version, clear space, minimum size)"
    type: blocking
    validation: "Visual comparison against brand guideline specs"
    veto_if_fail: "Incorrect logo usage damages brand recognition and trust"

  - id: color-palette
    check: "All colors match the approved brand color palette (primary, secondary, accent)"
    type: blocking
    validation: "Color codes match brand style guide HEX/RGB values"
    veto_if_fail: "Off-brand colors create visual inconsistency across channels"

  - id: typography
    check: "Typography follows brand guidelines (approved fonts, weights, sizes, hierarchy)"
    type: blocking
    validation: "Font families and sizes match brand typography system"

  - id: imagery-style
    check: "Imagery style is consistent with brand visual identity (photography style, illustration style, iconography)"
    type: recommended
    validation: "Visual assets match approved style guide references"
```

---

## Level 2: Tone of Voice

```yaml
tone_of_voice_checks:
  - id: brand-voice-attributes
    check: "Content matches defined brand voice attributes (e.g., professional, approachable, innovative)"
    type: blocking
    validation: "Read content aloud — does it sound like the brand?"
    veto_if_fail: "Misaligned tone breaks audience trust and brand consistency"

  - id: channel-appropriate
    check: "Tone is adapted appropriately for the target channel (social, email, blog, ad)"
    type: blocking
    validation: "Channel tone guidelines referenced and applied"

  - id: no-banned-words
    check: "Content does not contain any words or phrases from the banned words list"
    type: blocking
    validation: "grep against banned_words_list returns empty"
    veto_if_fail: "Banned words can cause legal issues or brand damage"

  - id: consistent-voice
    check: "Voice remains consistent throughout the entire piece (no shifts in register or persona)"
    type: recommended
    validation: "Full read-through confirms uniform tone from start to end"
```

---

## Level 3: Messaging

```yaml
messaging_checks:
  - id: brand-pillars-aligned
    check: "Key messages align with established brand pillars and strategic positioning"
    type: blocking
    validation: "Each core message traces back to at least one brand pillar"
    veto_if_fail: "Off-pillar messaging dilutes brand positioning"

  - id: cta-consistent
    check: "Call-to-action is consistent with brand CTA patterns and campaign objectives"
    type: blocking
    validation: "CTA wording matches approved CTA library or campaign brief"

  - id: value-proposition-clear
    check: "Value proposition is clearly communicated within the first 3 seconds / lines"
    type: blocking
    validation: "Reader can articulate the value proposition after first exposure"

  - id: audience-segment-match
    check: "Messaging is tailored to the intended audience segment"
    type: recommended
    validation: "Persona/segment referenced in content brief matches messaging approach"

  - id: competitive-differentiation
    check: "Content reinforces what differentiates the brand from competitors"
    type: recommended
    validation: "No generic claims that could apply to any competitor"
```

---

## Level 4: Legal & Compliance

```yaml
legal_compliance_checks:
  - id: no-unverified-claims
    check: "All claims in the content are verifiable and backed by data or sources"
    type: blocking
    validation: "Each claim has a traceable source (internal data, research, citation)"
    veto_if_fail: "Unverified claims expose the brand to legal liability"

  - id: lgpd-compliant
    check: "Content complies with LGPD requirements (data collection, consent, privacy)"
    type: blocking
    validation: "No personal data collected without explicit consent mechanism"
    veto_if_fail: "LGPD violation = legal penalty + brand reputation damage"

  - id: proper-disclaimers
    check: "All required disclaimers and disclosures are present and visible"
    type: blocking
    validation: "Industry-specific and platform-specific disclaimers present"
    veto_if_fail: "Missing disclaimers = regulatory risk"

  - id: trademark-usage
    check: "Third-party trademarks are used correctly with proper attribution"
    type: recommended
    validation: "Trademark symbols and attribution notices present where required"
```

---

## Scoring

| Score | Result | Action |
|-------|--------|--------|
| >= 8/10 | PASS | Content approved for publication |
| 6-7/10 | CONDITIONAL | Minor fixes required before publication |
| < 6/10 | FAIL | Major rework needed, cannot publish |

### Scoring Formula

```yaml
scoring_formula:
  level_1_visual_identity:
    weight: 2.5
    max_points: 2.5
    calculation: "(passed_checks / total_checks) * 2.5"
  level_2_tone_of_voice:
    weight: 2.5
    max_points: 2.5
    calculation: "(passed_checks / total_checks) * 2.5"
  level_3_messaging:
    weight: 2.5
    max_points: 2.5
    calculation: "(passed_checks / total_checks) * 2.5"
  level_4_legal_compliance:
    weight: 2.5
    max_points: 2.5
    calculation: "(passed_checks / total_checks) * 2.5"
  total: "Sum of all levels = 0-10"
```

---

## Validation Execution

### Manual Validation Checklist

Copy this checklist and fill in:

```markdown
## Brand Alignment Gate: {content_title}

### Level 1: Visual Identity
- [ ] Logo used correctly (version, clear space, minimum size)
- [ ] Colors match approved brand palette
- [ ] Typography follows brand guidelines
- [ ] Imagery style consistent with brand identity

### Level 2: Tone of Voice
- [ ] Matches brand voice attributes
- [ ] Channel-appropriate tone
- [ ] No banned words present
- [ ] Consistent voice throughout

### Level 3: Messaging
- [ ] Key messages aligned with brand pillars
- [ ] CTA consistent with brand patterns
- [ ] Value proposition clear
- [ ] Audience segment match
- [ ] Competitive differentiation reinforced

### Level 4: Legal & Compliance
- [ ] All claims verifiable
- [ ] LGPD compliant
- [ ] Proper disclaimers present
- [ ] Trademark usage correct

### Result

**Score:** ___/10
**Decision:** [ ] PASS (>= 8) | [ ] CONDITIONAL (6-7) | [ ] FAIL (< 6)
**Reviewer:** ___
**Date:** ___
**Notes:** ___
```

---

## Integration with Workflow

This checklist is invoked at:

```
Content Creation Pipeline
    |
[Content Draft Created]
    |
[@content-reviewer *review-content] <-- CONTENT QUALITY CHECKLIST
    |
[@content-reviewer *brand-check]   <-- THIS CHECKLIST
    |
    +-- PASS (>= 8)       --> Continue to pre-publish
    +-- CONDITIONAL (6-7)  --> Minor fixes, re-check
    +-- FAIL (< 6)         --> Return to content creator
```

---

**Version:** 1.0.0
**Created:** 2026-03-14
**Updated:** 2026-03-14
**Standard:** LMAS Marketing Domain — Brand Alignment
**Domain:** Marketing
