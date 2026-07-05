# NAP normalization rules (knowledge for `nap_check.py`)

Why this exists: **NAP (Name / Address / Phone) inconsistency is a silent
local-ranking killer.** When the citation on one directory says a different phone or
a differently-spelled address than the website and the Google Business Profile,
Google's confidence that all those listings describe *one* entity drops — and so does
the map-pack ranking. The hard part is telling a *real* divergence (a wrong phone
number) from a *cosmetic* one ("St" vs "Street"). Normalization is what draws that
line. These are the rules `scripts/seo/nap_check.py` applies before it diffs.

The principle: **normalize aggressively, then compare exactly.** Two values are
"consistent" only when their *normalized* forms are identical. Findings are raised on
normalized divergence — never on formatting alone.

---

## Phone

1. Reduce to digits only (drop spaces, `()`, `-`, `.`, `+`).
2. If the result is 11 digits and starts with `1` (US/Canada country code), drop the
   leading `1`. So `+1 (801) 555-0199`, `801.555.0199`, and `8015550199` all
   normalize to `8015550199`.
3. Compare the digit strings exactly. A different digit string = a real divergence.

Rationale: the country-code drop is the one transformation that is always safe for
North-American numbers; beyond that, *any* digit difference matters (a transposed or
forwarded number sends leads to the wrong place), so no further "smart" matching is
applied. Extensions, when present, are part of the digit string and a difference is
surfaced rather than guessed away.

## Address

1. Lowercase; replace `&` with `and`.
2. Treat `#` as the unit designator — expand it to `suite` (so `#200` == `Suite 200`).
3. Strip remaining punctuation to spaces.
4. Map each token through a fixed abbreviation table, then collapse whitespace.

The abbreviation table (USPS-style common forms, authored from first principles):

| Class | Maps to canonical |
|---|---|
| Street types | `st`/`str`→street, `ave`/`av`→avenue, `blvd`→boulevard, `rd`→road, `dr`→drive, `ln`→lane, `ct`→court, `pl`→place, `sq`→square, `ter`→terrace, `hwy`→highway, `pkwy`→parkway, `cir`→circle, `trl`→trail, `rte`→route, `expy`→expressway |
| Directionals | `n`→north, `s`→south, `e`→east, `w`→west, `ne`/`nw`/`se`/`sw`→spelled out |
| Unit designators | `ste`/`#`→suite, `apt`→apartment, `bldg`→building, `fl`→floor, `rm`→room, `dept`→department, `unit`→unit, `no`→number |

So `123 Main St, Ste 200`, `123 Main Street Suite 200`, and `123 Main St #200` all
normalize to `123 main street suite 200` — **consistent**. A different street number
or street name does not normalize away and is surfaced.

Note on scope: the table covers the high-frequency abbreviations that cause false
mismatches; it is deliberately conservative. It does not transliterate, geocode, or
reorder tokens — those would risk masking a real difference. State/ZIP differences,
when included in the address string, are preserved and compared.

## Name

1. Lowercase; replace `&` with `and`.
2. Strip punctuation to spaces; collapse whitespace.

So `Acme Plumbing, LLC` and `Acme Plumbing LLC` normalize equal, but `Acme Plumbing`
vs `Acme Plumbing LLC` differ (a legal-suffix presence/absence is a *real* citation
mismatch worth flagging, not cosmetic). The name fold is intentionally lighter than
the address map: business names carry meaning in their exact words, so only
punctuation/`&`/case are normalized.

---

## Severity model

A divergence's severity reflects how much it hurts the entity signal:

| Field | Severity | Why |
|---|---|---|
| **Phone** | HIGH | A wrong number splits leads and directly contradicts the entity's contact identity. |
| **Address** | HIGH | The address is the core NAP signal Google clusters listings on; a mismatch fractures it. |
| **Name** | MEDIUM | Name variants reduce citation-match confidence but rarely break the cluster outright. |

Findings sort HIGH-before-MEDIUM, then by source. A run is `consistent: true` only
when **all three** fields agree across every listing after normalization.

## Canonical selection

The listing every other is compared against is chosen, in order: an explicit
`--canonical <source>`; else the listing flagged `"primary": true`; else the first
listing. Pick the source you trust most as the truth (usually the website or the
verified GBP), then fix every divergent citation to match it exactly.

## What the script never does

It never invents a "correct" value, never fetches a phone/address from anywhere, and
never down-ranks a difference to silence it. The optional `--verify-urls` step only
*checks* whether the normalized phone/name actually appears on a listing's page
(through the shared SSRF guard) — it is corroboration, not a data source.
