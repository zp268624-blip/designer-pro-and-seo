#!/usr/bin/env python3
"""
a11y_static.py -- structural WCAG accessibility checker (stdlib, offline, deterministic).

Parses an HTML file or string with the standard-library `html.parser` and reports the
STRUCTURAL accessibility problems that can be judged from source alone -- the free Tier-2
path behind `design-accessibility` and `qa-gate` (a full computed-contrast / keyboard /
reduced-motion scan still needs Playwright + axe-core; this is the honest lower-fidelity
subset). Nothing is fetched; no key; same input -> byte-identical severity-ranked JSON.

Checks (each maps to a WCAG 2.2 success criterion):
  * img-missing-alt        (1.1.1)  <img> with no alt attribute (alt="" is decorative-OK)
  * heading-no-h1 / -skip  (1.3.1 / 2.4.6) headings present but no <h1>; a jumped level
  * heading-multiple-h1    (1.3.1)  more than one <h1>
  * control-no-label       (4.1.2 / 3.3.2) a form control with no accessible name
  * html-no-lang           (3.1.1)  <html> missing (or empty) lang
  * no-viewport-meta       (best-practice / mobile) no responsive viewport meta
  * viewport-zoom-blocked  (1.4.4 / 1.4.10) viewport disables pinch-zoom
  * no-main-landmark       (1.3.1)  no <main> / role="main" region
  * no-skip-link           (2.4.1)  no in-page "skip to content" anchor
  * contrast-below-min     (1.4.3 / 1.4.11) a design-token color pair below its ratio
                                     (only when --tokens is supplied)

The token-contrast cross-check REUSES the engine's own WCAG math -- `gen_palettes`'s
`relative_luminance` / `contrast_ratio` -- and the public thresholds recorded in
`references/shared/wcag-contrast-rules.md` (4.5:1 body text, 3:1 UI / large text). The
token pairs checked are DERIVED from the color slots this plugin's engine emits
(`tokens_emit.py` / `gen_palettes.py`: text, bg, surface, primary, on_primary, accent),
not from any external schema.

Usage:
  python3 a11y_static.py --file page.html
  python3 a11y_static.py --html '<html>...</html>' --human
  python3 a11y_static.py --file page.html --tokens tokens.json    # add contrast cross-check

JSON to stdout by default; --human prints an ASCII summary. Bad input (missing file,
no HTML, unparseable --tokens, argparse failure) -> JSON {"error": ...} + non-zero exit.
"""
import argparse
import json
import os
import sys
from html.parser import HTMLParser

# Reuse the engine's own WCAG luminance/contrast math (same-dir sibling) rather than
# re-implementing it -- one source of truth for the contrast formula.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_palettes import relative_luminance, contrast_ratio  # noqa: E402

# WCAG 2.x minimum ratios (references/shared/wcag-contrast-rules.md).
BODY_MIN = 4.5   # normal text
UI_MIN = 3.0     # large text / UI components & graphics

SEVERITY_ORDER = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}

# Form controls that carry no visible label requirement here: hidden has no UI; the
# button family names itself from its value/content.
_EXEMPT_INPUT_TYPES = {"hidden", "submit", "reset", "button", "image"}
_CONTROL_TAGS = {"input", "select", "textarea"}
_LANDMARK_TAGS = {"main", "nav", "header", "footer", "aside", "form", "section"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_MAIN_ISH_HREF = {"main", "content", "maincontent", "main-content", "skip", "skip-link"}
# Void elements carry no text content and (in HTML) have no end tag, so they never open a
# text-collection context -- an id on one records empty text.
_VOID_TAGS = {"input", "img", "meta", "br", "hr", "area", "base", "col", "embed",
              "link", "param", "source", "track", "wbr"}


class _Collector(HTMLParser):
    """Single pass over the document, collecting only the structural facts the checks
    need. Fully deterministic (document order preserved).

    Accessible-name evidence is collected as TEXT, not mere presence: a <label> (whether
    it wraps a control or points at one via `for`) and any element carrying an `id` (so an
    `aria-labelledby` target can be resolved) accumulate their visible text. That is what
    lets the label checks reject an EMPTY <label>/labelledby target as no accessible name."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.saw_html = False
        self.html_lang = None
        self.viewport = None            # content string of the viewport meta, or None
        self.headings = []              # ordered list of int levels
        self.h1_count = 0
        self.images = []                # list of {"has_alt": bool, "src": str}
        self.controls = []              # list of {"tag","type","attrs","wrap_label"}
        self.ids = set()                # every element id in the doc
        self.label_for_text = {}        # <label for="X"> target -> accumulated label text
        self.id_text = {}               # element id -> accumulated text content
        self.landmarks = set()          # semantic tags + "role:<value>" markers seen
        self.anchors = []               # list of {"href","text"}
        self._label_stack = []          # open <label> contexts: {"for","parts"}
        self._id_stack = []             # open non-void id'd elements: {"id","tag","parts"}
        self._cur_anchor = None         # {"href","text"} while inside an <a>

    def _push_id(self, tag, a):
        """Begin (or, for a void element, immediately record as empty) text collection for
        an element carrying an id, so an aria-labelledby reference resolves to real text."""
        eid = a.get("id")
        if not eid:
            return
        if tag in _VOID_TAGS:
            self.id_text.setdefault(eid, "")     # void: no text content, no end tag
        else:
            self._id_stack.append({"id": eid, "tag": tag, "parts": []})

    def _pop_id(self, tag):
        """Finalize the nearest open id'd element of this tag (plus any unclosed elements
        nested above it), recording each id's accumulated text content."""
        for i in range(len(self._id_stack) - 1, -1, -1):
            if self._id_stack[i]["tag"] == tag:
                for e in self._id_stack[i:]:
                    self.id_text[e["id"]] = self.id_text.get(e["id"], "") + "".join(e["parts"])
                del self._id_stack[i:]
                return

    def _close_label(self):
        if self._label_stack:
            e = self._label_stack.pop()
            if e["for"]:
                self.label_for_text[e["for"]] = self.label_for_text.get(e["for"], "") + "".join(e["parts"])

    def handle_starttag(self, tag, attrs):
        a = {}
        for k, v in attrs:
            a[k.lower()] = v if v is not None else ""
        if "id" in a and a["id"]:
            self.ids.add(a["id"])
        if "role" in a and a["role"]:
            self.landmarks.add("role:" + a["role"].strip().lower())
        if tag in _LANDMARK_TAGS:
            self.landmarks.add(tag)
        self._push_id(tag, a)

        if tag == "html":
            self.saw_html = True
            self.html_lang = a.get("lang")
        elif tag == "meta":
            if a.get("name", "").strip().lower() == "viewport":
                self.viewport = a.get("content", "")
        elif tag in _HEADING_TAGS:
            self.headings.append(int(tag[1]))
            if tag == "h1":
                self.h1_count += 1
        elif tag == "img":
            self.images.append({"has_alt": "alt" in a, "src": a.get("src", "")})
        elif tag == "label":
            self._label_stack.append({"for": a.get("for") or None, "parts": []})
        elif tag in _CONTROL_TAGS:
            self.controls.append({
                "tag": tag,
                "type": (a.get("type", "") or "").strip().lower(),
                "attrs": a,
                # innermost open <label>, if any -- resolved to its TEXT at analyze time
                "wrap_label": self._label_stack[-1] if self._label_stack else None,
            })
        elif tag == "a":
            self._cur_anchor = {"href": a.get("href", ""), "text": ""}

    def handle_startendtag(self, tag, attrs):
        # Void / self-closed elements (<img/>, <input/>, <label/>) still record their facts.
        self.handle_starttag(tag, attrs)
        if tag == "label":
            self._close_label()
        elif tag == "a":
            if self._cur_anchor is not None:
                self.anchors.append(self._cur_anchor)
                self._cur_anchor = None
        if tag not in _VOID_TAGS:
            self._pop_id(tag)

    def handle_endtag(self, tag):
        if tag == "label":
            self._close_label()
        elif tag == "a" and self._cur_anchor is not None:
            self.anchors.append(self._cur_anchor)
            self._cur_anchor = None
        if tag not in _VOID_TAGS:
            self._pop_id(tag)

    def handle_data(self, data):
        if self._cur_anchor is not None:
            self._cur_anchor["text"] += data
        for e in self._label_stack:          # accumulate into every open <label>...
            e["parts"].append(data)
        for e in self._id_stack:             # ...and every open id'd element
            e["parts"].append(data)


def _control_has_name(c, label_for_text, id_text):
    """A control has an accessible name ONLY when that name is NON-EMPTY: a wrapping
    <label> whose text is non-empty, a <label for> pointing at its id AND carrying
    non-empty text, a non-empty aria-label, an aria-labelledby whose referenced id(s)
    resolve to non-empty text, or a non-empty title. An EMPTY / whitespace-only <label>
    (whether wrapping or `for`-linked) or an empty aria-labelledby target is NOT an
    accessible name -- the control is still unlabeled. (A placeholder is never a name.)"""
    wl = c.get("wrap_label")
    if wl is not None and "".join(wl["parts"]).strip():
        return True
    a = c["attrs"]
    cid = a.get("id")
    if cid and label_for_text.get(cid, "").strip():
        return True
    if a.get("aria-label", "").strip():
        return True
    lb = a.get("aria-labelledby", "").strip()
    if lb and any(id_text.get(ref, "").strip() for ref in lb.split()):
        return True
    if a.get("title", "").strip():
        return True
    return False


def _viewport_blocks_zoom(content):
    """True when the viewport meta disables user zoom: user-scalable=no/0, or a
    maximum-scale capped at <= 1 (both defeat WCAG resize/reflow)."""
    parts = {}
    for chunk in content.replace(";", ",").split(","):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.strip().lower()] = v.strip().lower()
    us = parts.get("user-scalable")
    if us in ("no", "0", "false"):
        return True
    ms = parts.get("maximum-scale")
    if ms is not None:
        try:
            if float(ms) <= 1.0:
                return True
        except ValueError:
            pass
    return False


def _has_skip_link(anchors, ids):
    """A WORKING skip link is an in-page anchor href="#id" whose target id ACTUALLY EXISTS
    on the page (a dead #id jumps nowhere, so it is not a real skip link) AND that either
    says "skip" or targets a main/content-ish id. Id matching is case-sensitive (HTML ids
    are); only the main/content heuristic is case-folded."""
    for an in anchors:
        href = (an.get("href") or "").strip()
        if not href.startswith("#") or href == "#":
            continue
        raw_target = href[1:].strip()
        if raw_target not in ids:            # dead anchor -> not a working skip link
            continue
        target = raw_target.lower()
        text = (an.get("text") or "").strip().lower()
        if "skip" in text or target in _MAIN_ISH_HREF:
            return True
    return False


def _extract_colors(tokens):
    """Normalize a tokens object into a flat {slot: '#rrggbb'} map. Supports the engine's
    own shapes: a top-level {"colors": {...}} map, the W3C {"color": {slot: {"value": hex}}}
    shape emitted by tokens_emit.py --format json, or bare top-level slot->hex keys."""
    out = {}

    def _add(k, v):
        h = _norm_hex(v)
        if h:
            out.setdefault(k.replace("-", "_"), h)

    if isinstance(tokens, dict):
        colors = tokens.get("colors")
        if isinstance(colors, dict):
            for k, v in colors.items():
                if isinstance(v, str):
                    _add(k, v)
        w3c = tokens.get("color")
        if isinstance(w3c, dict):
            for k, v in w3c.items():
                if isinstance(v, dict) and isinstance(v.get("value"), str):
                    _add(k, v["value"])
                elif isinstance(v, str):
                    _add(k, v)
        for k, v in tokens.items():
            if isinstance(v, str):
                _add(k, v)
    return out


def _norm_hex(v):
    """Return '#rrggbb' for a 3- or 6-digit hex string, else None."""
    if not isinstance(v, str):
        return None
    s = v.strip().lstrip("#")
    if len(s) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in s):
        s = "".join(ch * 2 for ch in s)
    if len(s) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in s):
        return "#" + s.lower()
    return None


# The token pairs to cross-check: (foreground, background, minimum, kind, wcag, label).
# Slots come from what tokens_emit.py / gen_palettes.py emit; each pair fires only when
# BOTH colors are present.
_CONTRAST_PAIRS = [
    ("text", "bg", BODY_MIN, "body", "1.4.3", "Body text on page background"),
    ("text", "surface", BODY_MIN, "body", "1.4.3", "Body text on card surface"),
    ("on_primary", "primary", BODY_MIN, "body", "1.4.3", "Label text on primary button"),
    ("primary", "bg", UI_MIN, "ui", "1.4.11", "Primary UI accent against background"),
    ("accent", "bg", UI_MIN, "ui", "1.4.11", "Accent UI color against background"),
]


def _contrast_findings(tokens):
    colors = _extract_colors(tokens)
    out = []
    for fg, bg, minimum, kind, wcag, label in _CONTRAST_PAIRS:
        if fg in colors and bg in colors:
            ratio = contrast_ratio(colors[fg], colors[bg])
            if ratio < minimum:
                sev = "serious" if kind == "body" else "moderate"
                out.append({
                    "code": "contrast-below-min", "severity": sev, "category": "contrast",
                    "wcag": wcag, "pair": "%s/%s" % (fg, bg),
                    "ratio": ratio, "required": minimum,
                    "message": "%s is %.2f:1 (needs %s:1) -- %s on %s"
                               % (label, ratio, minimum, colors[fg], colors[bg]),
                })
    return out


def analyze(html, tokens=None):
    """Parse `html` and return the severity-ranked structural-a11y report:
      {tool, findings:[{code,severity,category,wcag,message,...}], counts, clean, summary}.
    Deterministic and side-effect free. `tokens` (optional) enables the token-contrast
    cross-check. Malformed markup is tolerated (html.parser is lenient)."""
    c = _Collector()
    c.feed(html or "")
    c.close()
    findings = []

    def add(code, severity, category, wcag, message, **extra):
        row = {"code": code, "severity": severity, "category": category,
               "wcag": wcag, "message": message}
        row.update(extra)
        findings.append(row)

    # --- html lang (3.1.1) ---------------------------------------------------------
    if not (c.html_lang and c.html_lang.strip()):
        add("html-no-lang", "serious", "language", "3.1.1",
            "<html> has no lang attribute -- screen readers cannot pick a voice/pronunciation.")

    # --- images alt coverage (1.1.1) ----------------------------------------------
    missing = [i for i in c.images if not i["has_alt"]]
    for i in missing:
        add("img-missing-alt", "serious", "images", "1.1.1",
            "<img%s> has no alt attribute -- add alt text (or alt=\"\" if purely decorative)."
            % ((' src="%s"' % i["src"]) if i["src"] else ""),
            src=i["src"])

    # --- headings (1.3.1 / 2.4.6) --------------------------------------------------
    if c.headings:
        if c.h1_count == 0:
            add("heading-no-h1", "serious", "headings", "1.3.1",
                "Headings exist but there is no <h1> -- the page needs one top-level heading.")
        elif c.h1_count > 1:
            add("heading-multiple-h1", "minor", "headings", "1.3.1",
                "%d <h1> elements -- prefer exactly one top-level heading." % c.h1_count,
                count=c.h1_count)
        prev = None
        for lvl in c.headings:
            if prev is not None and lvl > prev + 1:
                add("heading-skip", "moderate", "headings", "1.3.1",
                    "Heading level jumps from h%d to h%d -- do not skip levels." % (prev, lvl),
                    **{"from": prev, "to": lvl})
            prev = lvl

    # --- form controls (4.1.2 / 3.3.2) --------------------------------------------
    for ctl in c.controls:
        if ctl["tag"] == "input" and ctl["type"] in _EXEMPT_INPUT_TYPES:
            continue
        if not _control_has_name(ctl, c.label_for_text, c.id_text):
            add("control-no-label", "critical", "forms", "4.1.2",
                "<%s%s> has no accessible name -- add a <label for>, wrap it in a <label>, "
                "or set aria-label." % (ctl["tag"],
                                        (' type="%s"' % ctl["type"]) if ctl["type"] else ""))

    # --- viewport (best-practice / 1.4.4 / 1.4.10) --------------------------------
    if c.viewport is None:
        add("no-viewport-meta", "serious", "mobile", "1.4.10",
            "No responsive <meta name=\"viewport\"> -- the page will not adapt to mobile widths.")
    elif _viewport_blocks_zoom(c.viewport):
        add("viewport-zoom-blocked", "serious", "mobile", "1.4.4",
            "The viewport meta disables pinch-zoom (user-scalable=no / maximum-scale<=1) -- "
            "low-vision users cannot zoom.")

    # --- main landmark (1.3.1) -----------------------------------------------------
    if not ("main" in c.landmarks or "role:main" in c.landmarks):
        add("no-main-landmark", "moderate", "landmarks", "1.3.1",
            "No <main> or role=\"main\" region -- assistive tech cannot jump to the primary content.")

    # --- skip link (2.4.1) ---------------------------------------------------------
    if not _has_skip_link(c.anchors, c.ids):
        add("no-skip-link", "minor", "navigation", "2.4.1",
            "No in-page \"skip to content\" link -- keyboard users must tab through the header "
            "on every page.")

    # --- token contrast cross-check (1.4.3 / 1.4.11) ------------------------------
    if tokens is not None:
        findings.extend(_contrast_findings(tokens))

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["code"], f.get("wcag", "")))
    counts = {s: sum(1 for f in findings if f["severity"] == s)
              for s in ("critical", "serious", "moderate", "minor")}
    clean = not findings
    summary = ("no structural accessibility issues found"
               if clean else
               "%d structural issue(s): %d critical, %d serious, %d moderate, %d minor"
               % (len(findings), counts["critical"], counts["serious"],
                  counts["moderate"], counts["minor"]))
    return {"tool": "a11y_static", "findings": findings, "counts": counts,
            "clean": clean, "summary": summary,
            "coverage": "structural subset (source-only); a full computed-contrast / "
                        "keyboard / reduced-motion scan needs Playwright + axe-core"}


class _JsonArgParser(argparse.ArgumentParser):
    """argparse's own failures (unknown flag, bad type) must honor the JSON-error contract:
    {"error": ...} to stdout + a non-zero exit, never a bare usage dump. ASCII only."""
    def error(self, message):
        msg = str(message).encode("ascii", "replace").decode("ascii")
        print(json.dumps({"error": msg}))
        sys.exit(2)


def _human(report, target):
    lines = ["# a11y (structural): %s" % target, report["summary"]]
    for f in report["findings"]:
        extra = ""
        if f["code"] == "contrast-below-min":
            extra = "  [%s]" % f.get("pair", "")
        lines.append("  [%s] %-20s WCAG %s%s  %s"
                     % (f["severity"].upper(), f["code"], f["wcag"], extra, f["message"]))
    lines.append("(%s)" % report["coverage"])
    return "\n".join(lines).encode("ascii", "replace").decode("ascii")


def main(argv=None):
    ap = _JsonArgParser(description="Structural WCAG accessibility checker (stdlib, offline).")
    ap.add_argument("--file", help="local HTML file to check")
    ap.add_argument("--html", help="HTML string to check (offline)")
    ap.add_argument("--tokens", help="design-system token JSON (enables the contrast cross-check)")
    ap.add_argument("--human", action="store_true", help="ASCII summary instead of JSON")
    args = ap.parse_args(argv)

    if args.file:
        try:
            with open(args.file, encoding="utf-8", errors="replace") as fh:
                html = fh.read()
        except OSError as e:
            print(json.dumps({"error": "could not read HTML file: %s" % e}))
            return 1
        target = args.file
    elif args.html is not None:
        html = args.html
        target = "(inline)"
    else:
        print(json.dumps({"error": "no HTML to check -- pass --file <path> or --html '<...>'"}))
        return 1

    tokens = None
    if args.tokens:
        try:
            with open(args.tokens, encoding="utf-8") as fh:
                tokens = json.load(fh)
        except (OSError, ValueError) as e:
            print(json.dumps({"error": "could not read --tokens JSON: %s" % e}))
            return 1

    report = analyze(html, tokens=tokens)
    report["target"] = target
    if args.human:
        print(_human(report, target))
    else:
        print(json.dumps(report, indent=2))
    # Analysis SUCCEEDED even when it finds issues -> exit 0 (findings are the deliverable,
    # not a tool failure). Only bad input / unreadable inputs exit non-zero (handled above).
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
