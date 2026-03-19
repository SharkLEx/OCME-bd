# Validate Pattern — UI Pattern Best Practice Validation

> **Task ID:** ux-validate-pattern
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** dev, qa, architect, ux-design-expert
> **Elicit:** false
> **Category:** design-quality

---

## Purpose

Validate a UI component or design pattern against established best practices. Cross-references patterns data, components data, and accessibility checklists to produce a compliance score, list of issues found, and actionable recommendations.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `target` | string | yes | User Input | Component name (e.g., "modal"), pattern name (e.g., "infinite-scroll"), or file path to component |
| `mode` | string | no | User Input | `yolo` \| `interactive`. Default: `interactive` |
| `scope` | string | no | User Input | Validation scope: `a11y` \| `responsive` \| `tokens` \| `naming` \| `all`. Default: `all` |
| `strict` | boolean | no | User Input | If true, treat warnings as errors. Default: false |

---

## Execution Flow

### 1. Load Reference Data
1.1. Read `.lmas-core/development/data/ux/components.csv`
1.2. Read `.lmas-core/development/data/ux/patterns.csv` (if exists)
1.3. Load accessibility checklist from `.lmas-core/development/data/ux/accessibility-wcag-checklist.md` (if exists)
1.4. If any file missing → use built-in pattern knowledge as fallback
1.5. Validation: At least components.csv loaded

### 2. Resolve Target
2.1. If `target` is a file path:
   - Read the file content
   - Extract component name from file/export
   - Parse JSX/TSX structure, props, ARIA attributes, class names
2.2. If `target` is a component name:
   - Search `components.csv` for matching component definition
   - Extract expected props, ARIA requirements, interaction patterns
2.3. If `target` is a pattern name:
   - Search `patterns.csv` for matching pattern definition
   - Extract expected behavior, component composition, UX guidelines
2.4. If no match in CSVs → use built-in knowledge for common patterns (modal, dropdown, tabs, accordion, toast, form, nav, sidebar, table, card)
2.5. Validation: Target resolved to at least a component name

### 3. Accessibility Validation (scope includes `a11y` or `all`)
3.1. Check ARIA attributes:
   - Required roles present (e.g., `role="dialog"` for modal)
   - Required aria-* attributes (aria-label, aria-labelledby, aria-describedby)
   - Aria-hidden usage on decorative elements
3.2. Check keyboard navigation:
   - Tab order logical and non-trapping (except modals)
   - Focus management (focus-visible, focus trap where required)
   - Escape key handler (for overlays, modals, dropdowns)
   - Enter/Space activation for interactive elements
3.3. Check visual accessibility:
   - Color contrast >= 4.5:1 for text, >= 3:1 for large text/icons
   - Focus indicators visible (2px+ outline, not color-only)
   - Motion: respects `prefers-reduced-motion`
   - Text resizable to 200% without loss
3.4. Score: pass/warn/fail per check item

### 4. Responsive Validation (scope includes `responsive` or `all`)
4.1. Check breakpoint behavior:
   - Component adapts at standard breakpoints (640, 768, 1024, 1280px)
   - No horizontal overflow at any breakpoint
   - Touch targets >= 44x44px on mobile
4.2. Check layout patterns:
   - Multi-column → single-column stacking
   - Font sizes >= 16px on mobile
   - Images use responsive sizing (srcset or CSS)
4.3. Score: pass/warn/fail per check item

### 5. Token Usage Validation (scope includes `tokens` or `all`)
5.1. Check for hardcoded values:
   - No hardcoded colors (hex/rgb/hsl literals instead of tokens)
   - No hardcoded spacing (px values instead of spacing scale)
   - No hardcoded font sizes (px/em instead of type scale)
5.2. Check token naming:
   - Follows semantic naming (--color-primary, not --blue-500)
   - Uses design system tokens, not arbitrary values
5.3. Score: pass/warn/fail per check item

### 6. Naming Convention Validation (scope includes `naming` or `all`)
6.1. Component name: PascalCase
6.2. File name: kebab-case
6.3. Props interface: `{ComponentName}Props`
6.4. CSS classes: follow project convention (BEM, Tailwind utilities, CSS modules)
6.5. Event handlers: `on{Event}` prefix
6.6. Score: pass/warn/fail per check item

### 7. Calculate Compliance Score
7.1. Weight each category:
   - Accessibility: 40%
   - Responsive: 25%
   - Tokens: 20%
   - Naming: 15%
7.2. Calculate weighted score (0-100)
7.3. Assign grade: A (90+), B (80+), C (70+), D (60+), F (<60)
7.4. If `strict=true` → treat all warnings as failures (score penalized)
7.5. Validation: Score calculated

### 8. Format Output
8.1. Compliance score with grade
8.2. Issues table grouped by category
8.3. Recommendations ordered by severity
8.4. Quick-fix suggestions for common issues

---

## Output Format

```markdown
## ✅ Pattern Validation: {target}

### Compliance Score: {score}/100 (Grade {grade})

| Category | Score | Status |
|----------|-------|--------|
| Accessibility | {X}/40 | {✅/⚠️/❌} |
| Responsive | {X}/25 | {✅/⚠️/❌} |
| Token Usage | {X}/20 | {✅/⚠️/❌} |
| Naming | {X}/15 | {✅/⚠️/❌} |

### Issues Found ({count})
| # | Severity | Category | Issue | Fix |
|---|----------|----------|-------|-----|
| 1 | ERROR | a11y | Missing aria-label on close button | Add `aria-label="Close dialog"` |
| 2 | WARN | responsive | Touch target 32px < 44px minimum | Increase padding to 6px |
| 3 | INFO | tokens | Hardcoded `#333` found | Replace with `var(--color-text)` |

### Recommendations
1. **[HIGH]** {recommendation}
2. **[MEDIUM]** {recommendation}
3. **[LOW]** {recommendation}

### Quick Fixes
```diff
- <button class="close-btn">X</button>
+ <button class="close-btn" aria-label="Close dialog">X</button>
```
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Target not found | File path does not exist or component not in CSV | Ask user to verify path/name, list available components |
| CSV missing | patterns.csv or components.csv not in data directory | Use built-in knowledge, warn about limited validation |
| Unparseable file | Target file is not valid JSX/TSX | Skip file-based validation, validate by name only |
| No scope selected | Empty scope parameter | Default to `all` |

---

## Examples

### Example 1: Validate Modal

```
*validate-pattern modal
```

Returns: 85/100 (Grade B) — missing focus trap, aria-describedby absent, good token usage, correct naming.

### Example 2: Validate File

```
*validate-pattern src/components/ui/dropdown.tsx --scope=a11y
```

Returns: Accessibility-only validation — checks ARIA roles, keyboard navigation, focus management in the actual file.

### Example 3: Strict Mode

```
*validate-pattern form --strict
```

Returns: Strict scoring — all warnings become errors, lower threshold for passing.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/components.csv
  - .lmas-core/development/data/ux/patterns.csv
tags:
  - ux
  - validation
  - accessibility
  - quality-gate
  - data-driven
updated_at: 2026-03-17
```
