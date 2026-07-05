# Anti-Slop Principles — Intentional vs. Generic-AI Design

Shared reference for the design-generation skills (`design-build`,
`design-system-gen`, `design-visual-qa`, `parallel-build`). "Slop" is the
flat, templated, instantly-recognizable look of output that was generated
without a point of view. These are **original principles**, framed from first
principles for this plugin, that separate *intentional* design from slop. They
are evaluative knowledge — a rubric the build and QA skills reason against — not
a step list.

## The core thesis

Slop is not ugly; it is **decision-free**. Every property (color, spacing, type,
motion, copy) sits at the safe default, so nothing reinforces anything else and
the result reads as "a website" rather than "this product's website." Intentional
design is the accumulation of *defensible choices* that all point the same way.
The test for any element: **could you state, in one sentence, why it is this and
not the default?** If not, it is probably slop.

## The eight tells of slop (and the intentional counter-move)

1. **No point of view.** Slop tries to please everyone and commits to nothing.
   *Counter:* pick a thesis for the page (what should the visitor feel and do)
   and let it veto choices that don't serve it.

2. **Default everything.** 16px text, gray-on-white, a centered hero, three equal
   cards, a generic gradient. *Counter:* deviate deliberately on the few axes
   that carry the brand; keep the rest disciplined so the deviations read.

3. **Even, characterless rhythm.** Uniform spacing and equal weight everywhere
   flattens hierarchy. *Counter:* establish a clear primary → secondary →
   tertiary scale; use space as emphasis; let the most important thing be the
   biggest, boldest, or most isolated.

4. **Stock metaphors.** The floating 3D blob, the abstract swoosh, the smiling
   stock team, the rocket for "launch." *Counter:* prefer real, specific imagery
   tied to the actual subject; if illustration is used, give it a consistent,
   owned style.

5. **Decorative motion.** Things that fade and float because animation is
   available, not because movement means something. *Counter:* motion should
   clarify (reveal hierarchy, confirm an action, show relationship) and always
   respect `prefers-reduced-motion`.

6. **Hollow, hedging copy.** "Empower your business with cutting-edge solutions."
   *Counter:* concrete nouns and verbs, specific claims, a real voice; if a
   competitor could paste their name over your headline, it is slop.

7. **Borrowed, unmotivated system.** Tokens, type scale, and color picked because
   they are popular, not because they fit the content. *Counter:* derive the
   system from the brand and content; every token should earn its place.

8. **No restraint.** Everything turned up — gradients, shadows, glassmorphism,
   five accent colors — so nothing stands out. *Counter:* restraint creates
   contrast; a quiet field makes the one loud element land.

## The intentionality checklist (what good looks like)

- **A defensible reason** exists for each primary design decision.
- **Hierarchy is unmistakable** within three seconds of looking.
- **The system is coherent:** spacing, type, and color come from one scale, not
  ad-hoc values.
- **Specificity over genericness:** copy and imagery could only belong to *this*
  subject.
- **Restraint is visible:** the design says no to something.
- **Accessibility is structural, not retrofitted:** contrast, focus order, and
  reduced-motion are designed in (see `wcag-contrast-rules.md`), because
  accessible constraints tend to *improve* hierarchy and clarity.
- **It survives the swap test:** replace the logo and copy with a competitor's —
  if it still works unchanged, it was never about this product.

## How the plugin applies this (free-path note)

The design engine starts every build from an on-brand, accessible, *rendered*
scaffold whose tokens come from the deterministic system generator — so the
baseline already avoids the default-everything tell. The build and visual-QA
skills then score output against the tells above, treating each unexplained
default as a finding to elaborate, not a thing to ship. This is taste encoded as
a rubric; it requires no external service.
