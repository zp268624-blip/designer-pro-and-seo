# seo-drift SQLite store — schema rationale

Knowledge file for `seo-drift`. It explains *why* the baseline store is shaped the way it
is, so the schema can evolve without surprises. The DDL itself lives in
`scripts/seo/drift_baseline.py`; this file is the reasoning behind it.

## What the store is for

`seo-drift` is "git for SEO": capture a snapshot of a page's SEO-critical elements before a
deploy, then diff later captures against it. The store is the *baselines* — an append-only
log of snapshots, keyed so the engine can answer three questions cheaply:

1. *What was this URL's SEO state at capture time?* → resolve one baseline.
2. *Which baselines do I have?* → list, filtered by URL or label.
3. *How did SEO drift across the history?* → trend consecutive snapshots.

A local SQLite file (stdlib `sqlite3`, zero dependencies) is the right tool: a single
portable file under the user's workspace, transactional writes, and indexed queries — no
server, no extra install, consistent with the plugin's stdlib-only posture.

## The schema

```sql
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL              -- holds schema_version = 1
);

CREATE TABLE baselines (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT,              -- indexed: latest-per-URL lookups
    label         TEXT,              -- indexed: 'prod' / 'pre-deploy' grouping
    captured_at   TEXT NOT NULL,     -- ISO 8601; the ordering key
    snapshot_json TEXT NOT NULL      -- the full captured snapshot, verbatim
);

CREATE INDEX ix_baselines_url   ON baselines(url);
CREATE INDEX ix_baselines_label ON baselines(label);
```

## The load-bearing decision: blob the snapshot, promote the metadata

The captured element set is owned by `drift_tools.capture()` and is expected to grow
(more og tags, hreflang, a structured-data hash, …). Two ways to store it:

- **A column per element.** Fast to query a single field, but every change to
  `capture()` forces a schema migration, and a snapshot with a new field can't be written
  by an old binary. The element set becomes coupled to the database shape.
- **One JSON blob (`snapshot_json`) + promoted metadata columns.** The chosen design.
  The snapshot is stored as the exact JSON `capture()` produced (serialized with sorted
  keys for byte-stable storage). Adding or removing a captured element needs **no
  migration** — the blob just carries different keys, and `drift_severity.evaluate()`
  already ignores unknown keys and skips absent ones. Only the three fields the *store*
  needs to index on — `url`, `label`, `captured_at` — are lifted into real columns.

This keeps the store's contract narrow: it indexes *identity and time*, and treats the SEO
payload as opaque. The element list and the severity rules can evolve freely on the
`drift_tools` / `drift_severity` side without ever touching the database shape.

## Why these columns are indexed

- **`url`** — the common query is "the latest baseline for this URL." With the index,
  `WHERE url=? ORDER BY captured_at DESC, id DESC LIMIT 1` stays cheap as history grows.
- **`label`** — captures are tagged (`prod`, `pre-deploy`, a release name) so a compare can
  target "the latest `prod` baseline" regardless of URL. Indexed for the same reason.
- **`captured_at` as the ordering key** — ISO 8601 strings sort lexicographically in the
  same order as chronologically, so "latest" and "oldest-first history" are plain
  `ORDER BY captured_at`. `id` (autoincrement) is the deterministic tiebreak when two
  snapshots share a timestamp — which is exactly what the `--captured-at` test override
  exercises.

## Resolution order (which baseline a compare picks)

`get_baseline()` resolves a single row in this precedence, most-specific first:

1. `--baseline-id N` → that exact row.
2. else `--label L` → the latest row with that label.
3. else `--url U` → the latest row for that URL.
4. else → the latest row overall.

A compare that matches nothing returns a JSON error and a non-zero exit — the engine never
silently compares against an unrelated baseline.

## The `meta` table and forward compatibility

`meta` holds `schema_version` (currently `1`). It costs nothing now and gives a future
version a place to detect an old store and migrate it, rather than guessing from table
shape. Because the SEO payload is a blob, a v2 is far more likely to add an *index* or a
*metadata column* than to rewrite existing rows — the version marker makes that upgrade
explicit instead of implicit.

## Boundaries

- **Workspace-local.** The default path is `./.seo-drift/baselines.db` under the user's
  current directory — never inside the plugin (it ships read-only) and never outside the
  user's workspace.
- **Append-only by design.** Baselines are a history; the engine inserts, never updates a
  prior row. Trend analysis depends on that immutability.
- **No secrets, no PII.** Only public on-page SEO elements are captured and stored; the
  store never holds credentials or fetched user data.
