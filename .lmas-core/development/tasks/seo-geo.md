# SEO GEO Analysis (Generative Engine Optimization) — Worker Task

> **Owner:** @seo (Cypher) → Worker: GEO Sentinel
> **Trigger:** `*geo {url}` or spawned by `*audit`
> **Type:** Worker — standalone or parallel execution

---

## Purpose

Analyze a website's readiness for AI-powered search engines (Google AI Overviews, ChatGPT, Perplexity, Claude). Measures citability, structural readability, and technical accessibility for AI crawlers.

## Prerequisites

- Page HTML content (provided by orchestrator or fetched directly)
- Reference: GEO scoring and AI crawler data from `seo-references.md`

## Analysis Dimensions (5)

### 1. Citability (Weight: 25%)

AI search engines cite content that has self-contained, quotable passages.

| Check | Target | How to Measure |
|-------|--------|---------------|
| **Passage length** | 134-167 words per section | Count words per section/paragraph |
| **Self-contained claims** | Each passage makes a complete point | Assess if paragraphs stand alone |
| **Data density** | Specific numbers, dates, percentages | Count quantitative data points |
| **Source attribution** | Clear references to sources | Check for citations, links to studies |
| **Claim + Evidence pattern** | Claim → Data → Conclusion | Assess structure of key passages |

**Scoring:**
- 90-100: Rich in citable passages with data and clear claims
- 70-89: Good passages but inconsistent density
- 50-69: Some citable content, mostly generic
- 0-49: No self-contained, quotable passages

### 2. Structural Readability (Weight: 20%)

AI models parse structured content more effectively.

| Check | Target | Impact |
|-------|--------|--------|
| **Heading hierarchy** | H1 → H2 → H3, logical flow | AI parses sections by headers |
| **Lists and tables** | Key info in scannable format | Easy extraction by AI |
| **Short paragraphs** | 2-4 sentences per paragraph | AI prefers concise blocks |
| **Summary sections** | TL;DR, key takeaways | Direct citability |
| **Definition patterns** | "X is Y" format for key concepts | AI favors clear definitions |
| **FAQ sections** | Structured Q&A | Direct answer extraction |

### 3. Multi-Modal Content (Weight: 15%)

AI models increasingly cite multi-modal content.

| Check | Target | Why |
|-------|--------|-----|
| **Images with alt text** | Every image has descriptive alt | AI can reference images |
| **Videos** | Embedded with transcripts | Searchable by AI |
| **Infographics / charts** | Visual data representation | Multi-modal citation |
| **Code examples** | Formatted, runnable code blocks | Technical AI citations |
| **Tables with data** | Structured data presentation | Easy extraction |

### 4. Authority & Brand Signals (Weight: 20%)

AI search engines correlate brand mentions with citation probability.

| Check | Target | How |
|-------|--------|-----|
| **Brand mentions** | 2-3 natural mentions per article | Not forced, organic references |
| **Expert quotes** | Named expert with credentials | Adds authority to claims |
| **Original research** | Unique data, surveys, studies | Highly citable |
| **About/author info** | Clear expertise signals | E-E-A-T crossover |
| **Unique perspective** | Not rehashing existing content | AI prefers novel insights |

### 5. Technical Accessibility (Weight: 20%)

Can AI crawlers actually access and parse the content?

| Check | Target | How to Verify |
|-------|--------|--------------|
| **robots.txt — AI crawlers** | Not blocking GPTBot, Google-Extended, etc. | Parse robots.txt |
| **llms.txt** | Present at site root | Fetch /llms.txt |
| **Clean HTML** | Semantic markup, not JS-rendered walls | Check page source |
| **Page speed** | Fast loading for crawlers | TTFB < 800ms |
| **Render mode** | SSR/SSG preferred over pure CSR | Check if content is in initial HTML |
| **Canonical URL** | Prevent duplicate crawling | Check canonical tags |

#### AI Crawlers to Check in robots.txt

| Crawler | User-Agent | Platform |
|---------|-----------|----------|
| GPTBot | GPTBot | OpenAI / ChatGPT |
| Google-Extended | Google-Extended | Google AI (Gemini, AI Overviews) |
| anthropic-ai | anthropic-ai | Claude / Anthropic |
| CCBot | CCBot | Common Crawl |
| PerplexityBot | PerplexityBot | Perplexity AI |
| Applebot-Extended | Applebot-Extended | Apple Intelligence |

## Output Format

```markdown
## GEO Analysis — {url}

**GEO Health Score: {score}/100**
**AI Crawler Access: {Allowed/Partially Blocked/Blocked}**
**llms.txt: {Present/Missing}**

### Dimension Scores

| Dimension | Score | Weight | Weighted | Key Finding |
|-----------|-------|--------|----------|-------------|
| Citability | X/100 | 25% | X | {summary} |
| Structural Readability | X/100 | 20% | X | {summary} |
| Multi-Modal Content | X/100 | 15% | X | {summary} |
| Authority Signals | X/100 | 20% | X | {summary} |
| Technical Accessibility | X/100 | 20% | X | {summary} |

### AI Crawler Access

| Crawler | Status | robots.txt Rule |
|---------|--------|----------------|

### Citability Highlights
- Best citable passage found: {excerpt}
- Average passage length: {X words} (optimal: 134-167)
- Data density: {X data points per 1000 words}

### Findings (prioritized)
| # | Finding | Dimension | Severity | Recommendation |
|---|---------|-----------|----------|---------------|

### llms.txt Recommendation
{If missing, provide template. If present, review and suggest improvements.}

### Quick Wins for AI Search Visibility
| # | Action | Impact | Effort |
|---|--------|--------|--------|
```

## Scoring Logic

- Each dimension: 0-100 based on checks passed
- Final score: Weighted average per dimension weights
- Blocking ALL AI crawlers: Caps score at 20/100
- Missing llms.txt: -10 from Technical Accessibility
- No citable passages: Caps Citability at 20/100
