# WCAG Contrast — Ratios & Relative Luminance

Shared knowledge for every skill that judges color legibility
(`design-accessibility`, `design-system-gen`, `design-build`,
`design-visual-qa`, `qa-gate`). The contrast *math* is implemented in
`scripts/design/gen_palettes.py`; this file states the public thresholds and the
formula so they are recorded once and cited everywhere. Knowledge, not steps.

## The minimum contrast ratios (WCAG 2.x)

Contrast is expressed as a ratio between the relative luminance of the lighter
and darker of two colors, ranging from **1:1** (identical) to **21:1**
(black on white).

| Content | Level AA (minimum) | Level AAA (enhanced) |
|---|---|---|
| **Normal text** | **4.5 : 1** | 7 : 1 |
| **Large text** (>= 18.66 px bold, or >= 24 px regular) | **3 : 1** | 4.5 : 1 |
| **UI components & graphics** (borders, icons, form-field edges, focus rings, meaningful chart strokes) | **3 : 1** | — |

"Large text" is the size threshold above which the eye tolerates lower contrast,
so the bar drops from 4.5:1 to 3:1. Non-text essentials — the visual boundary of
an input, an icon that carries meaning, a focus indicator — must clear **3:1**
against what sits next to them.

### What is exempt

- **Disabled / inactive** controls have no contrast minimum.
- **Pure decoration** that conveys no information is exempt.
- **Logotypes** (text that is part of a brand logo) are exempt.
- Incidental text inside an image where the text is not the point is exempt.

## Computing the contrast ratio

```
ratio = (L_lighter + 0.05) / (L_darker + 0.05)
```

where `L_lighter` and `L_darker` are the relative luminances of the two colors
and the `0.05` flare term keeps the ratio finite for pure black.

## Relative luminance (the public sRGB formula)

For a color whose 8-bit channels are `R, G, B` in `0..255`:

1. **Normalize** each channel to `0..1`:  `c = channel / 255`.
2. **Linearize** (undo the sRGB gamma transfer) for each of `R, G, B`:

   ```
   c_lin = c / 12.92                       if c <= 0.03928
   c_lin = ((c + 0.055) / 1.055) ** 2.4    otherwise
   ```

3. **Weight and sum** the linear channels by human luminance sensitivity:

   ```
   L = 0.2126 * R_lin + 0.7152 * G_lin + 0.0722 * B_lin
   ```

The green coefficient dominates because the eye is most sensitive to green; blue
contributes least. `L` ranges `0` (black) to `1` (white).

## How the plugin uses this (free-path note)

The design engine computes luminance and contrast deterministically — no network,
no paid service — and uses it to:

- pick an accessible `on_primary` / `on_surface` text color for every generated
  palette (guaranteeing >= 4.5:1 for body text),
- grade series colors in generated charts for distinguishability,
- flag any token pair in the static accessibility check that falls below its
  threshold.

Because the formula is fixed and integer-seeded, the same colors always yield the
same ratio — the contrast guarantees are reproducible, not heuristic.
