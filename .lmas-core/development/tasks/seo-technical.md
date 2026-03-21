# SEO Technical Analysis — Worker Task

> **Owner:** @seo (Cypher) → Worker: Technical Eye
> **Trigger:** `*technical {url}` or spawned by `*audit`
> **Type:** Worker — standalone or parallel execution

---

## Purpose

Perform a comprehensive technical SEO analysis covering 9 categories. Returns structured findings with scores and prioritized recommendations.

## Prerequisites

- Page HTML content (provided by orchestrator or fetched directly)
- Reference: CWV thresholds and quality gates from `seo-references.md`

## Analysis Categories (9)

### 1. Crawlability
- robots.txt analysis (allow/disallow rules, AI crawlers)
- XML sitemap presence, validity, and completeness
- Crawl depth (important pages within 3 clicks)
- Internal link structure and orphan pages
- JavaScript rendering requirements (CSR vs SSR vs SSG)
- Pagination handling (rel=next/prev or infinite scroll)

### 2. Indexability
- Meta robots tags (index/noindex, follow/nofollow)
- Canonical tags (self-referencing, cross-domain)
- Duplicate content detection (near-duplicate pages)
- Hreflang implementation (if multilingual)
- IndexNow implementation check

### 3. URL Structure
- URL length (recommended < 75 chars)
- URL readability (slugs with keywords, no parameters)
- Trailing slash consistency
- URL case consistency (lowercase preferred)
- Redirect chains (max 1 hop, no loops)
- 404 error pages (custom vs default)

### 4. Security
- HTTPS implementation (mixed content check)
- HSTS header presence
- Content-Security-Policy header
- X-Frame-Options / X-Content-Type-Options
- SSL certificate validity and expiration

### 5. Mobile Friendliness
- Viewport meta tag
- Responsive design vs separate mobile site
- Touch target sizes (min 48x48px)
- Font sizes (min 16px base)
- Content wider than screen check

### 6. Page Speed Signals
- Server response time (TTFB < 800ms)
- Resource hints (preconnect, prefetch, preload)
- Compression (gzip/brotli)
- Browser caching headers
- Render-blocking resources
- Image optimization (WebP/AVIF, lazy loading, srcset)

### 7. Structured Data (Surface-Level)
- JSON-LD presence (detailed analysis in seo-schema.md)
- Multiple schema types detected
- Schema errors visible in HTML

### 8. International SEO
- hreflang tags (if applicable)
- Language declaration (html lang attribute)
- Content-Language header

### 9. Accessibility (SEO-Relevant)
- Heading hierarchy (single H1, logical order)
- Image alt text coverage
- Link descriptive text (not "click here")
- ARIA landmarks

## Output Format

```markdown
## Technical SEO Analysis — {domain}

**Technical Score: {score}/100**

### Category Scores
| Category | Score | Issues Found |
|----------|-------|-------------|
| Crawlability | X/100 | N issues |
| Indexability | X/100 | N issues |
| URL Structure | X/100 | N issues |
| Security | X/100 | N issues |
| Mobile | X/100 | N issues |
| Page Speed | X/100 | N issues |
| Structured Data | X/100 | N issues |
| International | X/100 | N issues |
| Accessibility | X/100 | N issues |

### Findings (prioritized)
| # | Finding | Category | Severity | Recommendation |
|---|---------|----------|----------|---------------|
```

## Scoring Logic

- Each category: 0-100 based on issues found
- Final score: Weighted average (crawlability and indexability have 2x weight)
- Critical issue in any category caps that category at 30/100
