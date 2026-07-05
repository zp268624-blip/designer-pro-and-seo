# Share of Local Voice (SoLV) + geo-grid math (knowledge for `geogrid.py`)

Why this exists: a single map-pack rank ("you're #3 for *plumber*") hides the truth
that local ranking is **geographic** — you might be #1 standing outside your shop and
invisible three miles away. A **geo-grid** samples the rank at a lattice of points
around the business; **Share of Local Voice (SoLV)** collapses that grid into one
honest visibility number. This file is the math `scripts/seo/geogrid.py` implements.

The clean-room note that matters: live SERP ranks at each point are a **Tier-1
acquisition** step (a maps connector or manual checks). `geogrid.py` does **not**
fetch them — it does the *math* over ranks you supply, so it is fully offline,
deterministic, and golden-file testable. The only thing it ever fetches is an
optional address → lat/lng geocode, through the shared SSRF guard.

---

## Per-point visibility

Each grid point `i` carries the business's local rank `r_i` (1 = top) at that
location, within a scan **depth** `D` (default 20; ranks past `D`, or a `null`/`0`/
absent rank, mean "not found here"). Convert rank to a per-point visibility:

```
v_i = 1 / r_i      if the business is found (1 <= r_i <= D)
v_i = 0            if not found within depth D
```

Reciprocal rank is a standard, generic information-retrieval weighting: it is `1.0`
at rank 1 and decays as rank worsens (0.5 at #2, 0.33 at #3, 0.05 at #20), matching
the steep real-world drop in how much attention a lower local-pack slot earns. It is
*not* any vendor's proprietary curve — just `1/r`, chosen because it is defensible,
parameter-free, and reproducible.

## SoLV

With optional per-point weights `w_i` (default `1.0`; raise a point's weight to
reflect denser population or higher commercial value there):

```
SoLV%  =  100 *  ( Σ_i  w_i · v_i )  /  ( Σ_i  w_i )
```

So an unweighted grid is just `100 × mean(v_i)`. A grid where the business ranks #1
everywhere scores **100%**; a grid where it is never found scores **0%** — the
never-fabricate floor. SoLV is the headline: the share of the *available* local
visibility, across the whole service area, that the business actually captures.

Worked example (the golden fixture): ranks `[1, 4, not-found]`, depth 20.
`v = [1.0, 0.25, 0.0]`, unweighted mean `= 1.25 / 3 = 0.41666…` → **SoLV 41.67%**.

## Supporting metrics

SoLV alone can hide *shape*, so the script reports four companions:

| Metric | Definition | Reads as |
|---|---|---|
| **coverage%** | found points / total points | how much of the area ranks you at all |
| **top-3%** | points with `r_i ≤ 3` / total | where you make the actual 3-pack |
| **avg found rank** | mean `r_i` over found points only | how strong you are *where* you show |
| **best / worst rank** | min / max found `r_i` | the spread |

coverage vs SoLV is the diagnostic: high coverage + low SoLV = "everywhere but
deep" (you appear widely but rank poorly); low coverage + high avg-rank = "strong but
small" (dominant near the shop, invisible at the edges).

---

## Building the grid

When you don't yet have coordinates, `--build-grid` generates an `N × N` lattice
around a center (`--center "lat,lng"` offline, or `--geocode "address"` via the free
OpenStreetMap **Nominatim** service through the SSRF guard) spanning `± radius` km on
each axis:

```
step_km        = (2 · radius) / (N - 1)          # spacing between adjacent points
Δlat per km    = 1 / 111.32                       # mean km per degree of latitude
Δlng per km    = 1 / (111.32 · cos(lat0))         # longitude degrees shrink toward the poles
```

Each point is `lat0 + north_km·Δlat`, `lng0 + east_km·Δlng`, with `north_km`/`east_km`
ranging over `[-radius, +radius]`. Rows run north→south, columns west→east; the center
of an odd-sized grid is the exact center coordinate. This is the standard
equirectangular (flat-earth) approximation — accurate at the few-km scale of a service
area, with the `cos(lat0)` longitude correction so cells stay roughly square; the
pole singularity (`cos → 0`) is guarded. Every built point starts **un-ranked** — fill
in `rank` (from a connector or manual checks), then feed the grid back through SoLV
mode.

## What the script never does

It never fetches or synthesizes a SERP rank, never reports a SoLV number for a grid
with no usable points (zero total weight is a hard input error), and never claims
field accuracy the equirectangular model can't give at large radii — keep grids to a
service-area scale.
