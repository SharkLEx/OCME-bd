# Mobile Check — Mobile-First Design Validation

> **Task ID:** ux-mobile-check
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** dev, qa, ux-design-expert
> **Elicit:** false
> **Category:** design-quality

---

## Purpose

Validate a component, page, or design against mobile-first best practices. Checks touch targets, font sizes, spacing, scroll behavior, viewport adaptations, and responsive patterns. Returns a mobile readiness score with specific issues and recommendations.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `target` | string | yes | User Input | File path, component name, or URL to validate |
| `mode` | string | no | User Input | `yolo` \| `interactive`. Default: `yolo` |
| `device` | string | no | User Input | Target device class: "phone", "tablet", "both". Default: `both` |
| `breakpoint` | number | no | User Input | Specific breakpoint to test (px). Default: 375 (iPhone SE) |

---

## Execution Flow

### 1. Load Reference Data
1.1. Read `.lmas-core/development/data/ux/components.csv` — component mobile specifications
1.2. Read `.lmas-core/development/data/ux/responsive.csv` (if exists) — responsive breakpoint rules
1.3. If responsive.csv missing → use built-in mobile-first standards
1.4. Validation: At least components.csv loaded

### 2. Resolve Target
2.1. If `target` is a file path (`.tsx`, `.jsx`, `.vue`, `.html`):
   - Read file content
   - Parse CSS classes, inline styles, layout components
   - Extract touch elements (buttons, links, inputs, selects)
2.2. If `target` is a component name:
   - Look up in components.csv for expected mobile behavior
   - Check against known patterns
2.3. If `target` is a URL:
   - Note: full URL audit requires browser tool
   - Provide static checklist for manual verification
2.4. Validation: Target resolved

### 3. Touch Target Audit
3.1. Identify all interactive elements:
   - Buttons, links, inputs, selects, checkboxes, radio buttons
   - Custom clickable areas (onClick handlers)
   - Icon-only buttons
3.2. Check minimum size: 44x44px (WCAG 2.5.8 Target Size)
   - Parse explicit width/height, padding, min-width/min-height
   - Check Tailwind classes: `p-*`, `h-*`, `w-*`, `min-h-*`, `min-w-*`
   - Icon buttons without padding are high-risk
3.3. Check spacing between targets: minimum 8px gap
3.4. Flag elements below threshold with exact measurements
3.5. Score: count passing / total interactive elements

### 4. Typography Audit
4.1. Check body text size: minimum 16px (prevents iOS auto-zoom)
4.2. Check heading hierarchy: minimum 20px for mobile H1
4.3. Check line height: minimum 1.4 for body text on mobile
4.4. Check text truncation: ensure `text-overflow: ellipsis` or responsive sizing
4.5. Check max line length: 45-75 characters per line recommended
4.6. Score: count passing / total text checks

### 5. Spacing & Layout Audit
5.1. Check horizontal padding: minimum 16px page margins on mobile
5.2. Check vertical spacing between sections: minimum 24px
5.3. Check for horizontal scroll:
   - Elements with fixed widths > viewport
   - Tables without horizontal scroll wrapper
   - Images without `max-width: 100%`
5.4. Check flex/grid behavior:
   - Multi-column → single-column at phone breakpoint
   - Grid items don't overflow container
5.5. Score: count passing / total layout checks

### 6. Scroll & Interaction Audit
6.1. Check scroll behavior:
   - `scroll-behavior: smooth` for anchor links
   - No scroll-jacking or unexpected scroll lock
   - Sticky headers don't consume > 15% viewport
6.2. Check gestures:
   - Swipe areas have sufficient size
   - No hover-only interactions (must have touch alternative)
   - Long-press actions have visible alternative
6.3. Check forms on mobile:
   - Correct `inputmode` attributes (numeric, email, tel, url)
   - Labels visible (not placeholder-only)
   - Submit button full-width on mobile
6.4. Score: count passing / total interaction checks

### 7. Performance Considerations
7.1. Check image optimization:
   - Images use responsive `srcset` or CSS `object-fit`
   - Lazy loading on below-fold images (`loading="lazy"`)
   - No images > 500KB without responsive sizing
7.2. Check animation:
   - Respects `prefers-reduced-motion` media query
   - No animations blocking interaction
7.3. Score: count passing / total performance checks

### 8. Calculate Mobile Readiness Score
8.1. Weight categories:
   - Touch Targets: 30%
   - Typography: 20%
   - Spacing & Layout: 20%
   - Scroll & Interaction: 20%
   - Performance: 10%
8.2. Calculate weighted score (0-100)
8.3. Assign readiness level: Ready (85+), Needs Work (70-84), Not Ready (<70)
8.4. Validation: Score calculated

---

## Output Format

```markdown
## 📱 Mobile Check: {target}

### Readiness Score: {score}/100 — {Ready/Needs Work/Not Ready}

| Category | Score | Issues |
|----------|-------|--------|
| Touch Targets | {X}/30 | {count} |
| Typography | {X}/20 | {count} |
| Spacing & Layout | {X}/20 | {count} |
| Scroll & Interaction | {X}/20 | {count} |
| Performance | {X}/10 | {count} |

### Issues Found ({total})
| # | Severity | Category | Element | Issue | Fix |
|---|----------|----------|---------|-------|-----|
| 1 | ERROR | touch | `.icon-btn` | 24x24px < 44px minimum | Add `p-2.5` (min-h-[44px] min-w-[44px]) |
| 2 | ERROR | typography | `body` | font-size: 14px < 16px minimum | Change to `text-base` (16px) |
| 3 | WARN | layout | `.grid` | 3-col at 375px causes overflow | Add `grid-cols-1 md:grid-cols-3` |

### Device Preview Notes
- **Phone (375px):** {summary}
- **Tablet (768px):** {summary}

### Quick Fixes
```diff
- <button class="p-1"><Icon /></button>
+ <button class="p-2.5 min-h-[44px] min-w-[44px]"><Icon /></button>
```
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| File not found | Target path does not exist | Ask user to verify path |
| Unparseable file | File format not supported | List supported formats (.tsx, .jsx, .vue, .html) |
| URL target | Cannot perform static analysis on URLs | Provide manual checklist, suggest using browser tool |
| No interactive elements | Component has no buttons/links/inputs | Skip touch target audit, validate layout only |

---

## Examples

### Example 1: Component File

```
*mobile-check src/components/Header.tsx
```

Returns: 72/100 (Needs Work) — hamburger icon too small, font size 14px in nav, sticky header takes 20% viewport.

### Example 2: Named Component

```
*mobile-check form --device=phone
```

Returns: Phone-specific validation — input modes, label visibility, submit button width, touch target sizes.

### Example 3: Specific Breakpoint

```
*mobile-check src/pages/Dashboard.tsx --breakpoint=390
```

Returns: Validation at iPhone 14 Pro width — checks layout, overflow, and spacing at exact 390px width.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/components.csv
tags:
  - ux
  - mobile-first
  - responsive
  - validation
  - data-driven
updated_at: 2026-03-17
```
