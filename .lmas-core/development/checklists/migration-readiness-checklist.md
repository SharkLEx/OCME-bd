# Migration Readiness Checklist

```yaml
checklist:
  id: migration-readiness
  version: 1.0.0
  created: 2026-03-17
  updated: 2026-03-17
  purpose: "Verify all prerequisites are met before starting a design system migration"
  mode: blocking
  domain: ux-design
  used_by:
    - "@ux-design-expert (Switch)"
    - "@architect (Architect)"
  scoring:
    scale: "0-10"
    pass: ">= 8"
    conditional: "6-7 (proceed with documented risks)"
    fail: "< 6 (do not start migration)"
```

---

## Category 1: Current State Assessment

- [ ] **Pattern audit completed** — `pattern-audit-checklist.md` passed with score >= 6
- [ ] **Component inventory finalized** — All existing components cataloged with usage counts
- [ ] **Technical debt documented** — Known issues, workarounds, and overrides are listed
- [ ] **Dependency map created** — Component inter-dependencies are mapped (which components use which)
- [ ] **Codebase metrics baseline** — Bundle size, number of components, CSS file count recorded as baseline

## Category 2: Token Extraction

- [ ] **Token extraction complete** — All hardcoded values converted to token definitions
- [ ] **Token naming validated** — Token names follow CTI convention and are reviewed by team
- [ ] **Semantic tokens defined** — Primitive tokens mapped to semantic aliases (primary, secondary, surface, etc.)
- [ ] **Multi-theme tokens ready** — Token structure supports light/dark themes (if applicable)
- [ ] **Token export pipeline tested** — Build generates CSS custom properties, Tailwind config, or target format correctly

## Category 3: Component Readiness

- [ ] **Target component API designed** — Props interface for each migrated component is defined
- [ ] **Component priority list created** — Migration order established (atoms first, then molecules, organisms)
- [ ] **Shared utilities identified** — Common hooks, utilities, and helpers needed by multiple components are listed
- [ ] **Third-party dependencies reviewed** — External UI libraries (if any) are compatible with new design system

## Category 4: Breaking Changes

- [ ] **Breaking changes inventory** — All prop renames, removed features, and API changes are documented
- [ ] **Codemod scripts prepared** — Automated migration scripts exist for mechanical changes (import paths, prop renames)
- [ ] **Deprecation warnings added** — Old components log deprecation warnings pointing to new equivalents
- [ ] **Migration guide written** — Step-by-step guide for consumers to migrate from old to new components

## Category 5: Rollback Plan

- [ ] **Rollback strategy defined** — Clear procedure to revert migration per-component if issues arise
- [ ] **Feature flags configured** — New components can be toggled off, falling back to old versions
- [ ] **Version pinning possible** — Consumers can pin to pre-migration version if needed
- [ ] **Data migration reversible** — Any config or data format changes can be reversed

## Category 6: Team Communication

- [ ] **Migration timeline shared** — Team knows start date, phases, and expected completion
- [ ] **Ownership assigned** — Each component has an assigned owner for migration
- [ ] **Review process defined** — PR review requirements for migrated components are agreed upon
- [ ] **Feedback channel established** — Team has a way to report migration issues quickly

## Category 7: Testing Coverage

- [ ] **Unit tests exist for old components** — Baseline tests capture current behavior before migration
- [ ] **Visual regression baseline captured** — Screenshots of all components in current state
- [ ] **Integration tests cover key flows** — Critical user flows have end-to-end test coverage
- [ ] **Accessibility tests automated** — axe-core or equivalent runs in CI for migrated components
- [ ] **Performance benchmarks recorded** — Render time and bundle size benchmarks for comparison post-migration

---

## Scoring Guide

| Score | Meaning |
|-------|---------|
| 10 | All prerequisites met — begin migration confidently |
| 8-9 | Minor gaps (communication, some tests) — proceed with tracked items |
| 6-7 | Token or rollback gaps — address before starting Phase 2+ |
| 4-5 | Significant readiness gaps — postpone migration, complete prerequisites |
| 0-3 | Critical gaps — migration would fail, restart preparation |
