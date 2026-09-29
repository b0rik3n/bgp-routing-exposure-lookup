# BGP Routing Exposure Lookup

A Múcaro tool for investigating external routing exposure.

Investigate external routing exposure: which external networks are observed
immediately before the target origin autonomous system (AS), and for which
prefixes, at the selected time? Use current or historical data, inspect the
evidence, and export results for further analysis. Provider identification is
supporting context, based on separately inferred relationships.

The tool includes a local browser interface, a command-line interface, and a
small asynchronous job API. It runs independently of Mucaro using Python's
standard library. No Python packages, Node.js, database, API key, or GitHub login
are required to run an extracted copy.

**Status:** local analyst/research tool. The bundled HTTP server is not a
production-ready public service. This is source code, not a signed desktop
application or a browser-only application.

**Important:** an observed BGP neighbor is not automatically an ISP or transit
provider. Relationship classifications are inferences, not proof of commercial
agreements, physical connectivity, or the route taken by your own traffic.

## Contents

- [Choose a lookup mode](#choose-a-lookup-mode)
- [Requirements and quick start](#requirements-and-quick-start)
- [Browser workflow](#browser-workflow)
- [Import formats](#import-formats)
- [Interpret the results](#interpret-the-results)
- [Saved investigations and comparisons](#saved-investigations-and-comparisons)
- [Current and historical data](#current-and-historical-data)
- [Command-line usage](#command-line-usage)
- [Exports and result structure](#exports-and-result-structure)
- [Architecture and processing](#architecture-and-processing)
- [BGPStream tradeoffs](#relationship-to-bgpstream)
- [Limits, caching, and performance](#limits-caching-and-performance)
- [Privacy and security](#privacy-and-security)
- [Local API](#local-api)
- [Configuration and hosting](#configuration-and-hosting)
- [Standalone project](#standalone-project)
- [Troubleshooting](#troubleshooting)
- [Development and project structure](#development-and-project-structure)
- [Known limitations](#known-limitations)
- [Data sources and licensing](#data-sources-and-licensing)
- [Glossary](#glossary)

## Choose a lookup mode

| | Observed BGP paths | Origin Mapping |
| --- | --- | --- |
| Main question | Which networks are observed immediately before the origin AS? | Which AS announces the network containing this IP or range? |
| Input | ASN, IPv4/IPv6 address, or CIDR | IPv4/IPv6 address, CIDR, or start-end range |
| Example | `AS63` or `129.55.110.9` | `129.55.110.9` or `129.55.0.0/24` |
| Primary evidence | RIPE RIS BGP paths | CAIDA RouteViews prefix-to-AS snapshots |
| Enrichment | CAIDA organization names and inferred AS relationships | CAIDA organization names |
| Maximum import | 20 entries | 1,000 entries |
| Historical selection | Routing state at 12:00 UTC on the selected day | Latest available routing snapshot within the selected day |

Choose **Observed BGP paths** to investigate observed external adjacencies and
potential ingress, with inferred provider relationships as supporting context. Choose **Origin Mapping** for bulk IP/range attribution.
Neither mode performs traceroute, pings the destination, or determines an end
user's retail broadband subscription.

## Requirements and quick start

### Requirements

- Python 3.10 or newer, with working HTTPS certificate trust.
- A modern browser for the graphical interface.
- Internet access to `stat.ripe.net` and `publicdata.caida.org` for lookups.
- A writable cache directory; by default, `data/` beside the scripts.
- Memory for routing indexes. Origin Mapping can use several hundred megabytes.

The local workflow has been verified on macOS. The code has no macOS-only runtime
dependency, but Windows and Linux workflows have not been validated as part of
this release. Commands below use a macOS/Linux-style shell.

### 1. Get the code

Extract the supplied ZIP and open a terminal in its `bgp-routing-exposure-lookup` folder.
Alternatively, clone the public repository:

```sh
git clone https://github.com/bayanilla/bgp-routing-exposure-lookup.git
cd bgp-routing-exposure-lookup
```

No GitHub sign-in is needed to clone this public repository or run the tool.

### 2. Start the local server

```sh
python3 --version
python3 server.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Keep the terminal running while
using the tool; stop it with `Ctrl+C` when finished. There is no `pip install`,
`npm install`, or database setup step. Use an equivalent Python 3.10+ command if
your system names the interpreter differently.

### 3. Run the example

Observed BGP paths is selected by default, with `AS63` in the input field. Select
**Latest**, then **Find observed paths**. Expand a path/prefix summary to inspect
full AS sequences. The first request can take longer while datasets download.

If port 8765 is occupied, use another port:

```sh
python3 server.py --port 8766
```

Then open [http://127.0.0.1:8766](http://127.0.0.1:8766). Use a different port when
another local application is already listening on port 8765.

## Browser workflow

### Observed BGP paths

1. Select **Observed BGP paths**.
2. Enter an ASN, IP, or CIDR, or choose **Import file**.
3. Select **Latest** or **Historical** and a UTC date.
4. Select **Find observed paths**.
5. Review each origin, its observed adjacent networks, relationship labels, and collector counts.
6. Expand path/prefix summaries. Hover over an ASN in a sequence for its organization name.
7. Export CSV or JSON as needed.

ASNs require the case-insensitive `AS` prefix: use `AS63`, not a bare `63`.
Start-end ranges are not supported in this mode; supply CIDRs instead.

### Origin Mapping

1. Select **Origin mapping**.
2. Paste IPs, CIDRs, or start-end ranges, or import a file.
3. Choose a routing date and select **Resolve networks**.
4. Review prefixes, origin ASNs, organizations, statuses, and source dates.
5. Use the text filter and status selector to narrow displayed results.
6. Export the lookup as CSV or JSON.

The **Example** button replaces the current input with examples for the selected
mode. Switching modes hides previous results. Export results you need before
replacing them with another lookup.

## Import formats

Paste text or import `.txt`, `.csv`, or `.tsv` files. The UTF-8 text limit is
256 KiB (262,144 bytes). Blank lines and lines beginning with `#` after leading
whitespace are ignored. Invalid entries remain visible as individual errors;
malformed CSV or an oversized batch can reject the entire import.

### Plain text

Observed BGP paths:

```text
AS63
129.55.110.9
129.55.0.0/24
```

Origin Mapping:

```text
# One resource per line
129.55.110.9
129.55.0.0/24
129.55.110.1-129.55.110.20
2606:4700:4700::1111
```

Headerless comma-separated values also work. One entry per line is easier to
inspect. Do not mix metadata into headerless input; those cells become resources.

### CSV or TSV with a header

Include exactly one recognized resource column:

`ip`, `ip_address`, `address`, `cidr`, `network`, `prefix`, `range`, `resource`, `asn`.

Header matching ignores case and converts spaces to underscores. Other columns
are ignored and are not carried into results or exports.

```csv
label,resource
Origin investigation,AS63
Single address,129.55.110.9
Network investigation,129.55.0.0/24
```

This example is for Observed BGP paths. Remove the ASN row for Origin Mapping.
TSV uses the same rules with tab separators. Files containing both `ip` and
`cidr` headers are rejected because the resource column would be ambiguous.

### Validation details

- URLs, domain names, and IPv6 zone identifiers are not accepted.
- CIDRs normalize to network boundaries: `129.55.110.9/24` becomes
  `129.55.110.0/24`. Origin Mapping records this in its result note.
- Range endpoints must use the same address family and be in ascending order.
- Known special-use inputs are identified using the ranges in `lookup.py`.
  This is not a complete public-address registry or a privacy firewall.

## Interpret the results

### Origin, observed adjacency, and inferred relationship

The **origin AS** is the final AS in an accepted observed path. Its organization
may be a university, enterprise, cloud operator, research network, or ISP.
Identifying the origin does not by itself identify an upstream provider.

The **observed adjacent AS** is the distinct AS immediately before the origin after
consecutive AS prepends are collapsed. The tool classifies this adjacency using
CAIDA's dated relationship dataset.

For this illustrative path:

```text
AS24482 -> AS1828 -> AS13789 -> AS63
```

`AS63` is the origin and `AS13789` is the immediate observed neighbor. `AS1828`
and `AS24482` occur farther along the observed path; the tool does not claim they
are direct providers of AS63. Example paths are not a promise of current routing.

### Three layers of interpretation

- **Observed fact:** in `AS367 -> AS636`, AS367 appears immediately before
  the origin AS636 in the collected BGP path for the displayed prefix and time.
- **Relationship inference:** separate, dated CAIDA data may classify AS367
  as a transit provider, peer, or customer of AS636. Missing classification
  remains unknown; adjacency alone does not establish a commercial relationship.
- **Security interpretation:** that adjacency represents potential ingress worth
  investigating. It does not confirm traffic flow, a reachable entry point,
  a security perimeter, an attack path, or a vulnerability.

Here, "routing exposure" means visibility of external routing adjacencies,
not a scan of exposed services. Other routes and private connections may be
absent from collector observations. Provider identification is supporting
context, not the primary conclusion.

### Relationship labels

| Label | Meaning relative to the origin |
| --- | --- |
| Transit provider | CAIDA infers that the neighbor is a provider of the origin. |
| Peer | CAIDA infers a peer relationship between the neighbor and origin. |
| Customer | CAIDA infers that the neighbor is a customer of the origin. |
| Unknown | No usable classification is available; the neighbor is not assumed to be a provider. |

These are inferences, not verified contracts. The tool respects the direction of
provider/customer relationships. See
[CAIDA AS Relationships](https://www.caida.org/catalog/datasets/as-relationships/).

### Counts and evidence

- **RIS peers:** distinct collector-peer sessions observing paths through a
  neighbor, deduplicated across prefixes. Not a count of end users or independent networks.
- **Collectors:** RIS collection points represented in the observations.
- **Path/prefix combinations:** distinct normalized AS-path and prefix pairs.
  The same path observed for two prefixes is two combinations.
- **Prefixes:** distinct destination prefixes in the group.
- Expanded paths include their prefix, collector names, and peer count.
- A direct observation containing only the origin does not invent a provider.

Counts measure visibility in the returned data, not bandwidth, traffic share,
physical links, network quality, or confidence. Fewer observations do not
necessarily mean an adjacency is less important.

### Status values

| Status | Interpretation |
| --- | --- |
| `mapped` | Origin Mapping found unambiguous coverage; Observed BGP paths processed observed routes. |
| `multiple_networks` | Different parts of an origin-mapping input map to different origin networks. |
| `partial` | Some of an origin-mapping input is covered and some is not observed. |
| `ambiguous` | An origin-mapping result contains multiple origins or an AS set. |
| `multiple_origins` | A segment has more than one reported origin ASN. |
| `as_set` | A segment has unordered/ambiguous AS-set origin evidence. |
| `not_observed` | No matching route was found in the selected data; this does not prove globally unrouted space. |
| `special_use` | The complete input lies within a recognized special-use range. |
| `invalid` | The individual resource could not be parsed. |
| `error` | A lookup failed; this is not evidence that no route exists. |

Observed BGP paths uses `mapped`, `not_observed`, `special_use`, `invalid`, and `error`.
Its `mapped` status does not guarantee a known name, a provider classification,
or even an observed adjacent AS.

## Saved investigations and comparisons

These features apply to **Observed BGP paths**, not Origin Mapping. They support
repeatable analysis of public observations, not proof of all real-world routing
dependencies. Independent, time-aligned operator evidence is still required to
measure accuracy or identify connections missed by public collectors.

### Capture and save an investigation

1. Select **Observed BGP paths** and enter up to 20 ASNs, IPs, or CIDRs.
2. Choose **Latest**, or **Historical** and a date above the lookup button.
3. Expand **Save and compare investigations**.
4. Select **Capture investigation**. This makes a new lookup using those inputs
   and settings; it does not retroactively capture a previous ordinary lookup.
5. Review the snapshot, provenance, warnings, and per-input replay checks.
6. Select **Export investigation ZIP** and keep the file on your computer.

Archives expire with their jobs after one hour and are lost on restart. There
is a 64 MB retained-archive budget; the oldest archive can be evicted sooner.
Export promptly. Failed or special-use inputs remain in the bundle with an
explicit unavailable replay status; they are never reported as verified routes.

### Open and replay without external queries

1. Start the local app normally; Internet access is not needed for saved bundles.
2. Expand **Save and compare investigations**, select **Open investigation**, and
   choose an exported ZIP (maximum 32 MB).
3. The server verifies member sizes and checksums, then reprocesses the saved
   evidence locally. No source URL in the imported file is fetched.
4. Select **Inspect snapshot** to browse either saved snapshot. JSON export is
   available for that snapshot. Export the ZIP to retain the original evidence.
5. Select **Replay saved evidence** to repeat the check using the installed code.

For an offline command-line inspection/replay:

```sh
python3 investigations.py routing-investigation.zip > replay-report.json
```

Exit 0 means the bundle was inspected without a replay mismatch; some inputs
may still be unavailable. Exit 1 indicates a replay mismatch; exit 2 indicates
an invalid bundle or read failure. Always inspect per-input statuses.

A match verifies route filtering, prepend normalization, exclusions, grouping,
and application of **saved enrichment values**. It does not independently
repeat CAIDA dataset parsing or authenticate upstream evidence. The interface
shows capture and replay code fingerprints; old bundles may differ under newer
processing code. Mismatched saved result tables are hidden, and comparison is
unavailable for that input. Original evidence remains in the ZIP.

### Compare two dates

1. Enter the same target inputs used for the investigation.
2. In **Save and compare investigations**, choose **Earlier date** and
   **Later date**. Both use observations at 12:00 UTC; the later date must follow
   the earlier date and must not be in the future.
3. Select **Compare dates** and wait for both snapshots.
4. Expand **All observations**, **Common reporting peers**, and
   **Relationship inferences** for each input.
5. Inspect either snapshot, export the comparison JSON, and export the ZIP
   containing both snapshots, their raw evidence, and the saved comparison.

Changes are keyed by origin AS, immediate adjacent AS, and prefix. The labels
are **Newly observed adjacency**, **Previously observed adjacency not seen**,
**Observed path changed**, **Observation coverage changed**, and
**Relationship inference changed**. Source dates, excluded paths, and missing
enrichment warnings remain visible. A failed lookup is unavailable, not a
route disappearance. Direct-origin observations are counted separately and
never assigned an invented adjacent network.

Common peers are collector-peer sources reporting selected target routes at
both times, not all active RIS sessions. Restricting to them can hide losses;
it is a sensitivity check alongside the full comparison, not a bias correction
or independent validation. Counts are not traffic shares or confidence scores.
Two snapshots cannot establish the exact change time, intermediate events,
physical connection additions/removals, or an attack path.

### Bundle format and limits

Version 1 contains exactly `manifest.json`, `investigation.json`, and
`SUMMARY.txt`. The manifest hashes the latter two with SHA-256 and records their
byte lengths. Checksums detect accidental corruption, not malicious fabrication
or source authenticity. Imports do not extract files, execute code, or follow
URLs, and reject unknown/duplicate members and unsupported versions.

`investigation.json` records input values, requested and observed times,
generation time, Python version, Git revision and dirty state where available,
processing source fingerprints, processing limits, results, warnings,
comparison output, and evidence. Each `risBase64` field encodes the exact RIPE
response body received (including its JSON envelope), retained even for cached
responses. Replay uses the observation time rather than treating capture time
as live routing time. Comparisons use all selected raw routes, not the capped
path list shown in the ordinary results table.

CAIDA compressed source files are identified by URL, snapshot date, and SHA-256.
The bundle includes only the result-relevant organization names and relationship
classifications needed for processing replay; **full CAIDA source datasets are
not included**. Reproducing their original parsing requires separately obtaining
the matching datasets and code. Review source terms before sharing any evidence
bundle, including derived enrichment. Queries, observer addresses, and analysis
results are included in exported files.

Limits: 16 MB encoded evidence per snapshot, 32 MB compressed ZIP, 48 MB total
uncompressed members, one or two snapshots, and 20 inputs. Oversized captures
fail explicitly; narrow the query instead of interpreting partial evidence.
The ZIP is a local saved investigation, not a managed archive or backup service.

## Current and historical data

| Data | Latest | Historical |
| --- | --- | --- |
| Observed BGP paths | Latest state returned by RIPE RIS | Selected day at 12:00 UTC |
| Origin mapping | Latest available daily snapshot per address family | Latest snapshot within the selected UTC day |
| Organization names | Newest snapshot on or before the routing observation date | Same rule |
| Relationship labels | Newest snapshot on or before the routing observation date | Same rule |

"Latest" is not instantaneous or continuously streaming data. Check displayed
source dates; IPv4 and IPv6 origin results can have different timestamps.

RIPE's BGP State endpoint reconstructs routing state from a preceding RIB and
subsequent updates. The tool does not approximate history by collecting all
announcements in a time window. See the
[RIPE BGP State documentation](https://stat.ripe.net/docs/data-api/api-endpoints/bgp-state).

The date selector accepts May 9, 2005 through today, but availability varies by
dataset, address family, and resource. Missing exact-day routing data is not
silently replaced with a different day. Organization and relationship snapshots
can intentionally be older; their dates are displayed.

If enrichment is unavailable:

- Observed BGP paths preserves observed paths with warnings, missing names, or
  unknown relationships as appropriate.
- Origin Mapping requires a usable dated organization dataset for the address
  family. Failure is an error. An individual ASN absent from an otherwise usable
  organization dataset can still be returned without a name.

Use **Save and compare investigations** for an evidence-backed two-date
comparison. Continuous monitoring, automatic timelines, and alerts are not
implemented; changes between observation times can remain invisible.

## Command-line usage

The CLI runs without the web server. Results go to standard output and progress
messages to standard error.

```sh
# Current observed BGP paths for an origin AS
python3 lookup.py --paths AS63

# Historical paths for a specific IP
python3 lookup.py --paths 129.55.110.9 --date 2026-08-01

# Map IPs and CIDRs to origin networks
python3 lookup.py 129.55.110.9 129.55.0.0/24

# Import and export historical origin mappings
python3 lookup.py --input networks.csv --date 2026-08-01 --format csv > origins.csv

# Export observed-path evidence
python3 lookup.py --paths --input resources.txt --format csv > observed-paths.csv
python3 lookup.py --paths AS63 > observed-paths.json

# Use a separate dataset cache
python3 lookup.py --paths AS63 --cache ./lookup-cache

# Show command options
python3 lookup.py --help
python3 server.py --help
```

| CLI option | Default | Purpose |
| --- | --- | --- |
| Positional resources | None | One or more resources to look up. |
| `--input PATH` | None | UTF-8 input file; takes precedence over positional resources. |
| `--paths` | Off | Use Observed BGP paths instead of Origin Mapping. |
| `--date YYYY-MM-DD` | `latest` | Historical date; `latest` is also accepted explicitly. |
| `--format json\|csv` | `json` | Output format. |
| `--cache PATH` | `data/` beside the script | Downloaded public dataset storage. |

Exit code `1` indicates an invalid/error result or a command-level failure. Other
statuses, including `not_observed`, can return `0`. Automation should inspect
result statuses, not treat exit code `0` as proof that a resource was mapped.

## Exports and result structure

**CSV** supports spreadsheets and reporting. Origin exports contain a row for
each segment/origin combination. Path exports contain retained path/prefix
evidence for each origin-neighbor pair. Formula-like values are escaped; still
treat source-derived strings as untrusted data.

**JSON** preserves grouping, warnings, counts, names, statuses, and source metadata.
Use it when scripts need richer context.

Origin Mapping filters affect the table, not its exports. The table shows at
most 500 matching segments; exports include the complete result within processing
limits. Observed-path exports contain retained evidence only, with truncation
notices when capped. Save needed exports: the server is not a durable archive.

| JSON scope | Important fields |
| --- | --- |
| Both modes | `requestedDate`, `generatedAt`, `meaning`, `results`, per-input `status`, optional `error` |
| Origin Mapping | `segments`, `prefix`, `origins`, `routing`, `organizations`, optional `normalized` and `note` |
| Observed BGP paths | `kind: "paths"`, `groups`, `asns`, `warnings`, `observation`, optional `relationships`, `organizations`, `skippedPaths` |
| Path group | `origin`, `neighbors`, `peerCount`, `collectors`, `prefixes`, `directObservations` |
| Path neighbor | `asn`, `relationship`, `paths`, `pathCount`, `pathsTruncated`, `peerCount`, `collectors`, `prefixes`, `routeObservations` |

This is an initial integration interface, not a versioned public API. Consumers
must handle missing optional fields and explicit errors.

## Architecture and processing

```text
Standalone browser -> Python job API -> lookup engine -> public data sources
Standalone CLI ----------------------> lookup engine -> public data sources
```

The browser reads files and renders results. Python validates inputs, retrieves
data, builds routing indexes, groups paths, matches relationships, and prepares
CSV output. RIPE performs the underlying routing-state query for Observed BGP paths.

### Observed BGP paths

1. Validate inputs and skip resources fully within known special-use ranges.
2. Request routing state from the fixed RIPEstat BGP State endpoint.
3. For ASN queries, retain paths ending at that ASN, not transit-only matches.
   For IPs, use the longest matching prefix per observation peer. For CIDRs,
   retain overlapping prefixes.
4. Collapse consecutive prepends. Exclude malformed paths, AS sets, and
   nonconsecutive repeated ASNs indicating loops, with an excluded-path count.
5. Group by origin and immediate neighbor; deduplicate observation counts.
6. Add dated CAIDA names and relationship inferences.
7. Return retained evidence, counts, warnings, and provenance.

### Origin Mapping

1. Select daily CAIDA RouteViews prefix-to-AS files for the required address families.
2. Load dated organization data.
3. Apply longest-prefix matching and split ranges at route boundaries, preserving gaps.
4. Preserve multiple origins and AS sets instead of choosing an arbitrary ASN.
5. Return segments, names, statuses, and source dates.

### Relationship to BGPStream

This tool **does not run libBGPStream or PyBGPStream**. For its current purpose,
analyst-directed origin and observed-path investigation, this is primarily an
architecture tradeoff rather than a major missing capability. It keeps setup
simple and avoids native BGPStream installation and local full-MRT ingestion.
It does not, however, make the tool a continuous routing-monitoring service.

The two lookup modes use different routing evidence:

- **Origin Mapping** uses CAIDA's precomputed daily prefix-to-AS files.
- **Observed BGP paths** uses RIPEstat's reconstructed BGP state, not those daily
  prefix-to-AS files. RIPE derives the state from a preceding RIB and subsequent
  updates. Latest and historical path investigations therefore do not require
  running BGPStream locally. See the
  [RIPE BGP State documentation](https://stat.ripe.net/docs/data-api/api-endpoints/bgp-state).

#### When the current approach is appropriate

| Requirement | Current approach |
| --- | --- |
| On-demand origin attribution for IPs and ranges | Supported through Origin Mapping, within its dataset and processing limits. |
| Investigating observed adjacent networks and inferred providers for an origin AS | Supported through Observed BGP paths, subject to collector visibility. |
| Historical, point-in-time observed-path investigation | Supported where upstream data is available; currently queries 12:00 UTC on the selected day. |
| Capturing routing changes throughout a day | Not implemented; isolated point-in-time queries can miss intervening events. |
| Continuous withdrawal or path-change alerts | Requires streaming, state tracking, and additional detection/alerting logic. |
| Large-scale work without relying on RIPE's query API | Would benefit from separate ingestion, indexing, and storage infrastructure. |
| Saving a portable investigation | Supported through bounded ZIP export and offline replay; long-term storage and backups are user-managed. |

The present design depends on upstream query availability, response sizes, and
data coverage. Observed BGP paths also sends resource queries to RIPE NCC, as described
in [Privacy and security](#privacy-and-security). A self-hosted ingestion approach
could provide greater control over processing and retention, but would introduce
storage, compute, updates, and operational responsibilities.

#### What BGPStream would and would not add

BGPStream provides access to historical BGP records and live update streams.
It could support future continuous monitoring or ingestion from additional
collectors. Installing it alone would not implement correct routing-state
reconstruction, a persistent archive, incident detection, or alerts. Those remain
application responsibilities. See the
[BGPStream overview](https://bgpstream.caida.org/docs) and
[PyBGPStream tutorials](https://bgpstream.caida.org/docs/tutorials/pybgpstream).

It would not automatically make provider identification more accurate. Additional
observation sources may improve coverage, but changing the ingestion library does
not prove commercial relationships or expose every private connection. Data
visibility and relationship inference remain separate limitations.

#### Recommended direction

Keep the current architecture for on-demand analyst lookups. Consider BGPStream
when continuous monitoring, additional data sources, query-volume requirements,
or control over retained evidence justify the extra infrastructure.

A smaller potential enhancement is an **exact historical UTC timestamp selector**
instead of the fixed 12:00 UTC query. RIPE's BGP State API already accepts a
timestamp, so that change would not require BGPStream. This is a future option,
not a currently implemented feature, and point-in-time selection would still not
capture every event during an interval.

## Limits, caching, and performance

| Resource | Implemented limit/behavior |
| --- | --- |
| Import text / HTTP job body | 262,144 bytes / 524,288 bytes including JSON overhead |
| Observed BGP paths / Origin Mapping batch | 20 / 1,000 entries |
| RIS response per resource | 12,000,000 bytes and 50,000 routes |
| Origin-neighbor combinations | At most 500 per observed-path input |
| Retained path evidence | At most 1,000 path/prefix combinations per input, divided among neighbors |
| Origin segments / overlapping routes | 5,000 segments per batch / 20,000 routes per input |
| Job execution | One worker; up to three outstanding jobs including the running job |
| Retained jobs | At most 40; expire one hour after creation; restart clears them |
| Browser polling | About every 1.5 seconds, with a 15-minute UI timeout |
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
memory/disk limit. Multiple processes need separate cache directories because
cross-process cache coordination is not implemented.

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

## Local API

| Method and path | Purpose |
| --- | --- |
| `GET /` | Browser interface |
| `GET /api/health` | Process readiness; does not test upstream data availability |
| `POST /api/jobs` | Create a lookup job |
| `GET /api/jobs/{id}` | Read status and the completed result |
| `GET /api/jobs/{id}/export` | Download CSV after completion |

Create a Observed BGP paths job:

```sh
curl --fail-with-body http://127.0.0.1:8765/api/jobs \
  -H 'Content-Type: application/json' \
  --data '{"text":"AS63","date":"latest","mode":"paths"}'
```

HTTP `202` returns an `id` and `token`. Substitute those values below. The
placeholders are not real credentials; keep the URL quoted when editing it:

```sh
curl --fail-with-body \
  -H 'X-Job-Token: <job-token>' \
  'http://127.0.0.1:8765/api/jobs/<job-id>'
```

States are `queued`, `running`, `complete`, and `failed`. A completed job contains
`result`, but individual entries may still have error statuses. Poll sparingly
instead of creating duplicate jobs.

Use `"mode":"origins"` for Origin Mapping. The API defaults to `origins` when
mode is omitted, unlike the browser's Observed BGP paths default. The date defaults
to `latest`. The health response's `maxInputs: 1000` refers to Origin Mapping;
Observed BGP paths is still limited to 20.

With a configured service token, all routes additionally require
`Authorization: Bearer <service-token>`, including static assets and health checks.
There is no separate JSON export route; completed job responses contain the result.

Investigation jobs use `mode: "investigation"` with `text`, `date`, and an
optional later historical `comparisonDate`. Download `/api/jobs/{id}/bundle`
with `X-Job-Token`. POST an `application/zip` body to
`/api/investigations/open` or `/api/investigations/replay` to inspect and reprocess
it without upstream requests. These endpoints retain existing Host/Origin and
configured service-token checks. Invalid ZIPs return 400; oversized uploads 413.
The ordinary JSON job response omits raw evidence and binary archives.

Common HTTP responses: `400` malformed input, `401` missing/incorrect configured
service token, `403` rejected local Host/Origin, `404` unknown/expired job or wrong
job token, `413` oversized body, `415` non-JSON job request, and `429` full job store.

## Configuration and hosting

| Setting | Default | Purpose |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Bind address; keep loopback for local use. |
| `--port` | `8765` | HTTP port. |
| `--cache` | `data/` beside the server | Public dataset cache directory. |
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

## Standalone project

BGP Routing Exposure Lookup is maintained and run as its own project. It is not integrated
into the Mucaro web app and does not require Next.js, Mucaro credentials, or a
Mucaro deployment. Run `python3 server.py` from this repository to use its own
browser interface, or use `lookup.py` directly for command-line lookups.

Committing or pushing this repository updates the standalone source on GitHub.
It does not deploy a hosted lookup service or change Mucaro. Hosting this tool
remains a separate decision subject to the requirements in
[Configuration and hosting](#configuration-and-hosting).

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
| Busy / HTTP `429` | Let work finish; unexpired retained jobs can also fill the store. |
| Job/export unavailable | It expired, the service restarted, or the token is wrong. Rerun the lookup. |
| Unauthorized after setting a token | The raw server now needs bearer authentication, including its UI. Use a trusted gateway/client. |
| Private GitHub repo shows 404 | Sign in with repository access or use a supplied ZIP; local execution does not need GitHub access. |

For a corrupt cached dataset, stop the service and move the affected cache file
aside before retrying. Caches are replaceable downloads, but restarting clears
in-memory jobs. Do not remove source files or saved analyst exports.

The browser's 15-minute timeout does not cancel a server-side job. There is no
cancellation endpoint in this version.

## Development and project structure

Run tests from the repository root:

```sh
python3 -m unittest discover -s . -p 'test_*.py'
```

The test suite includes fixture/mock-based processing and local HTTP tests, with no live provider requests.
It covers imports, CIDR normalization, longest-prefix matching, range boundaries,
multiple origins, dated dataset selection, relationship direction, path
normalization, observer deduplication, explicit upstream errors, job-token access,
expiration, and CSV formula escaping.

For behavior changes, add regression fixtures, exercise the browser and CLI,
check invalid/missing-data cases, and verify export provenance. Inspect desktop
and mobile layouts for UI changes. Passing tests does not guarantee upstream
availability or correctness of inferred business relationships. No hosted CI
workflow is included in this package.

```text
bgp-routing-exposure-lookup/
  README.md                 Setup and operational guidance
  THIRD_PARTY_NOTICES.md     Icon attribution and license notices
  .gitignore                Cache, environment, and metadata exclusions
  lookup.py                 Imports, datasets, origin lookup, and CLI
  paths.py                  RIS paths, relationship matching, and export
  server.py                 Local HTTP server and in-memory job API
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

## Known limitations

- Observations depend on collector visibility; they do not enumerate all
  providers, private peers, physical links, or Internet routes.
- AS paths are control-plane evidence, not packet traces from your location.
  Latency, reachability, bandwidth, and geography are not measured.
- Names and relationship inferences may lag reality or be incorrect.
  Organization country is registration context, not IP geolocation.
- IP/CIDR queries can return multiple origins. CIDR path results retain overlapping
  evidence, unlike Origin Mapping's disjoint address-range partitions.
- Observed BGP paths normalizes prepends and excludes ambiguous/looping paths; it is
  not a raw MRT archive. Only origin-neighbor relationships are classified.
- RPKI validation, route-leak/hijack verdicts, WHOIS abuse contacts, traceroute,
  alerts, and automatic mitigation are not implemented.
- Exported path evidence may be capped even when counts describe more observations.
- Jobs and live RIS response caches are in memory; exported ZIPs preserve investigations. There is no saved-investigation database,
  user account system, or cross-device synchronization.
- Cached files do not constitute a supported fully offline mode.
- The original code has not yet been assigned an open-source license.

## Data sources and licensing

| Source | Use |
| --- | --- |
| [RIPEstat BGP State / RIPE RIS](https://stat.ripe.net/docs/data-api/api-endpoints/bgp-state) | Current/historical observed AS paths. |
| [CAIDA RouteViews Prefix-to-AS](https://www.caida.org/catalog/datasets/routeviews-prefix2as/) | Daily prefix-to-origin mappings. |
| [CAIDA AS Organizations](https://www.caida.org/catalog/datasets/as-organizations/) | Dated ASN and organization names. |
| [CAIDA AS Relationships](https://www.caida.org/catalog/datasets/as-relationships/) | Dated serial-2 provider/customer and peer inferences. |
| [BGPStream](https://bgpstream.caida.org/docs) | Related ingestion framework, not a runtime dependency. |

Data remains subject to each provider's terms. Review them before redistribution
or public/commercial hosting. This package does not bundle CAIDA datasets, and
publishing source code does not grant rights to redistribute third-party data.

Lucide/Feather-derived icon notices are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). They cover the identified assets,
not all original application code. Choose an explicit code license before
presenting this as an open-source project. Keep data-provider terms separate.

## Glossary

| Term | Meaning in this tool |
| --- | --- |
| AS / ASN | Autonomous system and its identifier, written as `AS63`. |
| Origin AS | Final AS in an accepted observed route path. |
| AS path | Ordered AS sequence, read toward the origin. |
| Observed adjacent AS | Distinct AS immediately before the origin. |
| CIDR / prefix | Address block such as `129.55.0.0/24`. |
| Longest-prefix match | Prefer the most specific matching route for an address. |
| RIB | Routing Information Base, a routing-state baseline. |
| RIS / RRC | RIPE Routing Information Service and its remote route collectors. |
| Collector peer | BGP session supplying routes to a collector. |
| Prepending | Consecutive repetition of an ASN in an advertised path. |
| MOAS | Multiple origin ASNs reported for a prefix. |
| AS set | Unordered membership that does not establish a single ordered AS path. |
| Provenance | Source links and timestamps supporting a result. |
