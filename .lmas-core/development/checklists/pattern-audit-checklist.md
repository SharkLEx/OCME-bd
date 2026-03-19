# Pattern Audit Checklist

```yaml
checklist:
  id: pattern-audit
  version: 1.0.0
  created: 2026-03-17
  updated: 2026-03-17
  purpose: "Audit design system patterns for visual consistency, redundancy, and token extraction readiness"
  mode: blocking
  domain: ux-design
  used_by:
    - "@ux-design-expert (Switch)"
  scoring:
    scale: "0-10"
    pass: ">= 8"
    conditional: "6-7 (minor gaps acceptable)"
    fail: "< 6"
```

---

## Category 1: Visual Consistency

- [ ] **Color palette adherence** — All colors in use trace back to defined palette tokens (no one-off hex values)
- [ ] **Spacing scale compliance** — All spacing values follow the defined spacing scale (4px/8px grid or project standard)
- [ ] **Typography consistency** — Font families, sizes, weights, and line heights match the type scale definition
- [ ] **Border radius uniformity** — Border radius values come from a defined set (not arbitrary pixel values)
- [ ] **Shadow consistency** — Elevation levels use defined shadow tokens, no inline box-shadow overrides

## Category 2: Component Inventory

- [ ] **Atom inventory complete** — All atomic-level elements (buttons, inputs, labels, icons) are cataloged
- [ ] **Molecule inventory complete** — All composed elements (search bars, form groups, cards) are cataloged
- [ ] **Organism inventory complete** — All complex sections (headers, footers, sidebars, modals) are cataloged
- [ ] **Variant documentation** — Each component lists all known variants (size, state, theme)
- [ ] **Usage frequency recorded** — Components have approximate usage counts across the codebase

## Category 3: Redundancy Identification

- [ ] **Duplicate components flagged** — Components serving the same purpose are identified and grouped
- [ ] **Near-duplicate variants flagged** — Components differing by < 3 properties are marked for consolidation
- [ ] **Inconsistent naming detected** — Same-purpose components with different names across codebases are listed
- [ ] **Dead components identified** — Components with zero usage in production code are flagged for removal
- [ ] **Override frequency analyzed** — Components frequently overridden at the call site indicate design gaps

## Category 4: Token Extraction Readiness

- [ ] **Hardcoded values inventory** — All hardcoded color, spacing, and typography values are listed
- [ ] **Token naming draft** — Proposed token names follow CTI (Category-Type-Item) or project convention
- [ ] **Semantic mapping defined** — Primitive tokens map to semantic aliases (e.g., `blue-500` -> `color-primary`)
- [ ] **Theme support assessed** — Token structure supports light/dark or multi-brand theming
- [ ] **Export format decided** — Target formats identified (CSS custom properties, Tailwind config, JSON, etc.)

## Category 5: Framework Compatibility

- [ ] **React compatibility verified** — Components work as React components or can be wrapped
- [ ] **CSS strategy compatible** — Token format aligns with project CSS approach (Tailwind, CSS Modules, CSS-in-JS)
- [ ] **Build pipeline integration** — Token build step (Style Dictionary, custom script) is defined
- [ ] **Storybook integration path** — Components can render in Storybook with token theming
- [ ] **Testing strategy defined** — Visual regression and accessibility tests are planned for migrated components

---

## Scoring Guide

| Score | Meaning |
|-------|---------|
| 10 | All items pass, zero gaps |
| 8-9 | Minor gaps in non-blocking categories, safe to proceed |
| 6-7 | Gaps in token readiness or redundancy — address before migration |
| 4-5 | Significant inventory gaps — complete audit before proceeding |
| 0-3 | Audit incomplete — restart with focused data collection |
