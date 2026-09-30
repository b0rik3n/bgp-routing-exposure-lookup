# Analyst guide

[Back to README](../README.md) · Run commands from the repository root.

- [Browser workflow](#browser-workflow)
- [Import formats](#import-formats)
- [Interpret the results](#interpret-the-results)
- [Saved investigations and comparisons](#saved-investigations-and-comparisons)
- [Current and historical data](#current-and-historical-data)
- [Known limitations](#known-limitations)
- [Glossary](#glossary)

## Browser workflow

### Observed BGP paths

1. Select **Observed BGP paths**.
2. Enter an ASN, IP, or CIDR, or choose **Import file**.
3. Select **Latest** or **Historical** and a UTC date.
4. Select **Find observed paths**.
5. Review each origin, its observed adjacent networks, relationship labels, and collector counts.
6. Expand path/prefix summaries. AS names appear inline beside each ASN when available.
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
| `not_requested` | Processing stopped before this input completed; do not interpret it as missing routing. |

Observed BGP paths uses `mapped`, `not_observed`, `special_use`, `invalid`, `error`, and `not_requested`.
Its `mapped` status does not guarantee a known name, a provider classification,
or even an observed adjacent AS.

## Saved investigations and comparisons

These features apply to **Observed BGP paths**, not Origin Mapping. They support
repeatable analysis of public observations, not proof of all real-world routing
dependencies. Independent, time-aligned operator evidence is still required to
measure accuracy or identify connections missed by public collectors.

### Capture and save an investigation

1. Select **Observed BGP paths** and enter up to 1,000 ASNs, IPs, or CIDRs.
2. Choose **Latest**, or **Historical** and a date above the lookup button.
3. Expand **Save and compare investigations**.
4. Select **Capture investigation**. This makes a new lookup using those inputs
   and settings; it does not retroactively capture a previous ordinary lookup.
5. Review the snapshot, provenance, warnings, and per-input replay checks.
6. Select **Export investigation ZIP** and keep the file on your computer.

Archives expire with their jobs after one hour and are lost on restart. The
shared 128 MB result-and-archive budget can evict older finished jobs sooner.
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
uncompressed members, one or two snapshots, and 1,000 inputs. Oversized captures
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
