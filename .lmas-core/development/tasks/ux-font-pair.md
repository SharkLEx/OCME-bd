# Font Pair — Typography Pairing Recommendations

> **Task ID:** ux-font-pair
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** dev, architect, ux-design-expert
> **Elicit:** false
> **Category:** design-data

---

## Purpose

Recommend a typography pairing based on style or mood. Returns heading font, body font, weights, type scale ratio, line heights, Google Fonts CDN link, and fallback system fonts. All data sourced from `typography.csv`.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `query` | string | yes | User Input | Style or mood keyword: "elegant", "modern", "playful", "corporate", "minimal", "editorial", "technical" |
| `mode` | string | no | User Input | `yolo` \| `interactive`. Default: `yolo` |
| `context` | string | no | User Input | Usage context: "web", "mobile", "print", "dashboard". Default: `web` |

---

## Execution Flow

### 1. Load Typography Data
1.1. Read `.lmas-core/development/data/ux/typography.csv`
1.2. Parse rows with columns: style, mood, heading_font, body_font, heading_weights, body_weights, scale_ratio, line_height_heading, line_height_body, letter_spacing, tags, domain
1.3. Validation: CSV loaded successfully

### 2. Match Query
2.1. Search `style` column for exact match (case-insensitive)
2.2. If no match → search `mood` column
2.3. If no match → search `tags` column for partial keyword match
2.4. If no match → BM25 fuzzy across style, mood, tags, domain columns
   - Score threshold: >= 0.25
   - Return top 3 matches ranked by score
2.5. If zero results → return "modern" as default pairing
2.6. Validation: At least 1 pairing found

### 3. Build Typography System
3.1. Extract heading font family and body font family
3.2. Extract weights for each (e.g., heading: 600, 700; body: 400, 500, 700)
3.3. Build type scale using the matched `scale_ratio`:
   - Common ratios: 1.125 (Major Second), 1.200 (Minor Third), 1.250 (Major Third), 1.333 (Perfect Fourth), 1.414 (Augmented Fourth), 1.618 (Golden Ratio)
   - Generate sizes from `xs` (0.75rem) to `5xl` (3rem+) using the ratio
3.4. Set line heights: heading (1.1–1.3), body (1.5–1.7)
3.5. Set letter spacing: heading (-0.02em to 0em), body (0em to 0.01em)
3.6. Validation: Both fonts are distinct families (avoid same-family pairing unless intentional)

### 4. Generate Font Resources
4.1. Build Google Fonts CDN `<link>` tag with all required weights:
   ```html
   <link href="https://fonts.googleapis.com/css2?family={heading}:wght@{weights}&family={body}:wght@{weights}&display=swap" rel="stylesheet">
   ```
4.2. Generate `@font-face` alternative for self-hosting reference
4.3. Build fallback system font stacks:
   - Sans-serif: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
   - Serif: `Georgia, 'Times New Roman', Times, serif`
   - Monospace: `'JetBrains Mono', 'Fira Code', 'Courier New', monospace`
4.4. Validation: Google Fonts URL is well-formed

### 5. Context-Specific Adjustments
5.1. If `context=mobile`:
   - Increase body font size minimum to 16px (prevent iOS zoom)
   - Reduce heading scale by one step
   - Increase line height by 0.1
5.2. If `context=dashboard`:
   - Recommend monospace font for data/numbers
   - Use condensed heading weights
   - Reduce base size to 14px for density
5.3. If `context=print`:
   - Switch to serif body font if not already
   - Use larger line height (1.8)
   - Recommend pt sizes instead of rem
5.4. Validation: Adjustments applied to output

### 6. Format Output
6.1. Compile typography system into structured tables
6.2. Include visual hierarchy preview (text-based mockup)
6.3. Include CSS custom properties declaration
6.4. Include Tailwind fontFamily config snippet

---

## Output Format

```markdown
## 🔤 Typography: {query}

### Font Pairing
| Role | Font Family | Weights | Fallback Stack |
|------|------------|---------|----------------|
| Heading | {font} | 600, 700 | {fallback} |
| Body | {font} | 400, 500, 700 | {fallback} |
| Mono | {font} | 400 | {fallback} |

### Type Scale (ratio: {ratio})
| Token | Size (rem) | Size (px) | Usage |
|-------|-----------|-----------|-------|
| text-xs | 0.75 | 12 | Captions, labels |
| text-sm | 0.875 | 14 | Helper text |
| text-base | 1.0 | 16 | Body text |
| text-lg | 1.125 | 18 | Lead text |
| text-xl | 1.25 | 20 | H4 |
| text-2xl | 1.5 | 24 | H3 |
| text-3xl | 1.875 | 30 | H2 |
| text-4xl | 2.25 | 36 | H1 |
| text-5xl | 3.0 | 48 | Display |

### Line Heights & Spacing
| Element | Line Height | Letter Spacing |
|---------|-------------|----------------|
| Heading | {value} | {value} |
| Body | {value} | {value} |

### Google Fonts
```html
<link href="https://fonts.googleapis.com/css2?family=..." rel="stylesheet">
```

### CSS Custom Properties
```css
:root {
  --font-heading: '{heading}', {fallback};
  --font-body: '{body}', {fallback};
  ...
}
```
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| CSV not found | `typography.csv` missing | Error with path, suggest checking data directory |
| No match | Query does not match any style/mood/tag | Return "modern" default pairing, list available styles |
| Same family | Heading and body resolve to same font | Warn user, suggest weight differentiation or alternative pairing |
| Missing weights | Font lacks requested weight | Suggest closest available weight, warn about faux bold/italic |

---

## Examples

### Example 1: Elegant Style

```
*font-pair elegant
```

Returns: Playfair Display (heading) + Source Sans 3 (body), Golden Ratio scale (1.618), tight heading spacing.

### Example 2: Corporate with Context

```
*font-pair corporate --context=dashboard
```

Returns: Inter (heading) + Inter (body, different weights) + JetBrains Mono (data), compact scale (1.200), 14px base.

### Example 3: Playful Mood

```
*font-pair playful
```

Returns: Fredoka One (heading) + Nunito (body), Major Third scale (1.250), generous line heights, rounded aesthetic.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/typography.csv
tags:
  - ux
  - typography
  - fonts
  - data-driven
updated_at: 2026-03-17
```
