# CLI, API, and export reference

[Back to README](../README.md) · Run commands from the repository root.

- [Command-line usage](#command-line-usage)
- [Exports and result structure](#exports-and-result-structure)
- [Local API](#local-api)

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

## Local API

`GET /api/requests` returns the shared UTC-day count, notification flag, pacing,
and cooldown timing. It uses the same Host/Origin/service-token checks.

| Method and path | Purpose |
| --- | --- |
| `GET /` | Browser interface |
| `GET /api/health` | Process readiness; does not test upstream data availability |
| `POST /api/jobs` | Create a lookup job |
| `GET /api/jobs/{id}` | Read status and the completed result |
| `GET /api/jobs/{id}/export` | Download CSV after completion or cancellation with partial results |
| `POST /api/jobs/{id}/cancel` | Cancel future work; requires the job token |
| `GET /api/jobs/{id}/bundle` | Download a completed investigation ZIP |
| `POST /api/investigations/open` | Inspect an uploaded ZIP offline |
| `POST /api/investigations/replay` | Replay an uploaded ZIP offline |
| `GET /api/requests` | Read the shared request counter and pacing state |

Create an Observed BGP paths job:

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

States are `queued`, `running`, `complete`, `cancelled`, and `failed`. A completed job contains
`result`, but individual entries may still have error statuses. Poll sparingly
instead of creating duplicate jobs.

Use `"mode":"origins"` for Origin Mapping. The API defaults to `origins` when
mode is omitted, unlike the browser's Observed BGP paths default. The date defaults
to `latest`. The health response's `maxInputs: 1000` applies to both lookup modes.

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
job token, `413` oversized body, `415` non-JSON job request, and `429` active work capacity reached.
