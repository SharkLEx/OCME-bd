# Brand Audit — Brand Consistency Audit Across Touchpoints

> **Task ID:** ux-brand-audit
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** ux-design-expert, qa, pm, analyst
> **Elicit:** true
> **Category:** design-quality

---

## Purpose

Audit brand consistency across touchpoints by scanning provided files, URLs, or screenshots. Checks logo usage, color consistency, typography adherence, and spacing patterns against design token data. Returns a brand consistency score, list of deviations, and prioritized fixes.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `scope` | string | yes | User Input | Audit scope: file paths (glob), URL, component directory, or "full" for entire project |
| `mode` | string | no | User Input | `yolo` \| `interactive`. Default: `interactive` |

### Elicited Inputs (gathered during interactive mode)

| Field | Type | Required | Prompt |
|-------|------|----------|--------|
| `brand_colors` | string[] | no | "What are the official brand colors? (hex values)" |
| `brand_fonts` | string[] | no | "What are the official brand fonts? (font family names)" |
| `logo_path` | string | no | "Path to the official logo file (SVG preferred)" |
| `design_tokens_path` | string | no | "Path to design tokens file (CSS, JSON, or Tailwind config)" |
| `strictness` | string | no | "Audit strictness: relaxed, standard, strict?" Default: standard |

---

## Execution Flow

### 1. Load Reference Data
1.1. Read `.lmas-core/development/data/ux/colors.csv` — official color definitions
1.2. Read `.lmas-core/development/data/ux/typography.csv` — official font definitions
1.3. Read `.lmas-core/development/data/ux/sub-skills/cip-elements.csv` (if exists) — CIP standards
1.4. If `design_tokens_path` provided → read and parse design tokens
1.5. If `brand_colors` or `brand_fonts` provided → use as authoritative overrides
1.6. Validation: At least colors.csv or brand_colors available

### 2. Resolve Audit Scope
2.1. If `scope` is a glob pattern (e.g., `src/components/**/*.tsx`):
   - Resolve all matching files
   - Parse CSS classes, inline styles, color literals, font declarations
2.2. If `scope` is a directory:
   - Scan all `.tsx`, `.jsx`, `.css`, `.scss`, `.html`, `.vue` files
2.3. If `scope` is a URL:
   - Note: requires browser tool for full audit
   - Provide manual checklist for URL-based audit
2.4. If `scope` is "full":
   - Scan project `src/` directory recursively
   - Include Tailwind config, CSS files, and component files
2.5. Build inventory of files to audit
2.6. Validation: At least 1 file resolved

### 3. Color Consistency Audit
3.1. Extract all color values from scoped files:
   - Hex literals (#XXXXXX, #XXX)
   - RGB/RGBA values
   - HSL/HSLA values
   - Tailwind color classes (bg-*, text-*, border-*)
   - CSS custom property references (var(--color-*))
3.2. Compare each found color against brand palette:
   - Exact match → PASS
   - Close match (deltaE < 5) → WARN (near-miss, likely unintentional)
   - No match → FAIL (unauthorized color)
3.3. Track unique unauthorized colors and their locations
3.4. Calculate color consistency percentage:
   - (matching color uses / total color uses) * 100
3.5. Validation: Color audit complete

### 4. Typography Consistency Audit
4.1. Extract all font declarations from scoped files:
   - `font-family` CSS properties
   - Tailwind font classes (font-sans, font-serif, font-mono, font-*)
   - Google Fonts `<link>` tags
   - `@font-face` declarations
4.2. Compare against brand fonts:
   - Exact match → PASS
   - System font fallback only → WARN
   - Non-brand font → FAIL
4.3. Check font size adherence:
   - Extract all font-size declarations
   - Compare against type scale (if defined in tokens)
   - Flag arbitrary sizes not in scale
4.4. Check font weight usage:
   - Flag weights not in brand specification
4.5. Calculate typography consistency percentage
4.6. Validation: Typography audit complete

### 5. Logo Usage Audit
5.1. If `logo_path` provided:
   - Search scoped files for logo references (img src, SVG imports, background-image)
   - Check logo file format (prefer SVG for web)
   - Check for multiple logo versions (color, mono, reversed)
5.2. Check logo usage patterns:
   - Clear space: is logo surrounded by sufficient whitespace?
   - Minimum size: logo not rendered below minimum dimensions
   - No distortion: width/height not independently scaled
   - No color modifications: logo colors match original
5.3. If no logo_path → skip this section, note in output
5.4. Validation: Logo audit complete (or skipped)

### 6. Spacing Pattern Audit
6.1. Extract spacing values from scoped files:
   - Margin and padding declarations
   - Gap values (flex gap, grid gap)
   - Tailwind spacing classes (p-*, m-*, gap-*, space-*)
6.2. Compare against spacing scale (from spacing.csv or design tokens):
   - Values on scale → PASS
   - Arbitrary values → WARN
   - Inconsistent patterns (e.g., 13px, 17px) → FAIL
6.3. Calculate spacing consistency percentage
6.4. Validation: Spacing audit complete

### 7. Cross-Reference Design Tokens
7.1. If design tokens file available:
   - Check all components use tokens instead of raw values
   - Percentage of token usage vs. raw values
   - List of raw values that should be tokens
7.2. If Tailwind config available:
   - Check theme consistency
   - Verify custom colors/fonts/spacing match brand
7.3. Validation: Token cross-reference complete

### 8. Calculate Brand Consistency Score
8.1. Weight categories:
   - Color Consistency: 35%
   - Typography Consistency: 25%
   - Logo Usage: 15% (or redistributed if skipped)
   - Spacing Patterns: 15%
   - Token Adherence: 10%
8.2. Apply strictness modifier:
   - Relaxed: warnings don't reduce score
   - Standard: warnings reduce score by 50% of fail penalty
   - Strict: warnings treated as fails
8.3. Calculate weighted score (0-100)
8.4. Assign grade: A (90+), B (80+), C (70+), D (60+), F (<60)
8.5. Validation: Final score calculated

### 9. Generate Priority Fixes
9.1. Rank all deviations by:
   - Severity (FAIL > WARN)
   - Frequency (how many occurrences)
   - Visibility (user-facing > internal)
9.2. Group fixes by effort:
   - Quick wins (find-replace color/font, < 5 min)
   - Medium effort (component refactoring, 1-2 hours)
   - Major effort (system-wide token migration, days)
9.3. Generate top 10 priority fixes with file paths and line numbers
9.4. Validation: Fixes are actionable

---

## Output Format

```markdown
## 🔍 Brand Audit: {scope}

### Consistency Score: {score}/100 (Grade {grade})

| Category | Score | Deviations |
|----------|-------|------------|
| Color Consistency | {X}/35 | {count} |
| Typography | {X}/25 | {count} |
| Logo Usage | {X}/15 | {count} |
| Spacing Patterns | {X}/15 | {count} |
| Token Adherence | {X}/10 | {count} |

### Color Deviations ({count})
| # | File | Line | Found | Expected | Severity |
|---|------|------|-------|----------|----------|
| 1 | src/Header.tsx | 42 | #334155 | --color-text (#1E293B) | WARN |
| 2 | src/Card.tsx | 18 | #FF0000 | Not in brand palette | FAIL |

### Typography Deviations ({count})
| # | File | Line | Found | Expected | Severity |
|---|------|------|-------|----------|----------|
| 1 | src/Footer.tsx | 12 | Arial | Inter (--font-body) | FAIL |

### Spacing Deviations ({count})
| # | File | Pattern | Found | Nearest Token | Severity |
|---|------|---------|-------|--------------|----------|
| 1 | src/Card.tsx | padding | 13px | --space-3 (12px) | WARN |

### Priority Fixes (Top 10)
| # | Fix | Files | Effort | Impact |
|---|-----|-------|--------|--------|
| 1 | Replace #334155 with var(--color-text) | 8 files | Quick | High |
| 2 | Replace Arial with Inter | 3 files | Quick | High |
| 3 | Migrate padding to spacing tokens | 12 files | Medium | Medium |

### Quick Fix Script
```bash
# Color fix (global find-replace)
grep -rl '#334155' src/ | xargs sed -i 's/#334155/var(--color-text)/g'
```
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| No files in scope | Glob resolves to 0 files | Ask user to verify scope path, list available directories |
| No brand reference | Neither CSV nor manual brand colors provided | Cannot audit without reference — ask user for brand colors at minimum |
| Binary files | Scope includes images/fonts | Skip binary files, audit only code files |
| Large scope | > 500 files | Warn about duration, suggest narrowing scope or using `yolo` mode |

---

## Examples

### Example 1: Component Directory

```
*brand-audit src/components/
```

Returns: 82/100 (Grade B) — 5 unauthorized colors, 2 non-brand fonts, good spacing consistency.

### Example 2: Full Project with Tokens

```
*brand-audit full
> Brand colors: #3B82F6, #1E293B, #F8FAFC
> Brand fonts: Inter, JetBrains Mono
> Design tokens: src/styles/tokens.css
```

Returns: Comprehensive audit with token cross-reference, 94/100 (Grade A), 3 minor warnings.

### Example 3: Strict Mode

```
*brand-audit src/pages/ --strictness=strict
> Brand colors: #2563EB, #0F172A
```

Returns: Strict scoring — all near-miss colors flagged as failures, lower score, more actionable fixes.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/colors.csv
  - .lmas-core/development/data/ux/typography.csv
  - .lmas-core/development/data/ux/sub-skills/cip-elements.csv
tags:
  - ux
  - branding
  - audit
  - quality-gate
  - consistency
  - data-driven
updated_at: 2026-03-17
```
