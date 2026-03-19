# Legal Compliance Checklist

```yaml
checklist:
  id: legal-compliance
  version: 1.0.0
  created: 2026-03-14
  updated: 2026-03-14
  purpose: "NON-NEGOTIABLE legal compliance checks for all marketing content before publication (MK-III Constitution)"
  mode: blocking  # ALL items are blocking — any fail = content CANNOT be published
  domain: marketing
  severity: NON-NEGOTIABLE
  used_by:
    - "@content-reviewer (Sentinel)"
  constitutional_reference: "MK-III — Legal Compliance"
  scoring:
    scale: "pass/fail per item"
    pass: "ALL items pass"
    fail: "ANY single item fails = content blocked"
```

---

## Level 1: LGPD (Lei Geral de Protecao de Dados)

```yaml
lgpd_checks:
  - id: data-collection-consent
    check: "Any form of data collection has explicit consent mechanism (opt-in, not opt-out)"
    type: blocking
    validation: "Consent checkbox present, unchecked by default, with clear privacy language"
    veto_if_fail: "LGPD Art. 7 — Data processing without consent = administrative penalty up to 2% of revenue"

  - id: opt-out-mechanism
    check: "Clear and accessible opt-out/unsubscribe mechanism is provided"
    type: blocking
    validation: "Unsubscribe link present in emails; opt-out instructions visible in all data-collecting content"
    veto_if_fail: "LGPD Art. 18 — Data subjects have the right to revoke consent at any time"

  - id: privacy-policy-linked
    check: "Privacy policy link is present and accessible wherever data is collected"
    type: blocking
    validation: "Clickable link to current privacy policy near data collection points"
    veto_if_fail: "LGPD Art. 9 — Data subjects must be informed about data processing purposes"

  - id: cookie-notice
    check: "Cookie consent notice is present on web pages that use cookies or tracking"
    type: blocking
    validation: "Cookie banner displayed on first visit with accept/reject options"
    veto_if_fail: "LGPD requires informed consent for any form of tracking or profiling"

  - id: data-minimization
    check: "Only necessary data is collected (no excessive form fields or tracking)"
    type: blocking
    validation: "Form fields match stated purpose; no unnecessary personal data requested"
    veto_if_fail: "LGPD Art. 6 — Data processing must follow the principle of necessity"
```

---

## Level 2: Claims & Disclaimers

```yaml
claims_disclaimers_checks:
  - id: claims-verifiable
    check: "ALL claims in the content are verifiable with concrete evidence"
    type: blocking
    validation: "Each claim has a traceable source: internal data, study, official statistic, or customer data"
    veto_if_fail: "Unverifiable claims = false advertising risk (CDC Art. 37)"

  - id: sources-cited
    check: "Data points, statistics, and factual claims cite their sources"
    type: blocking
    validation: "Source identified for every numerical claim, percentage, or factual assertion"
    veto_if_fail: "Unsourced statistics mislead consumers and violate advertising standards"

  - id: disclaimers-present
    check: "Required disclaimers are present, visible, and not hidden in fine print"
    type: blocking
    validation: |
      Check for required disclaimers based on content type:
        - Financial: investment risk disclaimers
        - Health: professional consultation disclaimers
        - Promotions: terms and conditions
        - Testimonials: results may vary disclaimer
    veto_if_fail: "Missing disclaimers = regulatory violation + consumer protection risk"

  - id: no-absolute-guarantees
    check: "Content does not make absolute guarantees unless legally defensible"
    type: blocking
    validation: "No phrases like 'guaranteed results', '100% effective', 'always works' without legal backing"
    veto_if_fail: "Absolute guarantees create binding obligations (CDC Art. 30)"

  - id: comparative-claims-fair
    check: "Any comparison with competitors is factual, fair, and substantiated"
    type: blocking
    validation: "Comparative claims backed by objective, verifiable criteria"
    veto_if_fail: "Unfair comparative advertising violates CONAR Code Art. 32"
```

---

## Level 3: Rights & Licensing

```yaml
rights_licensing_checks:
  - id: image-rights
    check: "All images have proper licensing or rights for commercial use"
    type: blocking
    validation: |
      For each image:
        - Stock photo: license covers intended use (commercial, social, print)
        - Original photo: model release signed if people visible
        - User-generated: written permission obtained
    veto_if_fail: "Unlicensed image usage = copyright infringement + financial liability"

  - id: music-audio-rights
    check: "All music, audio, and sound effects have proper licensing for commercial use"
    type: blocking
    validation: "License documentation available for all audio assets"
    veto_if_fail: "Unlicensed audio = DMCA takedown + copyright claim"

  - id: testimonial-consent
    check: "All testimonials have documented written consent from the person quoted"
    type: blocking
    validation: "Signed consent form or written permission on file for each testimonial"
    veto_if_fail: "Using testimonials without consent violates personality rights (CC Art. 20)"

  - id: trademark-usage
    check: "Third-party trademarks are used correctly with proper attribution"
    type: blocking
    validation: |
      For each third-party trademark:
        - Correct spelling and capitalization
        - TM/R symbols where required
        - Attribution statement present
        - Usage within fair use or licensed scope
    veto_if_fail: "Improper trademark usage = trademark infringement risk"

  - id: font-licensing
    check: "All fonts used are properly licensed for the intended use (web, print, commercial)"
    type: blocking
    validation: "Font license covers commercial use in the specific medium"
    veto_if_fail: "Unlicensed font usage = copyright infringement"
```

---

## Level 4: Regulatory

```yaml
regulatory_checks:
  - id: industry-regulations
    check: "Content complies with industry-specific regulations (finance, health, education, etc.)"
    type: blocking
    validation: |
      Check applicable regulations:
        - Finance: CVM, BACEN guidelines
        - Health: ANVISA, CFM advertising rules
        - Education: MEC guidelines
        - Food/Beverage: ANVISA labeling rules
        - Real Estate: CRECI advertising rules
    veto_if_fail: "Industry regulatory violation = fines + potential license revocation"

  - id: advertising-standards
    check: "Content complies with CONAR (Conselho Nacional de Autorregulamentacao Publicitaria) code"
    type: blocking
    validation: "Content reviewed against CONAR Code of Ethics for advertising"
    veto_if_fail: "CONAR violation = mandatory content removal + public reprimand"

  - id: age-restrictions
    check: "Content with age-restricted themes has proper age gating and disclaimers"
    type: blocking
    validation: |
      If content involves:
        - Alcohol: no appeal to minors, mandatory disclaimer (Lei 9.294/96)
        - Gambling: age verification + responsible gambling notice
        - Adult content: proper age gating mechanism
    veto_if_fail: "Exposing age-restricted content to minors = serious legal violation"

  - id: accessibility-compliance
    check: "Digital content meets basic accessibility requirements (alt text, contrast, captions)"
    type: blocking
    validation: "WCAG 2.1 Level A minimum: alt text, color contrast ratio >= 4.5:1, video captions"
    veto_if_fail: "Inaccessible content excludes audiences and may violate LBI (Lei 13.146/2015)"

  - id: platform-policies
    check: "Content complies with the publishing platform's advertising and content policies"
    type: blocking
    validation: "Content reviewed against platform-specific ad policies (Meta, Google, TikTok, etc.)"
    veto_if_fail: "Platform policy violation = ad rejection, account suspension, or ban"
```

---

## Scoring

| Result | Criteria | Action |
|--------|----------|--------|
| PASS | ALL items across ALL levels pass | Content cleared for publication |
| FAIL | ANY single item fails | Content BLOCKED — cannot be published |

```yaml
scoring_rules:
  mode: "binary — pass/fail only"
  no_conditional: true
  rationale: "Legal compliance has no partial credit. Any violation exposes the brand to legal risk."
  escalation: |
    On FAIL:
      1. Content blocked immediately
      2. Specific failing items documented
      3. Content returned to creator with legal notes
      4. @marketing-chief (Vox) notified if Level 1 (LGPD) fails
      5. Legal review requested if Level 4 (Regulatory) fails
```

---

## Validation Execution

### Manual Validation Checklist

Copy this checklist and fill in:

```markdown
## Legal Compliance Gate: {content_title}

### Level 1: LGPD [ALL BLOCKING]
- [ ] Data collection has explicit consent mechanism
- [ ] Opt-out/unsubscribe mechanism provided
- [ ] Privacy policy linked
- [ ] Cookie notice present (if web)
- [ ] Only necessary data collected

### Level 2: Claims & Disclaimers [ALL BLOCKING]
- [ ] All claims verifiable with evidence
- [ ] Sources cited for data/statistics
- [ ] Required disclaimers present and visible
- [ ] No absolute guarantees without legal backing
- [ ] Comparative claims fair and substantiated

### Level 3: Rights & Licensing [ALL BLOCKING]
- [ ] Image rights/licenses confirmed
- [ ] Music/audio rights confirmed
- [ ] Testimonial consent documented
- [ ] Trademark usage correct
- [ ] Font licensing confirmed

### Level 4: Regulatory [ALL BLOCKING]
- [ ] Industry-specific regulations compliant
- [ ] CONAR code compliant
- [ ] Age restrictions properly handled
- [ ] Accessibility requirements met
- [ ] Platform policies compliant

### Result

**Total Items:** 20
**Passed:** ___/20
**Decision:** [ ] PASS (20/20) | [ ] FAIL (any item fails)
**Failing Items:** ___
**Reviewer:** ___
**Date:** ___
**Legal Notes:** ___
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
[@content-reviewer *legal-check] <-- THIS CHECKLIST
    |
    +-- PASS (20/20)  --> Pre-Publish Checklist
    +-- FAIL (any)     --> BLOCKED — return to creator with legal notes
                           +-- LGPD fail    --> Notify @marketing-chief
                           +-- Regulatory   --> Request legal review
```

---

**Version:** 1.0.0
**Created:** 2026-03-14
**Updated:** 2026-03-14
**Standard:** LMAS Marketing Domain — Legal Compliance (NON-NEGOTIABLE)
**Domain:** Marketing
**Constitutional Reference:** MK-III — Legal Compliance
