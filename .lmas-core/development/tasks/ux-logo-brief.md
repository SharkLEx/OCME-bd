# Logo Brief — Logo Design Brief Generator

> **Task ID:** ux-logo-brief
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** ux-design-expert, pm, analyst
> **Elicit:** true
> **Category:** branding

---

## Purpose

Generate a comprehensive logo design brief based on brand information. Matches brand characteristics to recommended logo styles, provides color direction, typography suggestions, and DO/DON'T guidelines. Data sourced from `logo-styles.csv` and `logo-principles.csv`.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `brand` | string | yes | User Input | Brand or company name |
| `mode` | string | no | User Input | `yolo` \| `interactive` \| `pre-flight`. Default: `interactive` |

### Elicited Inputs (gathered during interactive mode)

| Field | Type | Required | Prompt |
|-------|------|----------|--------|
| `industry` | string | yes | "What industry/sector is {brand} in?" |
| `values` | string[] | yes | "What are the top 3 brand values?" (e.g., trust, innovation, simplicity) |
| `personality` | string | yes | "Describe the brand personality in 3 words" (e.g., bold, friendly, premium) |
| `competitors` | string[] | no | "Name 2-3 competitors (for differentiation)" |
| `existing_logo` | boolean | no | "Does the brand already have a logo? (redesign vs. new)" |
| `constraints` | string | no | "Any constraints? (must include icon, text-only, monochrome needed, etc.)" |

---

## Execution Flow

### 1. Load Logo Data
1.1. Read `.lmas-core/development/data/ux/sub-skills/logo-styles.csv`
1.2. Read `.lmas-core/development/data/ux/sub-skills/logo-principles.csv`
1.3. Parse logo-styles columns: style_name, description, best_for_industry, best_for_personality, examples, complexity, versatility_score
1.4. Parse logo-principles columns: principle, description, applies_to, priority, do_example, dont_example
1.5. Validation: Both CSVs loaded

### 2. Elicit Brand Information (interactive mode)
2.1. If `mode=interactive` → prompt user for each elicited input sequentially
2.2. If `mode=yolo` → use brand name only, infer industry from context if possible
2.3. If `mode=pre-flight` → gather ALL inputs upfront before proceeding
2.4. Validate inputs: industry non-empty, at least 2 values, personality non-empty
2.5. Validation: Core brand info collected

### 3. Match Logo Style
3.1. Score each logo style from CSV against brand inputs:
   - **Industry match:** +3 if `best_for_industry` contains brand's industry
   - **Personality match:** +3 if `best_for_personality` overlaps with brand personality
   - **Versatility:** +1 per versatility_score point (scale 1-5)
   - **Complexity alignment:** +2 if complexity matches brand positioning (premium=higher, startup=lower)
3.2. If competitors provided → penalize styles too similar to competitors (-2)
3.3. Rank by total score, select top recommendation + 2 alternatives
3.4. Validation: At least 1 style matched

### 4. Generate Color Direction
4.1. Cross-reference with `.lmas-core/development/data/ux/colors.csv`:
   - Match industry to recommended color families
   - Match brand personality to mood-based colors
4.2. Recommend primary color family (not exact hex — direction only)
4.3. Suggest secondary/accent color approach
4.4. Include color psychology notes (why this direction fits the brand)
4.5. Warn about industry color cliches to avoid
4.6. Validation: Color direction aligns with brand values

### 5. Generate Typography Suggestion
5.1. Cross-reference with `.lmas-core/development/data/ux/typography.csv`:
   - Match personality to typography styles
5.2. Recommend font category for logotype:
   - Serif (traditional, premium, editorial)
   - Sans-serif (modern, clean, tech)
   - Display/script (creative, artisan, playful)
   - Custom lettering (unique, premium positioning)
5.3. Suggest 2-3 specific fonts as starting points
5.4. Validation: Typography aligns with logo style

### 6. Build DO/DON'T Guidelines
6.1. From `logo-principles.csv`, select principles relevant to:
   - The recommended logo style
   - The brand's industry
   - Common logo mistakes
6.2. Format as clear DO/DON'T pairs with visual descriptions
6.3. Include at least 5 DOs and 5 DON'Ts
6.4. Validation: Guidelines are actionable and specific

### 7. Compile Design Brief
7.1. Assemble all sections into a structured document
7.2. Include usage specifications:
   - Minimum size (favicon at 16px, social at 400px, print at 1")
   - Clear space requirements
   - Color variations needed (full color, mono, reversed)
   - File format deliverables (SVG, PNG, ICO)
7.3. Include timeline estimate based on complexity
7.4. Validation: Brief is complete and actionable

---

## Output Format

```markdown
## 🎨 Logo Design Brief: {brand}

### Brand Summary
| Attribute | Value |
|-----------|-------|
| Brand | {name} |
| Industry | {industry} |
| Values | {values} |
| Personality | {personality} |
| Competitors | {competitors} |

### Recommended Logo Style
**Primary:** {style_name}
> {description}
> Examples in this style: {examples}

**Alternatives:**
1. {style_2} — {reason}
2. {style_3} — {reason}

### Color Direction
- **Primary:** {color family} — {psychology rationale}
- **Secondary:** {approach}
- **Avoid:** {industry cliches}

### Typography Direction
- **Category:** {serif/sans-serif/display}
- **Suggested fonts:** {font 1}, {font 2}, {font 3}
- **Rationale:** {why this matches the personality}

### DO / DON'T Guidelines
| ✅ DO | ❌ DON'T |
|-------|----------|
| {do_1} | {dont_1} |
| {do_2} | {dont_2} |
| {do_3} | {dont_3} |
| {do_4} | {dont_4} |
| {do_5} | {dont_5} |

### Usage Specifications
- **Minimum size:** 16px (favicon), 48px (mobile), 120px (web)
- **Clear space:** 1x logo height on all sides
- **Color variants:** Full color, monochrome, reversed (white on dark)
- **Deliverables:** SVG (primary), PNG (2x, 3x), ICO (favicon)

### Estimated Timeline
| Phase | Duration |
|-------|----------|
| Concepts (3 directions) | {X} days |
| Refinement | {X} days |
| Finalization | {X} days |
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| CSV not found | Logo data CSVs missing from `sub-skills/` | Use built-in logo style knowledge (wordmark, icon, combination, emblem, abstract, mascot, letterform) |
| Insufficient brand info | User skips too many elicited fields in interactive mode | Proceed with available info, note limitations in brief |
| No style match | Brand attributes don't match any CSV entries well | Return top 3 by versatility score, explain general fit |
| Colors CSV missing | Cannot cross-reference color data | Provide general color psychology guidance without specific CSV data |

---

## Examples

### Example 1: Tech Startup

```
*logo-brief TechFlow
> Industry: SaaS / AI
> Values: innovation, simplicity, speed
> Personality: modern, bold, trustworthy
```

Returns: Abstract mark style, blue-purple direction, geometric sans-serif, tech-industry DOs/DON'Ts.

### Example 2: Artisan Brand

```
*logo-brief "Casa da Vovo"
> Industry: bakery / food
> Values: tradition, quality, warmth
> Personality: warm, handcrafted, nostalgic
```

Returns: Emblem/badge style, warm earth tones, script + serif pairing, artisan DOs/DON'Ts.

### Example 3: YOLO Mode

```
*logo-brief AcmeCorp
```

Returns: Brief with inferred industry, top 3 versatile styles, general guidelines.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/sub-skills/logo-styles.csv
  - .lmas-core/development/data/ux/sub-skills/logo-principles.csv
  - .lmas-core/development/data/ux/colors.csv
  - .lmas-core/development/data/ux/typography.csv
tags:
  - ux
  - branding
  - logo
  - design-brief
  - data-driven
updated_at: 2026-03-17
```
