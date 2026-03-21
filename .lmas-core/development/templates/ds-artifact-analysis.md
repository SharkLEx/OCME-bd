# Design System Artifact Analysis — {{ARTIFACT_NAME}}

> **Template ID:** ds-artifact-analysis | **Version:** 1.0.0 | **Created:** 2026-03-17
> **Used by:** @ux-design-expert (Switch)
> **Artifact Source:** {{file path, URL, or Figma link}}
> **Analysis Date:** {{DATE}}
> **Status:** {{Draft | Final}}

---

## 1. Artifact Overview

| Field | Value |
|-------|-------|
| **Type** | {{Figma file / Codebase / Style guide / CSS file / Component library}} |
| **Scope** | {{Full app / Single feature / Landing page / Component set}} |
| **Framework** | {{React / Vue / Angular / HTML-CSS / Framework-agnostic}} |
| **Size** | {{N components / N screens / N CSS files}} |
| **Last Modified** | {{DATE}} |

**Description:**
{{2-3 sentences describing what this artifact contains and its role in the project.}}

---

## 2. Patterns Found

### Color Patterns

| Pattern | Occurrences | Values | Recommendation |
|---------|-------------|--------|----------------|
| {{Primary action color}} | {{N}} | {{#2563EB, #3B82F6, #2555DD}} | Consolidate to single token `color-primary` |
| {{Error color}} | {{N}} | {{#EF4444, #DC2626, #FF0000}} | Consolidate to `color-error` |
| {{Text colors}} | {{N}} | {{#111827, #1F2937, #000}} | Normalize to `color-text-primary` |

### Typography Patterns

| Pattern | Occurrences | Values | Recommendation |
|---------|-------------|--------|----------------|
| {{Heading style}} | {{N}} | {{24px/700, 1.5rem/bold, 26px/600}} | Standardize to `font-size-2xl` + `font-weight-bold` |
| {{Body text}} | {{N}} | {{16px/400, 1rem/normal, 14px/400}} | Standardize to `font-size-base` |

### Spacing Patterns

| Pattern | Occurrences | Values | Recommendation |
|---------|-------------|--------|----------------|
| {{Container padding}} | {{N}} | {{16px, 20px, 24px, 1rem, 1.5rem}} | Normalize to `spacing-4` (16px) |
| {{Gap between elements}} | {{N}} | {{8px, 10px, 12px}} | Normalize to `spacing-2` (8px) or `spacing-3` (12px) |

---

## 3. Tokens Extracted

**Total tokens identified:** {{N}}

| Category | Count | Extraction Status |
|----------|-------|-------------------|
| Colors (primitive) | {{N}} | {{Done / Pending}} |
| Colors (semantic) | {{N}} | {{Done / Pending}} |
| Typography | {{N}} | {{Done / Pending}} |
| Spacing | {{N}} | {{Done / Pending}} |
| Borders | {{N}} | {{Done / Pending}} |
| Shadows | {{N}} | {{Done / Pending}} |
| Motion | {{N}} | {{Done / Pending}} |

---

## 4. Component Inventory

| Component | Type | Variants | Usage Count | Quality | Notes |
|-----------|------|----------|-------------|---------|-------|
| {{Button}} | Atom | {{N}} | {{N}} | {{Good / Needs work / Poor}} | {{e.g., "3 duplicate implementations"}} |
| {{Card}} | Molecule | {{N}} | {{N}} | {{Good / Needs work / Poor}} | |
| {{Modal}} | Organism | {{N}} | {{N}} | {{Good / Needs work / Poor}} | |
| {{Header}} | Organism | {{N}} | {{N}} | {{Good / Needs work / Poor}} | |

**Totals:** {{N}} atoms, {{N}} molecules, {{N}} organisms

---

## 5. Redundancy Analysis

### Duplicate Groups

| Group | Components | Similarity | Merge Effort |
|-------|------------|------------|--------------|
| {{Buttons}} | {{PrimaryButton, ActionButton, SubmitBtn}} | {{85%}} | {{Low — same API, different names}} |
| {{Cards}} | {{Card, ProductCard, InfoCard}} | {{60%}} | {{Medium — different prop interfaces}} |

### Dead Code

| Component | Last Used | Recommendation |
|-----------|-----------|----------------|
| {{OldButton}} | {{Never / 6+ months}} | Remove |
| {{LegacyModal}} | {{Never / 6+ months}} | Remove |

**Redundancy Score:** {{N}}% of components have duplicates or near-duplicates.

---

## 6. Recommendations

### Priority 1 (Critical)

- {{Action item — e.g., "Consolidate 47 unique colors to 20 semantic tokens"}}
- {{Action item — e.g., "Remove 5 dead components (0 usage in production)"}}

### Priority 2 (Important)

- {{Action item — e.g., "Standardize spacing to 4px grid — currently 23 unique values"}}
- {{Action item — e.g., "Add ARIA attributes to 12 interactive components missing a11y"}}

### Priority 3 (Nice to Have)

- {{Action item — e.g., "Create Storybook stories for all atoms"}}
- {{Action item — e.g., "Add dark mode token aliases"}}

---

## 7. Severity Ratings

| Area | Severity | Score | Notes |
|------|----------|-------|-------|
| Color consistency | {{Critical / High / Medium / Low}} | {{N}}/10 | |
| Typography consistency | {{Critical / High / Medium / Low}} | {{N}}/10 | |
| Spacing consistency | {{Critical / High / Medium / Low}} | {{N}}/10 | |
| Component quality | {{Critical / High / Medium / Low}} | {{N}}/10 | |
| Accessibility | {{Critical / High / Medium / Low}} | {{N}}/10 | |
| Documentation | {{Critical / High / Medium / Low}} | {{N}}/10 | |
| **Overall** | | **{{N}}/10** | |
