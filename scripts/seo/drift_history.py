#!/usr/bin/env python3
"""drift_history.py -- list and trend the stored SEO baselines.

Reads the SQLite store the seo-drift engine writes (no network, no capture) and answers
two questions:

  * `--list` (default): what baselines are stored (id, url, label, captured_at), oldest
    first, optionally filtered by `--url` / `--label`.
  * `--trend`: how SEO drifted ACROSS the stored history -- run the `drift_severity` engine
    on each consecutive pair of snapshots and report, per transition, how many elements
    changed and the per-tier (critical/high/advisory) tally. This is the regression
    timeline: a deploy that quietly added noindex shows up as a critical-count spike.

Reuses drift_baseline.py's store helpers and drift_severity.py's rules. Standard library
only. Deterministic; offline.

Usage:
  drift_history.py --db baselines.db [--url https://site.com/] [--label prod]
  drift_history.py --db baselines.db --url https://site.com/ --trend
"""
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drift_baseline  # noqa: E402  (the shared SQLite store)
import drift_severity  # noqa: E402  (the change->severity engine, for --trend)


class _JsonArgParser(argparse.ArgumentParser):
    """argparse's own failures (a missing required arg, a bad type/choice) must honor the
    JSON-error contract too: emit {"error": ...} to stdout + a non-zero exit, never a bare
    usage dump to stderr. stdlib + ASCII."""
    def error(self, message):
        msg = str(message).encode("ascii", "replace").decode("ascii")
        print(json.dumps({"error": msg}))
        sys.exit(2)


def _history(rows):
    return {"action": "history", "count": len(rows),
            "baselines": [{"id": r["id"], "url": r["url"], "label": r["label"],
                           "captured_at": r["captured_at"]} for r in rows]}


def _trend(rows, word_noise):
    transitions = []
    for prev, cur in zip(rows, rows[1:]):
        res = drift_severity.evaluate(drift_baseline.row_snapshot(prev),
                                      drift_baseline.row_snapshot(cur),
                                      word_noise=word_noise)
        transitions.append({"from_id": prev["id"], "to_id": cur["id"],
                            "captured_at": cur["captured_at"], "changed": res["changed"],
                            "counts": res["counts"], "summary": res["summary"]})
    return {"action": "trend", "transitions": transitions, "count": len(transitions)}


def _human(result):
    if result["action"] == "history":
        lines = ["%d stored baseline(s):" % result["count"]]
        for b in result["baselines"]:
            lines.append("  #%-4d %-22s %-10s %s"
                         % (b["id"], b["url"] or "-", b["label"] or "-", b["captured_at"]))
    else:
        lines = ["%d transition(s):" % result["count"]]
        for t in result["transitions"]:
            lines.append("  #%d -> #%d (%s): %d changed (%dC/%dH/%dA)"
                         % (t["from_id"], t["to_id"], t["captured_at"], t["changed"],
                            t["counts"]["critical"], t["counts"]["high"], t["counts"]["advisory"]))
    return "\n".join(lines).encode("ascii", "replace").decode("ascii")


def main(argv=None):
    ap = _JsonArgParser(description="List or trend the stored SEO baselines.")
    ap.add_argument("--db", help="SQLite store path (default: <cwd>/.seo-drift/baselines.db; "
                                 "refuses to default inside the plugin root)")
    ap.add_argument("--url", help="filter to this URL")
    ap.add_argument("--label", help="filter to this label")
    ap.add_argument("--trend", action="store_true", help="trend drift across consecutive snapshots")
    ap.add_argument("--list", action="store_true", help="list stored baselines (the default)")
    ap.add_argument("--word-noise", type=float, default=drift_severity.WORD_NOISE)
    ap.add_argument("--human", action="store_true")
    args = ap.parse_args(argv)

    try:
        db_path = args.db or drift_baseline.default_db_path()
    except drift_baseline.PluginRootError as e:
        print(json.dumps({"error": str(e)}))
        return 1
    if not os.path.exists(db_path):
        print(json.dumps({"error": "no baseline store at %s -- run drift_baseline.py first" % db_path}))
        return 1
    try:
        conn = drift_baseline.connect(db_path, create=False)
    except (OSError, sqlite3.Error) as e:
        print(json.dumps({"error": "could not open store %s: %s" % (db_path, e)}))
        return 1
    try:
        rows = drift_baseline.list_baselines(conn, url=args.url, label=args.label)
    except sqlite3.Error as e:
        print(json.dumps({"error": "could not read store: %s" % e}))
        return 1
    finally:
        conn.close()

    result = _trend(rows, args.word_noise) if args.trend else _history(rows)
    print(_human(result) if args.human else json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
