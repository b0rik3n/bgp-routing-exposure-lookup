import tempfile
import threading
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from lookup import Datasets,run_lookup
from server import JobStore
from ripe_queue import CancelWork,RipeGate

class CancelTests(TestCase):
    def wait(self,store,job):
        for _ in range(200):
            result=store.read(job['id'],job['token'])
            if result['state'] in ('complete','cancelled','failed'):return result
            time.sleep(.01)
        self.fail('job did not stop')
    def test_running_paths_cancel_keeps_partial_and_blocks_next_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=JobStore(Datasets(Path(tmp)),RipeGate(Path(tmp)/'private'))
            entered,release=threading.Event(),threading.Event()
            def ris(item,date):
                entered.set();release.wait(3)
                return {'bgp_state':[],'timestamp':'2026-01-01T12:00:00'},'https://stat.ripe.net/data/bgp-state/data.json'
            try:
                with patch.object(store.paths,'ris',side_effect=ris) as fetch:
                    job=store.create('AS63\nAS64','latest','paths');self.assertTrue(entered.wait(3))
                    self.assertFalse(store.cancel(job['id'],'wrong'))
                    self.assertTrue(store.cancel(job['id'],job['token']));release.set()
                    result=self.wait(store,job)
                self.assertEqual(result['state'],'cancelled');self.assertEqual(fetch.call_count,1)
                self.assertEqual(result['progress']['completed'],1)
                self.assertEqual(result['progress']['remaining'],1)
                self.assertEqual(result['progress']['notRequested'],1)
                self.assertEqual([x['status'] for x in result['result']['results']],['not_observed','not_requested'])
            finally:release.set();store.pool.shutdown()
    def test_queued_cancel_does_not_execute_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=JobStore(Datasets(Path(tmp)));release=threading.Event()
            store.pool.submit(release.wait,3)
            try:
                with patch.object(store.paths,'lookup',side_effect=AssertionError('cancelled job executed')):
                    job=store.create('AS63','latest','paths');store.cancel(job['id'],job['token']);release.set()
                    self.assertEqual(self.wait(store,job)['state'],'cancelled')
            finally:release.set();store.pool.shutdown()
    def test_origins_keep_completed_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            def progress(message):
                if 'entry 2' in message:raise CancelWork('Cancelled')
            result=run_lookup('10.0.0.1\n10.0.0.2','latest',Datasets(Path(tmp)),progress)
            self.assertEqual([x['status'] for x in result['results']],['special_use','not_requested'])
    def test_investigation_cancel_does_not_publish_partial_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=JobStore(Datasets(Path(tmp)))
            try:
                with patch('server.build_investigation',side_effect=CancelWork('Cancelled')):
                    job=store.create('AS63','latest','investigation');result=self.wait(store,job)
                self.assertEqual(result['state'],'cancelled');self.assertNotIn('result',result)
                self.assertIsNone(store.bundle(job['id'],job['token']))
            finally:store.pool.shutdown()
