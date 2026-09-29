import csv
import io
import ipaddress
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lookup import Datasets, LookupError, RouteIndex, csv_export, parse_import, parse_origins, parse_resource, resolve, run_lookup, validate_dataset_url
from server import JobStore


class LookupTests(unittest.TestCase):
    def index(self, lines):
        return RouteIndex(lines.splitlines(), 4)

    def test_ipv4_and_ipv6_input(self):
        self.assertEqual(parse_resource("129.55.110.9")["normalized"], "129.55.110.9")
        self.assertEqual(parse_resource("2001:4860::8888")["version"], 6)

    def test_normalization_is_visible(self):
        item = parse_resource("129.55.110.9/24")
        self.assertEqual(item["normalized"], "129.55.110.0/24")
        self.assertTrue(item["note"])

    def test_range_validation(self):
        self.assertEqual(parse_resource("8.8.8.1 - 8.8.8.9")["end"] - parse_resource("8.8.8.1-8.8.8.9")["start"], 8)
        for value in ["http://127.0.0.1", "1.1.1.2-1.1.1.1", "8.8.8.8-::1", "1.1.1.1/33", "fe80::1%en0"]:
            with self.assertRaises(LookupError):
                parse_resource(value)

    def test_csv_header_and_quoted_metadata(self):
        entries = parse_import('\ufefflabel,ip\n"one,two",8.8.8.8\nother,1.1.1.0/24')
        self.assertEqual([e["input"] for e in entries], ["8.8.8.8", "1.1.1.0/24"])

    def test_txt_and_invalid_rows_preserved(self):
        entries = parse_import("# comment\n8.8.8.8,1.1.1.1\ninvalid")
        self.assertEqual(len(entries), 3)
        self.assertIn("error", entries[-1])

    def test_limits(self):
        for text in ["", "8.8.8.8\n" * 1001, "x" * 262145, "ip,cidr\n8.8.8.8,1.1.1.0/24"]:
            with self.assertRaises(LookupError):
                parse_import(text)

    def test_more_specific_wins_for_ip(self):
        index = self.index("8.0.0.0 8 1\n8.8.8.0 24 2")
        item = parse_resource("8.8.8.8")
        result = resolve(item, index, {}, {}, {})
        self.assertEqual(result["segments"][0]["origins"][0]["asn"], 2)

    def test_range_preserves_parent_and_child(self):
        index = self.index("8.8.0.0 16 1\n8.8.8.0 24 2")
        result = resolve(parse_resource("8.8.0.0/16"), index, {}, {}, {})
        self.assertEqual(result["status"], "multiple_networks")
        self.assertEqual([s["origins"][0]["asn"] for s in result["segments"]], [1, 2, 1])
        self.assertEqual(sum(int(s["addressCount"]) for s in result["segments"]), 65536)

    def test_gaps_are_not_mapped_to_neighbor(self):
        index = self.index("8.8.8.0 25 1")
        result = resolve(parse_resource("8.8.8.0/24"), index, {}, {}, {})
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["segments"][1]["status"], "not_observed")

    def test_moas_and_sets_are_distinct(self):
        self.assertEqual(parse_origins("20_10"), ((10, 20), False))
        self.assertEqual(parse_origins("{20,10}_30"), ((10, 20, 30), True))
        index = self.index("8.8.8.0 24 10_20\n9.9.9.0 24 30,40")
        self.assertEqual(resolve(parse_resource("8.8.8.8"), index, {}, {}, {})["segments"][0]["status"], "multiple_origins")
        self.assertEqual(resolve(parse_resource("9.9.9.9"), index, {}, {}, {})["segments"][0]["status"], "as_set")

    def test_ipv6_longest_prefix(self):
        index = RouteIndex(["2001:4860:: 32 1", "2001:4860:4860:: 48 2"], 6)
        result = resolve(parse_resource("2001:4860:4860::8888"), index, {}, {}, {})
        self.assertEqual(result["segments"][0]["prefix"], "2001:4860:4860::/48")

    def test_sweep_matches_brute_force(self):
        routes = [("8.8.8.0", 24, 1), ("8.8.8.0", 25, 2), ("8.8.8.32", 27, 3), ("8.8.8.40", 29, 4), ("8.8.8.128", 26, 5)]
        index = self.index("\n".join(f"{ip} {bits} {asn}" for ip, bits, asn in routes))
        result = resolve(parse_resource("8.8.8.0/24"), index, {}, {}, {})
        for n in range(256):
            ip = ipaddress.ip_address(f"8.8.8.{n}")
            expected = max((bits, asn) for addr, bits, asn in routes if ip in ipaddress.ip_network(f"{addr}/{bits}"))[1]
            segment = next(s for s in result["segments"] if ipaddress.ip_address(s["start"]) <= ip <= ipaddress.ip_address(s["end"]))
            self.assertEqual(segment["origins"][0]["asn"], expected)

    def test_private_input_does_not_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            datasets = Datasets(Path(directory))
            with patch.object(datasets, "fetch", side_effect=AssertionError("network used")):
                result = run_lookup("10.0.0.0/8\n::1", "latest", datasets)
            self.assertEqual([r["status"] for r in result["results"]], ["special_use", "special_use"])

    def test_historical_selection_never_uses_future_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            datasets = Datasets(Path(directory))
            html = '<a href="20260801.as-org2info.txt.gz">a</a><a href="20260901.as-org2info.txt.gz">b</a>'
            with patch.object(datasets, "catalog", return_value=html), patch.object(datasets, "cached_file", side_effect=LookupError("sentinel")) as fetch:
                with self.assertRaises(LookupError):
                    datasets.organizations("2026-08-28", lambda _: None)
                self.assertTrue(fetch.call_args.args[0].endswith("20260801.as-org2info.txt.gz"))

    def test_no_silent_date_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            datasets = Datasets(Path(directory))
            with patch.object(datasets, "catalog", return_value='<a href="routeviews-rv2-20260820-1200.pfx2as.gz">x</a>'):
                with self.assertRaisesRegex(LookupError, "No IPv4 routing snapshot"):
                    datasets.routing(4, "2026-08-21", lambda _: None)

    def test_external_fetch_allowlist(self):
        for url in ["http://publicdata.caida.org/datasets/x", "https://evil.com/x", "https://publicdata.caida.org@evil.com/datasets/x", "https://127.0.0.1/datasets/x"]:
            with self.assertRaises(LookupError):
                validate_dataset_url(url)

    def test_export_neutralizes_spreadsheet_formulas(self):
        payload = {"results": [{"input": "=cmd()", "status": "invalid", "segments": []}]}
        row = list(csv.reader(io.StringIO(csv_export(payload))))[1]
        self.assertEqual(row[0], "'=cmd()")

    def test_job_access_token_required(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Datasets(Path(directory)))
            try:
                job = store.create("10.0.0.1", "latest")
                self.assertIsNone(store.read(job["id"], "wrong"))
                self.assertIsNotNone(store.read(job["id"], job["token"]))
            finally:
                store.pool.shutdown()

    def test_expired_jobs_are_removed_from_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Datasets(Path(directory)))
            store.jobs["expired"] = {"created": 0, "token": "test"}
            store.purge()
            self.assertFalse(store.jobs)
            store.pool.shutdown()

    def test_source_failure_is_not_reported_as_no_route(self):
        with tempfile.TemporaryDirectory() as directory:
            datasets = Datasets(Path(directory))
            with patch.object(datasets, "routing", side_effect=LookupError("Source unavailable")):
                payload = run_lookup("8.8.8.8", "latest", datasets)
            self.assertEqual(payload["results"][0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
