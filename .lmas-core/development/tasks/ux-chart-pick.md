# Chart Pick — Data Visualization Recommendations

> **Task ID:** ux-chart-pick
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** dev, data-engineer, analyst, ux-design-expert
> **Elicit:** false
> **Category:** design-data

---

## Purpose

Recommend the best chart type for a given data type or visualization need. Returns chart type recommendation, accessible color palette for the chart, library suggestions, mobile adaptation notes, and common mistakes to avoid. Data sourced from `chart-types.csv` and `chart-colors.csv`.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `data_type` | string | yes | User Input | Data visualization category: "comparison", "trend", "distribution", "composition", "relationship", "geo", "flow", "hierarchy" |
| `mode` | string | no | User Input | `yolo` \| `interactive`. Default: `yolo` |
| `data_points` | number | no | User Input | Approximate number of data points. Affects chart selection. |
| `library` | string | no | User Input | Preferred library: "recharts", "chart.js", "d3", "visx", "nivo", "any". Default: `any` |

---

## Execution Flow

### 1. Load Chart Data
1.1. Read `.lmas-core/development/data/ux/sub-skills/chart-types.csv`
1.2. Read `.lmas-core/development/data/ux/sub-skills/chart-colors.csv`
1.3. Parse chart-types columns: category, chart_name, best_for, data_points_min, data_points_max, complexity, mobile_friendly, a11y_notes, avoid_when, libraries
1.4. Parse chart-colors columns: palette_name, colors_hex, purpose, wcag_safe, colorblind_safe
1.5. Validation: Both CSVs loaded. If missing, use built-in chart recommendation engine.

### 2. Classify Data Type
2.1. Match `data_type` to chart-types category (case-insensitive)
2.2. If `data_type` is descriptive (e.g., "sales over time"), classify automatically:
   - Contains "over time" / "trend" / "timeline" → `trend`
   - Contains "compare" / "vs" / "versus" → `comparison`
   - Contains "breakdown" / "share" / "percentage" → `composition`
   - Contains "spread" / "range" / "frequency" → `distribution`
   - Contains "correlation" / "between" → `relationship`
2.3. Filter chart-types to matching category
2.4. Validation: Category identified

### 3. Rank Chart Options
3.1. From matched charts, score each by:
   - **Data points fit:** Does `data_points` fall within min/max range? (+3 if yes)
   - **Mobile friendliness:** Is `mobile_friendly` true? (+2 if yes)
   - **Complexity:** Lower complexity scores higher for simple needs (+1)
   - **Library availability:** Does chart exist in preferred library? (+2 if yes)
3.2. Sort by score descending
3.3. Select top recommendation + 2 alternatives
3.4. Validation: At least 1 chart recommendation

### 4. Select Color Palette
4.1. Filter `chart-colors.csv` for palettes marked `wcag_safe=true`
4.2. Prefer palettes also marked `colorblind_safe=true`
4.3. Match palette to data type:
   - Sequential data → sequential palette (light to dark single hue)
   - Categorical data → qualitative palette (distinct hues)
   - Diverging data → diverging palette (two hues from center)
4.4. Return hex values, purpose, and accessibility flags
4.5. Validation: Selected palette is both WCAG and colorblind safe

### 5. Generate Library Guidance
5.1. For the top recommended chart, provide library-specific implementation notes:
   - **Recharts:** Component name, key props, responsive wrapper
   - **Chart.js:** Chart type config, dataset format
   - **D3:** Scale type, axis generators, transition notes
   - **Visx/Nivo:** Component API reference
5.2. If `library=any` → recommend best library for this specific chart type
5.3. Include npm install command
5.4. Validation: Library guidance matches recommended chart

### 6. Mobile Adaptation
6.1. For each recommended chart, specify mobile behavior:
   - Minimum width before horizontal scroll activates
   - Touch interaction adaptations (pinch zoom, tap-to-reveal)
   - Simplified version for small screens (e.g., bar chart instead of grouped bar)
   - Legend placement (bottom on mobile, side on desktop)
6.2. Validation: Mobile notes present

### 7. Common Mistakes
7.1. List top 3 mistakes for the recommended chart type:
   - Over-plotting, misleading axes, poor color choices, 3D effects, etc.
7.2. Include the `avoid_when` data from CSV
7.3. Validation: At least 2 mistakes listed

---

## Output Format

```markdown
## 📊 Chart Recommendation: {data_type}

### Recommended Chart
| Attribute | Value |
|-----------|-------|
| Chart Type | {name} |
| Best For | {description} |
| Data Points | {min}-{max} optimal |
| Complexity | {low/medium/high} |
| Mobile | {yes/no + notes} |

### Alternatives
| # | Chart | When to Prefer |
|---|-------|---------------|
| 2 | {chart} | {reason} |
| 3 | {chart} | {reason} |

### Color Palette
| # | Hex | Swatch | Purpose |
|---|-----|--------|---------|
| 1 | #XXXXXX | ██ | Primary series |
| 2 | #XXXXXX | ██ | Secondary series |
| ... | ... | ... | ... |

**Accessibility:** ✅ WCAG safe | ✅ Colorblind safe (deuteranopia, protanopia tested)

### Library Implementation
**Recommended:** {library} (`npm install {package}`)

```jsx
// Example usage
<{Component} data={data} ... />
```

### Mobile Adaptation
- Min width: {X}px before scroll
- Touch: tap-to-reveal tooltips
- Small screen alternative: {chart type}

### Common Mistakes to Avoid
1. ❌ {mistake 1} — {why it's bad}
2. ❌ {mistake 2} — {why it's bad}
3. ❌ {mistake 3} — {why it's bad}
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| CSV not found | Chart data CSVs missing | Use built-in chart recommendation logic |
| Unknown data type | Category not recognized | Ask user to clarify or pick from list: comparison, trend, distribution, composition, relationship |
| No colorblind-safe palette | Missing from CSV | Generate palette using colorblind-safe hues (blue, orange, teal) |
| Library not supported | Requested library has no chart type | Suggest alternative library, still show chart recommendation |

---

## Examples

### Example 1: Trend Data

```
*chart trend
```

Returns: Line Chart (primary), Area Chart (alternative), with sequential blue palette, Recharts implementation, responsive container notes.

### Example 2: Comparison with Volume

```
*chart comparison --data_points=50
```

Returns: Grouped Bar Chart for moderate data, Dot Plot alternative for dense comparison, qualitative palette.

### Example 3: Specific Library

```
*chart distribution --library=d3
```

Returns: Histogram (primary), Box Plot (alternative), D3-specific scales and axis generators, diverging palette.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/sub-skills/chart-types.csv
  - .lmas-core/development/data/ux/sub-skills/chart-colors.csv
tags:
  - ux
  - data-visualization
  - charts
  - accessibility
  - data-driven
updated_at: 2026-03-17
```
