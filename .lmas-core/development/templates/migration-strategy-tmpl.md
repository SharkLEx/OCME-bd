# Migration Strategy — {{PROJECT_NAME}}

> **Template ID:** migration-strategy | **Version:** 1.0.0 | **Created:** 2026-03-17
> **Used by:** @ux-design-expert (Switch), @architect (Architect)
> **Status:** {{Draft | Approved | InProgress | Completed}}
> **Story Ref:** {{STORY_ID}}

---

## Executive Summary

{{2-3 sentences describing why this migration is happening, the expected outcome, and the high-level timeline. Focus on business value, not technical details.}}

**Key Numbers:**
- Components to migrate: {{N}}
- Estimated effort: {{N}} hours / {{N}} sprints
- Expected CSS reduction: {{N}}%
- Expected dev velocity improvement: {{N}}%

---

## Current State

### Design System Inventory

| Metric | Value |
|--------|-------|
| Total components | {{N}} |
| Unique colors in use | {{N}} |
| Spacing values in use | {{N}} |
| Font size combinations | {{N}} |
| Duplicate/near-duplicate components | {{N}} |
| CSS bundle size | {{N}} KB |

### Pain Points

1. {{Pain point 1 — e.g., "12 button variants across 4 files with inconsistent APIs"}}
2. {{Pain point 2 — e.g., "No design tokens — all values hardcoded"}}
3. {{Pain point 3 — e.g., "Accessibility failures on 30% of components"}}

### Audit Score

- Pattern Audit: {{N}}/10
- Migration Readiness: {{N}}/10

---

## Target State

### Architecture

- **Token format:** {{W3C DTCG / Style Dictionary / Custom}}
- **Component framework:** {{React + TypeScript}}
- **Styling approach:** {{Tailwind CSS / CSS Modules / CSS-in-JS}}
- **Documentation:** {{Storybook / custom docs site}}
- **Testing:** {{Visual regression + a11y + unit}}

### Token Structure

```
tokens/
  colors/
    primitive.yaml    # Raw color values
    semantic.yaml     # Alias tokens (primary, error, surface)
  typography/
    scale.yaml        # Font sizes, weights, line heights
  spacing/
    scale.yaml        # Spacing scale (4px base)
  shadows.yaml        # Elevation levels
  borders.yaml        # Radius, width
  motion.yaml         # Durations, easings
```

### Component Architecture

```
components/
  atoms/              # Button, Input, Label, Icon, Badge
  molecules/          # SearchBar, FormGroup, Card, Chip
  organisms/          # Header, Sidebar, Modal, DataTable
  layouts/            # PageLayout, SplitView, Stack
```

---

## 4-Phase Migration Plan

### Phase 1: Foundation (Sprint {{N}})

**Goal:** Establish token system and base styles.

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| Extract color tokens from codebase | @ux-design-expert | {{N}}h | [ ] |
| Extract typography tokens | @ux-design-expert | {{N}}h | [ ] |
| Extract spacing/border/shadow tokens | @ux-design-expert | {{N}}h | [ ] |
| Set up token build pipeline | @dev | {{N}}h | [ ] |
| Generate CSS custom properties export | @dev | {{N}}h | [ ] |
| Generate Tailwind config export | @dev | {{N}}h | [ ] |
| Create base theme (light) | @ux-design-expert | {{N}}h | [ ] |
| Create dark theme (if applicable) | @ux-design-expert | {{N}}h | [ ] |

**Exit criteria:** All tokens exported, build pipeline working, base styles applied globally.

### Phase 2: Atoms (Sprint {{N}})

**Goal:** Migrate foundational components using new tokens.

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| Button (all variants) | @dev | {{N}}h | [ ] |
| Input (text, number, search) | @dev | {{N}}h | [ ] |
| Label / FormLabel | @dev | {{N}}h | [ ] |
| Icon system | @dev | {{N}}h | [ ] |
| Badge / Tag | @dev | {{N}}h | [ ] |
| Typography components (Heading, Text) | @dev | {{N}}h | [ ] |
| Accessibility audit on atoms | @qa | {{N}}h | [ ] |
| Visual regression snapshots | @qa | {{N}}h | [ ] |

**Exit criteria:** All atoms pass component-quality-checklist (score >= 8), a11y audit clean.

### Phase 3: Molecules & Organisms (Sprint {{N}}-{{N}})

**Goal:** Migrate composed components, deprecate old versions.

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| Card / CardGroup | @dev | {{N}}h | [ ] |
| SearchBar | @dev | {{N}}h | [ ] |
| FormGroup | @dev | {{N}}h | [ ] |
| Modal / Dialog | @dev | {{N}}h | [ ] |
| Header / Navigation | @dev | {{N}}h | [ ] |
| Sidebar | @dev | {{N}}h | [ ] |
| DataTable | @dev | {{N}}h | [ ] |
| Deprecation warnings on old components | @dev | {{N}}h | [ ] |
| Integration tests for key flows | @qa | {{N}}h | [ ] |

**Exit criteria:** All organisms pass quality checklist, deprecation warnings active, no regressions.

### Phase 4: Cleanup & Documentation (Sprint {{N}})

**Goal:** Remove old components, finalize docs, validate metrics.

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| Remove deprecated components | @dev | {{N}}h | [ ] |
| Remove unused CSS | @dev | {{N}}h | [ ] |
| Final bundle size measurement | @dev | {{N}}h | [ ] |
| Storybook documentation complete | @ux-design-expert | {{N}}h | [ ] |
| Migration guide for consumers | @ux-design-expert | {{N}}h | [ ] |
| Final a11y audit (full suite) | @qa | {{N}}h | [ ] |
| ROI report generation | @ux-design-expert | {{N}}h | [ ] |

**Exit criteria:** Old code removed, bundle size meets target, docs complete, ROI validated.

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| {{Breaking change missed}} | Medium | High | Codemod scripts + feature flags |
| {{Token naming conflicts}} | Low | Medium | Naming convention review before Phase 1 |
| {{Team adoption resistance}} | Medium | Medium | Migration guide + pair sessions |
| {{Performance regression}} | Low | High | Bundle size CI check + performance benchmarks |
| {{Timeline slippage}} | Medium | Medium | Phase-gated approach, can pause after any phase |

---

## Rollback Procedures

### Per-Component Rollback
1. Revert the component's migration PR
2. Remove new component from exports
3. Re-enable deprecated component (remove deprecation warning)
4. Verify integration tests pass

### Full Phase Rollback
1. Revert all PRs in the phase (reverse merge order)
2. Remove generated token files if Phase 1
3. Re-enable all deprecated components
4. Run full test suite to confirm clean revert

### Emergency Rollback
1. Feature flag: disable new design system globally
2. Old components remain functional until flag is resolved
3. No data migration involved — purely code-level revert

---

## Timeline

| Phase | Start | End | Duration |
|-------|-------|-----|----------|
| Phase 1: Foundation | {{DATE}} | {{DATE}} | {{N}} sprint(s) |
| Phase 2: Atoms | {{DATE}} | {{DATE}} | {{N}} sprint(s) |
| Phase 3: Molecules & Organisms | {{DATE}} | {{DATE}} | {{N}} sprint(s) |
| Phase 4: Cleanup | {{DATE}} | {{DATE}} | {{N}} sprint(s) |
| **Total** | | | **{{N}} sprint(s)** |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| CSS bundle reduction | >= {{N}}% | Build output comparison |
| Component count reduction | >= {{N}}% | Component inventory count |
| WCAG AA compliance | 100% | axe-core CI scan |
| Developer satisfaction | >= 4/5 | Team survey post-migration |
| Design consistency score | >= 9/10 | Pattern audit re-run |
| Visual regression | 0 regressions | Snapshot comparison |
