# SEO Performance Analysis (Core Web Vitals) — Worker Task

> **Owner:** @seo (Cypher) → Worker: Performance Gauge
> **Trigger:** `*performance {url}` or spawned by `*audit`
> **Type:** Worker — standalone or parallel execution

---

## Purpose

Analyze Core Web Vitals and page performance metrics against Google's official thresholds. Provides specific optimization recommendations with expected impact.

## Prerequisites

- Page URL for analysis
- Reference: CWV thresholds from `seo-references.md`
- Optional: Lighthouse/PageSpeed MCP tools for real metrics

## Analysis Framework

### 1. Core Web Vitals (The Big Three)

#### LCP — Largest Contentful Paint (Loading)

| Rating | Threshold | Action |
|--------|-----------|--------|
| 🟢 Good | ≤ 2.5s | Maintain |
| 🟡 Needs Improvement | 2.5s – 4.0s | Optimize |
| 🔴 Poor | > 4.0s | Critical fix |

**LCP Sub-Parts Analysis:**

| Sub-Part | Target | Common Issues |
|----------|--------|---------------|
| TTFB | < 800ms | Slow server, no CDN, no caching |
| Resource Load Delay | < 100ms | No preload hint, render-blocking CSS |
| Resource Load Duration | < 800ms | Unoptimized images, no compression |
| Element Render Delay | < 100ms | Heavy JS, layout shifts before paint |

**Common LCP Elements:** Hero image, H1 text block, video poster, background image

#### INP — Interaction to Next Paint (Interactivity)

| Rating | Threshold | Action |
|--------|-----------|--------|
| 🟢 Good | ≤ 200ms | Maintain |
| 🟡 Needs Improvement | 200ms – 500ms | Optimize |
| 🔴 Poor | > 500ms | Critical fix |

**⚠️ INP replaced FID in March 2024. NEVER reference FID.**

**Common INP Issues:**
- Long tasks blocking main thread (>50ms)
- Heavy event handlers (click, input, keypress)
- Excessive DOM size (>1500 elements)
- Third-party scripts blocking interaction
- Layout recalculations during interaction

#### CLS — Cumulative Layout Shift (Visual Stability)

| Rating | Threshold | Action |
|--------|-----------|--------|
| 🟢 Good | ≤ 0.1 | Maintain |
| 🟡 Needs Improvement | 0.1 – 0.25 | Optimize |
| 🔴 Poor | > 0.25 | Critical fix |

**Common CLS Causes:**
- Images without explicit width/height
- Ads/embeds without reserved space
- Web fonts causing FOIT/FOUT
- Dynamically injected content above viewport
- Late-loading CSS causing reflow

### 2. Additional Performance Metrics

| Metric | Target | Impact |
|--------|--------|--------|
| **TTFB** | < 800ms | Server responsiveness |
| **FCP** | < 1.8s | First visual feedback |
| **TBT** | < 200ms | Main thread availability |
| **Speed Index** | < 3.4s | How quickly content appears |
| **TTI** | < 3.8s | Time to fully interactive |

### 3. Resource Optimization Checks

| Resource | Check | Recommendation |
|----------|-------|---------------|
| **Images** | Format (WebP/AVIF?), compression, dimensions, lazy loading, srcset | Convert to WebP/AVIF, add width/height, lazy load below fold |
| **CSS** | Render-blocking?, size, unused CSS | Critical CSS inline, defer non-critical, remove unused |
| **JavaScript** | Render-blocking?, size, defer/async, unused JS | Defer/async, code split, remove unused, lazy load |
| **Fonts** | FOIT/FOUT?, preload, font-display, subset | Preload, font-display: swap, subset to needed glyphs |
| **Third-party** | Impact on main thread, lazy loadable? | Defer, facade pattern, remove non-essential |

### 4. Server & Delivery

| Check | Target | Common Fixes |
|-------|--------|-------------|
| Compression | gzip or Brotli enabled | Enable at server level |
| Caching | Cache-Control headers present | Set appropriate max-age |
| CDN | Static assets on CDN | CloudFlare, Fastly, etc. |
| HTTP/2+ | HTTP/2 or HTTP/3 | Upgrade server/CDN |
| Preconnect | DNS prefetch for third-party origins | Add `<link rel="preconnect">` |

## Output Format

```markdown
## Performance Analysis — {url}

**Performance Score: {score}/100**

### Core Web Vitals

| Metric | Value | Rating | Threshold | Status |
|--------|-------|--------|-----------|--------|
| LCP | Xs | 🟢/🟡/🔴 | ≤ 2.5s | Pass/Fail |
| INP | Xms | 🟢/🟡/🔴 | ≤ 200ms | Pass/Fail |
| CLS | X.XX | 🟢/🟡/🔴 | ≤ 0.1 | Pass/Fail |

### LCP Sub-Parts Diagnosis
| Sub-Part | Value | Target | Status |
|----------|-------|--------|--------|

### Resource Optimization
| Resource | Issue | Impact | Fix | Effort |
|----------|-------|--------|-----|--------|

### Server & Delivery
| Check | Status | Recommendation |
|-------|--------|---------------|

### Prioritized Optimization Plan
| # | Action | Metric Impact | Priority | Effort |
|---|--------|--------------|----------|--------|
```

## Data Sources

1. **With MCP (PageSpeed Insights):** Real CrUX data + Lighthouse lab data
2. **Without MCP:** Analyze HTML for common performance patterns, estimate impacts based on detected issues

## Scoring Logic

- CWV all green: Start at 85/100
- CWV all good + optimizations: Up to 100/100
- Each "poor" CWV metric: -25 points
- Each "needs improvement": -10 points
- Missing compression: -5
- No caching headers: -5
- Render-blocking resources: -5 each (max -15)
