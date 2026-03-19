# SEO Content Analysis (E-E-A-T) — Worker Task

> **Owner:** @seo (Cypher) → Worker: Content Judge
> **Trigger:** `*content {url}` or spawned by `*audit`
> **Type:** Worker — standalone or parallel execution

---

## Purpose

Analyze content quality through the E-E-A-T framework (Experience, Expertise, Authoritativeness, Trustworthiness). Returns structured quality scores with specific improvement recommendations.

## Prerequisites

- Page HTML content (provided by orchestrator or fetched directly)
- Reference: E-E-A-T weights and quality gates from `seo-references.md`

## Analysis Dimensions (4)

### 1. Experience (Weight: 20%)

Evaluate first-hand experience signals:

| Signal | Check | Weight |
|--------|-------|--------|
| Original content | Not AI-generated boilerplate, unique perspective | High |
| First-person insights | Personal observations, real examples | Medium |
| Case studies / examples | Concrete real-world applications | Medium |
| User-generated content | Reviews, testimonials, comments | Low |
| Media evidence | Original photos, videos, screenshots | Medium |

**Scoring:**
- 90-100: Rich first-hand experience throughout
- 70-89: Some experience signals, mostly informational
- 50-69: Generic content, little personal touch
- 0-49: Clearly templated or AI-generated without expertise

### 2. Expertise (Weight: 25%)

Evaluate demonstrated knowledge:

| Signal | Check | Weight |
|--------|-------|--------|
| Technical accuracy | Claims are factually correct | Critical |
| Depth of coverage | Topic covered comprehensively | High |
| Author credentials | Bio, qualifications, links to profile | High |
| Terminology usage | Appropriate technical language | Medium |
| Current information | Up-to-date data and references | Medium |

**Scoring:**
- 90-100: Expert-level depth, author credentials clear
- 70-89: Good knowledge demonstrated, some gaps
- 50-69: Surface-level, lacks expert signals
- 0-49: Inaccurate or dangerously shallow

### 3. Authoritativeness (Weight: 25%)

Evaluate external recognition:

| Signal | Check | Weight |
|--------|-------|--------|
| Backlink profile | Quality and relevance of inbound links | High |
| Brand mentions | Mentions across the web | Medium |
| Citations | Referenced by other authoritative sources | High |
| Social proof | Followers, shares, engagement | Low |
| Industry recognition | Awards, features, partnerships | Medium |

**Note:** Full backlink analysis requires MCP tools (Ahrefs, DataForSEO). Without them, analyze on-page authority signals only.

**Scoring:**
- 90-100: Widely recognized authority in the niche
- 70-89: Solid reputation signals
- 50-69: Limited external validation
- 0-49: No authority signals detected

### 4. Trustworthiness (Weight: 30%)

Evaluate trust signals:

| Signal | Check | Weight |
|--------|-------|--------|
| HTTPS | Secure connection | Critical |
| Contact information | Real address, phone, email | High |
| Privacy policy | Present and comprehensive | High |
| About page | Team, mission, history | Medium |
| Transparency | Disclosures, editorial standards | Medium |
| Accuracy | No misleading claims, clear sourcing | Critical |
| Reviews/ratings | Third-party verification | Medium |

**Scoring:**
- 90-100: Full transparency, all trust signals present
- 70-89: Most trust signals, minor gaps
- 50-69: Notable gaps in trust signals
- 0-49: Untrustworthy — missing critical signals

## Additional Checks

### Content Quality Metrics
- **Word count** vs minimum for page type (see quality gates)
- **Readability** — Flesch-Kincaid or equivalent assessment
- **Unique content %** — Check for boilerplate/template ratio
- **Thin content** detection — Pages below minimum thresholds
- **Keyword stuffing** — Unnatural keyword density (>3% = warning)

### AI Content Assessment
- Signs of AI-generated content without expert review
- Repetitive sentence structures
- Lack of specific examples or data
- Generic advice without actionable depth
- Note: AI content is NOT automatically bad — but must pass E-E-A-T standards

### YMYL Detection
- Is this page about health, finance, safety, or legal topics?
- If YMYL: Apply HIGHEST E-E-A-T standards
- Flag if YMYL content lacks author credentials or sources

## Output Format

```markdown
## E-E-A-T Content Analysis — {url}

**Content Quality Score: {score}/100**
**YMYL Detected: {yes/no}**
**Page Type: {type}**
**Word Count: {count} (minimum: {min for type})**

### E-E-A-T Breakdown

| Factor | Score | Weight | Weighted | Key Finding |
|--------|-------|--------|----------|-------------|
| Experience | X/100 | 20% | X | {summary} |
| Expertise | X/100 | 25% | X | {summary} |
| Authoritativeness | X/100 | 25% | X | {summary} |
| Trustworthiness | X/100 | 30% | X | {summary} |

### Findings (prioritized)
| # | Finding | Factor | Severity | Recommendation |
|---|---------|--------|----------|---------------|

### Content Improvement Opportunities
{specific, actionable recommendations for improving E-E-A-T}
```

## Scoring Logic

- Final score: Weighted average of 4 factors (E: 20%, E: 25%, A: 25%, T: 30%)
- YMYL pages: All thresholds raised by 15 points (70 = "needs work" instead of 50)
- Thin content: Automatically caps score at 40/100
