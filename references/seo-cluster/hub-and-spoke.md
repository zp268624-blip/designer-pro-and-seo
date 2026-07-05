# Hub-and-spoke architecture + the internal-link matrix

How a cluster becomes a publishable content structure. Knowledge, not steps — the
generation is in `scripts/seo/serp_cluster.py`; this file is the reasoning the
output encodes.

## The shape

Each cluster ships as one **pillar (hub)** plus its **spokes**:

- **Pillar page** — broad, category-level, targets the head term (the most
  SERP-central keyword in the cluster). It is the page you want to rank for the
  competitive term; it links *down* to every spoke and earns most external links.
- **Spoke pages** — specific, long-tail, each answering one narrow query in depth.
  Every spoke links *up* to the pillar and *across* to a few sibling spokes.

This concentrates topical authority on the pillar (every spoke passes a signal up)
while letting each spoke rank for its own long-tail query — the opposite of a flat
pile of similar posts competing with each other.

## Intent decides the page type, not just the cluster

Classify every keyword's intent and let it shape the page:

| Intent | What the searcher wants | Page type for the pillar/spoke |
|---|---|---|
| **Informational** | learn / understand | guide, explainer, tutorial, FAQ |
| **Commercial** | compare before buying | "best", roundup, review, comparison |
| **Transactional** | buy / act now | product, pricing, service, booking |
| **Navigational** | reach a specific destination | brand/login/app page — usually *not* a content target |

A cluster's intent is its pillar's intent. Watch for **mixed-intent clusters**
(SERP overlap occasionally bridges an informational and a commercial query): when a
spoke's intent differs from the pillar's, it often wants its own page template, and
sometimes its own pillar — a signal to split. Navigational singletons (e.g. a brand
login) are reported but are rarely worth a content page; the skill flags them rather
than forcing them into a cluster.

## The internal-link matrix

The matrix is the concrete linking plan — one row per directed link, each with the
**anchor text** to use. The rules the generator encodes:

1. **Every *direct* spoke → pillar.** Anchor = the pillar keyword (the exact term you
   want the pillar to rank for). This is the load-bearing link. It exists for every
   spoke that genuinely co-ranks with the pillar (shares ≥ threshold URLs). The one
   honest exception: a member pulled into the cluster only through a single-linkage
   *chain* (it shares < threshold with the chosen pillar — see the chaining caveat in
   `serp-overlap-method.md`) is flagged `bridged` and links up to the member it actually
   co-ranks with, **not** the pillar — we never emit a hub-and-spoke pillar link below
   threshold.
2. **Pillar → every direct spoke.** Anchor = the spoke keyword, so the pillar acts as
   the table of contents and distributes crawl equity to each spoke it truly anchors.
3. **Spoke → 2–3 sibling spokes.** Anchor = the sibling keyword. Siblings are chosen
   by **shared-URL overlap** (the most topically-adjacent spokes first), so the
   cross-links connect genuinely related pages rather than arbitrary ones. Capping at
   ~3 keeps the link graph readable and avoids every page linking to every other.

### Anchor-text discipline

- Use the **target page's keyword** as the anchor, descriptive and natural — not
  "click here" / "read more" and not the same boilerplate anchor everywhere.
- Keep anchors varied across the cluster (pillar keyword up, spoke keywords down and
  across) so the profile reads natural, not over-optimized.
- The anchor is a *recommendation*: in prose, bend it to read naturally rather than
  pasting the exact string if it would be awkward.

## Handing off

Pillars and spokes are page briefs waiting to happen: pass each to
`seo-content-brief` to turn a cluster node into a per-page brief (word counts,
sections, the keyword it owns). The link matrix is the wiring those pages implement
once built. Feed the JSON to `templates/cluster-map.html` for an interactive
hub-and-spoke view to review the architecture before committing to it.
