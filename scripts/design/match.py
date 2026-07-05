#!/usr/bin/env python3
"""
match.py -- clean-room weighted ranker for the CSV-backed design engine.

ORIGINAL WORK (clean-room). Every weight, parameter, and formula below was authored
from first principles for THIS plugin's own data schema; no inspiration source was
opened. This module exists to replace `design_system._overlap` (raw token-overlap),
which counts every matched token equally and is therefore biased toward generic,
high-frequency tokens ("modern", "clean") that appear in many candidate rows.

THE RANKING MODEL (our own design)
----------------------------------
Given candidate rows, a query token set, and a list of (field, weight) pairs, a row's
score is:

    score(row) = ( SUM over query tokens qt of  contribution(qt, row) ) / lnorm(row)
                 + domain_adjust(row)

  1. Per-corpus IDF (the core fix for the generic-token bias).
     Each row is one "document" = the union of its weighted-field tokens. A token's
     document frequency df is the number of rows whose document contains it, over N
     rows. We weight each matched token by

         idf(t) = ln((N + 1) / (df + 1)) + 1.0          (smoothed; always >= 1.0)

     A token in every row (df = N) collapses to idf = 1.0 (it still counts, but barely);
     a token in one row earns the maximum idf. So "brutalist" (rare, specific) outweighs
     "modern" (common, generic) -- exactly the raw-overlap failure we are fixing.

  2. Field weights (our own ladder). A query token's contribution uses the HIGHEST-
     weighted field it appears in (one contribution per query token -- never summed
     across fields, so a token repeated across a row's fields cannot inflate the score):

         contribution(qt, row) = idf(matched_token) * max_field_weight(qt, row) * quality

     The per-picker weight ladders (identity/name field heaviest, mood/tags next, long
     prose lightest) live in design_system.py and are passed in as `field_weights`.

  3. difflib fuzzy pass (near-misses / typos). If a query token is not an EXACT member
     of a field's tokens, we take the best difflib ratio against that field's tokens; a
     ratio >= FUZZY_THRESHOLD counts as a (discounted) match with quality = ratio, using
     the matched corpus token's idf. This lets "minimalist" ~ "minimal" and
     "portfolio" ~ "portfolios" match without a synonym table.

  4. Length normalization (pivoted). So a verbose row does not win just by carrying more
     tokens, the summed contribution is divided by a pivoted-length factor:

         lnorm(row) = (1 - B) + B * (doc_len(row) / avg_doc_len)

     With B = LENGTH_NORM_B, a row of average length is unchanged (factor 1.0); a longer-
     than-average row is damped; a shorter, more focused row gets a mild lift. B = 0
     would disable normalization; B = 1 would fully divide by length. We use a mild B.

  5. Honesty (kept and sharpened from the old engine).
     * CONFIDENCE FLOOR -- best score < CONFIDENCE_FLOOR means no field carried a real,
       specific match; the dimension is reported as a weak match (matched = False), and
       design_system records it in "_fallbacks" exactly as before (closest row returned,
       never silently confident). The floor sits ABOVE any domain tie-break bonus
       (e.g. the palette AA bonus) so a bonus alone can never cross it.
     * TIE MARGIN -- if a different row's score is within TIE_MARGIN (relative) of the
       winner, the pick is flagged ambiguous so design_system can disclose that the top
       candidates were close (the deterministic winner is still returned).

  6. Determinism. Rows are scored in CSV order; the winner is updated only on a STRICTLY
     greater score, so exact ties resolve to the earliest (lowest-index) row -- identical
     to the old engine's tie-break and free of any dict-ordering dependence.

Standard library only (math, difflib, re). No randomness, no I/O.
"""
import difflib
import math
import re
from collections import namedtuple

# --- ORIGINAL ranker parameters (clean-room; tuned on THIS plugin's own corpus) -------
LENGTH_NORM_B = 0.25      # pivoted length-normalization strength (0 = off, 1 = full)
FUZZY_THRESHOLD = 0.82    # min difflib ratio for a near-miss to count as a match
CONFIDENCE_FLOOR = 1.5    # best score below this -> weak match (flagged, closest returned)
TIE_MARGIN = 0.05         # runner-up within this relative gap of the winner -> ambiguous

RankResult = namedtuple(
    "RankResult",
    ["row", "index", "matched", "ambiguous", "score", "runner_up", "scores"],
)


def tokens(s):
    """Lowercase alphanumeric token set. Mirrors design_system._tokens (kept local so
    this module has no dependency on its caller -- design_system imports match, not the
    reverse)."""
    return set(t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t)


def build_idf(field_token_sets, n_rows):
    """Per-corpus IDF over the row documents. `field_token_sets` is a list (one per row)
    of {field: token_set}; the row's document is the union of its field token sets.
    Returns {token: idf}. Smoothed so idf >= 1.0 (a token in every row still counts)."""
    df = {}
    for fts in field_token_sets:
        doc = set()
        for ts in fts.values():
            doc |= ts
        for t in doc:
            df[t] = df.get(t, 0) + 1
    idf = {}
    for t, d in df.items():
        idf[t] = math.log((n_rows + 1) / (d + 1)) + 1.0
    return idf


def _best_token_contribution(qt, field_tokensets, field_weights, idf):
    """Highest single-field contribution of one query token `qt` to one row. Exact field
    membership is preferred; otherwise a difflib near-miss (ratio >= FUZZY_THRESHOLD)
    counts, discounted by the ratio and scored with the matched corpus token's idf."""
    best = 0.0
    for col, weight in field_weights:
        ts = field_tokensets.get(col) or set()
        if not ts:
            continue
        if qt in ts:
            cand = weight * idf.get(qt, 1.0)
        else:
            # near-miss: best ratio against this field's tokens. Iterate in sorted order
            # and break ratio ties on the lexically-smallest token so the chosen idf
            # (and thus the result) is deterministic regardless of set hash ordering.
            mt, ratio = None, 0.0
            for cand_tok in sorted(ts):
                r = difflib.SequenceMatcher(None, qt, cand_tok).ratio()
                if r > ratio:
                    mt, ratio = cand_tok, r
            if mt is None or ratio < FUZZY_THRESHOLD:
                continue
            cand = weight * idf.get(mt, 1.0) * ratio
        if cand > best:
            best = cand
    return best


def rank(rows, query_tokens, field_weights, *, floor=CONFIDENCE_FLOOR,
         tie_margin=TIE_MARGIN, adjust=None):
    """Rank `rows` against `query_tokens`.

    field_weights : list of (column_name, weight); identity fields should weigh most.
    adjust        : optional callable(row, base_norm_score) -> score, for domain tie-break
                    bonuses/penalties (e.g. palette AA pass, style avoid_for). Applied
                    AFTER length normalization; keep any bonus smaller than `floor` so it
                    cannot by itself promote a no-match row above the confidence floor.

    Returns a RankResult. On an empty `rows`, returns an all-None/False result.
    The winner is the highest score, ties broken by CSV order (lowest index).
    """
    n = len(rows)
    if n == 0:
        return RankResult(None, -1, False, False, 0.0, None, [])

    # Precompute per-row field token sets and the per-corpus IDF + average doc length.
    cols = [c for c, _ in field_weights]
    field_token_sets = []
    doc_lens = []
    for r in rows:
        fts = {c: tokens(r.get(c)) for c in cols}
        field_token_sets.append(fts)
        doc = set()
        for ts in fts.values():
            doc |= ts
        doc_lens.append(len(doc))
    idf = build_idf(field_token_sets, n)
    avg_len = (sum(doc_lens) / n) or 1.0

    # Sort the query tokens so the float summation order is fixed run-to-run (set
    # iteration is hash-ordered; sorted summation keeps `base` bit-identical -> the
    # "same input, identical output / no dict-order or randomness" contract holds).
    q_sorted = sorted(query_tokens)
    scores = []
    for i, r in enumerate(rows):
        base = 0.0
        for qt in q_sorted:
            base += _best_token_contribution(qt, field_token_sets[i], field_weights, idf)
        denom = (1.0 - LENGTH_NORM_B) + LENGTH_NORM_B * ((doc_lens[i] / avg_len) if avg_len else 1.0)
        score = base / denom if denom else base
        if adjust is not None:
            score = adjust(r, score)
        scores.append(score)

    # Winner by strictly-greater update -> CSV-order tie-break (lowest index wins).
    best_i, best_s = 0, scores[0]
    for i in range(1, n):
        if scores[i] > best_s:
            best_i, best_s = i, scores[i]
    # Runner-up = highest score among the other rows (value-based).
    runner_up = None
    for i in range(n):
        if i == best_i:
            continue
        if runner_up is None or scores[i] > runner_up:
            runner_up = scores[i]

    matched = best_s >= floor
    ambiguous = bool(
        matched and runner_up is not None and best_s > 0
        and (best_s - runner_up) < tie_margin * best_s
    )
    return RankResult(rows[best_i], best_i, matched, ambiguous, best_s, runner_up, scores)
