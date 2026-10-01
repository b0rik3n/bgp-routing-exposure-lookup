# Codex Instructions for BGP Routing Exposure Lookup

These instructions apply to every contribution in this repository.

## Mission and scope

This is a locally run investigation tool for answering:

> Which external networks are observed immediately before a target network, for which prefixes, and how does that change over time?

It combines public BGP observations with optional enrichment. It is not a BGP router, a traffic monitor, a scanner, or an attack-detection system. Keep the tool focused on routing evidence and its limits.

Treat any hosted deployment, shared capture store, new external service, or live organizational investigation data as a separate system. Do not connect, publish, retain, or modify those systems without explicit authorization and a clear account of the privacy and operational effect.

Use the following three-part evidence model in UI text, exports, documentation, and code:

- **Observed fact:** a public collector observed an AS path, prefix, origin, or route at a particular time.
- **Relationship inference:** a relationship dataset can suggest a transit, peer, or customer/provider relationship.
- **Security interpretation:** an observed adjacency can be potential ingress worth investigating; it does not establish reachability, a perimeter, an attack path, or a vulnerability.

Never collapse these categories. In particular, do not describe an AS immediately before the target as the target's provider, perimeter, attacker, or confirmed ingress point unless an explicitly cited source establishes that narrow claim.

## Source integrity and provenance

- Treat RIPE RIS paths as public, collector-specific observations. They do not show end-host traffic, every route, or a complete view of the Internet.
- Treat CAIDA AS relationships as separately inferred and probabilistic. Do not present them as observed BGP facts.
- Treat RouteViews prefix-to-AS data as origin-mapping context, not path evidence.
- Preserve source name, URL, observation or dataset time, and available version/checksum information in captures and comparisons.
- Keep source failures visible. If a name or relationship cannot be resolved, show the ASN and state that enrichment is unavailable instead of inventing a label.
- Do not add a new external data provider or change source semantics without updating the README, privacy guidance, source-access indicators, and tests where applicable.

## Data handling and retention

- Consider retention, export, and deletion behavior before storing a new result type. Prefer the smallest amount of data needed for the local investigation.
- Keep investigation captures explicit, user-initiated, and portable. Do not automatically upload, synchronize, or share them.
- Preserve the distinction between transient in-memory results, local request-count metadata, cached source data, and exported evidence bundles. Each has different privacy and lifecycle expectations.
- Keep generated output, caches, downloaded datasets, virtual environments, and local configuration out of commits unless the repository deliberately tracks that exact artifact.

## Request privacy and respectful collection

- Inputs for live lookups, captures, and comparisons are sent to the relevant public data services. Never claim that a lookup is private or anonymous.
- Preserve the shared `RipeGate` request gate: one active RIPE request at a time and the configured minimum interval (currently two seconds) across all jobs, retries, lookups, and comparisons.
- Preserve cache reuse, deduplication, `Retry-After` handling, bounded exponential backoff, and the stop-after-repeated-failures behavior. Do not bypass these controls to make a batch finish sooner.
- Keep the request counter metadata-only: it must not record lookup targets.
- Prefer existing cached or captured evidence before making a new external request. Do not introduce hidden browser-side requests to data providers.

## Security and local operation

- Validate every network target, upload, archive member, query parameter, and HTTP request before use. Keep resource, size, timeout, and job-concurrency limits in place.
- The server is intended for local use. Preserve the loopback binding default, Host validation, Origin checks, and token requirement for non-loopback binding.
- Treat all external responses, downloaded datasets, imported captures, CSV values, and relationship labels as untrusted data. Render text safely and never execute imported content.
- Download datasets only from explicitly allowed CAIDA public-data locations, validate redirect destinations, and do not turn a user-controlled URL into a server-side request.
- Never commit tokens, credentials, proxy configuration, personal lookup history, or unredacted sensitive captures. Avoid printing targets or request headers in logs unless required for an approved diagnostic purpose.
- Captures may contain sensitive investigation context and are not encrypted by the application. Do not weaken this warning or make capture sharing automatic.

## Architecture and compatibility

- Keep the application dependency-light and compatible with its standard-library Python design unless a justified change requires otherwise.
- `server.py` owns HTTP handling and job lifecycle; `ripe_queue.py` owns RIPE request pacing; `lookup.py` performs source lookups; `paths.py` normalizes and analyzes paths; `web/` contains the local interface.
- Preserve existing JSON response shapes, capture schemas, result fields, and user-facing terminology unless a deliberate migration includes backward compatibility and documentation.
- Degrade gracefully in disconnected or corporate environments: routing results can remain useful even when organization-name or relationship enrichment is unavailable.
- Keep result handling bounded. A large CSV must remain cancellable, incrementally reported, and constrained by documented limits.

## Analyst experience

- Prefer clear evidence labels, timestamps, collector coverage, and source links over confidence scores or alarm language.
- Keep the interface accessible, responsive, keyboard-usable, and readable on narrow screens. Decorative artwork and status indicators must not obscure results or carry analytical meaning.
- Use restrained language and visuals. Avoid red/green signals that suggest compromise, safety, or threat severity; source-access indicators may only describe connectivity to that source.
- Explain uncertainty near the relevant result, export, or action rather than hiding it in a general disclaimer.

## Engineering workflow

- Follow pragmatic programming principles. Own the quality of the code you touch; leave it clearer, safer, and no more surprising than you found it.
- Make small, reversible changes with a single purpose. Prefer simple, direct code over clever abstractions, and avoid duplicating business rules across the server, lookup logic, and browser UI.
- State assumptions, invariants, units, time boundaries, and source semantics explicitly in code and tests. Use names that explain routing concepts without relying on comments to rescue ambiguous code.
- Design module boundaries as contracts. Validate inputs at those boundaries, return predictable errors, and keep source-specific behavior behind focused helpers.
- Detect problems early: validate at the point of entry, fail safely with useful messages, preserve enough context for diagnosis, and do not silently substitute guessed routing evidence.
- Automate repeatable checks. Prefer tests and small verification commands over manual, error-prone repetition; keep the test suite fast enough to run routinely.
- Treat duplication as a signal to extract a shared helper only when the behavior is genuinely the same and has a stable name. Do not create generic frameworks for a single use.
- Keep operational choices observable: report source availability, cache use, pacing, partial results, cancellation, and data age in language an analyst can act on.
- When requirements conflict, choose correctness of evidence, user privacy, and safe behavior over convenience or visual polish, then document the tradeoff.
- Inspect the current code, tests, and existing helper functions before changing behavior. Make the smallest complete change that meets the request.
- Do not perform unrelated refactors, formatting churn, dependency upgrades, or API redesigns while addressing a focused issue.
- Add or update meaningful `unittest` coverage for behavioral changes, especially validation, queue pacing, cancellation, capture compatibility, and source-failure behavior.
- For a bug fix, add a focused regression test when practical. Never delete, weaken, or bypass a test merely to make a change pass.
- Run the affected tests during development. Before handing off a code change, run `python3 -m unittest` when practical and always run `git diff --check`.
- For UI work, exercise the affected path and inspect narrow and wide layouts when the available tooling permits. For HTTP changes, include an invalid-input or upstream-failure case when practical.
- Never claim a test, manual check, build, or browser inspection ran unless it actually ran. If a relevant check cannot run, say why and state what was checked instead.
- Inspect `git status` and the final diff before reporting completion. Do not commit, push, publish, change repository visibility, or alter a remote without an explicit user request.
- Preserve existing user changes in the worktree. Stage only intended files, keep commits focused, and do not use destructive cleanup, reset, history rewriting, or force-push without explicit approval and a precise explanation of what would be lost.

## Completion standard

A change is complete only when it preserves the evidence model, respects external services and investigation privacy, handles failures safely, keeps the local interface understandable, and has appropriate verification. Before handoff, review the diff for scope expansion and sensitive data. Report what changed, what was checked, and any material limitations.
