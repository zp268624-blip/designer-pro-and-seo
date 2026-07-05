#!/usr/bin/env python3
"""
csv_to_report.py — Mechanical CSV summarizer for the csv-to-report skill.

Does the deterministic part of turning a CSV into a report: load, profile columns,
compute basic stats, optionally filter/group/select. The skill layer adds the
human part — column labels and business rules. Standard library only (no pandas).

Privacy (default-on, because this output may land in a transcript/log):
  - CREDENTIAL columns (password, token, ssn, api_key, ...) have their sample VALUES
    redacted. Pass --show-sensitive to override (your own data, your call).
  - CONTACT-PII columns (email, phone, mobile, fax, contact, address, ssn, dob, ...)
    are also redacted, AND any individual value that LOOKS like an email or a phone
    number is masked, in every column. Pass --show-pii to opt out of contact-PII
    redaction. Credentials stay redacted regardless of --show-pii.
Other column values are intentionally shown — summarizing them is the tool's job.

Contract (references/ENGINE-CONTRACTS.md): JSON to stdout by default; --human for
text; idempotent; never mutates the input.

Usage:
  python3 csv_to_report.py --in data.csv [--group-by COL] [--filter "COL=VAL"] \\
      [--select "A,B,C"] [--show-sensitive] [--show-pii] [--human]
"""
import argparse
import csv
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

SENSITIVE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|ssn|social.?security|"
    r"credit.?card|card.?number|cvv|auth|private[_-]?key|access[_-]?key)", re.I)

# Contact-PII column headers — redacted by default (opt out with --show-pii). "ssn" is in
# both sets (also a credential); a match in either set redacts the column by default.
CONTACT_PII = re.compile(
    r"(e[-_]?mail|phone|mobile|tel|fax|contact|address|ssn|dob|birth)", re.I)

# Value-level PII: an email-looking value, or a phone-looking value (a run of >= 7 digits
# with optional separators / leading +). Used to mask individual cells in ANY column.
_EMAIL_VAL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_VAL = re.compile(r"\+?\d[\d\s().\-]{5,}\d")


def _looks_pii(v):
    """True if a value looks like an email address or a phone number."""
    if not isinstance(v, str):
        return False
    if _EMAIL_VAL.search(v):
        return True
    m = _PHONE_VAL.search(v)
    return bool(m) and sum(ch.isdigit() for ch in m.group()) >= 7


REDACTED = "[redacted]"


def _redact_value(col, value, show_sensitive, show_pii):
    """DISPLAY-ONLY masking for a single emitted value belonging to column `col`. Returns
    (display_value, was_redacted); the REAL value is never touched here -- callers must have
    already filtered/grouped on the real value, and use this only on the EMITTED
    representation (the filter/applied echo, group-by keys, selected/human output).

    A credential column (SENSITIVE header) is masked unless --show-sensitive and is NEVER
    revealed by --show-pii. A contact-PII column (CONTACT_PII header) OR any PII-looking
    value (email/phone) is masked unless --show-pii."""
    if col and SENSITIVE.search(col):
        return (value, False) if show_sensitive else (REDACTED, True)
    if not show_pii:
        if col and CONTACT_PII.search(col):
            return REDACTED, True
        s = value if isinstance(value, str) else ("" if value is None else str(value))
        if _looks_pii(s):
            return REDACTED, True
    return value, False


# Only strip commas that look like thousands separators (1,234 / 1,234.56). A lone
# comma like "1,5" is left intact -> float() fails -> treated as non-numeric, rather
# than being silently misread as 15.
_THOUSANDS = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")


def _num(v):
    if not isinstance(v, str):
        try:
            return float(v)
        except (ValueError, TypeError):
            return None
    s = v.strip()
    if _THOUSANDS.match(s):
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def profile_column(name, values, show_sensitive, show_pii):
    non_empty = [v for v in values if v not in ("", None)]
    nums = [_num(v) for v in non_empty]
    numeric = [n for n in nums if n is not None]
    is_numeric = bool(non_empty) and len(numeric) >= math.ceil(0.8 * len(non_empty))
    info = {
        "column": name,
        "count": len(values),
        "non_empty": len(non_empty),
        "empty": len(values) - len(non_empty),
        "distinct": len(set(non_empty)),
    }
    # Column-level redaction by header name: credentials (unless --show-sensitive) and
    # contact-PII columns (unless --show-pii). Credentials are never revealed by --show-pii.
    is_cred = bool(SENSITIVE.search(name))
    is_contact = bool(CONTACT_PII.search(name))
    redact_col = (is_cred and not show_sensitive) or (is_contact and not show_pii)
    if is_numeric and not redact_col:
        info["type"] = "numeric"
        info["min"] = round(min(numeric), 4)
        info["max"] = round(max(numeric), 4)
        info["mean"] = round(sum(numeric) / len(numeric), 4)
    else:
        info["type"] = "categorical"
        top = Counter(non_empty).most_common(5)
        if redact_col:
            info["redacted"] = True
            info["top_values"] = [{"value": "[redacted]", "count": c} for _, c in top]
        else:
            # Value-level PII masking (default-on; opt out with --show-pii): any individual
            # email/phone-looking value is masked even in an otherwise non-sensitive column.
            tv, masked = [], False
            for v, c in top:
                if not show_pii and _looks_pii(v):
                    tv.append({"value": "[redacted]", "count": c})
                    masked = True
                else:
                    tv.append({"value": v, "count": c})
            if masked:
                info["redacted"] = True
            info["top_values"] = tv
    return info


def _load_rows(path):
    """Return (rows, fieldnames). fieldnames preserves duplicate headers; rows is
    None when the file cannot be read or decoded."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                return rows, (reader.fieldnames or [])
        except (UnicodeDecodeError, LookupError):
            continue
        except OSError:
            return None, None
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--group-by", default=None)
    ap.add_argument("--filter", dest="flt", default=None, help='COL=VALUE exact match')
    ap.add_argument("--select", default=None, help="comma-separated columns to keep")
    ap.add_argument("--show-sensitive", action="store_true",
                    help="do not redact values of credential-looking columns")
    ap.add_argument("--show-pii", action="store_true",
                    help="do not redact contact-PII columns or email/phone-looking values "
                         "(credentials stay redacted regardless)")
    ap.add_argument("--human", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.infile):
        print(json.dumps({"error": "file not found", "file": args.infile}))
        sys.exit(1)
    rows, fieldnames = _load_rows(args.infile)
    if rows is None:
        print(json.dumps({"error": "could not read CSV (tried utf-8/cp1252/latin-1)",
                          "file": args.infile}))
        sys.exit(1)
    if not rows:
        print(json.dumps({"error": "empty CSV (no data rows)", "file": args.infile}))
        sys.exit(1)

    headers = list(rows[0].keys())
    warnings = []
    dup_headers = [h for h, c in Counter(fieldnames).items() if c > 1]
    if dup_headers:
        warnings.append("duplicate column header(s) -- only the last occurrence's "
                        "values were kept (earlier ones dropped before profiling): "
                        + ", ".join(dup_headers))

    # filter
    applied = {}
    if args.flt:
        if "=" not in args.flt:
            warnings.append(f"--filter '{args.flt}' ignored (expected COL=VALUE)")
        else:
            col, val = (x.strip() for x in args.flt.split("=", 1))
            if col not in headers:
                warnings.append(f"--filter column '{col}' not found; filter skipped")
            else:
                # Filter on the REAL value; redact only the echoed representation so a
                # PII/secret filter value cannot leak through `applied`.
                rows = [r for r in rows if r.get(col, "") == val]
                disp_val, _ = _redact_value(col, val, args.show_sensitive, args.show_pii)
                applied["filter"] = {col: disp_val}

    # select
    if args.select:
        keep = [c.strip() for c in args.select.split(",")]
        unknown = [c for c in keep if c not in headers]
        if unknown:
            warnings.append(f"--select unknown columns ignored: {', '.join(unknown)}")
        keep = [c for c in keep if c in headers]
        if keep:
            headers = keep
            rows = [{h: r.get(h, "") for h in headers} for r in rows]

    report = {
        "file": args.infile,
        "row_count": len(rows),
        "column_count": len(headers),
        "applied": applied,
        "warnings": warnings,
        "columns": [profile_column(h, [r.get(h, "") for r in rows],
                                    args.show_sensitive, args.show_pii)
                    for h in headers],
    }

    if args.group_by:
        if args.group_by not in headers:
            warnings.append(f"--group-by column '{args.group_by}' not found; grouping skipped")
        else:
            # Group by the REAL key; redact only the emitted key so a PII/secret group
            # column cannot leak its values through the group-by output.
            groups = defaultdict(int)
            for r in rows:
                groups[r.get(args.group_by, "")] += 1
            report["group_by"] = {
                "column": args.group_by,
                "groups": [{"value": _redact_value(args.group_by, k,
                                                   args.show_sensitive, args.show_pii)[0],
                            "count": v}
                           for k, v in sorted(groups.items(), key=lambda x: -x[1])],
            }

    if args.human:
        print(f"# Report: {args.infile}")
        print(f"\n{report['row_count']} rows x {report['column_count']} columns")
        if applied:
            print(f"Applied: {applied}")
        for w in warnings:
            print(f"! {w}")
        print("\n## Columns")
        for c in report["columns"]:
            line = f"- **{c['column']}** ({c['type']}): {c['non_empty']}/{c['count']} filled, {c['distinct']} distinct"
            if c["type"] == "numeric":
                line += f" — min {c['min']}, mean {c['mean']}, max {c['max']}"
            else:
                tv = ", ".join(f"{t['value']}({t['count']})" for t in c["top_values"])
                line += (f" — top: {tv}" + (" [redacted]" if c.get("redacted") else ""))
            print(line)
        if "group_by" in report:
            print(f"\n## Grouped by {report['group_by']['column']}")
            for g in report["group_by"]["groups"]:
                print(f"- {g['value'] or '(blank)'}: {g['count']}")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    main()
