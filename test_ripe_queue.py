import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from email.utils import formatdate

from lookup import Datasets, LookupError
from paths import PathLookup
from ripe_queue import RipeGate, PauseWork


class FakeClock:
    def __init__(self): self.now=1780000000.0
    def __call__(self): return self.now
    def sleep(self,seconds): self.now+=seconds


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.clock=FakeClock()
        self.gate=RipeGate(self.temp.name,clock=self.clock,sleep=self.clock.sleep)
    def tearDown(self): self.temp.cleanup()
    def fetch(self,url='u',callback=lambda:b'raw',requested='latest'):
        return self.gate.fetch(url,requested,callback,lambda raw:None)
    def test_only_budget_survives_restart(self):
        self.fetch();self.assertEqual(self.gate.status()['usedToday'],1)
        other=RipeGate(self.temp.name,clock=self.clock,sleep=self.clock.sleep)
        self.assertIsNone(other.cached('u','latest'))
        self.assertEqual(other.status()['usedToday'],1)
        self.clock.now+=301
        self.fetch();self.assertEqual(self.gate.status()['usedToday'],2)
    def test_spacing_and_retries_count(self):
        starts=[]
        def request():
            starts.append(self.clock())
            if len(starts)==1:raise HTTPError('u',429,'rate limited',{'Retry-After':'7'},None)
            return b'raw'
        self.fetch(callback=request)
        self.fetch('second',lambda:starts.append(self.clock()) or b'raw')
        self.assertGreaterEqual(starts[1]-starts[0],7)
        self.assertGreaterEqual(starts[2]-starts[1],2)
        self.assertEqual(self.gate.status()['usedToday'],3)
    def test_notice_at_1000_does_not_block_and_resets_utc(self):
        self.fetch()
        with self.gate.db() as db:db.execute('UPDATE gate SET used=999 WHERE id=1')
        self.assertFalse(self.gate.status()['registrationNotice'])
        self.fetch('second')
        self.assertTrue(self.gate.status()['registrationNotice'])
        self.fetch('third')
        self.assertEqual(self.gate.status()['usedToday'],1001)
        other=RipeGate(self.temp.name,clock=self.clock,sleep=self.clock.sleep)
        self.assertEqual(other.status()['usedToday'],1001)
        self.clock.now+=86400
        self.assertFalse(self.gate.status()['registrationNotice'])
        self.fetch('fourth');self.assertEqual(self.gate.status()['usedToday'],1)
    def test_retry_after_http_date_survives_restart(self):
        def failure():raise HTTPError('u',503,'busy',{'Retry-After':formatdate(self.clock()+3600,usegmt=True)},None)
        with self.assertRaises(PauseWork):self.fetch(callback=failure)
        other=RipeGate(self.temp.name,clock=self.clock,sleep=self.clock.sleep)
        with self.assertRaises(PauseWork):other.fetch('v','latest',lambda:self.fail('cooldown bypass'),lambda _:None)
        self.assertGreaterEqual(other.status()['blockedUntil'],self.clock()+3599)
    def test_repeated_errors_open_shared_circuit(self):
        def failure():raise HTTPError('u',503,'busy',{},None)
        with self.assertRaises(PauseWork):self.fetch(callback=failure)
        self.assertEqual(self.gate.status()['usedToday'],3)
        with self.assertRaises(PauseWork):self.fetch('other')
        self.assertEqual(self.gate.status()['usedToday'],3)
    def test_checkpoint_interrupts_wait_before_network(self):
        self.fetch();calls=[]
        with self.gate.context(lambda:(_ for _ in ()).throw(PauseWork('pause')),lambda _:None):
            with self.assertRaises(PauseWork):self.fetch('v',lambda:calls.append(1))
        self.assertEqual(calls,[])
    def test_pause_is_after_slow_failed_response(self):
        def failure():
            self.clock.now+=10
            raise HTTPError('u',404,'missing',{},None)
        with self.assertRaises(HTTPError):self.fetch(callback=failure)
        finished=self.clock();starts=[]
        self.fetch('v',lambda:starts.append(self.clock()) or b'raw')
        self.assertGreaterEqual(starts[0]-finished,2)

    def test_nontransient_not_retried(self):
        def failure():raise HTTPError('u',404,'missing',{},None)
        with self.assertRaises(HTTPError):self.fetch(callback=failure)
        self.assertEqual(self.gate.status()['usedToday'],1)
    def test_only_one_request_active(self):
        active=0;maximum=0;lock=threading.Lock();entered=threading.Event();release=threading.Event()
        def request():
            nonlocal active,maximum
            with lock:active+=1;maximum=max(maximum,active)
            entered.set();release.wait(2)
            with lock:active-=1
            return b'raw'
        first=threading.Thread(target=lambda:self.fetch('a',request));second=threading.Thread(target=lambda:self.fetch('b',request))
        first.start();entered.wait(2);second.start();release.set();first.join(3);second.join(3)
        self.assertFalse(first.is_alive() or second.is_alive());self.assertEqual(maximum,1)
    def test_invalid_payload_not_cached(self):
        with self.assertRaises(ValueError):self.gate.fetch('u','latest',lambda:b'bad',lambda _:(_ for _ in ()).throw(ValueError()))
        self.assertIsNone(self.gate.cached('u','latest'))


if __name__=='__main__':unittest.main()
