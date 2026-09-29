"""Observed RIS AS paths and dated CAIDA relationship inferences."""

from collections import OrderedDict
import bz2
import csv
from datetime import date, datetime, timezone
import io
import ipaddress
import json
import re
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from lookup import BASE, Datasets, Links, LookupError, https_context, is_special, parse_import, parse_resource

MAX_PATH_INPUTS = 20
MAX_RIS_ROUTES = 50000
MAX_EVIDENCE = 1000
REL_LABELS = {"provider": "Transit provider (inferred)", "peer": "Peer (inferred)",
              "customer": "Customer (inferred)", "unknown": "Relationship unknown"}


def parse_path_resource(raw):
    value = raw.strip()
    match = re.fullmatch(r"AS([0-9]{1,10})", value, re.IGNORECASE)
    if match:
        asn = int(match.group(1))
        if not 1 <= asn <= 4294967295:
            raise LookupError("Invalid ASN.")
        return {"input": value, "resource": f"AS{asn}", "asn": asn}
    item = parse_resource(value)
    if "-" in item["normalized"]:
        raise LookupError("Provider paths accept IPs, CIDRs, or ASNs such as AS63. Convert ranges to CIDRs.")
    return {**item, "resource": item["normalized"]}


def normalize_path(raw):
    if not isinstance(raw, list) or not raw or len(raw) > 255:
        return None
    path = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, (int, str)) or not re.fullmatch(r"[0-9]{1,10}", str(value)):
            return None
        asn = int(value)
        if not 1 <= asn <= 4294967295:
            return None
        if not path or path[-1] != asn:
            path.append(asn)
    # Repeated consecutive ASNs are prepending. Other repeats indicate a loop.
    return path if len(set(path)) == len(path) else None


def select_routes(state, item):
    routes = state.get("bgp_state")
    if not isinstance(routes, list) or len(routes) > MAX_RIS_ROUTES:
        raise LookupError("RIS response is unavailable or too large. Query a narrower prefix.")
    if isinstance(state.get("nr_routes"), int) and state["nr_routes"] > len(routes):
        raise LookupError("RIS returned incomplete route data; query a narrower prefix.")
    selected, skipped = [], 0
    network = None if "asn" in item else ipaddress.ip_network(item["resource"], strict=False)
    for route in routes:
        if not isinstance(route, dict):
            skipped += 1
            continue
        path = normalize_path(route.get("path"))
        try:
            prefix = ipaddress.ip_network(route.get("target_prefix", ""), strict=True)
        except (ValueError, TypeError):
            skipped += 1
            continue
        peer = route.get("source_id", "")
        if not path or not isinstance(peer, str) or not re.fullmatch(r"[0-9]{1,3}-[0-9a-fA-F:.]+", peer):
            skipped += 1
            continue
        if prefix.prefixlen == 0:
            continue
        if "asn" in item and path[-1] != item["asn"]:
            continue
        if network and (prefix.version != network.version or not prefix.overlaps(network)):
            continue
        selected.append({"prefix": str(prefix), "length": prefix.prefixlen, "path": path, "source": peer,
                         "collector": "rrc" + peer.split("-", 1)[0].zfill(2)})
    if network and network.prefixlen == network.max_prefixlen:
        longest = {}
        for row in selected:
            longest[row["source"]] = max(longest.get(row["source"], 0), row["length"])
        selected = [row for row in selected if row["length"] == longest[row["source"]]]
    return selected, skipped


def parse_relationships(lines, origins):
    relationships = {}
    for line in lines:
        if line.startswith("#") or not line.strip():
            continue
        fields = line.strip().split("|")
        if len(fields) < 3:
            raise LookupError("Malformed AS relationship dataset.")
        first, second, relationship = int(fields[0]), int(fields[1]), fields[2]
        if first not in origins and second not in origins:
            continue
        if relationship == "-1":
            relationships[(second, first)] = "provider"
            relationships[(first, second)] = "customer"
        elif relationship == "0":
            relationships[(first, second)] = relationships[(second, first)] = "peer"
    return relationships


def summarize_routes(routes, organizations, relationships):
    groups = {}
    all_asns = set()
    for route in routes:
        path = route["path"]
        all_asns.update(path)
        origin = path[-1]
        group = groups.setdefault(origin, {"origin": origin, "neighbors": {}, "sources": set(), "collectors": set(), "prefixes": set(), "directObservations": 0})
        group["sources"].add(route["source"])
        group["collectors"].add(route["collector"])
        group["prefixes"].add(route["prefix"])
        if len(path) < 2:
            group["directObservations"] += 1
            continue
        neighbor = path[-2]
        entry = group["neighbors"].setdefault(neighbor, {"asn": neighbor, "sources": set(), "collectors": set(), "prefixes": set(), "paths": {}, "observations": set()})
        entry["sources"].add(route["source"])
        entry["collectors"].add(route["collector"])
        entry["prefixes"].add(route["prefix"])
        key = (route["prefix"], tuple(path))
        evidence = entry["paths"].setdefault(key, {"prefix": route["prefix"], "asns": path, "collectors": set(), "sources": set()})
        evidence["collectors"].add(route["collector"])
        evidence["sources"].add(route["source"])
        entry["observations"].add((route["source"], key))
    neighbor_count = sum(len(group["neighbors"]) for group in groups.values())
    if neighbor_count > 500:
        raise LookupError("Too many origin-neighbor combinations. Query a narrower prefix.")
    evidence_limit = max(1, MAX_EVIDENCE // max(1, neighbor_count))
    result = []
    for group in groups.values():
        neighbors = []
        for entry in group["neighbors"].values():
            paths = sorted(entry["paths"].values(), key=lambda p: (-len(p["sources"]), len(p["asns"]), p["asns"], p["prefix"]))
            neighbors.append({"asn": entry["asn"], "relationship": relationships.get((group["origin"], entry["asn"]), "unknown"),
                              "peerCount": len(entry["sources"]), "collectors": sorted(entry["collectors"]),
                              "prefixes": sorted(entry["prefixes"]), "routeObservations": len(entry["observations"]),
                              "pathCount": len(paths), "pathsTruncated": len(paths) > evidence_limit,
                              "paths": [{"prefix": p["prefix"], "asns": p["asns"], "collectors": sorted(p["collectors"]), "peerCount": len(p["sources"])} for p in paths[:evidence_limit]]})
        neighbors.sort(key=lambda entry: (entry["relationship"] != "provider", -entry["peerCount"], entry["asn"]))
        result.append({"origin": group["origin"], "neighbors": neighbors, "peerCount": len(group["sources"]),
                       "collectors": sorted(group["collectors"]), "prefixes": sorted(group["prefixes"]), "directObservations": group["directObservations"]})
    names = {str(asn): organizations.get(asn, {"asn": asn, "name": None}) for asn in sorted(all_asns)}
    return result, names


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class PathLookup:
    def __init__(self, datasets):
        self.datasets = datasets
        self.cache = OrderedDict()

    def ris(self, item, requested):
        params = {"resource": item["resource"]}
        if requested != "latest":
            params["timestamp"] = requested + "T12:00:00"
        url = "https://stat.ripe.net/data/bgp-state/data.json?" + urlencode(params)
        cached = self.cache.get(url)
        if cached and time.time() - cached[0] < (300 if requested == "latest" else 3600):
            return cached[1], url
        try:
            req = Request(url, headers={"User-Agent": "BGPProviderLookup/0.2", "Accept": "application/json"})
            with build_opener(NoRedirect(), HTTPSHandler(context=https_context())).open(req, timeout=45) as response:
                raw = response.read(12_000_001)
            if len(raw) > 12_000_000:
                raise LookupError("RIS response is too large. Query a narrower prefix.")
            payload = json.loads(raw)
            if payload.get("status") != "ok" or not isinstance(payload.get("data"), dict):
                raise LookupError("RIS could not provide routing state for this resource and time.")
            state = payload["data"]
            if not isinstance(state.get("timestamp"), str):
                raise LookupError("RIS did not provide an observation timestamp.")
            observed = datetime.fromisoformat(state["timestamp"].replace("Z", "+00:00"))
            if requested != "latest" and observed.date().isoformat() != requested:
                raise LookupError("RIS returned a different observation date; this result was not used.")
            self.cache[url] = (time.time(), state)
            self.cache.move_to_end(url)
            while len(self.cache) > 8:
                self.cache.popitem(last=False)
            return state, url
        except (URLError, TimeoutError, OSError, ValueError, AttributeError) as exc:
            if isinstance(exc, LookupError):
                raise
            raise LookupError("RIPE RIS paths could not be retrieved. Retry shortly.") from exc

    def relationships(self, observed_date, origins):
        base = BASE + "as-relationships/serial-2/"
        candidates = sorted(name for name in Links(self.datasets.catalog(base)).links
                            if re.fullmatch(r"\d{8}\.as-rel2\.txt\.bz2", name) and name[:8] <= observed_date.replace("-", ""))
        if not candidates:
            raise LookupError("No relationship snapshot is available on or before this date.")
        name = candidates[-1]
        with bz2.open(self.datasets.cached_file(base + name), "rt") as stream:
            relationships = parse_relationships(stream, origins)
        return relationships, {"url": base + name, "snapshotDate": datetime.strptime(name[:8], "%Y%m%d").date().isoformat()}

    def lookup(self, text, requested, progress=lambda _: None):
        items = parse_import(text, parse_path_resource, MAX_PATH_INPUTS)
        if requested != "latest":
            try:
                if not date(2005, 5, 9) <= date.fromisoformat(requested) <= datetime.now(timezone.utc).date():
                    raise ValueError()
            except (ValueError, TypeError):
                raise LookupError("Choose a valid historical date.")
        results = []
        for i, item in enumerate(items):
            result = {"input": item["input"], "groups": [], "asns": {}, "warnings": []}
            results.append(result)
            if "error" in item:
                result.update(status="invalid", error=item["error"])
                continue
            if "asn" not in item and is_special(item):
                result.update(status="special_use", error="Private or special-use address space has no public provider path lookup.")
                continue
            try:
                progress(f"Reading RIS paths for {item['resource']} ({i + 1}/{len(items)})")
                state, url = self.ris(item, requested)
                routes, skipped = select_routes(state, item)
                result["observation"] = {"url": url, "observedAt": state["timestamp"], "source": "RIPE RIS"}
                result["skippedPaths"] = skipped
                if skipped:
                    result["warnings"].append(f"{skipped} malformed, looping, or ambiguous AS paths were excluded.")
                if not routes:
                    result.update(status="not_observed")
                    continue
                observed_date = state["timestamp"][:10]
                progress("Resolving network names and provider relationships")
                try:
                    organizations, provenance = self.datasets.organizations(observed_date, progress)
                    result["organizations"] = provenance
                except (LookupError, OSError, EOFError, ValueError):
                    organizations = {}
                    result["warnings"].append("Organization names are unavailable; ASNs are shown.")
                try:
                    relationships, provenance = self.relationships(observed_date, {row["path"][-1] for row in routes})
                    result["relationships"] = provenance
                except (LookupError, OSError, EOFError, ValueError):
                    relationships = {}
                    result["warnings"].append("Relationship data is unavailable; neighbors are not classified as transit providers.")
                result["groups"], result["asns"] = summarize_routes(routes, organizations, relationships)
                result["status"] = "mapped"
            except LookupError as exc:
                result.update(status="error", error=str(exc))
        return {"kind": "paths", "requestedDate": requested, "generatedAt": datetime.now(timezone.utc).isoformat(),
                "meaning": "Observed BGP neighbors and inferred relationships, not contractual proof or a measurement from your network.", "results": results}


def path_csv_export(payload):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["input", "status", "origin_asn", "origin_organization", "neighbor_asn", "neighbor_organization", "relationship",
                     "prefix", "as_path", "ris_peers", "collectors", "observed_at_utc", "relationship_date", "organization_date", "source", "note"])
    for result in payload["results"]:
        if not result["groups"]:
            writer.writerow([result["input"] if not result["input"].lstrip().startswith(("=", "+", "-", "@")) else "'" + result["input"], result["status"]] + [""] * 13 + [result.get("error", "")])
        for group in result["groups"]:
            for neighbor in group["neighbors"] or [{"asn": None, "relationship": "unknown", "paths": [{}]}]:
                for path in neighbor["paths"]:
                    row = [result["input"], result["status"], group["origin"], result["asns"].get(str(group["origin"]), {}).get("name"),
                           neighbor["asn"], result["asns"].get(str(neighbor["asn"]), {}).get("name"), REL_LABELS[neighbor["relationship"]],
                           path.get("prefix", ""), " ".join(map(str, path.get("asns", []))), path.get("peerCount", ""), " ".join(path.get("collectors", [])),
                           result.get("observation", {}).get("observedAt", ""), result.get("relationships", {}).get("snapshotDate", ""),
                           result.get("organizations", {}).get("snapshotDate", ""), result.get("observation", {}).get("url", ""),
                           f"Evidence limited to {len(neighbor['paths'])} paths for this neighbor" if neighbor.get("pathsTruncated") else ""]
                    writer.writerow(["'" + str(value) if str(value).lstrip().startswith(("=", "+", "-", "@")) else value for value in row])
    return output.getvalue()
