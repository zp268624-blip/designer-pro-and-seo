# Golden example — seo-local-unified (Tier-2: `nap_check.py` + `geogrid.py`)

Proves the **free, key-absent Tier-2** path of `seo-local-unified` delivers both
halves of the `local-maps` capability with no network and no API key — NAP
consistency and Share-of-Local-Voice geo-grid math — entirely offline and
reproducible. These are the built-in product; a maps connector (Tier 1) only adds
*live* rank acquisition on top.

## Inputs

- `sample-listings.json` — four listings for one business. `search-directory` and
  `social-directory` differ from the canonical `website` only by formatting
  ("Street"/"Ste"/"#"/"Suite", `(801) 555-0199` vs `+1 801 555 0199`);
  `review-directory` carries a **different phone number** (`…0142`), so the checker
  has a real HIGH finding to raise plus formatting noise it must normalize away.
- `sample-grid.json` — a 3-point geo-grid with ranks `1`, `4`, and not-found, so the
  SoLV math has a top result, a mid result, and a miss.

## Commands

NAP consistency (offline):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/nap_check.py" \
  --listings references/examples/seo-local-unified/sample-listings.json --no-network --human
```

Share of Local Voice (offline):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seo/geogrid.py" \
  --grid references/examples/seo-local-unified/sample-grid.json --no-network --human
```

(From the repo root during development, drop `${CLAUDE_PLUGIN_ROOT}/` and run the
bare `scripts/...` path — that is what the gate and `tests/test_local_maps.py` do.)

## Expected free deliverable (Tier 2)

`nap_check.py` reports **INCONSISTENT**, with exactly one `[HIGH] review-directory
phone` finding — the divergent number — while the name and address fields come back
*consistent* because `St`/`Street`/`Ste`/`#`/`Suite` and the three phone formats all
normalize to one value. The fix is explicit: make every citation's phone match the
canonical website number.

`geogrid.py` reports the grid's visibility:

```
SoLV          : 41.67%
coverage      : 66.67% (2/3 points found)
top-3 share   : 33.33%
avg found rank: 2.5   best: 1   worst: 4
```

i.e. visibility `[1/1, 1/4, 0] → mean 0.4167 → 41.67%`. No rank is fabricated — the
not-found point scores 0. `needs_tier1` (live per-point SERP ranks, GBP review
ratings) is satisfied only by connecting a DataForSEO / Google Places maps MCP
(Tier 1); the NAP matrix and the SoLV math above are complete on their own — the
product.
