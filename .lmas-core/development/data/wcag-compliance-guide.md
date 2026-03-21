# WCAG Compliance Guide — On-Demand Knowledge Base

> **Usage:** Loaded on-demand by @ux-design-expert (Switch) and @qa (Oracle) during accessibility audits.
> Do NOT pre-load during agent activation. Load when performing a11y reviews.
> **Last Updated:** 2026-03 (review quarterly)

---

## 1. Contrast Ratios

### Requirements

| Level | Normal Text (< 18pt) | Large Text (>= 18pt or 14pt bold) | UI Components |
|-------|----------------------|-------------------------------------|---------------|
| **AA** | 4.5:1 | 3:1 | 3:1 |
| **AAA** | 7:1 | 4.5:1 | Not specified |

### How to measure
- Compare foreground color against background color
- Use relative luminance formula: `L = 0.2126*R + 0.7152*G + 0.0722*B`
- Contrast ratio: `(L1 + 0.05) / (L2 + 0.05)` where L1 is the lighter color

### Common failures
- Gray text on white: `#9CA3AF` on `#FFFFFF` = 2.9:1 (FAILS AA)
- Light gray text on white: `#D1D5DB` on `#FFFFFF` = 1.5:1 (FAILS)
- Placeholder text: browsers default to low-contrast — override with `::placeholder` styles

### Safe text colors on white (#FFFFFF)
| Color | Hex | Ratio | Level |
|-------|-----|-------|-------|
| Gray 500 | #6B7280 | 5.0:1 | AA pass |
| Gray 600 | #4B5563 | 7.2:1 | AAA pass |
| Gray 700 | #374151 | 10.3:1 | AAA pass |
| Blue 600 | #2563EB | 4.6:1 | AA pass |
| Red 600 | #DC2626 | 4.6:1 | AA pass |

---

## 2. Keyboard Navigation

### Required keyboard interactions

| Component | Keys | Behavior |
|-----------|------|----------|
| Button | `Enter`, `Space` | Activate |
| Link | `Enter` | Navigate |
| Checkbox | `Space` | Toggle |
| Radio | `Arrow Up/Down` | Move selection within group |
| Select/Dropdown | `Arrow Up/Down`, `Enter`, `Escape` | Navigate options, select, close |
| Tab/TabPanel | `Arrow Left/Right` | Switch tabs |
| Modal | `Tab` (trapped), `Escape` | Cycle focus, close |
| Menu | `Arrow Up/Down`, `Enter`, `Escape` | Navigate items, activate, close |
| Slider | `Arrow Left/Right` | Adjust value |
| Accordion | `Enter`, `Space` | Toggle section |

### Focus management rules
1. **Visible focus ring** — Never `outline: none` without a visible replacement
2. **Logical tab order** — Follows DOM order (avoid `tabindex > 0`)
3. **Focus trap in modals** — Tab cycles within modal, Escape closes
4. **Focus return** — When a modal/popover closes, return focus to the trigger element
5. **Skip links** — First focusable element should be "Skip to main content"

---

## 3. ARIA Patterns

### When to use ARIA
1. First, use semantic HTML (`<button>`, `<nav>`, `<main>`, `<dialog>`)
2. Only add ARIA when HTML semantics are insufficient
3. Never use ARIA to override correct native semantics

### Common ARIA patterns

**Disclosure (expandable section):**
```html
<button aria-expanded="false" aria-controls="panel1">Section Title</button>
<div id="panel1" role="region" hidden>Content...</div>
```

**Tabs:**
```html
<div role="tablist">
  <button role="tab" aria-selected="true" aria-controls="tab1-panel">Tab 1</button>
  <button role="tab" aria-selected="false" aria-controls="tab2-panel">Tab 2</button>
</div>
<div role="tabpanel" id="tab1-panel">Panel 1 content</div>
<div role="tabpanel" id="tab2-panel" hidden>Panel 2 content</div>
```

**Modal dialog:**
```html
<div role="dialog" aria-modal="true" aria-labelledby="dialog-title">
  <h2 id="dialog-title">Dialog Title</h2>
  <p>Dialog content</p>
  <button>Close</button>
</div>
```

**Live region (status messages):**
```html
<div role="status" aria-live="polite">3 items added to cart</div>
<div role="alert" aria-live="assertive">Error: invalid email</div>
```

### ARIA state attributes

| Attribute | Used for | Values |
|-----------|----------|--------|
| `aria-expanded` | Dropdowns, accordions | `true` / `false` |
| `aria-selected` | Tabs, list items | `true` / `false` |
| `aria-checked` | Checkboxes, toggles | `true` / `false` / `mixed` |
| `aria-disabled` | Disabled elements | `true` / `false` |
| `aria-hidden` | Decorative elements | `true` / `false` |
| `aria-busy` | Loading states | `true` / `false` |
| `aria-invalid` | Form validation | `true` / `false` |
| `aria-current` | Current page/step | `page` / `step` / `true` |

---

## 4. Color Independence

Never rely on color alone to convey information:

| Pattern | Bad | Good |
|---------|-----|------|
| Form errors | Red border only | Red border + error icon + error text |
| Status indicators | Green/red dot | Dot + label text ("Active" / "Inactive") |
| Charts | Color-only legend | Color + pattern fill + text labels |
| Links in text | Color only | Color + underline |
| Required fields | Red asterisk | Asterisk + "Required" text for screen readers |

---

## 5. Motion Sensitivity

### `prefers-reduced-motion`

Always provide a reduced-motion alternative:

```css
/* Default: animations enabled */
.element { transition: transform 300ms ease; }

/* Reduced motion: instant transitions */
@media (prefers-reduced-motion: reduce) {
  .element { transition: none; }
}
```

### Rules
- Disable parallax scrolling when reduced motion is preferred
- Replace slide/bounce animations with fade or instant transitions
- Never auto-play video/animation without a pause control
- Avoid content that flashes more than 3 times per second (seizure risk)

---

## 6. Text Alternatives

### Image `alt` text rules

| Image Type | Alt Text |
|------------|----------|
| Informative | Describe the content and function |
| Decorative | `alt=""` (empty string) |
| Functional (button/link) | Describe the action, not the image |
| Complex (chart/diagram) | Short alt + long description via `aria-describedby` |
| Text in image | Reproduce the text verbatim |

### Icon guidelines
- Icons with text labels: `aria-hidden="true"` on the icon (text provides meaning)
- Icons without text: `aria-label="Description"` on the icon or its container
- Icon buttons: `aria-label` on the `<button>`, icon is decorative

---

## 7. Form Validation

### Accessible error handling

1. **Identify errors** — Use `aria-invalid="true"` on the field
2. **Describe errors** — Link with `aria-describedby` to error message element
3. **Announce errors** — Use `role="alert"` or `aria-live="assertive"` for dynamic errors
4. **Error summary** — On submit, show summary at top of form with links to each error field
5. **Focus management** — Move focus to error summary or first error field after submit

```html
<label for="email">Email</label>
<input id="email" type="email" aria-invalid="true" aria-describedby="email-error" />
<div id="email-error" role="alert">Please enter a valid email address</div>
```

---

## 8. Testing Checklist (Quick Reference)

| Test | Tool | Time |
|------|------|------|
| Automated scan | axe-core / axe DevTools | 1 min |
| Contrast check | Browser DevTools color picker | 2 min |
| Keyboard navigation | Tab through entire page | 5 min |
| Screen reader | NVDA (Windows) / VoiceOver (Mac) | 10 min |
| Zoom test | Browser zoom to 200% | 2 min |
| Reduced motion | OS setting or CSS media query | 1 min |
