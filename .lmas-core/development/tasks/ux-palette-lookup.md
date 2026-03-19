# Palette Lookup — WCAG-Compliant Color Palette

> **Task ID:** ux-palette-lookup
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** dev, architect, ux-design-expert
> **Elicit:** false
> **Category:** design-data

---

## Purpose

Retrieve a complete, WCAG-compliant color palette for a specific domain or mood. Returns primary, secondary, accent, and neutral colors with hex values, contrast ratios, accessibility notes, and light/dark mode variations. All data is sourced from `colors.csv`.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `query` | string | yes | User Input | Domain name (e.g., "fintech") OR mood (e.g., "energetic", "calm", "professional") |
| `mode` | string | no | User Input | `yolo` \| `interactive`. Default: `yolo` |
| `variants` | string | no | User Input | `light` \| `dark` \| `both`. Default: `both` |
| `format` | string | no | User Input | `table` \| `css` \| `tailwind`. Default: `table` |

---

## Execution Flow

### 1. Load Color Data
1.1. Read `.lmas-core/development/data/ux/colors.csv`
1.2. Parse all rows into structured records with columns: domain, mood, role, hex, hsl, usage, tags
1.3. Validation: CSV loaded, minimum 1 row parsed

### 2. Match Query
2.1. Check if `query` matches a `domain` column value (case-insensitive exact match)
2.2. If no domain match → check `mood` column for exact match
2.3. If no mood match → check `tags` column for partial match
2.4. If still no match → apply BM25 fuzzy scoring across domain, mood, and tags
   - Tokenize query into keywords
   - Score each row by term frequency
   - Collect rows with score >= 0.25
2.5. If zero results → return "generic" palette with suggestion of available domains/moods
2.6. Validation: At least 4 colors found (primary, secondary, accent, neutral)

### 3. Build Palette
3.1. Group matched colors by role: primary, secondary, accent, neutral, success, warning, error, info
3.2. For each color, include:
   - Hex value (#XXXXXX)
   - HSL value (hsl(H, S%, L%))
   - RGB value (rgb(R, G, B))
   - Recommended usage description
3.3. If fewer than 4 roles filled → derive missing colors:
   - Secondary: shift primary hue by ±30°
   - Accent: complementary of primary (hue + 180°)
   - Neutral: desaturate primary to 5-10% saturation
3.4. Validation: All 4 core roles (primary, secondary, accent, neutral) present

### 4. Calculate Accessibility
4.1. For each foreground/background combination:
   - Calculate relative luminance per WCAG 2.1
   - Compute contrast ratio
   - Flag AA compliance (>= 4.5:1 normal text, >= 3:1 large text)
   - Flag AAA compliance (>= 7:1 normal text, >= 4.5:1 large text)
4.2. Generate accessible text color recommendations for each background
4.3. Flag any combinations that fail AA with suggested adjustments
4.4. Validation: Primary + white/black text meets AA minimum

### 5. Generate Variants
5.1. **Light mode:** Use palette as-is, ensure white/light backgrounds
5.2. **Dark mode:** Invert luminance relationships:
   - Backgrounds: shift to 10-15% luminance
   - Foregrounds: shift to 85-95% luminance
   - Accent colors: increase saturation by 10-15% for vibrancy on dark
5.3. Generate both if `variants=both`
5.4. Validation: Dark mode colors also meet WCAG AA

### 6. Format Output
6.1. If `format=table` → markdown table with all values
6.2. If `format=css` → CSS custom properties block
6.3. If `format=tailwind` → Tailwind `theme.extend.colors` config
6.4. Always include accessibility summary at the end

---

## Output Format

```markdown
## 🎨 Palette: {query}

### Core Palette
| Role | Hex | HSL | Usage | AA Text | Contrast |
|------|-----|-----|-------|---------|----------|
| Primary | #3B82F6 | hsl(217, 91%, 60%) | CTA, links, focus | White ✓ | 4.7:1 |
| Secondary | #6366F1 | hsl(239, 84%, 67%) | Secondary actions | White ✓ | 4.5:1 |
| Accent | #F59E0B | hsl(38, 92%, 50%) | Highlights, badges | Black ✓ | 5.2:1 |
| Neutral-50 | #F8FAFC | hsl(210, 40%, 98%) | Background | Black ✓ | 18.1:1 |
| Neutral-900 | #0F172A | hsl(222, 47%, 11%) | Text | White ✓ | 15.4:1 |

### Dark Mode Variant
| Role | Hex (dark) | Usage |
|------|-----------|-------|
| ... | ... | ... |

### Accessibility Summary
- ✅ All primary text combinations meet WCAG AA (4.5:1)
- ✅ Large text combinations meet WCAG AA (3:1)
- ⚠️ Accent on neutral-200 is 3.8:1 — use only for large text

### Available Domains
`SaaS` `fintech` `health` `e-commerce` `education` `portfolio` `startup`
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| CSV not found | `colors.csv` missing | Error message with path, suggest checking data directory |
| No matches | Query does not match any domain, mood, or tag | Return generic palette, list available domains/moods |
| Insufficient colors | Matched domain has fewer than 4 color roles | Auto-derive missing roles from primary color, flag as generated |
| Contrast failure | Combination fails WCAG AA | Suggest adjusted hex with minimum modification to pass AA |

---

## Examples

### Example 1: Domain Lookup

```
*palette fintech
```

Returns: Conservative palette — navy primary (#1E3A5F), forest green secondary (#2D6A4F), gold accent (#D4A843), cool neutrals. All AA-compliant.

### Example 2: Mood Lookup

```
*palette energetic
```

Returns: Vibrant palette — electric blue (#2563EB), hot coral (#FF6B6B), sunny yellow (#FBBF24), crisp neutrals.

### Example 3: With Format

```
*palette SaaS --format=tailwind
```

Returns: Tailwind `theme.extend.colors` config object ready to paste into `tailwind.config.js`.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/colors.csv
tags:
  - ux
  - colors
  - accessibility
  - data-driven
updated_at: 2026-03-17
```
