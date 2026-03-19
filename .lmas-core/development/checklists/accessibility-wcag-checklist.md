# Accessibility — WCAG 2.1 Compliance Checklist

```yaml
checklist:
  id: accessibility-wcag
  version: 1.0.0
  created: 2026-03-17
  updated: 2026-03-17
  purpose: "Verify WCAG 2.1 AA compliance with AAA recommendations for design system components and pages"
  mode: blocking
  domain: ux-design
  used_by:
    - "@ux-design-expert (Switch)"
    - "@qa (Oracle)"
  scoring:
    scale: "pass/fail per criterion"
    pass: "All AA items pass"
    conditional: "AA passes, some AAA items fail"
    fail: "Any AA item fails"
  reference: "https://www.w3.org/TR/WCAG21/"
```

---

## Principle 1: Perceivable

Information and UI components must be presentable in ways users can perceive.

### 1.1 Text Alternatives

- [ ] **1.1.1 Non-text Content (A)** — All images, icons, and non-text elements have `alt` text or `aria-label`
- [ ] **1.1.1 Decorative images** — Decorative images use `alt=""` or `role="presentation"` to be ignored by screen readers
- [ ] **1.1.1 Complex images** — Charts, diagrams, and infographics have long descriptions or data tables

### 1.2 Time-based Media

- [ ] **1.2.1 Audio-only/Video-only (A)** — Pre-recorded audio has transcript; pre-recorded video has audio description or text alternative
- [ ] **1.2.2 Captions (A)** — Pre-recorded video has synchronized captions
- [ ] **1.2.5 Audio Description (AA)** — Pre-recorded video has audio description for visual-only content

### 1.3 Adaptable

- [ ] **1.3.1 Info and Relationships (A)** — Semantic HTML conveys structure (headings, lists, tables, landmarks)
- [ ] **1.3.2 Meaningful Sequence (A)** — DOM order matches visual reading order
- [ ] **1.3.3 Sensory Characteristics (A)** — Instructions do not rely solely on shape, color, size, or location
- [ ] **1.3.4 Orientation (AA)** — Content works in both portrait and landscape orientation
- [ ] **1.3.5 Identify Input Purpose (AA)** — Input fields use `autocomplete` attributes for common fields (name, email, address)

### 1.4 Distinguishable

- [ ] **1.4.1 Use of Color (A)** — Color is not the sole means of conveying information (links, errors, status)
- [ ] **1.4.2 Audio Control (A)** — Auto-playing audio longer than 3 seconds can be paused or stopped
- [ ] **1.4.3 Contrast Minimum (AA)** — Text has at least 4.5:1 contrast ratio (3:1 for large text 18pt+/14pt bold+)
- [ ] **1.4.4 Resize Text (AA)** — Text can be resized to 200% without loss of content or functionality
- [ ] **1.4.5 Images of Text (AA)** — Real text is used instead of images of text (except logos)
- [ ] **1.4.6 Contrast Enhanced (AAA)** — Text has at least 7:1 contrast ratio (4.5:1 for large text)
- [ ] **1.4.10 Reflow (AA)** — Content reflows at 320px width (no horizontal scroll) and 256px height
- [ ] **1.4.11 Non-text Contrast (AA)** — UI components and graphical objects have at least 3:1 contrast
- [ ] **1.4.12 Text Spacing (AA)** — Content adapts when line height is 1.5x, paragraph spacing 2x, letter spacing 0.12em, word spacing 0.16em
- [ ] **1.4.13 Content on Hover/Focus (AA)** — Tooltips and popovers are dismissible, hoverable, and persistent

---

## Principle 2: Operable

UI components and navigation must be operable.

### 2.1 Keyboard Accessible

- [ ] **2.1.1 Keyboard (A)** — All functionality is available via keyboard
- [ ] **2.1.2 No Keyboard Trap (A)** — Focus is never trapped (except modals with proper Escape handling)
- [ ] **2.1.4 Character Key Shortcuts (A)** — Single character key shortcuts can be turned off or remapped

### 2.2 Enough Time

- [ ] **2.2.1 Timing Adjustable (A)** — Time limits can be extended, adjusted, or turned off
- [ ] **2.2.2 Pause, Stop, Hide (A)** — Auto-moving, blinking, or scrolling content can be paused

### 2.3 Seizures and Physical Reactions

- [ ] **2.3.1 Three Flashes (A)** — Nothing flashes more than 3 times per second

### 2.4 Navigable

- [ ] **2.4.1 Bypass Blocks (A)** — Skip navigation link or landmark regions allow bypassing repeated content
- [ ] **2.4.2 Page Titled (A)** — Pages have descriptive, unique `<title>` elements
- [ ] **2.4.3 Focus Order (A)** — Tab order follows logical reading sequence
- [ ] **2.4.4 Link Purpose (A)** — Link text describes destination (no "click here" links)
- [ ] **2.4.6 Headings and Labels (AA)** — Headings and labels describe their topic or purpose
- [ ] **2.4.7 Focus Visible (AA)** — Keyboard focus indicator is clearly visible on all interactive elements

### 2.5 Input Modalities

- [ ] **2.5.1 Pointer Gestures (A)** — Multi-point or path-based gestures have single-pointer alternatives
- [ ] **2.5.2 Pointer Cancellation (A)** — Actions fire on up-event, not down-event (allows cancellation)
- [ ] **2.5.3 Label in Name (A)** — Accessible name contains the visible label text
- [ ] **2.5.4 Motion Actuation (A)** — Motion-triggered actions have UI alternatives and can be disabled

---

## Principle 3: Understandable

Information and UI operation must be understandable.

### 3.1 Readable

- [ ] **3.1.1 Language of Page (A)** — `<html lang="...">` attribute is set correctly
- [ ] **3.1.2 Language of Parts (AA)** — Content in different languages uses `lang` attribute on the element

### 3.2 Predictable

- [ ] **3.2.1 On Focus (A)** — Focusing an element does not trigger unexpected context change
- [ ] **3.2.2 On Input (A)** — Changing a form control does not auto-submit or navigate unexpectedly
- [ ] **3.2.3 Consistent Navigation (AA)** — Navigation patterns are consistent across pages
- [ ] **3.2.4 Consistent Identification (AA)** — Same-function components have consistent labels and icons

### 3.3 Input Assistance

- [ ] **3.3.1 Error Identification (A)** — Errors are identified in text (not color alone) and describe the problem
- [ ] **3.3.2 Labels or Instructions (A)** — Form inputs have visible labels and instructions
- [ ] **3.3.3 Error Suggestion (AA)** — Error messages suggest how to fix the problem
- [ ] **3.3.4 Error Prevention (AA)** — Legal, financial, or data-deletion actions are reversible, verified, or confirmed

---

## Principle 4: Robust

Content must be robust enough for assistive technologies.

### 4.1 Compatible

- [ ] **4.1.1 Parsing (A)** — HTML is well-formed (no duplicate IDs, proper nesting)
- [ ] **4.1.2 Name, Role, Value (A)** — Custom components expose name, role, and value to assistive tech via ARIA
- [ ] **4.1.3 Status Messages (AA)** — Status messages use `role="status"` or `aria-live` to announce without focus change

---

## Testing Tools Reference

| Tool | Purpose |
|------|---------|
| axe-core / axe DevTools | Automated WCAG scanning |
| WAVE | Visual accessibility evaluation |
| Lighthouse | Audit score (accessibility section) |
| NVDA / VoiceOver | Screen reader manual testing |
| Colour Contrast Analyser | Manual contrast ratio verification |
| Keyboard only | Tab through entire flow without mouse |
