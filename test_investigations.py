import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from lookup import Datasets, LookupError
from paths import PathLookup
from investigations import Capture, build, pack, unpack, encode, digest, tool_version, differences


def route(path, peer='00-8.8.8.8', prefix='129.55.0.0/16'):
    return {'path': path, 'source_id': peer, 'target_prefix': prefix}


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = PathLookup(Datasets(Path(self.tmp.name)))
        self.addCleanup(self.tmp.cleanup)

    def capture(self, states, dates=None):
        dates = dates or ['2026-08-01']
        def ris(item, requested):
            rows = states[requested]
            if isinstance(rows, Exception):
                raise rows
            state = {'timestamp': requested+'T12:00:00', 'bgp_state': rows}
            self.engine.raw_response = json.dumps({'status': 'ok', 'data': state}).encode()
            return state, 'https://stat.ripe.net/data/bgp-state/data.json?resource=AS63'
        with patch.object(self.engine, 'ris', side_effect=ris), patch.object(self.engine.datasets, 'organizations', return_value=({63:{'asn':63,'name':'Example'}}, {'url':'https://publicdata.caida.org/datasets/example.gz','snapshotDate':'2026-08-01','sha256':'0'*64})), patch.object(self.engine, 'relationships', return_value=({(63,13789):'provider'}, {'snapshotDate':'2026-08-01'})):
            return build(self.engine, 'AS63', dates)

    def data(self, blob):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            return json.loads(z.read('investigation.json'))

    def test_thousand_target_comparison_roundtrip(self):
        def ris(item, requested):
            state = {'timestamp': requested+'T12:00:00', 'bgp_state': []}
            self.engine.raw_response = json.dumps({'status': 'ok', 'data': state}).encode()
            return state, 'https://stat.ripe.net/data/bgp-state/data.json'
        text = '\n'.join(f'AS{i}' for i in range(1, 1001))
        updates = []
        def progress(message): pass
        progress.report = updates.append
        with patch.object(self.engine, 'ris', side_effect=ris) as fetch:
            view, blob = build(self.engine, text, ['2026-08-01', '2026-08-02'], progress)
        self.assertEqual(updates[-1]['snapshot'], 2)
        self.assertEqual(updates[-1]['processed'], 1000)
        self.assertEqual(updates[-1]['remaining'], 0)
        self.assertEqual({v['date'] for v in updates}, {'2026-08-01','2026-08-02'})
        self.assertEqual(fetch.call_count, 2000)
        opened = unpack(blob)
        self.assertEqual(len(opened['inputs']), 1000)
        self.assertEqual(len(opened['comparison']), 1000)
        self.assertEqual(opened['comparisonReplay'], 'match')
        self.assertTrue(all(c['status'] == 'match' for checks in opened['replay'] for c in checks))
        with self.assertRaises(LookupError):
            build(self.engine, text+'\nAS1001', ['2026-08-01'])

    def test_exact_raw_response_and_offline_replay(self):
        view, blob = self.capture({'2026-08-01':[route([174,13789,63])]})
        raw = base64.b64decode(self.data(blob)['snapshots'][0]['evidence'][0]['risBase64'])
        self.assertEqual(raw, self.engine.raw_response)
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network not allowed')):
            opened = unpack(blob)
        self.assertEqual(opened['replay'][0][0]['status'], 'match')
        self.assertEqual(opened['snapshots'], view['snapshots'])
        self.assertEqual(opened['snapshots'][0]['results'][0]['groups'][0]['neighbors'][0]['relationship'], 'provider')

    def test_corrupt_member_checksum_rejected(self):
        _, blob = self.capture({'2026-08-01':[route([174,63])]})
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            files = {name:z.read(name) for name in z.namelist()}
        files['SUMMARY.txt'] += b'corruption'
        output = io.BytesIO()
        with zipfile.ZipFile(output,'w') as z:
            for name,value in files.items(): z.writestr(name,value)
        with self.assertRaisesRegex(LookupError,'integrity'):
            unpack(output.getvalue())

    def test_replay_detects_modified_saved_result_even_with_new_hash(self):
        _, blob = self.capture({'2026-08-01':[route([174,63])]})
        data = self.data(blob)
        data['snapshots'][0]['result']['results'][0]['groups'][0]['neighbors'][0]['peerCount']=999
        opened = unpack(pack(data))
        self.assertEqual(opened['replay'][0][0]['status'],'mismatch')
        self.assertEqual(opened['snapshots'][0]['results'][0]['groups'],[])

    def test_no_common_peers_is_unavailable_not_zero_changes(self):
        view,_=self.capture({'2026-08-01':[route([174,63])], '2026-08-02':[route([1299,63],peer='01-1.1.1.1')]},['2026-08-01','2026-08-02'])
        result=view['comparison'][0]
        self.assertIsNone(result['commonPeerChanges'])
        self.assertEqual(len(result['allChanges']),2)

    def test_common_peer_view_separates_coverage_change(self):
        a=[route([174,63]),route([1299,63],peer='01-1.1.1.1')]
        b=[route([174,63])]
        view,_=self.capture({'2026-08-01':a,'2026-08-02':b},['2026-08-01','2026-08-02'])
        row=view['comparison'][0]
        self.assertEqual(row['commonPeerChanges'],[])
        self.assertEqual(row['allChanges'][0]['change'],'Previously observed adjacency not seen')
        self.assertEqual(row['coverage']['notSeen'],['01-1.1.1.1'])

    def test_source_error_does_not_infer_disappearance(self):
        view,blob=self.capture({'2026-08-01':[route([174,63])],'2026-08-02':LookupError('unavailable')},['2026-08-01','2026-08-02'])
        self.assertEqual(view['comparison'][0]['status'],'unavailable')
        self.assertEqual(unpack(blob)['comparison'][0]['status'],'unavailable')

    def test_empty_success_is_valid_negative_observation(self):
        view,blob=self.capture({'2026-08-01':[route([174,63])],'2026-08-02':[]},['2026-08-01','2026-08-02'])
        self.assertEqual(unpack(blob)['replay'][1][0]['status'],'match')
        self.assertEqual(view['comparison'][0]['allChanges'][0]['change'],'Previously observed adjacency not seen')

    def test_prepend_normalization_replays(self):
        _,blob=self.capture({'2026-08-01':[route([174,174,63]),route([174,1299,174,63])]})
        view=unpack(blob)
        self.assertEqual(view['replay'][0][0]['status'],'match')
        self.assertEqual(view['snapshots'][0]['results'][0]['skippedPaths'],1)

    def test_path_change_preserves_adjacency(self):
        view,_=self.capture({'2026-08-01':[route([174,13789,63])],'2026-08-02':[route([1299,13789,63])]},['2026-08-01','2026-08-02'])
        self.assertEqual(view['comparison'][0]['allChanges'][0]['change'],'Observed path changed')

    def test_relationship_change_is_separate(self):
        _,blob=self.capture({'2026-08-01':[route([13789,63])],'2026-08-02':[route([13789,63])]},['2026-08-01','2026-08-02'])
        data=self.data(blob);second=data['snapshots'][1]
        second['evidence'][0]['relationships'][0][2]='peer'
        second['result']['results'][0]['groups'][0]['neighbors'][0]['relationship']='peer'
        view=unpack(pack(data))
        self.assertEqual(view['comparison'][0]['allChanges'],[])
        self.assertEqual(view['comparison'][0]['relationshipChanges'][0]['after'],'peer')

    def test_reject_path_traversal_duplicate_and_unknown_members(self):
        for names in [['../x','manifest.json','investigation.json'],['manifest.json']*3,['a','b','c']]:
            output=io.BytesIO()
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                with zipfile.ZipFile(output,'w') as z:
                    for name in names:z.writestr(name,'{}')
            with self.assertRaises(LookupError):unpack(output.getvalue())

    def test_unknown_schema_and_input_mismatch_rejected(self):
        _,blob=self.capture({'2026-08-01':[route([174,63])]})
        data=self.data(blob)
        for field,value in [('schemaVersion',99),('inputs',['AS100'])]:
            bad=copy.deepcopy(data);bad[field]=value
            with self.assertRaises(LookupError):unpack(pack(bad))

    def test_raw_timestamp_cannot_be_relabeled(self):
        _,blob=self.capture({'2026-08-01':[route([174,63])]})
        data=self.data(blob);data['snapshots'][0]['requestedDate']='2026-08-02'
        with self.assertRaises(LookupError):unpack(pack(data))

    def test_enrichment_absence_is_preserved(self):
        def ris(item,requested):
            state={'timestamp':'2026-08-01T12:00:00','bgp_state':[route([174,63])]}
            self.engine.raw_response=json.dumps({'status':'ok','data':state}).encode();return state,'https://stat.ripe.net/data/bgp-state/data.json'
        with patch.object(self.engine,'ris',side_effect=ris),patch.object(self.engine,'relationships',side_effect=LookupError('missing')),patch.object(self.engine.datasets,'organizations',side_effect=LookupError('missing')):
            _,blob=build(self.engine,'AS63',['2026-08-01'])
        result=unpack(blob)
        self.assertEqual(result['replay'][0][0]['status'],'match')
        self.assertEqual(len(result['snapshots'][0]['results'][0]['warnings']),2)

    def test_special_use_has_no_replay_claim(self):
        with patch.object(self.engine,'ris',side_effect=AssertionError('network')):
            view,blob=build(self.engine,'10.0.0.1',['latest'])
        self.assertEqual(unpack(blob)['replay'][0][0]['status'],'unavailable')

    def test_capture_limit_is_explicit(self):
        cap=Capture();cap.size=16_000_000
        with self.assertRaisesRegex(LookupError,'exceeds'):
            cap.add({'input':'AS63'},b'{}','url',{}, {})

    def test_zip_expansion_limit(self):
        _,blob=self.capture({'2026-08-01':[route([174,63])]})
        with patch('investigations.MAX_EXPANDED',100):
            with self.assertRaises(LookupError):unpack(blob)

    def test_invalid_comparison_order(self):
        with self.assertRaises(LookupError):build(self.engine,'AS63',['2026-08-02','2026-08-01'])


if __name__=='__main__':unittest.main()
