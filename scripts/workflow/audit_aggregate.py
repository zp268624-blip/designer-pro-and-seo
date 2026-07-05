#!/usr/bin/env python3
"""
audit_aggregate.py -- roll per-specialist SEO scores up into one overall health
score, RE-NORMALIZED over the specialists that actually ran.

The seo-audit socket dispatches a variable set of specialists (some are always-on,
some are conditional on business type / connected tooling). A fixed-denominator
average would silently penalise a site whenever a specialist was *skipped* -- e.g.
not running seo-ecommerce on a non-store would drag the score toward zero. This
script instead re-normalizes the weights over only the specialists present, so a
skipped specialist neither helps nor hurts; the score reflects exactly the work
that was done, and the breakdown shows which specialists contributed.

Each specialist has a default weight (our own table). A specialist not in the table
gets DEFAULT_WEIGHT. The overall score is the weight-normalized average of the
present specialists' scores:
    overall = sum(weight_i * score_i) / sum(weight_i)   over present specialists

Input: a JSON object mapping specialist -> score, via --scores '<json>' or
--file PATH. A score may be a bare number (0-100) or an object {"score": N, ...}
(extra keys like "findings" are carried through to the breakdown).

Output: JSON to stdout by default; --human prints an ASCII summary. On bad input
(unparseable JSON, empty map, out-of-range / non-numeric score) it prints a JSON
error object and exits non-zero -- never a raw traceback. Stdlib only; deterministic.

Usage:
  py audit_aggregate.py --scores '{"seo-technical":80,"seo-page":90}'
  py audit_aggregate.py --file scores.json --human
"""
import argparse
import json
import sys


# Our own per-specialist weight table (not derived from any third party). Higher
# weight = larger contribution to the health score when that specialist is present.
DEFAULT_WEIGHTS = {
    "seo-technical": 20,
    "seo-page": 20,
    "seo-content": 15,
    "seo-schema": 10,
    "seo-sitemap": 10,
    "seo-image-audit": 10,
    "seo-local-unified": 10,
    "seo-ecommerce": 10,
    "seo-google": 10,
    "seo-backlinks": 10,
    "seo-geo": 5,
}
DEFAULT_WEIGHT = 10


def _grade(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _coerce_score(name, value):
    """Pull a numeric 0-100 score out of a bare number or {"score": N}.
    Returns (score_float, findings_count). Raises ValueError on bad shape."""
    findings = 0
    if isinstance(value, dict):
        if "score" not in value:
            raise ValueError("specialist %r object has no 'score' key" % name)
        raw = value.get("score")
        f = value.get("findings")
        if isinstance(f, list):
            findings = len(f)
        elif isinstance(f, int):
            findings = f
    else:
        raw = value
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("specialist %r score must be a number, got %r"
                         % (name, raw))
    score = float(raw)
    if not (0.0 <= score <= 100.0):
        raise ValueError("specialist %r score %s out of range 0-100" % (name, score))
    return score, findings


def aggregate(scores):
    """Return the aggregate dict. `scores` is a specialist -> score/object map.
    Raises ValueError on bad input. Deterministic."""
    if not isinstance(scores, dict):
        raise ValueError("scores must be a JSON object of specialist -> score")
    if not scores:
        raise ValueError("no specialist scores provided")

    present = []
    for name in sorted(scores):
        score, findings = _coerce_score(name, scores[name])
        weight = DEFAULT_WEIGHTS.get(name, DEFAULT_WEIGHT)
        present.append({"specialist": name, "score": score,
                        "weight": weight, "findings": findings})

    total_weight = sum(p["weight"] for p in present)
    breakdown = []
    weighted_sum = 0.0
    for p in present:
        nw = p["weight"] / total_weight if total_weight else 0.0
        contribution = nw * p["score"]
        weighted_sum += contribution
        breakdown.append({
            "specialist": p["specialist"],
            "score": round(p["score"], 2),
            "weight": p["weight"],
            "normalized_weight": round(nw, 6),
            "contribution": round(contribution, 4),
            "findings": p["findings"],
        })

    overall = round(weighted_sum, 2)
    return {
        "overall_score": overall,
        "grade": _grade(overall),
        "specialists_present": [p["specialist"] for p in present],
        "specialists_count": len(present),
        "total_weight": total_weight,
        "breakdown": breakdown,
        "note": "weights re-normalized over the %d specialist(s) that ran; "
                "skipped specialists do not affect the score" % len(present),
    }


def _load_scores(args):
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            return json.load(fh)
    if args.scores is not None:
        return json.loads(args.scores)
    raise ValueError("provide --scores '<json>' or --file PATH")


def _format_human(result):
    lines = [
        "Overall health: %s (%s)  -- %d specialist(s)"
        % (result["overall_score"], result["grade"], result["specialists_count"]),
        "  breakdown (specialist: score x normalized-weight):",
    ]
    for b in result["breakdown"]:
        lines.append("    %-20s %6.2f x %.3f = %6.2f"
                     % (b["specialist"], b["score"], b["normalized_weight"],
                        b["contribution"]))
    text = "\n".join(lines)
    return text.encode("ascii", "replace").decode("ascii")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Aggregate per-specialist scores into a re-normalized health score.")
    ap.add_argument("--scores", help="specialist -> score map as a JSON string")
    ap.add_argument("--file", help="path to a JSON file of specialist scores")
    ap.add_argument("--human", action="store_true", help="ASCII summary")
    args = ap.parse_args(argv)

    try:
        raw = _load_scores(args)
    except FileNotFoundError:
        print(json.dumps({"error": "scores file not found: %s" % args.file}))
        return 1
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": "invalid JSON scores: %s" % exc}))
        return 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    try:
        result = aggregate(raw)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    if args.human:
        print(_format_human(result))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
