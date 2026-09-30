# Development guide

[Back to README](../README.md) · Run commands from the repository root.

- [Development and project structure](#development-and-project-structure)

## Development and project structure

Run all commands in these guides from the repository root, not `docs/`.

Run tests:

```sh
python3 -m unittest discover -s . -p 'test_*.py'
```

The test suite includes fixture/mock-based processing and local HTTP tests, with no live provider requests.
It covers imports, CIDR normalization, longest-prefix matching, range boundaries,
multiple origins, dated dataset selection, relationship direction, path
normalization, observer deduplication, explicit upstream errors, job-token access,
expiration, CSV formula escaping, 1,000-entry batches, cancellation, progress,
connection deadlines, finished-job eviction, and combined result/ZIP budgets.

For behavior changes, add regression fixtures, exercise the browser and CLI,
check invalid/missing-data cases, and verify export provenance. Inspect desktop
and mobile layouts for UI changes. Passing tests does not guarantee upstream
availability or correctness of inferred business relationships. No hosted CI
workflow is included in this package.

```text
bgp-routing-exposure-lookup/
  README.md                 Quick start and worked investigation
  docs/                     Analyst, operations, reference, architecture, and development guides
  THIRD_PARTY_NOTICES.md     Icon attribution and license notices
  .gitignore                Cache, environment, and metadata exclusions
  lookup.py                 Imports, datasets, origin lookup, and CLI
  paths.py                  RIS paths, relationship matching, and export
  server.py                 Local HTTP server and in-memory job API
  batch_progress.py         Per-input progress snapshots
  test_hardening.py          Connection, retention, storage budget, and progress tests
  ripe_queue.py             Shared pacing, backoff, and request-count notification
  test_ripe_queue.py         Request scheduling and notification tests
  test_cancel.py            Queued/running cancellation and partial results tests
  investigations.py         Evidence bundles, offline replay, and two-date comparisons
  test_investigations.py     Replay, bundle integrity, and comparison tests
  test_investigation_http.py Bundle API and access-control tests
  test_lookup.py            Origin/import/job tests
  test_paths.py             Observed-path/relationship tests
  web/
    index.html              Standalone page
    app.js                  Shared browser component
    style.css               Interface styles
    icons.svg               Icon assets
  data/                     Runtime cache; not committed or distributed
```
