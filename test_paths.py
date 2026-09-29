from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lookup import Datasets, LookupError, parse_import
from paths import PathLookup, normalize_path, parse_path_resource, parse_relationships, select_routes, summarize_routes, path_csv_export


def route(path, prefix="129.55.0.0/16", peer="00-8.8.8.8"):
    return {"path": path, "target_prefix": prefix, "source_id": peer}


class PathTests(unittest.TestCase):
    def test_accepts_asn_ip_and_cidr(self):
        self.assertEqual(parse_path_resource("as63")["resource"], "AS63")
        self.assertEqual(parse_path_resource("129.55.110.9")["resource"], "129.55.110.9")
        self.assertEqual(parse_path_resource("129.55.110.9/24")["resource"], "129.55.110.0/24")

    def test_invalid_resources_and_batch_limits(self):
        for text in ["AS0", "AS4294967296", "http://localhost", "8.8.8.1-8.8.8.2"]:
            with self.assertRaises(LookupError):
                parse_path_resource(text)
        with self.assertRaises(LookupError):
            parse_import("AS63\n"*21, parse_path_resource, 20)

    def test_prepend_only_collapses_consecutive_repeats(self):
        self.assertEqual(normalize_path([174, 174, 13789, 63, 63]), [174, 13789, 63])
        self.assertIsNone(normalize_path([174, 13789, 174, 63]))

    def test_ambiguous_and_invalid_as_paths_are_excluded(self):
        for values in [["{174,3356}", 63], [True, 63], [0, 63], [], [None, 63], [4294967296, 63]]:
            self.assertIsNone(normalize_path(values))

    def test_origin_filter_excludes_transit_matches(self):
        rows, skipped = select_routes({"bgp_state": [route([174,63]),route([174,63,100])]}, parse_path_resource("AS63"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(skipped, 0)

    def test_ip_uses_longest_prefix_per_observer(self):
        state = {"bgp_state": [route([174,63]),route([1299,100],"129.55.110.0/24"),route([11164,63],peer="01-1.1.1.1")]}
        rows, _ = select_routes(state, parse_path_resource("129.55.110.9"))
        self.assertEqual([r["path"][-1] for r in rows], [100,63])

    def test_prefix_scope_rejects_unrelated_more_specifics(self):
        rows, _ = select_routes({"bgp_state": [route([174,63]),route([174,63],"129.55.201.0/24")]}, parse_path_resource("129.55.0.0/24"))
        self.assertEqual(len(rows),1)

    def test_incomplete_ris_response_is_an_error(self):
        with self.assertRaises(LookupError):
            select_routes({"nr_routes":2,"bgp_state":[route([174,63])]}, parse_path_resource("AS63"))

    def test_relationship_orientation(self):
        relations=parse_relationships(["13789|63|-1|bgp", "63|11164|0|bgp", "63|99|-1|bgp"], {63})
        self.assertEqual(relations[(63,13789)],"provider")
        self.assertEqual(relations[(63,11164)],"peer")
        self.assertEqual(relations[(63,99)],"customer")
        self.assertEqual(relations[(13789,63)],"customer")

    def test_only_adjacent_as_is_a_direct_neighbor(self):
        rows,_=select_routes({"bgp_state":[route([174,1299,13789,63])]},parse_path_resource("AS63"))
        groups,_=summarize_routes(rows,{}, {})
        self.assertEqual([n["asn"] for n in groups[0]["neighbors"]],[13789])
        self.assertEqual(groups[0]["neighbors"][0]["relationship"],"unknown")

    def test_peers_deduplicated_across_prefixes_and_rows(self):
        state={"bgp_state":[route([174,13789,63]),route([174,13789,63]),route([174,13789,63],"129.55.201.0/24"),route([174,13789,63],peer="01-1.1.1.1")]}
        rows,_=select_routes(state,parse_path_resource("AS63"))
        groups,_=summarize_routes(rows,{}, {(63,13789):"provider"})
        neighbor=groups[0]["neighbors"][0]
        self.assertEqual(neighbor["peerCount"],2)
        self.assertEqual(neighbor["pathCount"],2)
        self.assertEqual(neighbor["routeObservations"],3)

    def test_direct_origin_does_not_invent_provider(self):
        rows,_=select_routes({"bgp_state":[route([63])]},parse_path_resource("AS63"))
        groups,_=summarize_routes(rows,{}, {})
        self.assertEqual(groups[0]["neighbors"],[])
        self.assertEqual(groups[0]["directObservations"],1)

    def test_special_use_stays_local(self):
        with tempfile.TemporaryDirectory() as directory:
            lookup=PathLookup(Datasets(Path(directory)))
            with patch.object(lookup,"ris",side_effect=AssertionError("network call")):
                payload=lookup.lookup("10.0.0.1","latest")
            self.assertEqual(payload["results"][0]["status"],"special_use")

    def test_missing_relationships_preserves_observed_neighbors(self):
        with tempfile.TemporaryDirectory() as directory:
            lookup=PathLookup(Datasets(Path(directory)))
            state={"timestamp":"2026-08-01T12:00:00","bgp_state":[route([174,13789,63])]}
            with patch.object(lookup,"ris",return_value=(state,"https://stat.ripe.net/data/bgp-state/data.json")), patch.object(lookup.datasets,"organizations",return_value=({},{})), patch.object(lookup,"relationships",side_effect=LookupError("unavailable")):
                payload=lookup.lookup("AS63","2026-08-01")
            result=payload["results"][0]
            self.assertEqual(result["groups"][0]["neighbors"][0]["relationship"],"unknown")
            self.assertTrue(result["warnings"])
            self.assertIn("13789",path_csv_export(payload))

    def test_relationship_snapshot_not_after_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            lookup=PathLookup(Datasets(Path(directory)))
            html='<a href="20260801.as-rel2.txt.bz2">a</a><a href="20260901.as-rel2.txt.bz2">b</a>'
            with patch.object(lookup.datasets,"catalog",return_value=html),patch.object(lookup.datasets,"cached_file",side_effect=LookupError("sentinel")) as fetch:
                with self.assertRaises(LookupError):
                    lookup.relationships("2026-08-28",{63})
            self.assertTrue(fetch.call_args.args[0].endswith("20260801.as-rel2.txt.bz2"))


if __name__ == "__main__":
    unittest.main()
