import http.client
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import json

from lookup import Datasets
from investigations import build
from paths import PathLookup
from server import Handler, JobStore, LookupHTTPServer


class InvestigationHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.datasets = Datasets(Path(cls.tmp.name))
        cls.server = LookupHTTPServer(('127.0.0.1',0), Handler)
        cls.server.service_token = ''
        cls.server.jobs = JobStore(cls.datasets)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        _, cls.bundle = build(PathLookup(cls.datasets),'10.0.0.1',['latest'])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
        cls.server.jobs.pool.shutdown();cls.tmp.cleanup()

    def request(self, method, path, body=b'', headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            conn.request(method,path,body,headers or {})
            response=conn.getresponse();return response.status,response.read()
        finally:conn.close()

    def test_open_and_replay_do_not_use_network(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('external network used')):
            for action in ('open','replay'):
                status,body=self.request('POST','/api/investigations/'+action,self.bundle,{'Content-Type':'application/zip'})
                self.assertEqual(status,200)
                self.assertEqual(json.loads(body)['replay'][0][0]['status'],'unavailable')

    def test_cross_origin_upload_rejected(self):
        status,_=self.request('POST','/api/investigations/open',self.bundle,{'Content-Type':'application/zip','Origin':'https://example.com'})
        self.assertEqual(status,403)

    def test_bundle_requires_job_token_and_binary_type(self):
        import time
        self.server.jobs.jobs['fixture']={'created':time.time(),'token':'secret','bundle':self.bundle,'state':'complete','result':{'kind':'investigation'}}
        status,_=self.request('GET','/api/jobs/fixture/bundle')
        self.assertEqual(status,404)
        status,body=self.request('GET','/api/jobs/fixture/bundle',headers={'X-Job-Token':'secret'})
        self.assertEqual(status,200);self.assertEqual(body,self.bundle)
        status,body=self.request('GET','/api/jobs/fixture',headers={'X-Job-Token':'secret'})
        self.assertNotIn('bundle',json.loads(body))

    def test_malformed_zip_rejected(self):
        status,_=self.request('POST','/api/investigations/open',b'not a zip',{'Content-Type':'application/zip'})
        self.assertEqual(status,400)

    def test_service_token_applies_to_import(self):
        self.server.service_token='test-token'
        try:
            status,_=self.request('POST','/api/investigations/open',self.bundle,{'Content-Type':'application/zip'})
            self.assertEqual(status,401)
        finally:self.server.service_token=''


if __name__=='__main__':unittest.main()
