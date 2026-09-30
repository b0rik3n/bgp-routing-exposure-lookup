# Múcaro | BGP Routing Exposure Lookup

**It maps an organization’s observed internet connections to help analysts
investigate external dependencies and changes.**

This tool helps us understand which networks sit between an organization and the
wider internet. It uses publicly available routing information to show connections
that have been observed and how they change over time.

Think of it as studying a road map around a building: it helps identify possible
approaches, but it doesn’t tell us which road a particular visitor took—or whether
any doors are unlocked.

Investigate **which external networks are observed immediately before a target
origin AS, for which prefixes, and how those observations change over time**.
Use public BGP observations, separately inferred relationships, and saved evidence
to investigate routing dependencies. Provider identification is supporting context.

**Status:** local analyst/research prototype. It does not measure your traffic's
actual path, identify exploitable entry points, or prove an organization's complete
external connectivity. The bundled server is not a production public service.

## Contents

- [Quick start](#quick-start)
- [Choose a lookup mode](#choose-a-lookup-mode)
- [Worked investigation](#worked-investigation)
- [Imports, progress, and cancellation](#imports-progress-and-cancellation)
- [Privacy and operating limits](#privacy-and-operating-limits)
- [What the evidence cannot establish](#what-the-evidence-cannot-establish)
- [Documentation](#documentation)
- [Questions and feedback](#questions-and-feedback)
- [Data sources and licensing](#data-sources-and-licensing)

## Quick start

You need **Python 3.10+**, a modern browser, working HTTPS certificate trust,
Internet access for live lookups, and a writable cache directory. Origin Mapping
can use several hundred MB of memory. The local workflow has been verified on
macOS; Windows and Linux have not been validated for this release.

The application uses Python's standard library. No Python packages, Node.js,
API key, or separate database installation are required. Python's bundled SQLite
stores the request counter and timing automatically. No GitHub login is required
to clone this public repository or run an extracted copy.

### 1. Get the code and start the server

In Terminal:

```sh
git clone https://github.com/bayanilla/bgp-routing-exposure-lookup.git
cd bgp-routing-exposure-lookup
python3 --version
python3 server.py
```

If you already downloaded and extracted the project, open Terminal in its folder
and run the last two commands. These examples use a macOS/Linux-style shell.

### 2. Open the interface and run a lookup

1. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).
2. Leave **Observed BGP paths** selected and enter `AS3333`.
3. Select **Latest**, then **Find observed paths**.
4. Expand a path/prefix summary. AS names appear inline when available.
5. Review warnings and source dates before exporting **CSV** or **JSON**.

AS3333 is RIPE NCC’s network and is used as a public routing example. No
affiliation or endorsement by RIPE NCC is implied.

The first lookup can take longer while public datasets download. Keep the terminal
running; stop the server with `Ctrl+C` when finished. Opening `web/index.html`
directly does not run the app. If port 8765 is occupied, start with
`python3 server.py --port 8766` and open [port 8766](http://127.0.0.1:8766).
See [troubleshooting](docs/operations.md#troubleshooting) for other problems.

## Choose a lookup mode

| | Observed BGP paths | Origin Mapping |
| --- | --- | --- |
| Question | Which networks appear immediately before the origin AS? | Which AS announces the prefix covering an address or range? |
| Inputs | ASN (`AS3333`), IP, or CIDR | IP, CIDR, or start-end range |
| Routing source | RIPE RIS paths via RIPEstat | CAIDA RouteViews prefix-to-AS snapshots |
| Supporting data | CAIDA names and inferred relationships | CAIDA names |
| History | Observation at 12:00 UTC on the selected date | Latest available routing snapshot within the selected date |
| Import limit | 1,000 entries | 1,000 entries |

Neither mode probes the destination. Historical availability and collector coverage
vary. See [date semantics](docs/user-guide.md#current-and-historical-data).

## Worked investigation

**Question:** Which networks are observed adjacent to AS3333 for a selected prefix,
and does that observation differ between two dates?

### 1. Inspect the evidence

Run the quick-start lookup and expand a path. The following is an **illustrative
example**, based on a RIS observation at 2026-09-30 07:59:47 UTC.
It is not a promise of current routing; your results may differ:

```text
Prefix: 193.0.0.0/21
Path:   AS24482 → AS20562 → AS1103 → AS3333
```

| Layer | Supported interpretation |
| --- | --- |
| Observed fact | AS1103 immediately precedes origin AS3333 in this path for this prefix at the recorded observation time. |
| Relationship inference | A separate CAIDA snapshot may classify AS1103 as provider, peer, or customer; absent evidence remains unknown. |
| Security interpretation | This is a routing dependency worth investigating, not a confirmed ingress point or vulnerability. |

AS20562 and AS24482 appear farther along this path; that does not make them direct
neighbors of AS3333. Record the **RIS observation time**, **collector coverage**,
**CAIDA source dates**, and any **warnings or truncation**. Peer counts measure
visibility in the collected data, not traffic share or confidence.

### 2. Save a reproducible investigation

1. Keep the target in the input field and select the desired routing date.
2. Expand **Save and compare investigations**.
3. Select **Capture investigation**. This starts a new capture; it does not attach
   evidence retroactively to the ordinary lookup you just ran.
4. Review the results and replay checks, then select **Export investigation ZIP**.
5. Use **Open investigation** to reopen that ZIP later without external queries.

A matching replay means the saved evidence reproduces the processing results.
It does **not** authenticate the source or independently verify CAIDA enrichment.
Checksums detect accidental changes; they do not prevent fabricated evidence.

### 3. Compare two dates

1. Keep the same target inputs. Under **Save and compare investigations**, choose
   **Earlier date** and **Later date**; both use 12:00 UTC.
2. Select **Compare dates** and review both snapshots' statuses and source dates.
3. Expand **All observations**, **Common reporting peers**, and
   **Relationship inferences**. Check whether the reporting peers changed too.
4. Export the comparison JSON and the investigation ZIP containing both snapshots.

If an adjacency appears only in the later snapshot, report it as **newly observed**,
not a proven new connection. If a snapshot failed, the comparison is unavailable;
that is not evidence of disappearance. Common-peer comparisons are a visibility
check, not a correction for every collector bias.

To decide whether a change is expected, compare it with independent, time-aligned
operator records or authorized network measurements. Two snapshots cannot tell
you the exact change time or what happened between them. There is no continuous
monitoring. See the [investigation guide](docs/user-guide.md#saved-investigations-and-comparisons)
for bundle contents, replay limitations, and detailed comparison labels.

## Imports, progress, and cancellation

Paste one resource per line, or select **Import file** for CSV, TSV, or TXT.
A CSV can use a single recognized resource column, for example:

```csv
resource
AS3333
193.0.0.1
193.0.0.0/24
```

ASNs require the `AS` prefix and work only in Observed BGP paths. Both modes
accept up to **1,000 entries** within **262,144 bytes** of input text. Other CSV
columns are ignored; normalized duplicate targets are collapsed for server path
lookups and captures. See [all import rules](docs/user-guide.md#import-formats).

- **Progress:** current target, processed, completed, failed, special-use skipped,
  and remaining inputs. Comparisons show each snapshot separately.
- **Warnings:** review failed or unprocessed inputs, unavailable enrichment,
  partial coverage, and truncated evidence. Processing finished does not mean
  every entry succeeded or that routing visibility is complete.
- **Cancel lookup:** stops future work; an in-flight operation may finish first.
  Completed ordinary results remain exportable. Interrupted captures/comparisons
  do not produce an incomplete ZIP. Closing a tab does not cancel the job.

## Privacy and operating limits

**Local interface does not mean private queries.** Live path lookups, captures,
and comparisons send normalized targets and requested observation times to RIPE,
which also sees your public source IP. CAIDA receives dataset download requests.
Offline bundle replay makes no external queries. Exports are unencrypted and may
contain sensitive investigation context. Read [query privacy](docs/operations.md#query-privacy)
before submitting confidential targets.

| Behavior | What to expect |
| --- | --- |
| RIPE pacing | One active request, then a two-second pause, shared across server tabs and job types; cache reuse, deduplication, and bounded retries reduce load. |
| Daily count | Notification at 1,000 attempts; no daily cap. Retries count, cache hits do not. |
| Large batches | 1,000 uncached requests need about 33 minutes of pacing alone, plus retrieval/processing. Two-date comparisons can double requests. |
| Capture size | 16 MB encoded evidence per snapshot; 32 MB ZIP; 48 MB expanded members. A 1,000-entry batch may still need splitting. |
| Result retention | Up to one hour; older finished jobs can be evicted earlier at 40 jobs or the shared 128 MB result/ZIP budget. Restart clears results. Save exports promptly. |
| Local access | Keep the default loopback binding. Connection protections do not make this a production public server. |

The storage budget is not a total process-memory cap. The request counter persists
in SQLite; lookup results do not. See [request pacing](docs/operations.md#respectful-ripe-requests-and-cancellation),
[progress and connection protections](docs/operations.md#progress-result-retention-and-connection-protection),
and [full limits](docs/operations.md#limits-caching-and-performance).

## What the evidence cannot establish

Public collectors do not reveal every provider, private peer, or physical link.
Names and inferred relationships may be incomplete or stale. The tool does not
perform traceroute, RPKI validation, route-leak/hijack verdicts, vulnerability
scanning, or automatic mitigation. It is not yet validated against independent
ground truth as a complete measurement of organizational routing dependencies.
See [known limitations](docs/user-guide.md#known-limitations).

## Documentation

| Guide | Use it for |
| --- | --- |
| [Analyst guide](docs/user-guide.md) | Browser workflows, input formats, statuses, interpretation, captures, comparisons, dates, and glossary. |
| [Operations and security](docs/operations.md) | RIPE pacing, progress, cancellation, resource limits, privacy, hosting, and troubleshooting. |
| [CLI, API, and exports](docs/reference.md) | Commands, endpoints, authentication, result fields, and export formats. |
| [Architecture](docs/architecture.md) | Processing decisions, BGPStream tradeoffs, and standalone deployment scope. |
| [Development](docs/development.md) | Test commands, validation scope, and current project structure. |

## Questions and feedback

Use [GitHub Issues](https://github.com/bayanilla/bgp-routing-exposure-lookup/issues)
for questions about the tool, bug reports, and feature requests. Search existing
issues first. For a bug report, include your operating system, Python version,
steps to reproduce, and expected versus actual behavior using a non-sensitive
example.

Issues are public. Do not post confidential targets, investigation bundles,
credentials, or sensitive network details. Remove sensitive information from
screenshots and logs before sharing them.

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
not all original application code. **The application currently has no open-source
license.** Public visibility is not an unrestricted reuse grant. Keep provider
data and third-party asset terms separate.
