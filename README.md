# BGP Provider Lookup

Find observed paths and incoming providers for an ASN, IP, or CIDR, or import
IPv4/IPv6 addresses, CIDRs, and start-end ranges to identify their origin
ASNs and network organizations. This directory is self-contained and
can become its own GitHub repository. No Mucaro, Node, database, API key, or Python
package dependency is required for the standalone tool. Requires Python 3.10+.

## Run locally

```sh
python3 server.py
```

Open http://127.0.0.1:8765. Provider Paths is the default view; enter `AS63`
or an IP/CIDR. Switch to Origin Mapping for bulk daily mappings and range imports.
Paste input or import CSV, TSV, or TXT. Select Latest or a historical UTC date.
CSV files can have one named address column:
`ip`, `ip_address`, `address`, `cidr`, `network`, `prefix`, `range`, `resource`, or `asn`.
Other CSV columns are ignored. Headerless files accept comma-separated values
or one value per line. Origin imports allow 1,000 entries; provider paths allow
20 entries. Both have a 256 KB limit. Provider Paths accepts ASNs, IPs, and CIDRs,
but requires arbitrary start-end ranges to be converted to CIDRs first.

```sh
python3 lookup.py 129.55.110.9 129.55.0.0/24
python3 lookup.py --input networks.csv --date 2026-08-01 --format csv
python3 lookup.py --paths AS63
python3 lookup.py --paths 129.55.110.9 --date 2026-08-01 --format csv
python3 -m unittest discover -s . -p 'test_*.py'
```

The first lookup downloads public datasets. Subsequent lookups use the local
`data/` cache. New dates can take tens of seconds or longer. Current mappings
mean the latest available daily snapshot, not the real-time routing table.
The interface displays source dates and exports CSV or JSON with provenance.
If a selected date is unavailable, that family returns an error; the tool does
not silently substitute a different date.

## Provider paths

RIPE RIS supplies BGP routing state reconstructed from a RIB plus subsequent
updates. The tool keeps paths terminating at the requested origin AS, collapses
consecutive AS prepends, and identifies the distinct ASN immediately before
the origin. AS sets, malformed paths, and paths with loops are excluded with
a visible count. IP lookups select the longest matching prefix per observation
peer; CIDR lookups retain overlapping routes. Names come from CAIDA AS Organizations.

The immediate neighbor's relationship to the origin is inferred using CAIDA's
dated serial-2 AS Relationships dataset: provider, peer, customer, or unknown.
It is not contractual proof. Missing relationship data leaves the neighbor
unknown instead of assuming it is an ISP. Neighbor observations, prefixes,
collector names, and full AS paths can be inspected and exported.

Latest uses RIS's latest available observation and displays its timestamp.
Historical dates query 12:00 UTC. Organization and relationship snapshots are
chosen on or before that observation date, which does not eliminate inference
error or dataset lag. RIS coverage is incomplete and vantage-point dependent;
these are not measurements from the user's network. Counts of distinct
collector-peer sessions are neither independent network counts nor traffic share.

Path requests send the entered public IP, prefix, or ASN to RIPE NCC. They never
connect to the imported destination. Known private/special-use IPs stay local.
Responses are memory cached for 5 minutes (latest) or 1 hour (historical), up to
8 responses. Responses over 12 MB or 50,000 routes return an explicit error.
Evidence is capped at 1,000 path/prefix combinations per input, divided among
neighbors, and truncation is disclosed in UI/exports. Counts reflect the returned
RIS observations even when stored evidence is limited.

## Origin mapping

`IP -> longest matching BGP prefix -> origin ASN(s) -> organization name`

- An origin organization can be an ISP, cloud provider, university, enterprise,
  or another organization. BGP origin alone does not prove the retail ISP or
  upstream transit provider, legal ownership, or physical location.
- Ranges are split at route boundaries. More-specific routes override covering
  routes. Multiple origins and ambiguous AS sets are preserved.
- Missing routes are labeled `not_observed`, not definitively unrouted. CAIDA's
  daily files derive from a single RouteViews collector per address family.
- Historical routing uses a snapshot taken during the selected UTC day.
  Organization names use the newest available organization snapshot on or
  before that routing date. Both timestamps are visible. Registration data may
  lag actual organizational changes.
- Organization country is registration context, not IP geolocation.
- Default routes are excluded. Known private and special-use inputs are flagged.
- IPv4 routing availability starts in May 2005; IPv6 starts in January 2007.
  Organization mapping availability is independent; missing data is an error.
- Results are limited to 5,000 segments per batch and 20,000 overlapping routes
  per input. Large ranges return an explicit error instead of truncating silently.

## Relationship to BGPStream

Origin Mapping uses CAIDA's precomputed **RouteViews prefix-to-AS daily
datasets**. Provider Paths uses RIPEstat's BGP State API, based on RIS data.
Neither runs the libBGPStream runtime. This makes bulk mapping and historical
daily lookups portable without compiling native C dependencies or downloading
entire MRT RIB files. The data is derived from BGP routing observations.

Continuous live streaming or a self-hosted BGP archive would require a
BGPStream ingestion worker that replays a RIB plus subsequent updates and
withdrawals. Simply collecting announcements from a time window would produce
misleading historical state. RIPE RIS currently supplies that reconstructed
state for the Provider Paths view.

Sources:

- https://www.caida.org/catalog/datasets/routeviews-prefix2as/
- https://www.caida.org/catalog/datasets/as-organizations/
- https://bgpstream.caida.org/docs
- https://stat.ripe.net/docs/data-api/api-endpoints/bgp-state
- https://www.caida.org/catalog/datasets/as-relationships/

CAIDA's dataset Acceptable Use Agreement applies separately from the code.
Review the linked dataset terms before redistribution or public/commercial use.
Do not commit or redistribute downloaded datasets in the GitHub repository.
Icons are from Lucide; see THIRD_PARTY_NOTICES.md. Choose a license for the
original code before publishing this as an open-source repository.

## Mucaro integration

From the Mucaro root, run `python3 tools/bgp-provider-lookup/server.py` and the
usual Next.js development server. Open `/network-lookup`. In development,
Mucaro's API defaults to the loopback lookup service on port 8765. Both interfaces
use the same web component and Python engine; no separate algorithm is maintained.

The Next.js API forwards only validated import/job requests to an operator-set
service URL. It never fetches submitted IPs, CIDRs, or arbitrary URLs. Imports
are rate limited; result requests require a per-job secret token. Existing
Mucaro APIs and mobile contracts are unchanged.

For a hosted Mucaro deployment, run this service as a separate persistent worker
behind HTTPS. Set `BGP_LOOKUP_SERVICE_URL` and the same random
`BGP_LOOKUP_SERVICE_TOKEN` (32+ characters) in both environments. The token stays
server-side. The standalone server requires a token to bind beyond loopback.
Serve remote end-user access through Mucaro, not the token-protected raw server.
The Python standard-library HTTP server is intended for local review; production
hosting, authentication/access policy, TLS termination, and operations need to
be finalized before public deployment. Nothing here provisions or deploys it.

Jobs live in memory for up to one hour, require a secret access token, and are
not persisted. A restart clears them. Origin Mapping never sends uploaded IPs
to data providers. Provider Paths sends public IP/prefix/ASN queries to RIPE NCC.
CAIDA receives only public dataset download requests. Requests and inputs are not
logged. The service runs one lookup at a time, queues at most two more, retains
at most 40 jobs, and caps compressed dataset cache usage at approximately 512 MB.
Routing indexes are memory cached, with at most two loaded datasets. Expect
several hundred MB of RAM. Multiple server processes should use separate caches.

On macOS, the downloader also trusts the system `/etc/ssl/cert.pem` bundle.
TLS verification remains enabled. For other corporate environments, configure
Python's `SSL_CERT_FILE` with your approved CA bundle.
