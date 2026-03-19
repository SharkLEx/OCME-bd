# Content Quality Checklist

```yaml
checklist:
  id: content-quality
  version: 1.0.0
  created: 2026-03-14
  updated: 2026-03-14
  purpose: "Score content quality 0-10 across structure, writing, engagement, SEO, and technical dimensions"
  mode: advisory  # Scores content quality, does not hard-block on its own
  domain: marketing
  used_by:
    - "@content-reviewer (Sentinel)"
  scoring:
    scale: "0-10 (each level scores 0-2, total sum)"
    approve: ">= 7"
    revise: "5-6"
    reject: "< 5"
```

---

## Level 1: Structure (0-2 points)

```yaml
structure_checks:
  - id: clear-headline
    check: "Headline is clear, compelling, and accurately represents the content"
    type: blocking
    points_contribution: 0.5
    validation: "Headline passes the 'would I click this?' test and sets correct expectations"
    veto_if_fail: "Weak or misleading headline kills content performance at first impression"

  - id: logical-flow
    check: "Content follows a logical flow from introduction to conclusion"
    type: blocking
    points_contribution: 0.5
    validation: "Each section naturally leads to the next; no jarring topic jumps"

  - id: proper-formatting
    check: "Content uses proper formatting (headings, paragraphs, lists, whitespace)"
    type: recommended
    points_contribution: 0.5
    validation: "Visual hierarchy is clear; no wall-of-text blocks"

  - id: scannable
    check: "Content is scannable (subheadings, bold key points, bullet lists, short paragraphs)"
    type: recommended
    points_contribution: 0.5
    validation: "Reader can extract main points by scanning in under 30 seconds"
```

### Level 1 Scoring

```yaml
level_1_scoring:
  max_points: 2.0
  calculation: "Sum of points from passed checks (0.5 each, max 2.0)"
  breakdown:
    2.0: "All 4 checks pass"
    1.5: "3 of 4 checks pass"
    1.0: "2 of 4 checks pass"
    0.5: "1 of 4 checks pass"
    0.0: "No checks pass"
```

---

## Level 2: Writing Quality (0-2 points)

```yaml
writing_quality_checks:
  - id: grammar-correct
    check: "Content is free of grammar and syntax errors"
    type: blocking
    points_contribution: 0.5
    validation: "No grammatical errors detectable on careful review"
    veto_if_fail: "Grammar errors destroy credibility immediately"

  - id: spelling-correct
    check: "Content is free of spelling errors and typos"
    type: blocking
    points_contribution: 0.5
    validation: "Spellcheck passes; no typos or misspellings found"

  - id: readability
    check: "Content readability matches target audience level"
    type: recommended
    points_contribution: 0.5
    validation: "Sentence length and vocabulary appropriate for the audience"

  - id: voice-consistency
    check: "Writing voice remains consistent throughout (no shifts in person, tense, or register)"
    type: recommended
    points_contribution: 0.5
    validation: "Uniform voice from first word to last"
```

### Level 2 Scoring

```yaml
level_2_scoring:
  max_points: 2.0
  calculation: "Sum of points from passed checks (0.5 each, max 2.0)"
  breakdown:
    2.0: "All 4 checks pass"
    1.5: "3 of 4 checks pass"
    1.0: "2 of 4 checks pass"
    0.5: "1 of 4 checks pass"
    0.0: "No checks pass"
```

---

## Level 3: Engagement (0-2 points)

```yaml
engagement_checks:
  - id: hook-opening
    check: "Hook captures attention within the first 3 words (social/ad) or 3 seconds (video/audio)"
    type: blocking
    points_contribution: 0.5
    validation: "Opening line creates curiosity, urgency, or emotional response"
    veto_if_fail: "Without a hook, audience scrolls past — content never gets consumed"

  - id: compelling-cta
    check: "Call-to-action is clear, compelling, and creates urgency or desire"
    type: blocking
    points_contribution: 0.5
    validation: "CTA uses action verbs and communicates clear benefit"

  - id: audience-resonance
    check: "Content addresses a specific pain point, desire, or interest of the target audience"
    type: recommended
    points_contribution: 0.5
    validation: "Target persona would feel 'this was written for me'"

  - id: emotional-connection
    check: "Content creates an emotional response (inspiration, curiosity, urgency, belonging)"
    type: recommended
    points_contribution: 0.5
    validation: "At least one emotional trigger is present and authentic"
```

### Level 3 Scoring

```yaml
level_3_scoring:
  max_points: 2.0
  calculation: "Sum of points from passed checks (0.5 each, max 2.0)"
  breakdown:
    2.0: "All 4 checks pass"
    1.5: "3 of 4 checks pass"
    1.0: "2 of 4 checks pass"
    0.5: "1 of 4 checks pass"
    0.0: "No checks pass"
```

---

## Level 4: SEO & Discovery (0-2 points)

```yaml
seo_discovery_checks:
  - id: keywords-present
    check: "Target keywords are naturally integrated into title, body, and headings"
    type: blocking
    points_contribution: 0.5
    validation: "Primary keyword in title + H2; secondary keywords in body"

  - id: meta-description
    check: "Meta description is present, compelling, and within character limits (150-160 chars)"
    type: recommended
    points_contribution: 0.5
    validation: "Meta description exists and includes primary keyword"

  - id: alt-text
    check: "All images have descriptive alt text that includes relevant keywords"
    type: recommended
    points_contribution: 0.5
    validation: "Every <img> tag has meaningful alt attribute"

  - id: hashtags-social
    check: "If social content: relevant hashtags are included (mix of broad and niche)"
    type: recommended
    points_contribution: 0.5
    validation: "3-10 hashtags relevant to content and audience; no banned hashtags"
    applies_to: "social media content only"
```

### Level 4 Scoring

```yaml
level_4_scoring:
  max_points: 2.0
  calculation: "Sum of points from passed checks (0.5 each, max 2.0)"
  breakdown:
    2.0: "All 4 checks pass (or N/A items scored as pass)"
    1.5: "3 of 4 checks pass"
    1.0: "2 of 4 checks pass"
    0.5: "1 of 4 checks pass"
    0.0: "No checks pass"
```

---

## Level 5: Technical (0-2 points)

```yaml
technical_checks:
  - id: links-working
    check: "All links are functional, point to correct destinations, and open correctly"
    type: blocking
    points_contribution: 0.5
    validation: "Each link returns HTTP 200 and reaches intended page"
    veto_if_fail: "Broken links = lost traffic + damaged credibility"

  - id: images-correct-size
    check: "Images meet platform-required dimensions and file size limits"
    type: blocking
    points_contribution: 0.5
    validation: "Image dimensions match platform specs; file size within limits"

  - id: format-specs-met
    check: "Content meets all format specifications for the target platform"
    type: recommended
    points_contribution: 0.5
    validation: "Character limits, aspect ratios, file formats all compliant"

  - id: responsive-rendering
    check: "Content renders correctly across devices (mobile, tablet, desktop)"
    type: recommended
    points_contribution: 0.5
    validation: "Visual inspection on mobile and desktop shows no layout issues"
```

### Level 5 Scoring

```yaml
level_5_scoring:
  max_points: 2.0
  calculation: "Sum of points from passed checks (0.5 each, max 2.0)"
  breakdown:
    2.0: "All 4 checks pass"
    1.5: "3 of 4 checks pass"
    1.0: "2 of 4 checks pass"
    0.5: "1 of 4 checks pass"
    0.0: "No checks pass"
```

---

## Overall Scoring

| Total Score | Result | Action |
|-------------|--------|--------|
| >= 7/10 | APPROVE | Content ready for brand alignment check |
| 5-6/10 | REVISE | Return to content creator with specific feedback |
| < 5/10 | REJECT | Content requires significant rework |

### Scoring Formula

```yaml
scoring_formula:
  level_1_structure: "0-2 points"
  level_2_writing_quality: "0-2 points"
  level_3_engagement: "0-2 points"
  level_4_seo_discovery: "0-2 points"
  level_5_technical: "0-2 points"
  total: "Sum of all levels = 0-10"
  note: "Each level has 4 checks worth 0.5 points each"
```

---

## Validation Execution

### Manual Validation Checklist

Copy this checklist and fill in:

```markdown
## Content Quality Gate: {content_title}

### Level 1: Structure (___/2)
- [ ] Clear, compelling headline
- [ ] Logical flow from intro to conclusion
- [ ] Proper formatting (headings, paragraphs, lists)
- [ ] Scannable (subheadings, bold, bullets)

### Level 2: Writing Quality (___/2)
- [ ] Grammar correct
- [ ] Spelling correct
- [ ] Readability appropriate for audience
- [ ] Voice consistent throughout

### Level 3: Engagement (___/2)
- [ ] Hook in first 3 words/seconds
- [ ] Compelling CTA
- [ ] Audience resonance
- [ ] Emotional connection

### Level 4: SEO & Discovery (___/2)
- [ ] Keywords naturally integrated
- [ ] Meta description present and optimized
- [ ] Alt text on all images
- [ ] Hashtags included (if social content)

### Level 5: Technical (___/2)
- [ ] All links working
- [ ] Images correct size
- [ ] Format specs met
- [ ] Responsive rendering

### Result

**Total Score:** ___/10
**Level Breakdown:** L1: ___  L2: ___  L3: ___  L4: ___  L5: ___
**Decision:** [ ] APPROVE (>= 7) | [ ] REVISE (5-6) | [ ] REJECT (< 5)
**Reviewer:** ___
**Date:** ___
**Feedback:** ___
```

---

## Integration with Workflow

This checklist is invoked at:

```
Content Creation Pipeline
    |
[Content Draft Created]
    |
[@content-reviewer *review-content] <-- THIS CHECKLIST
    |
    +-- APPROVE (>= 7) --> Brand Alignment Checklist
    +-- REVISE (5-6)   --> Return to creator with feedback
    +-- REJECT (< 5)   --> Significant rework required
```

---

**Version:** 1.0.0
**Created:** 2026-03-14
**Updated:** 2026-03-14
**Standard:** LMAS Marketing Domain — Content Quality
**Domain:** Marketing
