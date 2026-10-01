# Operations and security

[Back to README](../README.md) · Run commands from the repository root.

- [Respectful RIPE requests and cancellation](#respectful-ripe-requests-and-cancellation)
- [Limits, caching, and performance](#limits-caching-and-performance)
- [Progress, result retention, and connection protection](#progress-result-retention-and-connection-protection)
- [Privacy and security](#privacy-and-security)
- [Configuration and hosting](#configuration-and-hosting)
- [Troubleshooting](#troubleshooting)

## Respectful RIPE requests and cancellation

All RIPE requests from the local server share one request gate across ordinary
lookups, captures, comparisons, and browser tabs. It allows **one active request
at a time**, with a **two-second pause after a response**, including retries.
There is **no daily request cap**. Observed paths, captures, comparisons, and Origin Mapping accept up to 1,000
entries per submission. Large batches take longer: 1,000 uncached RIPE requests
require about 33 minutes of pacing alone, plus response and processing time.
Two-date comparisons can require twice as many requests. Existing result and
evidence size limits still apply; a large capture may need smaller batches.

The page shows requests attempted today (UTC). At **1,000 attempts**, an in-page
notification advises registering regular high-volume use with RIPE; processing
continues. Retries count; cache hits, local-only inputs, and CAIDA downloads do
not. The notice remains visible for that UTC day, including after a page reload.
The counter resets at midnight UTC and survives server restarts. It applies to
this cache directory, not all software using your public IP address.

[RIPEstat's usage guidance](https://data.stat.ripe.net/docs/data-api/ripestat-data-api)
allows eight concurrent requests per source IP and asks users to register if
regularly exceeding 1,000 requests/day. Our single-request/two-second pace is a
conservative choice, not RIPE-mandated timing or a guarantee against throttling.
The app does not register or send email on your behalf.

Normalized duplicate targets are collapsed before a server lookup/capture.
Responses are reused from bounded memory caches (latest: five minutes;
historical: one hour). This avoids extra queries without saving raw responses
or investigation targets in a new disk database.

HTTP 429, HTTP 5xx, and transport failures trigger exponential backoff, honoring
`Retry-After` in seconds or HTTP-date form. Three consecutive transient failures
stop further requests for at least five minutes; a longer `Retry-After` takes
precedence. A single service-requested delay over 60 seconds also stops the job
instead of keeping it waiting indefinitely. Retry explicitly after the cooldown.
Ordinary lookups retain partial results and mark remaining targets `not_requested`.
Interrupted evidence captures/comparisons do not publish an incomplete ZIP.

**Cancel lookup** appears while a job is queued or running. It cancels future work,
including requests waiting in backoff. An in-flight request or parsing step may
finish first; requests already sent still count. Completed ordinary results
remain exportable. Closing the browser does not cancel the server job.

The small `data/private/requests.sqlite3` file stores only counts and timing,
not targets or evidence. The shared raw-response cache is bounded to 32 MB in
memory, in addition to the existing path cache. A previous prototype database,
if present, is left untouched; its counter can be copied once to preserve usage.
No persistent bulk jobs, recovery keys, or new evidence storage are added.

Use `python3 server.py --ripe-interval 2` (or a larger interval) to configure
pacing. `lookup.py --paths` uses the same gate and counter. Only one network-using
process can own a cache directory; use the running server rather than a concurrent
CLI process. Different directories/hosts have separate gates, so avoid parallel
instances that multiply aggregate load.

## Limits, caching, and performance

| Resource | Implemented limit/behavior |
| --- | --- |
| Import text / HTTP job body | 262,144 bytes / 524,288 bytes including JSON overhead |
| Observed BGP paths / Origin Mapping batch | 1,000 / 1,000 entries |
| RIS response per resource | 12,000,000 bytes and 50,000 routes |
| Origin-neighbor combinations | At most 500 per observed-path input |
| Retained path evidence | At most 1,000 path/prefix combinations per input, divided among neighbors |
| Origin segments / overlapping routes | 5,000 segments per batch / 20,000 routes per input |
| Job execution | One worker; up to three outstanding jobs including the running job |
| Retained jobs | At most 40; active jobs retained; finished results expire after one hour or earlier under storage pressure; restart clears them |
| Browser polling | About every 1.5 seconds for jobs; shared counter every five seconds |
| RIS response cache | Up to eight responses; latest for five minutes, historical for one hour |
| In-memory dataset maps | Up to two routing indexes and two organization maps |
| Catalog cache | One hour |
| Compressed dataset cache | Approximately 512 MB; oldest files evicted when new downloads need space |

Most limits produce explicit errors. Retained path evidence is capped with a
notice; its counts still describe all accepted routes in the returned response.

Origin Mapping can require substantial parsing and several hundred MB of memory.
Caching reduces downloads but does not eliminate parsing after a restart.
Observed BGP paths avoids the full prefix-to-AS index but still processes RIS and
CAIDA enrichment locally. Actual performance depends on input and upstream data.

The cache contains public data, not saved user reports. Catalog files are separate
from the compressed-file cap; the application does not have a hard 512 MB total
memory/disk limit. One network-using process may own each cache directory at a time.

## Progress, result retention, and connection protection

Live jobs show the current target and completed, failed, special-use skipped, and
remaining input counts. Comparisons show progress separately for each dated
snapshot. These are input counts, not RIPE request counts. After cancellation,
remaining includes inputs that were not requested. Failed captures do not produce
an incomplete investigation ZIP.

Results show a persistent completeness summary and per-input warnings for failed
or unprocessed inputs, unavailable enrichment, partial coverage, and truncated
path evidence. Completed means processing finished; it does not guarantee full
Internet visibility. Observed advertisements are not measured traffic paths, and
collector counts are not confidence scores or traffic shares.

Each observed origin also has a public-routing-visibility label based only on
the number of distinct RIS collectors: **Limited** for one collector,
**Multi-collector** for two or three, and **Broader** for four or more. The
adjacent label shows the exact collector, collector-peer, prefix, and observation
time counts. It is evidence context, not a confidence, risk, reachability, or
traffic-volume assessment.

Finished jobs expire after one hour, or earlier when new work needs space.
The server evicts the oldest finished jobs at the 40-job limit or the shared
128 MB budget for serialized results plus investigation ZIPs. Queued and running
jobs are protected. A result larger than that budget fails with a smaller-batch
message. Download files you want to keep; downloaded files are not evicted.
This budget does not cap temporary processing memory or total process memory.

The server allows at most 32 simultaneous connections and closes excess ones.
Connections have a 10-second initial idle timeout and a 15-second absolute
header deadline. Job uploads have a 15-second idle timeout and 30-second total
body deadline; investigation uploads use 30 and 60 seconds respectively.
These deadlines do not limit background jobs; the browser polls separately.

## Privacy and security

### External transmission and retention

| Action | Data flow |
| --- | --- |
| Observed BGP paths | Validated, normalized public IP/prefix/ASN queries are sent to RIPE NCC. |
| Origin Mapping | Imported resources are matched locally; CAIDA receives dataset download requests, not resource queries. |
| Enrichment | Public dataset download requests go to CAIDA. |
| Imported destination | No ping, DNS enrichment, web fetch, or connection is made to the submitted destination. |

Inputs fully within recognized special-use ranges are handled without external
resource queries. Do not treat that filter as a guarantee that arbitrary
sensitive inputs stay local: Observed BGP paths is an external-query workflow.

Results and input strings live in server memory until expiration or restart.
Imports/results are not intentionally persisted by the service; user exports
are saved files. Browser memory, OS swap, gateways, hosting logs, and upstream
providers have separate retention behavior. The HTTP handler suppresses its
ordinary request logging, but that does not guarantee the surrounding environment
logs nothing.

### Query privacy

**Running the interface locally does not make live BGP queries private.** When
an Observed BGP paths lookup needs an external request, RIPE NCC receives the
normalized target ASN, IP address, or prefix, the requested observation time
(for historical queries), and the public source IP of the connection. Capturing
an investigation or comparing two dates uses this same lookup workflow. HTTPS
encrypts the connection but does not hide the query from RIPE; a VPN changes the
source IP visible to RIPE, not the target in the query.

To investigate without sending new target queries, open and replay an existing
investigation ZIP in the local interface or use the offline replay command.
Opening/replaying a bundle makes no external requests; following a source link
is a separate browser request. Saved evidence reflects only its recorded times
and coverage, not necessarily current routing.

The tool does not yet provide an enforced offline mode for ordinary lookups,
automatically search saved bundles before querying RIPE, or ingest full routing
archives for private local target searches. A cache hit may avoid a request,
but the cache is not a privacy guarantee. If a target must remain confidential,
do not submit it to the live lookup, capture, or comparison workflow.

Investigation ZIPs and other exports are unencrypted and can disclose your
targets and findings. Store and share them according to the sensitivity of the
investigation. Local replay does not change upstream retention of queries that
were already sent when the evidence was captured.

### Existing controls

- Loopback binding by default and local Host/Origin validation without a service token.
- Fixed external sources, dataset URL validation, and restricted redirects.
- TLS verification remains enabled.
- Bounded inputs, downloads, results, and job queue.
- Random job IDs and separate per-job bearer tokens for result access.
- Optional server-to-server token, required for non-loopback binding.
- Basic browser security headers, text-based rendering, and CSV formula escaping.

These are not per-user accounts, workspace isolation, durable auditing, or a
public-service rate limiter. Anyone able to reach an unprotected local service
can submit jobs. Keep job tokens and service tokens private; do not put them in
URLs or client-side code. Treat exported investigation context as potentially sensitive.

## Configuration and hosting

| Setting | Default | Purpose |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Bind address; keep loopback for local use. |
| `--port` | `8765` | HTTP port. |
| `--ripe-interval` | `2` | Pause between RIPE requests in seconds; minimum 2. |
| `--cache` | `data/` beside the server | Dataset cache plus a private request-count/timing database; no saved job targets. |
| `BGP_LOOKUP_SERVICE_TOKEN` | Unset | Shared secret; 32+ characters required for non-loopback binding. |
| `SSL_CERT_FILE` | Python's trust configuration | Optional approved CA bundle. |

The standalone scripts read process environment variables; they do **not** load
`.env` files automatically. On macOS, the downloader also trusts the system
`/etc/ssl/cert.pem` bundle when present. Certificate verification remains enabled.

### Before public hosting

Do not expose the bundled standard-library HTTP server directly to the internet.
Production release work includes:

- Production serving, HTTPS, private networking, and process supervision.
- End-user authentication/authorization, quotas, and request limits at a trusted gateway.
- Secret storage and rotation, with tokens kept server-side.
- Capacity planning, monitoring, timeouts, upstream failures, and cost controls.
- Restart/persistence policy and a multi-process cache strategy.
- Provider usage terms, submitted-resource privacy, deployment tests, and rollback.

A service token alone does not make this production-ready. A normal browser does
not automatically supply it to the protected standalone UI. Serve users through
an authenticated application/gateway; never expose the token in browser code.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Python missing or syntax/import errors | Check that the selected interpreter is Python 3.10+. |
| Local page cannot be reached | Keep `server.py` running and use its printed address. Opening `web/index.html` directly is insufficient. |
| Port already in use | Use `--port 8766` and the matching URL. |
| First lookup is slow | Downloads/parsing may be running. Watch status and avoid duplicate submissions. |
| CAIDA/RIS retrieval failure | Check connectivity, approved outbound access, TLS trust, and upstream availability; retry later. |
| Certificate error | Configure a supported Python trust setup or approved `SSL_CERT_FILE`; do not disable verification. |
| No historical snapshot | Coverage is incomplete. Choose another date deliberately. |
| Unknown relationship/name | Check warnings and enrichment dates; missing data does not prove no provider exists. |
| `not_observed` | Review input, date, address family, and collector coverage; do not assume globally unreachable. |
| Too many routes/response too large | Use narrower prefixes or smaller imports, not weaker safety limits. |
| Busy / HTTP `429` | Let active work finish or cancel your queued job. |
| Job/export unavailable | It expired, the service restarted, or the token is wrong. Rerun the lookup. |
| Unauthorized after setting a token | The raw server now needs bearer authentication, including its UI. Use a trusted gateway/client. |
| Private GitHub repo shows 404 | Sign in with repository access or use a supplied ZIP; local execution does not need GitHub access. |

For a corrupt cached dataset, stop the service and move the affected cache file
aside before retrying. Caches are replaceable downloads, but restarting clears
in-memory jobs. Do not remove source files or saved analyst exports.

Use **Cancel lookup** while a job is queued or running. It stops subsequent work;
an in-flight request or parsing step may finish first. Completed ordinary lookup
results remain exportable; unfinished targets are marked `not_requested`.
Cancelling an investigation capture/comparison does not produce an incomplete ZIP.
If cancellation arrives after processing finishes, the completed result is retained.
The API is `POST /api/jobs/{id}/cancel`, using the job's `X-Job-Token` and the same
Host/Origin/service-token checks as other job routes. Closing a tab alone does not
cancel a server-side job.
