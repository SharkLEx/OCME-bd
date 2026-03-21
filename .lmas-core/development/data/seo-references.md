# SEO References — On-Demand Knowledge Base

> **Usage:** This file is loaded on-demand by @seo (Cypher) worker tasks.
> Do NOT pre-load during agent activation. Load only when executing SEO analysis tasks.
> **Last Updated:** 2026-03 (review quarterly)

---

## 1. SEO Health Score (0-100)

### Dimension Weights

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Technical SEO | 22% | Crawlability, indexability, security, URL structure, rendering |
| Content Quality | 23% | E-E-A-T, originality, depth, readability |
| On-Page SEO | 20% | Title tags, meta descriptions, headings, internal links |
| Schema/Structured Data | 10% | JSON-LD presence, validity, coverage |
| Performance (CWV) | 10% | LCP, INP, CLS |
| AI Search Readiness | 10% | GEO score, citability, llms.txt |
| Images | 5% | Alt text, formats, lazy loading, CLS impact |

### Score Interpretation

| Range | Rating | Color | Action |
|-------|--------|-------|--------|
| 90-100 | Excellent | 🟢 Green | Maintain and monitor |
| 70-89 | Good | 🟡 Yellow | Optimize opportunities |
| 50-69 | Needs Work | 🟠 Orange | Priority improvements needed |
| 0-49 | Critical | 🔴 Red | Immediate action required |

---

## 2. E-E-A-T Framework

> Source: Google Search Quality Rater Guidelines (Sep 2025 + Dec 2025 update)

### Scoring Weights

| Factor | Weight | Signals |
|--------|--------|---------|
| **Experience** | 20% | First-hand experience, original content, personal insights, user-generated content |
| **Expertise** | 25% | Credentials, technical accuracy, depth of knowledge, author bios |
| **Authoritativeness** | 25% | External recognition, backlinks, citations, brand mentions, industry awards |
| **Trustworthiness** | 30% | Transparency, security (HTTPS), accurate info, clear policies, contact info |

### YMYL (Your Money Your Life) Pages

Pages about health, finance, safety, legal — require HIGHEST E-E-A-T standards.
- Author credentials MUST be verifiable
- Sources MUST be cited
- Content MUST be reviewed by qualified professionals

---

## 3. Core Web Vitals Thresholds

> Source: web.dev (Feb 2026) — Lighthouse 13.0

### Current Metrics (INP replaced FID in March 2024)

| Metric | Good | Needs Improvement | Poor | What It Measures |
|--------|------|-------------------|------|------------------|
| **LCP** (Largest Contentful Paint) | ≤ 2.5s | 2.5s – 4.0s | > 4.0s | Loading performance |
| **INP** (Interaction to Next Paint) | ≤ 200ms | 200ms – 500ms | > 500ms | Interactivity responsiveness |
| **CLS** (Cumulative Layout Shift) | ≤ 0.1 | 0.1 – 0.25 | > 0.25 | Visual stability |

### LCP Sub-Parts (advanced diagnosis)

| Sub-Part | Description | Target |
|----------|-------------|--------|
| TTFB | Time to First Byte | < 800ms |
| Resource Load Delay | Time from TTFB to resource start | < 100ms |
| Resource Load Duration | Time to download LCP resource | < 800ms |
| Element Render Delay | Time from resource loaded to rendered | < 100ms |

### DEPRECATED — Do NOT Use

- **FID** (First Input Delay) — replaced by INP in March 2024. NEVER reference FID.

---

## 4. Schema.org — Types & Deprecations

### Recommended Types by Page

| Page Type | Schema Types |
|-----------|-------------|
| Homepage | Organization, WebSite, SearchAction |
| Product | Product, Offer, AggregateRating, Review |
| Article/Blog | Article, BlogPosting, BreadcrumbList, Author |
| Service | Service, Offer, AreaServed |
| FAQ | FAQPage (⚠️ restricted — see below) |
| Local Business | LocalBusiness, PostalAddress, GeoCoordinates, OpeningHoursSpecification |
| Event | Event, VirtualLocation/Place, Offer |
| Video | VideoObject, BroadcastEvent, Clip |
| Software | SoftwareApplication, SoftwareSourceCode |
| Person/Profile | ProfilePage, Person |
| Course | Course, CourseInstance |

### DEPRECATED Schema Types — NEVER Recommend

| Type | Deprecated Since | Reason |
|------|-----------------|--------|
| **HowTo** | Sep 2023 | Google removed rich results for HowTo |
| **SpecialAnnouncement** | Jul 2025 | COVID-era type, no longer supported |

### RESTRICTED Schema Types

| Type | Restriction | Since |
|------|-------------|-------|
| **FAQPage** | Only shows rich results for government and health authority sites | Aug 2023 |

### Validation Rules

- Always use `https://schema.org` (not `http://`)
- JSON-LD is the PREFERRED format (over Microdata/RDFa)
- No placeholder text in schema (e.g., "Lorem ipsum", "TODO")
- All required fields must be populated
- URLs in schema must be absolute, not relative
- datePublished and dateModified must be ISO 8601 format

---

## 5. Quality Gates

### Content Minimums by Page Type

| Page Type | Min Words | Unique Content % | Notes |
|-----------|-----------|-------------------|-------|
| Homepage | 500 | 100% | Must articulate clear value proposition |
| Service page | 800 | 100% | Unique for each service |
| Blog post | 1,500 | 100% | Long-form, well-researched |
| Product page | 400 | 80%+ | Template OK for specs, unique description required |
| Location (primary) | 600 | 60%+ | City-level pages with unique local content |
| Location (secondary) | 500 | 40%+ | Neighborhood/area with local signals |
| Landing page | 600 | 90%+ | Conversion-focused, mostly unique |

### Scaling Limits (Anti-Doorway)

| Threshold | Level | Action |
|-----------|-------|--------|
| 30+ location pages | ⚠️ WARNING | Require 60%+ unique content each |
| 50+ location pages | 🛑 HARD STOP | Do NOT create without explicit justification + quality plan |
| 100+ programmatic pages | ⚠️ WARNING | Require review process + quality sampling |
| 500+ programmatic pages | 🛑 HARD STOP | Do NOT create without data-driven justification |

### Google Enforcement Waves (Reference)

- **Jun 2025:** Scaled content abuse enforcement wave
- **Aug 2025:** Follow-up enforcement, stricter doorway page detection
- **Dec 2025:** Core update with content quality signals enhanced

---

## 6. GEO (Generative Engine Optimization)

### GEO Health Score (0-100)

| Dimension | Weight | Signals |
|-----------|--------|---------|
| **Citability** | 25% | Self-contained passages (134-167 words optimal), clear claims with data |
| **Structural Readability** | 20% | Headers, lists, tables, short paragraphs, scannable format |
| **Multi-Modal Content** | 15% | Images with alt text, videos, infographics, charts |
| **Authority & Brand Signals** | 20% | Brand mentions, expert quotes, original research, citations |
| **Technical Accessibility** | 20% | AI crawler access, llms.txt, clean HTML, fast loading |

### AI Crawler Robots.txt

| Crawler | User-Agent | Platform |
|---------|-----------|----------|
| GPTBot | GPTBot | OpenAI / ChatGPT |
| Google-Extended | Google-Extended | Google AI (Gemini, AI Overviews) |
| Anthropic | anthropic-ai | Claude |
| CCBot | CCBot | Common Crawl |
| PerplexityBot | PerplexityBot | Perplexity |
| Applebot-Extended | Applebot-Extended | Apple Intelligence |

### Citability Optimization

- **Optimal passage length:** 134-167 words per self-contained section
- **Structure:** Claim → Evidence → Conclusion in each passage
- **Data density:** Include specific numbers, dates, percentages
- **Attribution:** Clear source attribution increases citation probability
- **Brand mentions:** Correlation with AI citation frequency (2-3 natural mentions per article)

### llms.txt Standard

```
# llms.txt — AI-readable site summary
# Place at site root: /llms.txt

> Site description in 1-2 sentences

## Key Topics
- Topic 1: brief description
- Topic 2: brief description

## Important Pages
- /about: Company overview
- /pricing: Plans and pricing
- /docs: Documentation
```

---

## 7. Priority Classification

### Finding Severity Levels

| Level | Description | Timeframe | Examples |
|-------|-------------|-----------|---------|
| **Critical** | Blocks indexation or causes penalties | Immediate | noindex on key pages, security issues, manual actions |
| **High** | Significant ranking impact | 1 week | Missing title tags, broken canonical, CWV failures |
| **Medium** | Optimization opportunity | 1 month | Schema gaps, image optimization, internal linking |
| **Low** | Nice to have | Backlog | Minor meta description tweaks, alt text refinements |

---

## 8. Industry Vertical Defaults

### Business Type Detection Signals

| Type | Detection Signals |
|------|------------------|
| **SaaS** | /pricing, /features, /integrations, "free trial", "sign up", "demo" |
| **E-commerce** | /products, /cart, /checkout, "add to cart", product schema, price elements |
| **Local Business** | Phone number, physical address, service area, Google Maps embed, LocalBusiness schema |
| **Publisher/Media** | /blog, /news, article schema, multiple author pages, high content volume |
| **Agency** | /case-studies, /portfolio, /clients, client logos, service descriptions |

### Schema Priority by Industry

| Industry | Priority Schema Types |
|----------|----------------------|
| SaaS | Organization, SoftwareApplication, FAQPage*, Pricing table, WebSite+SearchAction |
| E-commerce | Product, Offer, AggregateRating, Review, BreadcrumbList, ItemList |
| Local | LocalBusiness, PostalAddress, GeoCoordinates, OpeningHours, Service |
| Publisher | Article, BlogPosting, NewsArticle, Author, BreadcrumbList, WebSite |
| Agency | Organization, Service, Review, CaseStudy (custom), BreadcrumbList |

*FAQPage: limited rich results since Aug 2023 (gov/health only), but still useful for structured data

---

## 9. Title Tag & Meta Description Guidelines

### Title Tags

| Rule | Guideline |
|------|-----------|
| Length | 30-60 characters (optimal: 50-60) |
| Format | Primary Keyword — Secondary Keyword \| Brand |
| Uniqueness | Every page MUST have a unique title |
| Keywords | Primary keyword as close to the start as possible |

### Meta Descriptions

| Rule | Guideline |
|------|-----------|
| Length | 120-160 characters (optimal: 150-160) |
| CTA | Include call-to-action when appropriate |
| Uniqueness | Every page SHOULD have a unique description |
| Keywords | Include primary keyword naturally |

---

## 10. Internal Linking Best Practices

| Rule | Guideline |
|------|-----------|
| Anchor text | Descriptive, keyword-relevant (not "click here") |
| Depth | Important pages within 3 clicks from homepage |
| Orphan pages | Zero orphan pages (every page linked from at least 1 other page) |
| Hub & spoke | Pillar pages link to cluster pages and vice versa |
| Broken links | Zero internal 404s |
| Redirect chains | Maximum 1 redirect hop (no chains of 3+) |
