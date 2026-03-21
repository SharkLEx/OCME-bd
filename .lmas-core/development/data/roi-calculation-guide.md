# Design System ROI Calculation — On-Demand Knowledge Base

> **Usage:** Loaded on-demand by @ux-design-expert (Switch) when generating shock reports and business cases.
> Do NOT pre-load during agent activation. Load when calculating or presenting ROI.
> **Last Updated:** 2026-03 (review quarterly)

---

## 1. Time Savings Formulas

### Component Reuse Savings

```
time_saved_per_sprint = (components_reused × avg_build_time) - (components_reused × avg_integration_time)
```

| Variable | How to Measure | Typical Values |
|----------|---------------|----------------|
| `avg_build_time` | Time to build a component from scratch | 4-8 hours |
| `avg_integration_time` | Time to integrate an existing component | 0.5-1 hour |
| `components_reused` | Number of component instances per sprint | 5-15 |

**Example:**
- 10 components reused × (6h build - 0.75h integration) = **52.5 hours saved per sprint**

### Consistency Tax Elimination

```
consistency_savings = design_reviews_per_sprint × avg_review_time × inconsistency_rate
```

Without a design system, inconsistencies cause review cycles. With tokens and standardized components, review rounds drop.

| Variable | Typical Before DS | Typical After DS |
|----------|-------------------|------------------|
| `design_reviews_per_sprint` | 8-12 | 3-5 |
| `avg_review_time` | 30 min | 15 min |
| `inconsistency_rate` | 40-60% | 5-10% |

---

## 2. Consistency Metrics

### Visual Consistency Score

```
score = (tokens_used / total_values) × 100
```

| Score | Rating | Meaning |
|-------|--------|---------|
| 90-100% | Excellent | Nearly all values use tokens |
| 70-89% | Good | Some hardcoded values remain |
| 50-69% | Fair | Significant hardcoded values |
| < 50% | Poor | No real token adoption |

### Redundancy Index

```
redundancy = (duplicate_components / total_components) × 100
```

Target: < 10% redundancy after consolidation.

---

## 3. Developer Velocity Impact

### Before/After Metrics

| Metric | Before DS | After DS | Improvement |
|--------|-----------|----------|-------------|
| Time to build new page | 16-24h | 4-8h | 60-70% faster |
| Time to ship a feature | 2-3 sprints | 1-2 sprints | 40-50% faster |
| PR review cycles | 3-4 rounds | 1-2 rounds | 50% fewer |
| Onboarding time (new dev) | 2-3 weeks | 1 week | 50-65% faster |
| Bug fix time (UI) | 2-4h | 0.5-1h | 70-80% faster |

### Velocity Formula

```
velocity_improvement = 1 - (time_with_ds / time_without_ds)
```

---

## 4. Maintenance Cost Reduction

### CSS Bundle Reduction

```
css_savings = (current_css_size - projected_css_size) / current_css_size × 100
```

Typical token-based design systems reduce CSS by 30-60%.

### Component Maintenance

```
maintenance_reduction = (current_component_count - consolidated_count) / current_component_count × 100
```

| Area | Typical Reduction |
|------|-------------------|
| Component count | 30-50% |
| CSS file count | 40-60% |
| Design-related bugs | 50-70% |
| A11y violations | 60-80% |

---

## 5. Quality Improvement Quantification

### Accessibility ROI

```
a11y_savings = (legal_risk_reduction + user_base_expansion + bug_reduction)
```

| Factor | Value |
|--------|-------|
| Legal risk (ADA lawsuits avg) | $25,000-$75,000 per incident |
| User base expansion (disability) | 15-20% of population |
| A11y bug reduction | 60-80% with automated tokens |

### Quality Score Improvement

| Quality Dimension | Before DS | After DS |
|-------------------|-----------|----------|
| Visual consistency | 4/10 | 9/10 |
| Accessibility compliance | 40-60% | 90-100% |
| Cross-browser consistency | 70% | 95% |
| Performance (CSS efficiency) | Variable | Optimized |

---

## 6. Investment Cost

### One-Time Costs

| Item | Effort | Cost Estimate |
|------|--------|---------------|
| Pattern audit | 1-2 sprints | {{N}} dev-hours |
| Token extraction | 1 sprint | {{N}} dev-hours |
| Component migration | 2-4 sprints | {{N}} dev-hours |
| Documentation | 1 sprint | {{N}} dev-hours |
| Testing infrastructure | 0.5 sprint | {{N}} dev-hours |
| **Total** | **5-8 sprints** | **{{N}} dev-hours** |

### Ongoing Costs

| Item | Effort/Sprint |
|------|---------------|
| Token maintenance | 2-4 hours |
| New component creation | 4-8 hours |
| Documentation updates | 2-4 hours |
| Design review | 2-4 hours |

---

## 7. ROI Summary Formula

```
ROI = (Annual Savings - Annual Cost) / Initial Investment × 100

Annual Savings =
  (time_saved_per_sprint × sprints_per_year × hourly_rate)
  + (consistency_savings × sprints_per_year × hourly_rate)
  + (maintenance_reduction_hours × hourly_rate)
  + (bug_reduction_hours × hourly_rate)

Annual Cost =
  ongoing_maintenance_hours × hourly_rate

Initial Investment =
  total_migration_hours × hourly_rate
```

### Typical ROI Timeline

| Period | ROI |
|--------|-----|
| Month 1-3 | Negative (investment phase) |
| Month 4-6 | Break-even |
| Month 7-12 | 150-300% ROI |
| Year 2+ | 400-800% ROI |

---

## 8. Presentation Format for Stakeholders

### Executive Summary Template

```
BEFORE: [N] unique colors, [N] duplicate components, [N]h per feature
AFTER:  [N] semantic tokens, [N] reusable components, [N]h per feature

INVESTMENT: [N] dev-hours (≈ [N] sprints)
ANNUAL SAVINGS: [N] dev-hours (≈ $[N])
ROI: [N]% in first year, break-even at month [N]
```

### Key visuals to include:
1. **Before/after color palette** — chaos vs order
2. **Component count reduction** — bar chart
3. **Time-to-feature chart** — sprint comparison
4. **Cumulative savings** — line chart over 12 months
5. **Quality score radar** — before vs after across dimensions
