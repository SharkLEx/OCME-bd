# Pattern Consolidation Algorithms — On-Demand Knowledge Base

> **Usage:** Loaded on-demand by @ux-design-expert (Switch) during design system audits and pattern consolidation.
> Do NOT pre-load during agent activation. Load when analyzing redundancy and merging patterns.
> **Last Updated:** 2026-03 (review quarterly)

---

## 1. Visual Similarity Clustering

### Purpose
Group components or values that are visually similar enough to consolidate into a single pattern.

### Algorithm: Color Clustering

1. **Extract** all unique color values from the codebase (hex, rgb, hsl)
2. **Normalize** to a common format (hex lowercase)
3. **Calculate distance** between each pair using CIEDE2000 (perceptual color difference)
4. **Cluster** colors with delta E < 3.0 (imperceptible difference to human eye)
5. **Select representative** from each cluster (most frequently used value)

| Delta E | Perception | Action |
|---------|------------|--------|
| 0-1 | Identical | Merge unconditionally |
| 1-3 | Barely noticeable | Merge (safe) |
| 3-5 | Noticeable on close inspection | Review before merging |
| 5-10 | Clearly different | Separate tokens |
| > 10 | Very different | Definitely separate |

### Algorithm: Component Similarity

1. **Extract props interface** for each component
2. **Compare props overlap** — percentage of shared prop names and types
3. **Compare rendered output** — visual diff of default states
4. **Score similarity:**
   - Props overlap > 80% AND visual diff < 5% = **High similarity** (merge)
   - Props overlap 60-80% OR visual diff 5-15% = **Medium similarity** (review)
   - Props overlap < 60% OR visual diff > 15% = **Low similarity** (keep separate)

---

## 2. Usage Frequency Analysis

### Purpose
Prioritize consolidation based on how often patterns are used. High-frequency patterns yield the most value.

### Method

1. **Count occurrences** of each component/value across the codebase
2. **Rank by frequency** (descending)
3. **Apply 80/20 rule** — the top 20% of patterns typically cover 80% of usage
4. **Prioritize** consolidation of the top 20% first

### Decision Matrix

| Frequency | Duplicates? | Action |
|-----------|-------------|--------|
| High (50+ uses) | Yes | **Consolidate immediately** — highest ROI |
| High (50+ uses) | No | **Tokenize** — ensure consistency |
| Medium (10-50 uses) | Yes | **Consolidate** — good ROI |
| Medium (10-50 uses) | No | **Document** — ensure reuse |
| Low (< 10 uses) | Yes | **Consolidate or remove** — may be dead code |
| Low (< 10 uses) | No | **Review necessity** — might be one-off |

---

## 3. Variance Scoring

### Purpose
Quantify how much a pattern varies across its instances to determine if it is stable enough to consolidate.

### Formula

```
variance_score = (unique_values / total_instances) * 100
```

| Variance Score | Interpretation | Action |
|---------------|----------------|--------|
| 0-10% | Very stable | Safe to consolidate into single token |
| 10-25% | Mostly stable | Consolidate with 2-3 variants |
| 25-50% | Moderate variance | May need a scale (sm/md/lg) instead of one value |
| 50%+ | High variance | Not a pattern — investigate if it should be |

### Example

Button padding across the codebase:
- `8px 16px` (45 instances)
- `12px 24px` (32 instances)
- `4px 8px` (18 instances)
- `16px 32px` (5 instances)

Unique values: 4, Total instances: 100
Variance: 4% — very stable. Consolidate to 3 size variants (sm, md, lg) and remove the 4th.

---

## 4. Merge Strategies

### Strategy A: Direct Replace

**When:** Components are > 90% identical (same props, same behavior).
**How:** Pick the better-implemented version, deprecate the others, run codemod.

```
ButtonPrimary + ActionButton + SubmitButton → Button (variant="primary")
```

### Strategy B: Variant Extraction

**When:** Components share 60-90% of logic but have visual variants.
**How:** Create a single component with a `variant` prop.

```
InfoCard + ProductCard + UserCard → Card (variant="info" | "product" | "user")
```

### Strategy C: Composition

**When:** Components share a base but have significantly different content.
**How:** Create a base component with slots/children for customization.

```
SimpleModal + ConfirmModal + FormModal → Modal (children={...})
```

### Strategy D: Token Normalization

**When:** The same intent is expressed with different values (e.g., 5 shades of "blue").
**How:** Cluster values, pick one, create a semantic token, replace all instances.

```
#2563EB, #2555DD, #2460E0 → var(--color-primary) = #2563EB
```

---

## 5. Naming Conventions for Consolidated Patterns

### Component Naming

| Before | After | Rule |
|--------|-------|------|
| PrimaryButton, ActionButton | Button | Use the generic name |
| InfoCard, ProductCard | Card | Generic + variant prop |
| SmallInput, LargeInput | Input | Generic + size prop |

### Token Naming

| Before | After | Rule |
|--------|-------|------|
| blue, brandBlue, mainBlue | color-primary | Semantic over visual |
| text-dark, text-black | color-text-primary | Purpose over appearance |
| gap-small, gap-s, smallGap | spacing-2 | Scale-based |

---

## 6. Automated vs Manual Decisions

### Automate (codemod-safe)

- Import path changes (`from 'old/Button'` to `from 'ds/Button'`)
- Prop renames when mapping is 1:1 (`color="blue"` to `variant="primary"`)
- Value replacements (`#2563EB` to `var(--color-primary)`)
- Removing unused imports after consolidation

### Manual Review Required

- Components with different behavior (same name, different logic)
- Props that map to multiple possible values
- Components with different accessibility implementations
- Edge cases where the visual diff exceeds 5%
- Components consumed by external packages or published APIs

---

## 7. Consolidation Workflow

```
1. AUDIT    → Run pattern audit checklist, collect data
2. CLUSTER  → Group similar patterns (colors, components, spacing)
3. SCORE    → Calculate usage frequency + variance for each cluster
4. PLAN     → Choose merge strategy per cluster (A/B/C/D)
5. EXECUTE  → Implement consolidation (highest ROI first)
6. VALIDATE → Visual regression + a11y tests
7. CLEANUP  → Remove deprecated patterns, update docs
```
