import http.client
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from lookup import Datasets
from server import Handler, JobStore, LookupHTTPServer, SourceAccess


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(Datasets(Path(self.tmp.name)))
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.store.pool.shutdown)

    def finish(self, job):
        for _ in range(500):
            value = self.store.read(job['id'], job['token'])
            if value['state'] not in ('queued', 'running'):
                return value
            time.sleep(.002)
        self.fail('Job did not finish')

    def test_forty_first_job_evicts_oldest_finished(self):
        jobs = []
        for _ in range(41):
            job = self.store.create('invalid', 'latest', 'paths')
            self.assertEqual(self.finish(job)['state'], 'complete')
            jobs.append(job)
        self.assertEqual(len(self.store.jobs), 40)
        self.assertIsNone(self.store.read(jobs[0]['id'], jobs[0]['token']))
        self.assertIsNotNone(self.store.read(jobs[-1]['id'], jobs[-1]['token']))

    def test_combined_budget_and_token_access(self):
        self.store.result_budget = 200
        payload = {'kind':'investigation', 'value':'x'*50}
        with patch('server.build_investigation', return_value=(payload, b'x'*100)):
            first = self.store.create('AS63', 'latest', 'investigation')
            self.finish(first)
            second = self.store.create('AS64', 'latest', 'investigation')
            value = self.finish(second)
        self.assertEqual(value['result'], payload)
        self.assertIsNone(self.store.read(first['id'], first['token']))
        self.assertIsNone(self.store.read(second['id'], 'wrong'))
        self.assertIsNone(self.store.bundle(second['id'], 'wrong'))
        self.assertEqual(self.store.bundle(second['id'], second['token']), b'x'*100)
        self.assertLessEqual(self.store.retained_bytes(), 200)
        self.assertIsInstance(self.store.jobs[second['id']]['result_bytes'], bytes)
        self.assertNotIn('result', self.store.jobs[second['id']])

    def test_oversized_single_result_fails_without_retention(self):
        self.store.result_budget = 10
        value = self.finish(self.store.create('invalid', 'latest', 'paths'))
        self.assertEqual(value['state'], 'failed')
        self.assertIn('smaller batches', value['message'])
        self.assertEqual(self.store.retained_bytes(), 0)

    def test_active_jobs_not_evicted(self):
        self.store.jobs = {'active':dict(created=0, state='running', token='x'),
                           'queued':dict(created=0, state='queued', token='y'),
                           'done':dict(created=1, state='complete', token='z')}
        with self.store.lock:
            self.assertTrue(self.store.evict_finished())
            self.assertFalse(self.store.evict_finished())
        self.store.purge()
        self.assertEqual(set(self.store.jobs), {'active', 'queued'})

    def test_thousand_entries_progress(self):
        text = '\n'.join(f'10.0.{i//256}.{i%256}' for i in range(1000))
        value = self.finish(self.store.create(text, 'latest', 'paths'))
        self.assertEqual(value['progress']['processed'], 1000)
        self.assertEqual(value['progress']['skipped'], 1000)
        self.assertEqual(value['progress']['remaining'], 0)
        self.assertEqual(len(value['result']['results']), 1000)

    def test_progress_available_during_lookup(self):
        entered, release = threading.Event(), threading.Event()
        def ris(item, requested):
            entered.set()
            release.wait(3)
            return {'timestamp':'2026-08-01T12:00:00','bgp_state':[]}, 'fixture'
        try:
            with patch.object(self.store.paths, 'ris', side_effect=ris):
                job = self.store.create('AS63\ninvalid\n10.0.0.1', 'latest', 'paths')
                self.assertTrue(entered.wait(3))
                progress = self.store.read(job['id'], job['token'])['progress']
                self.assertEqual(progress['current'], 'AS63')
                self.assertEqual(progress['remaining'], 3)
                release.set()
                value = self.finish(job)['progress']
            self.assertEqual((value['completed'], value['failed'], value['skipped']), (1,1,1))
        finally:
            release.set()


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        class SmallServer(LookupHTTPServer):
            max_connections = 2
            header_deadline = .3
            idle_timeout = .15
        self.server = SmallServer(('127.0.0.1',0), Handler)
        self.server.service_token = 'secret'
        self.server.jobs = type('Jobs', (), {'purge':lambda self: None})()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def connect(self):
        sock = socket.create_connection(self.server.server_address, timeout=1)
        self.addCleanup(sock.close)
        return sock

    def test_idle_connection_expires(self):
        sock = self.connect()
        self.assertEqual(sock.recv(1), b'')

    def test_trickling_headers_expires_before_authentication(self):
        sock = self.connect()
        sock.sendall(b'GET /api/health HTTP/1.1\r\nX-Test: ')
        start = time.monotonic()
        while time.monotonic()-start < .6:
            try:
                sock.sendall(b'a')
            except OSError:
                break
            time.sleep(.04)
        self.assertLess(time.monotonic()-start, .6)
        try:
            data = sock.recv(4096)
        except ConnectionResetError:
            data = b''
        self.assertEqual(data, b'')

    def test_excess_connection_closed_and_slots_recover(self):
        # Reserve both slots deterministically, independent of accept scheduling.
        self.server.connections.acquire(); self.server.connections.acquire()
        try:
            sock = self.connect()
            self.assertEqual(sock.recv(1), b'')
        finally:
            self.server.connections.release(); self.server.connections.release()
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            conn.request('GET','/api/health',headers={'Authorization':'Bearer secret'})
            response = conn.getresponse()
            self.assertEqual(response.status,200)
            self.assertEqual(json.loads(response.read())['status'],'ready')
        finally:
            conn.close()

    def test_static_policy_allows_only_ripe_live_websocket(self):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            conn.request('GET','/app.js',headers={'Authorization':'Bearer secret'})
            response = conn.getresponse()
            self.assertEqual(response.status,200)
            self.assertIn("connect-src 'self' wss://ris-live.ripe.net;", response.getheader('Content-Security-Policy'))
        finally:
            conn.close()

    def test_country_map_static_asset_is_served(self):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            conn.request('GET','/world-countries.json',headers={'Authorization':'Bearer secret'})
            response = conn.getresponse()
            self.assertEqual(response.status,200)
            self.assertIn('application/geo+json', response.getheader('Content-Type'))
            payload = json.loads(response.read())
            self.assertEqual(payload['type'], 'FeatureCollection')
            self.assertGreaterEqual(len(payload['features']), 230)
        finally:
            conn.close()


class SourceAccessTests(unittest.TestCase):
    def test_status_reports_each_required_source(self):
        access = SourceAccess()
        self.addCleanup(access.shutdown)
        def probe(url):
            return ("as-organizations" not in url, None if "as-organizations" not in url else "URLError")
        with patch.object(access, 'probe', side_effect=probe):
            access.refresh()
        sources = {entry['id']: entry for entry in access.status()['sources']}
        self.assertEqual(sources['ripe']['state'], 'available')
        self.assertEqual(sources['organizations']['state'], 'unavailable')
        self.assertEqual(sources['relationships']['state'], 'available')
