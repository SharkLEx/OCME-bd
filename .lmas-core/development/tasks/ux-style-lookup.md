# Style Lookup — Complete Design Token Recommendations

> **Task ID:** ux-style-lookup
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** dev, architect, ux-design-expert
> **Elicit:** false
> **Category:** design-data

---

## Purpose

Look up a complete set of style recommendations for a specific domain or industry. Reads multiple CSV data sources and assembles a unified style guide with color palette, typography pairing, spacing system, shadow levels, and border radii — all tailored to the target domain.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `domain` | string | yes | User Input | Non-empty. Examples: "SaaS", "fintech", "health", "e-commerce", "education" |
| `mode` | string | no | User Input | `yolo` \| `interactive` \| `pre-flight`. Default: `yolo` |
| `theme` | string | no | User Input | `light` \| `dark` \| `both`. Default: `both` |

---

## Execution Flow

### 1. Load Data Sources
1.1. Read `.lmas-core/development/data/ux/colors.csv`
1.2. Read `.lmas-core/development/data/ux/typography.csv`
1.3. Read `.lmas-core/development/data/ux/spacing.csv`
1.4. Read `.lmas-core/development/data/ux/shadows.csv` (if exists, else use defaults)
1.5. Read `.lmas-core/development/data/ux/borders.csv` (if exists, else use defaults)
1.6. Validation: All core CSVs loaded successfully

### 2. Match Domain
2.1. Search each CSV for rows where `domain` column matches the input parameter (case-insensitive)
2.2. If exact match found → collect all matching rows
2.3. If NO exact match → apply BM25 fuzzy matching:
   - Tokenize domain input into keywords
   - Score each CSV row by term frequency across `domain`, `tags`, `mood` columns
   - Select top-scoring rows (threshold: score >= 0.3)
2.4. If still no matches → fall back to "generic" / "universal" domain entries
2.5. Validation: At least one match found per CSV category

### 3. Assemble Color Palette
3.1. Extract primary, secondary, accent, neutral colors from colors.csv matches
3.2. Include hex values, HSL values, and CSS custom property names
3.3. Calculate WCAG 2.1 AA contrast ratios for text/background combinations
3.4. Generate light mode and dark mode variants (if `theme=both`)
3.5. Validation: All color pairs meet minimum 4.5:1 contrast for normal text

### 4. Assemble Typography
4.1. Extract heading font, body font, and monospace font from typography.csv matches
4.2. Include font weights, line heights, letter spacing, and type scale ratio
4.3. Generate Google Fonts CDN `<link>` tag for recommended fonts
4.4. List fallback system font stacks
4.5. Validation: Font pairs are distinct enough for visual hierarchy

### 5. Assemble Spacing System
5.1. Extract base unit, scale multipliers, and named spacing tokens from spacing.csv
5.2. Map to CSS custom properties (e.g., `--space-1` through `--space-12`)
5.3. Include component-level spacing recommendations (padding, margin, gap)
5.4. Validation: Spacing scale follows consistent mathematical ratio

### 6. Assemble Shadows & Borders
6.1. Extract shadow levels (sm, md, lg, xl) with CSS `box-shadow` values
6.2. Extract border radii (none, sm, md, lg, full) with pixel/rem values
6.3. Include border widths and border colors
6.4. Validation: Shadow and border tokens are complete

### 7. Format Output
7.1. Compile all tokens into a structured table format
7.2. Group by category: Colors → Typography → Spacing → Shadows → Borders
7.3. Include CSS custom property declarations block
7.4. Include Tailwind theme extension snippet (if applicable)
7.5. Validation: Output is scannable and copy-paste ready

---

## Output Format

```markdown
## 🎨 Style Guide: {domain}

### Colors
| Token | Hex | HSL | Usage | Contrast |
|-------|-----|-----|-------|----------|
| --color-primary | #XXXXXX | hsl(X, X%, X%) | Primary actions, CTA | 7.2:1 ✓ |
| ... | ... | ... | ... | ... |

### Typography
| Role | Font | Weight | Size | Line Height |
|------|------|--------|------|-------------|
| Heading | {font} | 700 | 2rem | 1.2 |
| Body | {font} | 400 | 1rem | 1.6 |

**Google Fonts:** `<link href="https://fonts.googleapis.com/css2?family=..." />`

### Spacing Scale
| Token | Value | Usage |
|-------|-------|-------|
| --space-1 | 0.25rem | Tight spacing |
| ... | ... | ... |

### Shadows
| Level | CSS Value |
|-------|-----------|
| sm | 0 1px 2px rgba(...) |
| ... | ... |

### Border Radii
| Token | Value |
|-------|-------|
| --radius-sm | 0.25rem |
| ... | ... |

### CSS Custom Properties
```css
:root { ... }
```

### Tailwind Config Extension
```js
theme: { extend: { ... } }
```
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| CSV file not found | Data file missing from `.lmas-core/development/data/ux/` | Warn user, use defaults for missing category, suggest running `*validate-data` |
| No domain match | Domain not present in any CSV and fuzzy match fails | Fall back to "generic" entries, inform user of closest available domains |
| Incomplete data | Some CSV categories lack entries for matched domain | Fill gaps with generic/universal defaults, flag which categories are defaults |
| Contrast failure | Color combination fails WCAG AA | Auto-adjust lightness/saturation, flag adjusted colors in output |

---

## Examples

### Example 1: SaaS Style Lookup

```
*style SaaS
```

Output: Full style guide with SaaS-optimized blue/purple palette, Inter/system-ui typography, 4px base spacing, subtle shadows, medium border radii.

### Example 2: Fintech Style Lookup

```
*style fintech
```

Output: Conservative palette (navy, green, neutrals), serif/sans-serif pairing, generous spacing, minimal shadows, sharp border radii.

### Example 3: Fuzzy Match

```
*style "kids education app"
```

No exact match → BM25 matches "education" + "kids" → Returns playful palette, rounded typography, generous spacing, soft shadows, large border radii.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/colors.csv
  - .lmas-core/development/data/ux/typography.csv
  - .lmas-core/development/data/ux/spacing.csv
tags:
  - ux
  - design-tokens
  - data-driven
updated_at: 2026-03-17
```
