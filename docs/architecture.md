# Architecture and design decisions

[Back to README](../README.md) · Run commands from the repository root.

- [Architecture and processing](#architecture-and-processing)
- [Standalone project](#standalone-project)

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
in [Privacy and security](operations.md#privacy-and-security). A self-hosted ingestion approach
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

## Standalone project

BGP Routing Exposure Lookup is maintained and run as its own project. It is not integrated
into the Mucaro web app and does not require Next.js, Mucaro credentials, or a
Mucaro deployment. Run `python3 server.py` from this repository to use its own
browser interface, or use `lookup.py` directly for command-line lookups.

Committing or pushing this repository updates the standalone source on GitHub.
It does not deploy a hosted lookup service or change Mucaro. Hosting this tool
remains a separate decision subject to the requirements in
[Configuration and hosting](operations.md#configuration-and-hosting).
