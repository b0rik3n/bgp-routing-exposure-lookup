"""Local web interface and bounded job API for BGP Routing Exposure Lookup."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import csv
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import threading
import time
from urllib.parse import urlparse

from lookup import Datasets, LookupError, MAX_TEXT, csv_export, parse_import, run_lookup
from investigations import MAX_BUNDLE, build as build_investigation, unpack as open_investigation
from ripe_queue import RipeGate, PauseWork, CancelWork, acquire_owner
from paths import MAX_PATH_INPUTS, PathLookup, parse_path_resource, path_csv_export

ROOT = Path(__file__).parent
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css"), "/icons.svg": ("icons.svg", "image/svg+xml")}


class JobStore:
    def __init__(self, datasets, gate=None, result_budget=128_000_000):
        self.result_budget = result_budget
        self.datasets = datasets
        self.paths = PathLookup(datasets, gate)
        self.jobs = {}
        self.lock = threading.Lock()
        self.capacity = threading.BoundedSemaphore(3)
        self.pool = ThreadPoolExecutor(max_workers=1)

    def create(self, text, requested, mode="origins", comparison_date=None):
        self.purge()
        with self.lock:
            if not self.capacity.acquire(blocking=False):
                raise LookupError("Lookup service is busy. Retry shortly.")
            if len(self.jobs) >= 40:
                self.evict_finished()
            if len(self.jobs) >= 40:
                self.capacity.release()
                raise LookupError("Lookup service is busy. Retry shortly.")
            job_id, token = secrets.token_hex(16), secrets.token_urlsafe(32)
            job = {"id": job_id, "token": token, "created": time.time(), "state": "queued", "message": "Queued"}
            self.jobs[job_id] = job
        self.pool.submit(self.run, job_id, text, requested, mode, comparison_date)
        return {"id": job_id, "token": token}

    def evict_finished(self):
        # Caller holds the lock; active work is never evicted.
        finished = [(key, job) for key, job in self.jobs.items() if job["state"] not in ("queued", "running")]
        if not finished:
            return False
        key, _ = min(finished, key=lambda item: item[1].get("finished", item[1]["created"]))
        del self.jobs[key]
        return True

    def retained_bytes(self):
        return sum(len(j.get("result_bytes", b"")) + len(j.get("bundle", b"")) for j in self.jobs.values())

    def purge(self):
        with self.lock:
            self.jobs = {key: job for key, job in self.jobs.items() if (job.get("state") in ("queued","running") or time.time() - job.get("finished",job["created"]) < 3600)}

    def cancel(self, job_id, token):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or not secrets.compare_digest(job['token'],token):
                return False
            if job['state'] in ('queued','running'):
                job['cancelRequested'] = True
                job['message'] = 'Cancelling; an in-flight request may finish.'
            return True

    def run(self, job_id, text, requested, mode, comparison_date=None):
        def checkpoint():
            with self.lock:
                if self.jobs.get(job_id, {}).get('cancelRequested'):
                    raise CancelWork('Cancelled by user.')
        def progress(message):
            checkpoint()
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id].update(state="running", message=message)
        def report(value):
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id]["progress"] = value
        progress.report = report
        try:
            checkpoint()
            self.datasets.checkpoint = checkpoint
            bundle = None
            context = self.paths.gate.context(checkpoint, progress) if self.paths.gate else nullcontext()
            with context:
                if mode == "investigation":
                    dates = [requested, comparison_date] if comparison_date else [requested]
                    result, bundle = build_investigation(self.paths, text, dates, progress)
                else:
                    result = self.paths.lookup(text, requested, progress) if mode == "paths" else run_lookup(text, requested, self.datasets, progress)
            encoded = json.dumps(result, separators=(",", ":"), allow_nan=False).encode()
            amount = len(encoded) + len(bundle or b"")
            if amount > self.result_budget:
                raise LookupError("Result exceeds the shared storage budget. Split the input into smaller batches.")
            with self.lock:
                if job_id in self.jobs:
                    while self.retained_bytes() + amount > self.result_budget:
                        if not self.evict_finished():
                            raise LookupError("Result storage is full. Split the input into smaller batches.")
                    cancelled = self.jobs[job_id].get('cancelRequested', False)
                    self.jobs[job_id].update(state="cancelled" if cancelled else "complete",
                        message="Cancelled; completed results are available." if cancelled else "Complete",
                        result_bytes=encoded, finished=time.time())
                    if bundle:
                        self.jobs[job_id]["bundle"] = bundle
        except CancelWork:
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id].update(state='cancelled',message='Cancelled. No complete result or investigation bundle was produced.')
        except (PauseWork, LookupError, csv.Error, ValueError) as exc:
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id].update(state="failed", message=str(exc) if isinstance(exc, (LookupError, PauseWork)) else "Lookup could not complete. Check the input and dataset availability.")
        except Exception:
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id].update(state="failed", message="Lookup service failed. Retry or check the local service.")
        finally:
            self.datasets.checkpoint = lambda: None
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id].setdefault("finished",time.time())
            self.capacity.release()

    def read(self, job_id, token):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or (job.get("state") not in ("queued","running") and time.time() - job.get("finished",job["created"]) >= 3600) or not secrets.compare_digest(job["token"], token):
                return None
            value = {key: value for key, value in job.items() if key not in ("token", "created", "bundle", "finished", "result_bytes")}
            encoded = job.get("result_bytes")
        if encoded is not None:
            value["result"] = json.loads(encoded)
        return value

    def bundle(self, job_id, token):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or (job.get("state") not in ("queued","running") and time.time() - job.get("finished",job["created"]) >= 3600) or not secrets.compare_digest(job["token"], token):
                return None
            return job.get("bundle")


class LookupHTTPServer(ThreadingHTTPServer):
    max_connections = 32
    header_deadline = 15
    idle_timeout = 10

    def __init__(self, *args, **kwargs):
        self.connections = threading.BoundedSemaphore(self.max_connections)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            request.settimeout(self.idle_timeout)
            super().process_request(request, client_address)
        except Exception:
            self.connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connections.release()

    def service_actions(self):
        self.jobs.purge()


class Handler(BaseHTTPRequestHandler):
    server_version = "BGPRoutingExposureLookup/0.1"

    def expire_connection(self):
        self.connection_expired = True
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def handle_one_request(self):
        self.connection_expired = False
        self.header_timer = threading.Timer(self.server.header_deadline, self.expire_connection)
        self.header_timer.daemon = True
        self.header_timer.start()
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        finally:
            self.header_timer.cancel()

    def parse_request(self):
        try:
            return super().parse_request() and not self.connection_expired
        finally:
            self.header_timer.cancel()

    def read_body(self, size, deadline):
        timer = threading.Timer(deadline, self.expire_connection)
        timer.daemon = True
        timer.start()
        try:
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise LookupError("Incomplete upload. Try again.")
            return raw
        finally:
            timer.cancel()

    def log_message(self, *_):
        pass

    def reply(self, value, status=200, content_type="application/json", filename=None):
        body = value if isinstance(value, bytes) else (json.dumps(value).encode() if content_type == "application/json" else value.encode())
        self.send_response(status)
        self.send_header("Content-Type", content_type if content_type == "application/zip" else content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def allowed(self):
        token = self.server.service_token
        if token:
            if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.reply({"error": "Unauthorized"}, 401)
                return False
        else:
            host = self.headers.get("Host", "")
            if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                self.reply({"error": "Invalid host"}, 403)
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                self.reply({"error": "Cross-origin requests are not allowed"}, 403)
                return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        path = urlparse(self.path).path
        if path in ASSETS:
            filename, kind = ASSETS[path]
            return self.reply((ROOT / "web" / filename).read_bytes(), content_type=kind)
        if path == "/api/requests":
            return self.reply(self.server.jobs.paths.gate.status())
        if path == "/api/health":
            return self.reply({"status": "ready", "maxInputs": 1000})
        parts = path.strip("/").split("/")
        if len(parts) in (3, 4) and parts[:2] == ["api", "jobs"]:
            job = self.server.jobs.read(parts[2], self.headers.get("X-Job-Token", ""))
            if not job:
                return self.reply({"error": "Import not found or expired"}, 404)
            if len(parts) == 3:
                return self.reply(job)
            if parts[3] == "bundle" and job["state"] in ("complete","cancelled") and "result" in job:
                bundle = self.server.jobs.bundle(parts[2], self.headers.get("X-Job-Token", ""))
                if bundle is None:
                    return self.reply({"error": "Bundle unavailable or expired. Capture the investigation again."}, 404)
                return self.reply(bundle, content_type="application/zip", filename="routing-investigation.zip")
            if parts[3] == "export" and job["state"] in ("complete","cancelled") and "result" in job and job["result"].get("kind") != "investigation":
                exporter = path_csv_export if job["result"].get("kind") == "paths" else csv_export
                return self.reply(exporter(job["result"]), content_type="text/csv", filename="network-lookup.csv")
        self.reply({"error": "Not found"}, 404)

    def do_POST(self):
        if not self.allowed():
            return
        parts = self.path.strip('/').split('/')
        if len(parts)==4 and parts[:2]==['api','jobs'] and parts[3]=='cancel':
            if not self.server.jobs.cancel(parts[2], self.headers.get('X-Job-Token','')):
                return self.reply({'error':'Job not found'},404)
            return self.reply({'status':'Cancellation requested'})
        if self.path in ("/api/investigations/open", "/api/investigations/replay"):
            return self.import_investigation()
        if self.path != "/api/jobs":
            return self.reply({"error": "Not found"}, 404)
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            return self.reply({"error": "JSON input required"}, 415)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_TEXT * 2:
                return self.reply({"error": "Import exceeds the size limit"}, 413)
            self.connection.settimeout(15)
            body = json.loads(self.read_body(size, 30))
            if not isinstance(body, dict):
                raise LookupError("Invalid import.")
            text, requested = body.get("text"), body.get("date", "latest")
            mode = body.get("mode", "origins")
            if mode not in ("origins", "paths", "investigation"):
                raise LookupError("Invalid lookup mode.")
            if mode in ("paths", "investigation"):
                parse_import(text, parse_path_resource, MAX_PATH_INPUTS)
            else:
                parse_import(text)
            if requested != "latest":
                if not isinstance(requested, str) or not (date(2005, 5, 9) <= date.fromisoformat(requested) <= datetime.now(timezone.utc).date()):
                    raise LookupError("Choose a valid historical date.")
            comparison_date = body.get("comparisonDate")
            if comparison_date is not None:
                if mode != "investigation" or requested == "latest" or not isinstance(comparison_date, str):
                    raise LookupError("Choose two historical dates for comparison.")
                if not date.fromisoformat(requested) < date.fromisoformat(comparison_date) <= datetime.now(timezone.utc).date():
                    raise LookupError("Comparison dates must be chronological and not in the future.")
            if mode in ("paths","investigation"):
                import io
                unique = {}
                for item in parse_import(text, parse_path_resource, MAX_PATH_INPUTS):
                    unique.setdefault(item.get('resource',item['input']),item)
                output = io.StringIO()
                writer = csv.writer(output)
                for item in unique.values():
                    writer.writerow([item['input']])
                text = output.getvalue()
            job = self.server.jobs.create(text, requested, mode, comparison_date)
            return self.reply(job, 202)
        except LookupError as exc:
            return self.reply({"error": str(exc)}, 429 if "busy" in str(exc) else 400)
        except (ValueError, TypeError, csv.Error, TimeoutError, RecursionError):
            return self.reply({"error": "Invalid import or date"}, 400)

    def import_investigation(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/zip":
            return self.reply({"error": "Investigation ZIP required"}, 415)
        # One import/replay at a time, using the same capacity budget as lookups.
        if not self.server.jobs.capacity.acquire(blocking=False):
            return self.reply({"error": "Lookup service is busy. Retry shortly."}, 429)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BUNDLE:
                return self.reply({"error": "Investigation must be at most 32 MB"}, 413)
            self.connection.settimeout(30)
            raw = self.read_body(size, 60)
            result = open_investigation(raw)
            return self.reply(result)
        except (LookupError, ValueError, TimeoutError, OSError) as exc:
            return self.reply({"error": str(exc) if isinstance(exc, LookupError) else "Investigation could not be read."}, 400)
        finally:
            self.server.jobs.capacity.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--cache", type=Path, default=ROOT / "data")
    parser.add_argument('--ripe-interval', type=float, default=2.0, help='Seconds between RIPE requests (minimum 2)')
    args = parser.parse_args()
    service_token = os.environ.get("BGP_LOOKUP_SERVICE_TOKEN", "")
    if args.host != "127.0.0.1" and len(service_token) < 32:
        parser.error("A service token of at least 32 characters is required for non-loopback binding.")
    server = LookupHTTPServer((args.host, args.port), Handler)
    server.service_token = service_token
    try:
        owner = acquire_owner(args.cache)
        gate = RipeGate(args.cache / 'private', args.ripe_interval)
    except ValueError as exc:
        parser.error(str(exc))
    server.jobs = JobStore(Datasets(args.cache), gate)
    print(f"BGP Routing Exposure Lookup: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
