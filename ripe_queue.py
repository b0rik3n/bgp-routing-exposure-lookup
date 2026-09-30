"""One shared, persistent RIPE request gate for the local server."""
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from collections import OrderedDict
import os
from pathlib import Path
import sqlite3
import threading
import time
from urllib.error import HTTPError, URLError


class PauseWork(Exception):
    """Stop before further remote work; the caller may resume later."""


class CancelWork(PauseWork):
    """The user cancelled this job."""


class RipeGate:
    def __init__(self, directory, interval=2.0, clock=time.time, sleep=time.sleep):
        if not 2 <= interval <= 3600:
            raise ValueError('RIPE interval must be 2–3600 seconds.')
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.directory / 'requests.sqlite3'
        is_new = not self.path.exists()
        self.responses = OrderedDict()
        self.cache_lock = threading.Lock()
        self.interval = interval
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self.local = threading.local()
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS gate (id INTEGER PRIMARY KEY, day TEXT, used INTEGER, next REAL, failures INTEGER, blocked REAL)')
            db.execute("INSERT OR IGNORE INTO gate VALUES (1, '', 0, 0, 0, 0)")
            # Preserve today's counter from the earlier bulk prototype, without loading evidence.
            legacy = self.directory / 'queue.sqlite3'
            if is_new and legacy.exists():
                with sqlite3.connect('file:'+str(legacy)+'?mode=ro', uri=True) as old:
                    row = old.execute('SELECT day,used,next,failures,blocked FROM gate WHERE id=1').fetchone()
                if row:
                    db.execute('UPDATE gate SET day=?,used=?,next=?,failures=?,blocked=? WHERE id=1',row)
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def context(self, checkpoint, progress):
        self.local.checkpoint, self.local.progress = checkpoint, progress
        try:
            yield
        finally:
            self.local.checkpoint = self.local.progress = None

    def check(self):
        callback = getattr(self.local, 'checkpoint', None)
        if callback:
            callback()

    def report(self, text):
        callback = getattr(self.local, 'progress', None)
        if callback:
            callback(text)

    def status(self):
        with self.db() as db:
            row = dict(db.execute('SELECT * FROM gate WHERE id=1').fetchone())
        today = datetime.fromtimestamp(self.clock(), timezone.utc).date().isoformat()
        used = row['used'] if row['day'] == today else 0
        return {'intervalSeconds': self.interval, 'day':today, 'noticeThreshold':1000,
                'usedToday': used, 'registrationNotice':used>=1000,
                'blockedUntil': row['blocked'], 'nextRequestAt': row['next']}

    def cached(self, url, requested):
        with self.cache_lock:
            row = self.responses.get(url)
            if row and 0 <= self.clock()-row[0] < (300 if requested == 'latest' else 3600):
                return row[1]
        return None

    def remember(self, url, raw):
        with self.cache_lock:
            self.responses[url] = (self.clock(),raw)
            self.responses.move_to_end(url)
            while sum(len(r[1]) for r in self.responses.values()) > 32_000_000:
                self.responses.popitem(last=False)

    def retry_after(self, value):
        if not value:
            return 0
        try:
            return max(0, int(value))
        except (ValueError, TypeError):
            try:
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return max(0, parsed.timestamp()-self.clock())
            except (ValueError, TypeError, OverflowError):
                return 0

    def fetch(self, url, requested, fetcher, validator):
        # Hold the gate through receipt of the response, across all callers.
        while not self.lock.acquire(timeout=0.2):
            self.check()
        try:
            self.check()
            raw = self.cached(url, requested)
            if raw is not None:
                return raw
            while True:
                self.check()
                now = self.clock()
                with self.db() as db:
                    row = db.execute('SELECT * FROM gate WHERE id=1').fetchone()
                    today = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
                    used = row['used'] if row['day'] == today else 0
                    if row['blocked'] > now:
                        raise PauseWork('RIPE requests are cooling down. Try again after '+datetime.fromtimestamp(row['blocked'],timezone.utc).isoformat())
                    wait = row['next']-now
                    if wait <= 0:
                        # Reserve each attempt before network I/O, including retries.
                        db.execute('UPDATE gate SET day=?,used=?,next=? WHERE id=1', (today,used+1,now+self.interval))
                if wait > 0:
                    self.report('Waiting for the shared RIPE request pace')
                    self.sleep(min(wait,0.2))
                    continue
                try:
                    raw = fetcher()
                    validator(raw)
                except (HTTPError, URLError, TimeoutError, OSError) as exc:
                    transient = not isinstance(exc,HTTPError) or exc.code == 429 or 500 <= exc.code <= 599
                    if not transient:
                        if isinstance(exc,HTTPError):
                            exc.close()
                        raise
                    after = self.retry_after(exc.headers.get('Retry-After') if isinstance(exc,HTTPError) and exc.headers else None)
                    with self.db() as db:
                        failures = db.execute('SELECT failures FROM gate WHERE id=1').fetchone()[0]+1
                        delay = max(after, min(300,5*2**min(failures-1,6)))
                        until = self.clock()+delay
                        blocked = max(until,self.clock()+300) if failures >= 3 else (until if after > 60 else 0)
                        db.execute('UPDATE gate SET failures=?,next=?,blocked=? WHERE id=1', (failures,until,blocked))
                    if isinstance(exc,HTTPError):
                        exc.close()
                    if blocked:
                        raise PauseWork('RIPE rate limit or repeated service errors. Requests paused until '+datetime.fromtimestamp(blocked,timezone.utc).isoformat()) from exc
                    self.report('Temporary RIPE error; backing off before retrying')
                    continue
                finally:
                    with self.db() as db:
                        db.execute('UPDATE gate SET next=MAX(next,?) WHERE id=1',(self.clock()+self.interval,))
                with self.db() as db:
                    db.execute('UPDATE gate SET failures=0,blocked=0,next=? WHERE id=1',(self.clock()+self.interval,))
                self.remember(url,raw)
                return raw
        finally:
            self.lock.release()


def acquire_owner(directory):
    """Keep the returned file open for the lifetime of a network-using process."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    owner = open(directory / '.server.lock', 'a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            if owner.tell() == 0:
                owner.write(b'0'); owner.flush()
            owner.seek(0)
            msvcrt.locking(owner.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        owner.close()
        raise ValueError('Another process is using this cache. Use the running server so RIPE pacing and budgets stay shared.')
    return owner
