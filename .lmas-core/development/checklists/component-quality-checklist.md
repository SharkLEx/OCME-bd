# Component Quality Checklist

```yaml
checklist:
  id: component-quality
  version: 1.0.0
  created: 2026-03-17
  updated: 2026-03-17
  purpose: "Ensure every design system component meets quality, accessibility, performance, and documentation standards before release"
  mode: blocking
  domain: ux-design
  used_by:
    - "@ux-design-expert (Switch)"
    - "@dev (Neo)"
    - "@qa (Oracle)"
  scoring:
    scale: "0-10"
    pass: ">= 8"
    conditional: "6-7 (non-blocking items may be deferred)"
    fail: "< 6"
```

---

## Category 1: TypeScript & Props

- [ ] **Props interface defined** — Component has an explicit `ComponentNameProps` interface
- [ ] **No `any` types** — All props use specific types or `unknown` with type guards
- [ ] **Default props documented** — Default values are declared and match design spec
- [ ] **Event handler types correct** — Event props use React event types (e.g., `React.MouseEvent<HTMLButtonElement>`)
- [ ] **Generic props supported** — Polymorphic components accept `as` prop with correct type inference

## Category 2: Accessibility (a11y)

- [ ] **ARIA role assigned** — Interactive components have correct `role` attribute
- [ ] **ARIA labels present** — Non-text elements have `aria-label` or `aria-labelledby`
- [ ] **ARIA states managed** — Dynamic states use `aria-expanded`, `aria-selected`, `aria-disabled` correctly
- [ ] **Keyboard navigation works** — All interactions reachable via Tab, Enter, Space, Escape, Arrow keys
- [ ] **Focus management correct** — Focus trap in modals, focus return on close, visible focus ring
- [ ] **Screen reader tested** — Component announces correctly in NVDA/VoiceOver

## Category 3: Responsive Behavior

- [ ] **Mobile breakpoint works** — Component renders correctly at 320px width minimum
- [ ] **Tablet breakpoint works** — Component adapts at medium breakpoints (768px)
- [ ] **Desktop breakpoint works** — Component uses available space at 1024px+
- [ ] **No horizontal overflow** — No unintended horizontal scroll at any breakpoint
- [ ] **Touch targets adequate** — Interactive areas are at least 44x44px on mobile

## Category 4: Visual Regression

- [ ] **Snapshot test exists** — Visual snapshot covers default state
- [ ] **Variant snapshots exist** — Each variant (size, color, state) has a snapshot
- [ ] **Interaction states captured** — Hover, focus, active, disabled states are snapshot-tested
- [ ] **Dark mode snapshot exists** — Component renders correctly in dark theme (if applicable)

## Category 5: Documentation

- [ ] **JSDoc on component** — Component has JSDoc comment explaining purpose and usage
- [ ] **Props table generated** — All props are documented with types, defaults, and descriptions
- [ ] **Usage examples provided** — At least 2 code examples (basic and advanced usage)
- [ ] **Do/Don't guidelines** — Common misuse patterns are documented with correct alternatives

## Category 6: Storybook / Examples

- [ ] **Default story exists** — Storybook story shows component in default state
- [ ] **All variants shown** — Each prop variant has a dedicated story
- [ ] **Interactive controls** — Storybook args allow real-time prop manipulation
- [ ] **Composition example** — Story shows component composed with other components

## Category 7: Performance

- [ ] **Bundle size measured** — Component's contribution to bundle is under threshold (< 5KB gzipped)
- [ ] **No unnecessary re-renders** — Component uses `React.memo` or `useMemo` where beneficial
- [ ] **Lazy loading supported** — Heavy components support `React.lazy` import
- [ ] **No layout thrashing** — Component does not cause forced reflows on mount/update

## Category 8: Design Token Usage

- [ ] **No hardcoded colors** — All colors reference design tokens (CSS custom properties or theme)
- [ ] **No hardcoded spacing** — All spacing uses token scale values
- [ ] **No hardcoded typography** — Font sizes, weights, line heights use tokens
- [ ] **Theme-aware** — Component responds to theme changes without code modification

---

## Scoring Guide

| Score | Meaning |
|-------|---------|
| 10 | All items pass — production ready |
| 8-9 | Minor documentation or snapshot gaps — ship with follow-up ticket |
| 6-7 | Accessibility or responsive gaps — fix before release |
| 4-5 | Missing TypeScript types or significant a11y failures — blocked |
| 0-3 | Fundamental quality issues — requires redesign |
