"""Bulk BGP origin lookups using dated CAIDA RouteViews and AS organization data."""

from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import OrderedDict
import csv
from datetime import date, datetime, timezone
import gzip
import heapq
from html.parser import HTMLParser
import io
import ipaddress
import json
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler

BASE = "https://publicdata.caida.org/datasets/"
MAX_INPUTS = 1000
MAX_TEXT = 262144
MAX_ROUTES = 20000
MAX_SEGMENTS = 5000
HEADERS = {"ip", "ip_address", "address", "cidr", "network", "prefix", "range", "resource", "asn"}


class LookupError(ValueError):
    pass


def parse_resource(raw: str) -> dict:
    value = raw.strip()
    if not value or len(value) > 160 or "%" in value:
        raise LookupError("Enter an IPv4/IPv6 address, CIDR, or start-end range.")
    try:
        if "-" in value:
            first, last = [ipaddress.ip_address(v.strip()) for v in value.split("-", 1)]
            if first.version != last.version or int(first) > int(last):
                raise ValueError()
            normalized = f"{first}-{last}"
            note = ""
        else:
            network = ipaddress.ip_network(value, strict=False)
            first, last = network.network_address, network.broadcast_address
            normalized = str(network) if "/" in value else str(first)
            note = f"Normalized to {network}" if "/" in value and value != str(network) else ""
        return {"input": value, "normalized": normalized, "version": first.version,
                "start": int(first), "end": int(last), "note": note}
    except ValueError as exc:
        raise LookupError("Invalid IP address or range.") from exc


def parse_import(text: str, parser=parse_resource, max_inputs=MAX_INPUTS) -> list[dict]:
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_TEXT:
        raise LookupError("Import must be at most 256 KB.")
    text = text.lstrip("\ufeff")
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise LookupError("Add at least one IP address or network.")
    delimiter = "\t" if "\t" in lines[0] else ","
    rows = list(csv.reader(lines, delimiter=delimiter, strict=True))
    header = [cell.strip().lower().replace(" ", "_") for cell in rows[0]]
    columns = [i for i, cell in enumerate(header) if cell in HEADERS]
    if len(columns) > 1:
        raise LookupError("CSV must contain one address column (ip, cidr, network, range, or resource).")
    values = []
    if columns:
        column = columns[0]
        for row in rows[1:]:
            values.append(row[column] if column < len(row) else "")
    else:
        values = [cell for row in rows for cell in row]
    if not values or len(values) > max_inputs:
        raise LookupError(f"Import between 1 and {max_inputs:,} entries.")
    output = []
    for value in values:
        try:
            output.append(parser(value))
        except LookupError as exc:
            output.append({"input": value[:160], "error": str(exc)})
    return output


def parse_origins(value: str) -> tuple[tuple[int, ...], bool]:
    # CAIDA uses '_' for multiple origins and ',' (optionally braced) for AS sets.
    if not re.fullmatch(r"[\d_,{}]+", value):
        raise LookupError("Invalid ASN encoding in routing dataset.")
    asns = tuple(sorted({int(part) for part in re.findall(r"\d+", value)}))
    if not asns or any(asn < 1 or asn > 4294967295 for asn in asns):
        raise LookupError("Invalid ASN in routing dataset.")
    return asns, "," in value


class RouteIndex:
    def __init__(self, lines, version: int):
        self.version = version
        self.bits = 32 if version == 4 else 128
        self.tables = {}
        self.origins = {}
        count = 0
        for line in lines:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 3:
                raise LookupError("Malformed routing dataset.")
            address, length, origins = fields
            net = ipaddress.ip_network(f"{address}/{length}", strict=True)
            if net.version != version:
                raise LookupError("Routing dataset address family does not match.")
            if origins not in self.origins:
                self.origins[origins] = parse_origins(origins)
            if net.prefixlen == 0:
                continue
            self.tables.setdefault(net.prefixlen, {})[int(net.network_address)] = origins
            count += 1
        if not count:
            raise LookupError("Routing dataset is empty.")
        self.keys = {length: sorted(table) for length, table in self.tables.items()}
        self.count = count

    def segments(self, start: int, end: int):
        events = {}
        route_count = 0
        for length, table in self.tables.items():
            size = 1 << (self.bits - length)
            keys = self.keys[length]
            lo = bisect_left(keys, (start // size) * size)
            hi = bisect_right(keys, (end // size) * size)
            route_count += hi - lo
            if route_count > MAX_ROUTES:
                raise LookupError("Range overlaps too many routes. Import smaller CIDR blocks.")
            for address in keys[lo:hi]:
                left, right = max(start, address), min(end, address + size - 1)
                events.setdefault(left, []).append((-length, right, address, table[address]))
                events.setdefault(right + 1, [])
        events.setdefault(start, [])
        events.setdefault(end + 1, [])
        heap = []
        points = sorted(events)
        segments = []
        # Sweep route boundaries; the longest matching prefix wins within each interval.
        for i, point in enumerate(points[:-1]):
            for route in events[point]:
                heapq.heappush(heap, route)
            while heap and heap[0][1] < point:
                heapq.heappop(heap)
            key = (heap[0][0], heap[0][2], heap[0][3]) if heap else None
            right = points[i + 1] - 1
            if segments and segments[-1][2] == key and segments[-1][1] + 1 == point:
                segments[-1] = (segments[-1][0], right, key)
            else:
                segments.append((point, right, key))
        if len(segments) > MAX_SEGMENTS:
            raise LookupError("Range produces too many segments. Import smaller CIDR blocks.")
        return segments


class Links(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(value for key, value in attrs if key == "href" and value)


class RestrictedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_dataset_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_dataset_url(url: str):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "publicdata.caida.org"
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or not parsed.path.startswith("/datasets/")):
        raise LookupError("Dataset URL is outside the CAIDA data source.")


def https_context():
    context = ssl.create_default_context()
    if sys.platform == "darwin" and Path("/etc/ssl/cert.pem").is_file():
        context.load_verify_locations("/etc/ssl/cert.pem")
    return context


class Datasets:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.indexes = OrderedDict()
        self.org_cache = OrderedDict()

    def fetch(self, url: str, max_bytes=50_000_000) -> bytes:
        validate_dataset_url(url)
        request = Request(url, headers={"User-Agent": "BGPProviderLookup/0.1", "Accept": "*/*"})
        try:
            with build_opener(RestrictedRedirect(), HTTPSHandler(context=https_context())).open(request, timeout=45) as response:
                value = response.read(max_bytes + 1)
            if len(value) > max_bytes:
                raise LookupError("Dataset exceeds the download size limit.")
            return value
        except (URLError, TimeoutError, OSError) as exc:
            raise LookupError("CAIDA dataset download failed. Retry when the source is available.") from exc

    def catalog(self, url: str, lifetime=3600) -> str:
        import hashlib
        path = self.directory / (hashlib.sha256(url.encode()).hexdigest() + ".index")
        if path.exists() and time.time() - path.stat().st_mtime < lifetime:
            return path.read_text()
        text = self.fetch(url, 4_000_000).decode("utf-8")
        path.write_text(text)
        return text

    def cached_file(self, url: str) -> Path:
        validate_dataset_url(url)
        name = Path(urlparse(url).path).name
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+\.(?:gz|bz2)", name):
            raise LookupError("Invalid dataset filename.")
        path = self.directory / name
        if not path.exists():
            value = self.fetch(url)
            files = sorted([*self.directory.glob("*.gz"), *self.directory.glob("*.bz2")], key=lambda entry: entry.stat().st_mtime)
            total = sum(entry.stat().st_size for entry in files)
            while files and total + len(value) > 512_000_000:
                oldest = files.pop(0)
                total -= oldest.stat().st_size
                oldest.unlink()
            temp = path.with_suffix(".download")
            temp.write_bytes(value)
            temp.replace(path)
        return path

    def routing(self, version: int, requested: str, progress):
        folder = "routeviews-prefix2as" if version == 4 else "routeviews6-prefix2as"
        base = BASE + "routing/" + folder + "/"
        pattern = r"routeviews-(?:rv2|rv6)-(?P<day>\d{8})-(?P<hour>\d{4})\.pfx2as\.gz"
        progress(f"Finding IPv{version} routing snapshot")
        if requested == "latest":
            log = self.catalog(base + "pfx2as-creation.log")
            paths = [line.split()[2] for line in log.splitlines()
                     if line.strip() and not line.startswith("#") and len(line.split()) == 3]
        else:
            target = date.fromisoformat(requested)
            folder = target.strftime("%Y/%m/")
            paths = [folder + name for name in Links(self.catalog(base + folder)).links
                     if re.fullmatch(pattern, name) and target.strftime("%Y%m%d") in name]
        candidates = []
        for path in paths:
            match = re.fullmatch(r"\d{4}/\d{2}/(" + pattern + r")", path)
            if match:
                stamp = datetime.strptime(match.group("day") + match.group("hour"), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
                candidates.append((stamp, path))
        if not candidates:
            raise LookupError(f"No IPv{version} routing snapshot is available for {requested}.")
        stamp, relative = max(candidates)
        url = base + relative
        progress(f"Loading IPv{version} routes from {stamp.date()}")
        if url not in self.indexes:
            path = self.cached_file(url)
            try:
                with gzip.open(path, "rt") as stream:
                    index = RouteIndex(stream, version)
            except (OSError, EOFError, ValueError) as exc:
                raise LookupError("Routing snapshot could not be read. Remove the cached file and retry.") from exc
            self.indexes[url] = index
            while len(self.indexes) > 2:
                self.indexes.popitem(last=False)
        self.indexes.move_to_end(url)
        return self.indexes[url], {"url": url, "snapshotAt": stamp.isoformat(), "collector": "route-views2" if version == 4 else "route-views6"}

    def organizations(self, on_or_before: str, progress):
        base = BASE + "as-organizations/"
        links = Links(self.catalog(base)).links
        candidates = sorted(name for name in links if re.fullmatch(r"\d{8}\.as-org2info\.txt\.gz", name)
                            and name[:8] <= on_or_before.replace("-", ""))
        if not candidates:
            raise LookupError("No organization snapshot exists on or before the routing date.")
        name = candidates[-1]
        if name not in self.org_cache:
            progress(f"Loading organization names from {name[:8]}")
            organizations, asns = {}, {}
            fields = []
            with gzip.open(self.cached_file(base + name), "rt", encoding="utf-8") as stream:
                for line in stream:
                    if line.startswith("# format:"):
                        fields = line.split(":", 1)[1].strip().split("|")
                    elif line.strip() and not line.startswith("#"):
                        entry = dict(zip(fields, line.rstrip("\n").split("|")))
                        if "aut" in entry:
                            asns[int(entry["aut"])] = entry
                        elif "org_id" in entry:
                            organizations[entry["org_id"]] = entry
            resolved = {}
            for asn, entry in asns.items():
                org = organizations.get(entry.get("org_id"), {})
                resolved[asn] = {"asn": asn, "name": org.get("org_name") or entry.get("aut_name") or None,
                                 "asName": entry.get("aut_name"), "country": org.get("country"), "registry": entry.get("source")}
            if not resolved:
                raise LookupError("Organization dataset is empty.")
            self.org_cache[name] = resolved
            while len(self.org_cache) > 2:
                self.org_cache.popitem(last=False)
        return self.org_cache[name], {"url": base + name, "snapshotDate": datetime.strptime(name[:8], "%Y%m%d").date().isoformat()}


def address(value: int, version: int):
    return (ipaddress.IPv4Address if version == 4 else ipaddress.IPv6Address)(value)


SPECIAL = [ipaddress.ip_network(value) for value in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
    "172.16.0.0/12", "192.168.0.0/16", "192.0.2.0/24", "198.18.0.0/15", "198.51.100.0/24",
    "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4", "::/128", "::1/128", "::ffff:0:0/96",
    "100::/64", "2001:db8::/32", "fc00::/7", "fe80::/10", "ff00::/8")]


def is_special(item):
    return any(net.version == item["version"] and int(net.network_address) <= item["start"]
               and int(net.broadcast_address) >= item["end"] for net in SPECIAL)


def resolve(item, index, orgs, routing, organizations):
    result = {"input": item["input"], "normalized": item["normalized"], "note": item["note"],
              "status": "mapped", "segments": [], "routing": routing, "organizations": organizations}
    for start, end, route in index.segments(item["start"], item["end"]):
        origins, ambiguous, prefix = (), False, None
        if route:
            length, base, raw = route
            prefix = f"{address(base, item['version'])}/{-length}"
            origins, ambiguous = index.origins[raw]
        segment = {"start": str(address(start, item["version"])), "end": str(address(end, item["version"])),
                   "addressCount": str(end - start + 1), "prefix": prefix,
                   "status": "as_set" if ambiguous else "multiple_origins" if len(origins) > 1 else "mapped" if origins else "not_observed",
                   "origins": [orgs.get(asn, {"asn": asn, "name": None}) for asn in origins]}
        result["segments"].append(segment)
    statuses = {segment["status"] for segment in result["segments"]}
    if statuses == {"not_observed"}:
        result["status"] = "not_observed"
    elif "not_observed" in statuses:
        result["status"] = "partial"
    elif statuses & {"multiple_origins", "as_set"}:
        result["status"] = "ambiguous"
    elif len({tuple(o["asn"] for o in segment["origins"]) for segment in result["segments"]}) > 1:
        result["status"] = "multiple_networks"
    return result


def run_lookup(text: str, requested: str, datasets: Datasets, progress=lambda _: None):
    inputs = parse_import(text)
    if requested != "latest":
        try:
            selected = date.fromisoformat(requested)
            if selected > datetime.now(timezone.utc).date() or selected < date(2005, 5, 9):
                raise ValueError()
        except (ValueError, TypeError):
            raise LookupError("Select a date from 2005-05-09 through today.")
    families = {}
    family_errors = {}
    for version in sorted({item["version"] for item in inputs if "error" not in item and not is_special(item)}):
        try:
            index, routing = datasets.routing(version, requested, progress)
            orgs, organizations = datasets.organizations(routing["snapshotAt"][:10], progress)
            families[version] = index, orgs, routing, organizations
        except LookupError as exc:
            family_errors[version] = str(exc)
    results = []
    remaining = MAX_SEGMENTS
    for i, item in enumerate(inputs):
        progress(f"Resolving entry {i + 1} of {len(inputs)}")
        if "error" in item:
            result = {"input": item["input"], "status": "invalid", "error": item["error"], "segments": []}
        elif is_special(item):
            result = {"input": item["input"], "normalized": item["normalized"], "status": "special_use",
                      "note": "Private, shared, documentation, or other special-use address space.", "segments": []}
        elif item["version"] in family_errors:
            result = {"input": item["input"], "status": "error", "error": family_errors[item["version"]], "segments": []}
        else:
            try:
                result = resolve(item, *families[item["version"]])
                if len(result["segments"]) > remaining:
                    raise LookupError("Batch result limit reached. Split the import into smaller batches.")
                remaining -= len(result["segments"])
            except LookupError as exc:
                result = {"input": item["input"], "status": "error", "error": str(exc), "segments": []}
        results.append(result)
    return {"requestedDate": requested, "generatedAt": datetime.now(timezone.utc).isoformat(),
            "source": "CAIDA RouteViews prefix-to-AS and AS Organizations datasets",
            "meaning": "Origin network organization; not proof of retail ISP, upstream transit, physical location, or ownership.",
            "results": results}


def csv_export(payload):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["input", "normalized", "status", "range_start", "range_end", "matched_prefix", "asn",
                     "organization", "organization_country", "routing_snapshot_utc", "organization_snapshot", "routing_source", "organization_source", "note"])
    for result in payload["results"]:
        for segment in result.get("segments") or [{}]:
            for origin in segment.get("origins") or [{}]:
                row = [result["input"], result.get("normalized", ""), segment.get("status", result["status"]),
                       segment.get("start", ""), segment.get("end", ""), segment.get("prefix", ""), origin.get("asn", ""),
                       origin.get("name", ""), origin.get("country", ""), result.get("routing", {}).get("snapshotAt", ""),
                       result.get("organizations", {}).get("snapshotDate", ""), result.get("routing", {}).get("url", ""),
                       result.get("organizations", {}).get("url", ""), result.get("error") or result.get("note", "")]
                writer.writerow(["'" + str(value) if str(value).lstrip().startswith(("=", "+", "-", "@")) else value for value in row])
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resources", nargs="*")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--date", default="latest", help="YYYY-MM-DD or latest")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    parser.add_argument("--paths", action="store_true", help="Find observed provider paths for IPs, CIDRs, or ASNs")
    parser.add_argument("--cache", type=Path, default=Path(__file__).parent / "data")
    args = parser.parse_args()
    try:
        text = args.input.read_text(encoding="utf-8-sig") if args.input else "\n".join(args.resources)
        progress = lambda message: print(message, file=sys.stderr)
        if args.paths:
            from paths import PathLookup, path_csv_export
            payload = PathLookup(Datasets(args.cache)).lookup(text, args.date, progress)
            exporter = path_csv_export
        else:
            payload = run_lookup(text, args.date, Datasets(args.cache), progress)
            exporter = csv_export
        print(exporter(payload) if args.format == "csv" else json.dumps(payload, indent=2))
        return 1 if any(result["status"] in ("invalid", "error") for result in payload["results"]) else 0
    except (ValueError, OSError, csv.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
