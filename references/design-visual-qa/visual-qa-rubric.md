# Visual-QA rubric — hierarchy, rhythm, contrast, restraint

Durable knowledge for `design-visual-qa`: the criteria a reviewer (Claude's vision, or
a human running the Tier-4 checklist) judges a rendered surface against. The skill's
mechanics — capture baselines, diff later runs, report the tier — live in the SKILL
body. This file is *what makes a rendering good or regressed*, so a "changed" verdict is
graded against a standard rather than vibes.

Two jobs share these criteria: **regression** (did this run drift from its baseline, and
does the drift make it better or worse?) and **absolute quality** (is what's on screen
intentional design or slop?). The four axes below serve both; they are the visual
complement to `references/shared/anti-slop-principles.md` (evaluated on *pixels*, where
that rubric is evaluated on *decisions*).

## Axis 1 — Hierarchy

Within three seconds, is the single most important thing on screen unmistakable, and
does everything else fall into a clear primary → secondary → tertiary order?

- One dominant focal point per view; the primary CTA reads as primary (size, weight,
  color, isolation) and there is exactly one per view.
- Type scale is stepped and legible: distinct heading/subhead/body sizes, body ≥ ~16px
  effective, line length in a readable band (~45–90 characters).
- Reading order matches importance — the eye lands where the page thesis wants it, not
  on whatever is merely largest by accident.
- **Regression flag:** a diff that flattens hierarchy (headline shrank to body size, the
  CTA lost its emphasis, two elements now compete) is a *worse* change even if pixel
  delta is small.

## Axis 2 — Rhythm

Is spacing systematic, or ad-hoc? Rhythm is the spacing/alignment cadence that makes a
page feel composed rather than assembled.

- Spacing comes from one scale (consistent gaps, padding, section rhythm) — not a
  scatter of one-off pixel values.
- Alignment holds: shared baselines and a consistent grid/gutter; elements line up to
  something.
- Vertical rhythm is even where it should be and *deliberately* broken only for
  emphasis (whitespace used as a tool, not left as an accident).
- **Regression flag:** new inconsistent gaps, a broken grid, cramped or collapsed
  spacing, or content touching viewport edges after a change.

## Axis 3 — Contrast

Both the accessibility floor and the design tool. Contrast must be *sufficient* (legible
for everyone) and *purposeful* (directing attention).

- Text over its background clears WCAG AA — 4.5:1 normal, 3:1 large — checked with the
  luminance math in `references/shared/wcag-contrast-rules.md`. This is a hard floor: a
  render that fails it fails QA regardless of how it looks.
- Non-text affordances (buttons, icons, focus rings, form borders) clear 3:1.
- Meaning is never carried by color alone — state, series, and status are also encoded
  by shape, label, or position (survives color-blindness and grayscale).
- Contrast is *used*: the important element is the high-contrast one; quiet areas stay
  low-contrast so the loud element lands.
- **Regression flag:** any text/affordance that dropped below its ratio, a focus state
  that disappeared, or a "prettier" low-contrast restyle that broke legibility.

## Axis 4 — Restraint

Does the design say no to something? Slop turns everything up until nothing stands out.

- A limited, intentional palette and effect set — not five accents, stacked gradients,
  glass, and heavy shadow all at once.
- Decoration is motivated; motion clarifies (and honors `prefers-reduced-motion`) rather
  than fades-and-floats because it can.
- Empty space is allowed to exist; not every region is filled.
- **Regression flag:** creeping ornamentation, a new gradient/shadow/animation with no
  job, or a second competing accent color introduced since baseline.

## Turning the axes into a verdict

For a **regression** run, classify each observed change, don't just measure pixels:

- **Intentional-improvement** — the change moves an axis in the right direction (clearer
  hierarchy, tighter rhythm, better contrast). Note it; not a defect.
- **Neutral** — cosmetic, no axis meaningfully affected (a copy tweak, a minor color
  nudge that stays AA). Record and move on.
- **Regression** — an axis got worse (see each axis's flag). Report the specific
  element, viewport, and axis, and whether it looks deliberate.

An exact pixel-diff % (when a differ is present) tells you *where* and *how much*
changed; the four axes tell you *whether it matters*. A large delta that is a deliberate
redesign can pass; a tiny delta that drops text below AA or hides a focus ring fails.

## Severity ladder (what to escalate)

- **Critical** — contrast/AA failure, lost focus-visible state, primary CTA no longer
  identifiable, content clipped or unreachable at a supported viewport.
- **High** — hierarchy inverted or flattened, grid/alignment broken, a second primary
  CTA introduced.
- **Advisory** — spacing inconsistencies, unmotivated decoration, minor rhythm drift.

## See also

- `references/shared/anti-slop-principles.md` — the decision-level rubric this evaluates
  on pixels.
- `references/shared/wcag-contrast-rules.md` — the AA ratios and luminance formula for
  Axis 3.
- `design-accessibility` — the structural-a11y counterpart to a visual pass (alt text,
  heading order, labels, landmarks, token-contrast); pair a visual diff with it for full
  coverage.
