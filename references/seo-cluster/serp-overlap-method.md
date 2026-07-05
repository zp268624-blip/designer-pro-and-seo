# SERP-overlap clustering — the method

Why this skill clusters keywords by **shared search results** instead of by how
similar the words look. Knowledge, not steps — the procedure lives in the SKILL body
and in `scripts/seo/serp_cluster.py`.

## The core claim

Two keywords belong on the **same page** when Google already returns the **same
pages** for both. If `best running shoes` and `running shoe reviews` share most of
their top-10 results, Google has decided they satisfy one intent; trying to rank a
separate page for each splits your authority and triggers keyword cannibalization.
If they share *none*, they are different intents no matter how similar the wording —
one page cannot win both.

So the similarity that matters is **result overlap**, observed from live SERPs, not
lexical or embedding distance. This is the one signal that is *Google's own verdict*
rather than a proxy for it.

## Why not text / embedding similarity

- **Lexical overlap** treats `apple pie recipe` and `apple stock price` as close
  (shared token "apple") and `cheap flights` / `budget airfare` as far. Both wrong.
- **Embeddings** cluster by topical relatedness, which is *broader* than "same
  page." They happily merge `how to brew coffee` with `best coffee maker` —
  different intents (informational vs commercial) that need different pages and
  different templates. Embedding clusters look tidy but Google does not recognize
  them, so they do not predict whether one URL can rank for the group.
- **SERP overlap** sidesteps both: it reads the answer key. Its cost is that it
  needs real SERP data per keyword (the acquisition step), which is why this plugin
  separates acquisition (a Claude/WebSearch or DataForSEO/Semrush step) from the
  deterministic clustering this script performs.

## The overlap metric

For each keyword, take its **top-N** ranked URLs (default N=10). Normalize each URL
to a comparable page key — lowercased host with `www.` stripped, path without a
trailing slash, and scheme / query / fragment dropped — so `http://www.site.com/a`,
`https://site.com/a`, and `site.com/a/` are one page.

The pairwise overlap of keywords *i* and *j* is the **count of shared normalized
URLs** in their top-N:

```
overlap(i, j) = | top_N(i)  ∩  top_N(j) |
```

A simple shared-count is used (not a normalized ratio) because the decision is a
threshold on absolute co-ranking pages, which is how practitioners reason ("share 3+
of the top 10 → same topic"). The ratio is available for reporting but the cluster
edge is the count.

## Threshold → single-linkage components

An **edge** connects two keywords when `overlap(i, j) >= threshold` (default 3 of
the top 10). Clusters are the **connected components** of that edge graph
(single-linkage): a keyword joins a cluster if it strongly overlaps *any* member.

- **Choosing the threshold.** Higher (4–5) → tighter, more clusters, higher
  precision, more singletons. Lower (2) → broader, fewer clusters, risk of merging
  near-topics. 3 of 10 is a balanced default; expose it so the caller can tune to
  the corpus and the SERP depth they supplied.
- **The chaining caveat (state it honestly).** Single-linkage can chain A–B–C into
  one cluster even when A and C barely overlap, if B bridges them. This is the known
  trade-off of the simple, deterministic method. Mitigations: raise the threshold,
  supply deeper SERPs (more top-N), or split a visibly over-merged cluster by hand.
  The pillar-centrality report (below) surfaces a weakly-attached member so you can
  spot a bridge. **What the generator does about it:** a member that ends up sharing
  fewer than `threshold` URLs with the *chosen* pillar is flagged `bridged: true` in
  the output and is linked up to the member it actually co-ranks with (its bridge),
  never to the pillar — so the emitted hub-and-spoke matrix never claims a pillar link
  below threshold. Bridged members are your cue to consider splitting the cluster.

## Picking the pillar (hub)

Within a cluster the **pillar** is the most SERP-central keyword: the one whose
summed overlap with its siblings is highest — it co-ranks with the most of them, so
it is the broadest umbrella the others specialize under. Ties break toward the
*headier* term (fewer words, then fewer characters, then alphabetical) so the pillar
reads as the category page and the spokes as its long-tail support. The choice is
deterministic — the same blob always yields the same pillar.

## Determinism + honesty contract

- Same blob + same flags → byte-identical output (keywords processed in sorted
  order; components and members returned sorted; stable tie-breaks).
- The script **never invents** keyword volume, CPC, or difficulty. Those are a
  Tier-1 (DataForSEO / Semrush) deepener and are emitted as a `needs_tier1` list —
  never a synthesized number. The clustering + architecture is complete without
  them; they only add prioritization data.
