# Pitch Deck — Presentation Design Structure & Visual Guidelines

> **Task ID:** ux-pitch-deck
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** ux-design-expert, pm, analyst
> **Elicit:** true
> **Category:** presentation-design

---

## Purpose

Design a pitch deck structure with slide sequence, layout recommendations, content zones, visual guidelines, and speaker notes guidance. Tailored to audience, goal, and duration. Data sourced from `slide-layouts.csv` and `slide-principles.csv`.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `topic` | string | yes | User Input | Pitch topic or company name |
| `mode` | string | no | User Input | `yolo` \| `interactive` \| `pre-flight`. Default: `interactive` |

### Elicited Inputs (gathered during interactive mode)

| Field | Type | Required | Prompt |
|-------|------|----------|--------|
| `audience` | string | yes | "Who is the audience? (investors, clients, internal, conference)" |
| `goal` | string | yes | "Primary goal? (raise funding, sell product, inform, inspire)" |
| `duration` | number | yes | "Presentation duration in minutes? (5, 10, 15, 20, 30)" |
| `highlights` | string[] | no | "3-5 key points you MUST cover" |
| `data_heavy` | boolean | no | "Is this data-heavy? (charts, metrics, comparisons)" Default: false |
| `brand_colors` | string | no | "Brand hex colors if available (e.g., #3B82F6, #1E293B)" |

---

## Execution Flow

### 1. Load Slide Data
1.1. Read `.lmas-core/development/data/ux/sub-skills/slide-layouts.csv`
1.2. Read `.lmas-core/development/data/ux/sub-skills/slide-principles.csv`
1.3. Parse slide-layouts columns: layout_name, description, content_zones, best_for, visual_weight, data_friendly
1.4. Parse slide-principles columns: principle, description, applies_to_audience, priority, example
1.5. Validation: Both CSVs loaded. If missing, use built-in pitch deck frameworks.

### 2. Elicit Presentation Context
2.1. If `mode=interactive` → prompt for each elicited input
2.2. If `mode=yolo` → default audience=investors, goal=sell, duration=10
2.3. Validate: duration determines slide count (rule of thumb: 1 slide per 1-2 minutes + title/closing)
2.4. Calculate target slide count:
   - 5 min → 5-7 slides
   - 10 min → 8-12 slides
   - 15 min → 12-15 slides
   - 20 min → 15-18 slides
   - 30 min → 18-25 slides
2.5. Validation: Context complete

### 3. Build Slide Sequence
3.1. Select slide framework based on goal:
   - **Investors:** Problem → Solution → Market → Product → Traction → Team → Business Model → Ask
   - **Clients:** Pain Point → Solution → How It Works → Results/Case Studies → Pricing → Next Steps
   - **Internal:** Context → Current State → Proposal → Impact → Timeline → Resources → Q&A
   - **Conference:** Hook → Problem → Insight → Solution → Demo → Takeaways
3.2. Map `highlights` to specific slides (ensure each highlight has a dedicated slide)
3.3. Trim or expand sequence to match target slide count
3.4. Validation: Slide count within target range

### 4. Assign Layouts
4.1. For each slide in the sequence, match to a layout from `slide-layouts.csv`:
   - Title slides → full-bleed or centered minimal
   - Data slides → split layout (visual left, data right) or full chart
   - Story slides → large image with text overlay or quote layout
   - List/feature slides → grid or icon-row layout
4.2. If `data_heavy=true` → prefer `data_friendly=true` layouts
4.3. Define content zones per slide:
   - Header zone (slide title, 20% height)
   - Content zone (main content, 60-70% height)
   - Footer zone (page number, brand, 10% height)
4.4. Validation: Every slide has an assigned layout

### 5. Generate Visual Guidelines
5.1. **Color system:**
   - If `brand_colors` provided → use as primary + derive secondary
   - If not → recommend based on audience (investors=navy/green, clients=brand, conference=bold)
   - Max 3 colors + white + dark gray
5.2. **Typography:**
   - Heading: 32-44pt, bold, high contrast
   - Body: 18-24pt, regular weight
   - Captions/labels: 14-16pt
   - Rule: max 3 font sizes per slide
5.3. **Imagery:**
   - Full-bleed photos for emotional slides
   - Icons for feature/process slides
   - Charts for data slides (follow `*chart` recommendations)
   - Rule: 1 image per slide maximum (focus)
5.4. **Spacing:**
   - Slide margins: 5-8% of slide width
   - Element spacing: 24-40px between blocks
   - White space: minimum 40% per slide
5.5. Validation: Visual system is consistent

### 6. Generate Speaker Notes Guidance
6.1. For each slide, provide:
   - **Key message** — the ONE thing the audience should remember
   - **Talking points** — 2-3 bullet points for the speaker
   - **Transition** — how to move to the next slide
   - **Timing** — suggested seconds for this slide
6.2. Include audience engagement tips:
   - Questions to ask the audience
   - Pause points for emphasis
   - Data points to highlight verbally
6.3. Validation: Total timing sums to target duration (±10%)

### 7. Compile Deck Blueprint
7.1. Assemble complete slide-by-slide structure
7.2. Include visual guideline summary
7.3. Include speaker notes per slide
7.4. Include slide design principles relevant to audience
7.5. Include implementation tips (Figma, PowerPoint, Google Slides, Keynote)

---

## Output Format

```markdown
## 🎤 Pitch Deck: {topic}

**Audience:** {audience} | **Goal:** {goal} | **Duration:** {duration} min | **Slides:** {count}

### Visual Guidelines
| Element | Specification |
|---------|--------------|
| Colors | {primary}, {secondary}, {accent} + white + dark |
| Heading Font | {font}, 36-44pt, Bold |
| Body Font | {font}, 20-24pt, Regular |
| Slide Size | 16:9 (1920x1080) |
| Margins | 80px all sides |
| White Space | ≥40% per slide |

### Slide Sequence

#### Slide 1: {Title} — {layout_name}
**Layout:** {description}
**Content Zones:**
- Header: {brand logo + slide title}
- Center: {main headline, 44pt}
- Bottom: {subtitle, speaker name, date}

**Speaker Notes:**
- Key message: {message}
- Talking points: {bullets}
- Timing: {X} seconds
- Transition: "{transition phrase}"

---

#### Slide 2: {Problem} — {layout_name}
**Layout:** {description}
...

{repeat for all slides}

### Design Principles
1. **{principle}** — {description}
2. ...

### Implementation Tips
- **Figma:** Use auto-layout frames, 8px grid
- **PowerPoint:** Use slide master for consistency
- **Google Slides:** Use theme editor for brand colors
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| CSV not found | Slide data CSVs missing from `sub-skills/` | Use built-in pitch deck frameworks (investor, sales, internal, conference) |
| Duration too short | < 3 minutes | Warn minimum 3 slides, suggest elevator pitch format |
| Duration too long | > 45 minutes | Warn about attention span, suggest breakout sections |
| No highlights | User provides no key points | Infer from topic/goal, ask for confirmation |
| Brand colors invalid | Hex format incorrect | Ignore, use default audience-based palette |

---

## Examples

### Example 1: Investor Pitch

```
*pitch-deck "MyStartup Series A"
> Audience: investors
> Goal: raise funding
> Duration: 10
> Highlights: ARR $2M, 10x growth, AI-powered
```

Returns: 10-slide investor deck — Title, Problem, Solution, Market Size, Product Demo, Traction (ARR chart), Business Model, Team, Competition, Ask ($5M Series A).

### Example 2: Client Presentation

```
*pitch-deck "Agency Services"
> Audience: clients
> Goal: sell product
> Duration: 15
```

Returns: 13-slide sales deck — Hook (result), Pain Points, Our Approach, Services, Case Study x2, Process, Results, Pricing, Team, Testimonial, Next Steps, Contact.

### Example 3: Conference Talk

```
*pitch-deck "Future of AI Design"
> Audience: conference
> Goal: inspire
> Duration: 20
> Data heavy: true
```

Returns: 17-slide conference deck with data-heavy layouts, chart-optimized slides, bold visuals, minimal text per slide.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/sub-skills/slide-layouts.csv
  - .lmas-core/development/data/ux/sub-skills/slide-principles.csv
tags:
  - ux
  - presentation
  - pitch-deck
  - visual-design
  - data-driven
updated_at: 2026-03-17
```
