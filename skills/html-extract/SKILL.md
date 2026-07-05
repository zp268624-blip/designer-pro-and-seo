---
name: html-extract
description: Capture a reference site's section structure, color and font tokens, and recurring component patterns into a clean, annotated inspiration file for rebuilding from scratch — never verbatim reuse. Renders with Playwright when connected; otherwise uses a static fetch (lower fidelity on JS-heavy sites). Trigger when the user says "html extract", "scrape this site for reference", "pull the structure from this site", "pull components from this page", "capture this site's layout for rebuild", or "use this site as a build reference".
---

# html-extract

**Family:** build-and-qa
**Status:** Stable

## Purpose

Given a reference URL, extract the rendered structure, design tokens (fonts,
colors), and component patterns into a clean, annotated reference that downstream
skills (`design-build`, `parallel-build`, `blast-prompt`) use as *inspiration*.
This is pattern capture for reimplementation — **not** copy/paste of someone's
deployed code.

## Triggers

- "html extract" / "scrape this site for reference"
- "pull the structure from this site" / "pull components from this page"
- "capture this site's layout for rebuild" / "use this site as a build reference"

## Inputs

- Reference URL
- What to extract: full page | hero | nav | pricing | components-only
- Output location (defaults to the user's project workspace, e.g. `./inspiration/`)

## Steps

1. **Fetch the page** — static fetch (WebFetch / `curl`) for the free path; if it's
   JS-rendered and Playwright is available, render first. Say which path ran.
2. **Extract**: the HTML structure (section outline), the dominant color palette and
   font families, and the recurring component patterns (hero, nav, pricing,
   testimonials, footer).
3. **Clean**: strip analytics, ads, third-party scripts, and deploy-only IDs/classes
   — keep structure and tokens, drop the cruft.
4. **Annotate**: label each section with what it is and *why* it's worth borrowing
   (the pattern, not the pixels).
5. **Save** to the user's project workspace (e.g. `./inspiration/<slug>.md`) with the
   source URL + capture date in frontmatter, and a banner: **inspiration only — never
   deploy verbatim**.

## Outputs

- Annotated inspiration file (structure + token list + component catalog)
- Source attribution (URL + date) in the file's frontmatter

## Dependencies

- Playwright (optional — adds rendered capture of JS-heavy sites; free path: static fetch via WebFetch/curl)

## Notes

The legal/ethical line is firm: capture *patterns* to rebuild with the user's own
brand and content; the output is context for other skills, never deployable code.
Respect the source site's Terms of Service (see `PRIVACY.md`).

Related skills: to turn a captured reference into a coherent brand system (color,
type, motion, spacing language), hand the extracted tokens to `design-system-gen`.
