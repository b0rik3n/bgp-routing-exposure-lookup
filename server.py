"""Local web interface and bounded job API for BGP Provider Lookup."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlparse

from lookup import Datasets, LookupError, MAX_TEXT, csv_export, parse_import, run_lookup
from paths import MAX_PATH_INPUTS, PathLookup, parse_path_resource, path_csv_export

ROOT = Path(__file__).parent
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css"), "/icons.svg": ("icons.svg", "image/svg+xml")}


class JobStore:
    def __init__(self, datasets):
        self.datasets = datasets
        self.paths = PathLookup(datasets)
        self.jobs = {}
        self.lock = threading.Lock()
        self.capacity = threading.BoundedSemaphore(3)
        self.pool = ThreadPoolExecutor(max_workers=1)

    def create(self, text, requested, mode="origins"):
        self.purge()
        with self.lock:
            if len(self.jobs) >= 40 or not self.capacity.acquire(blocking=False):
                raise LookupError("Lookup service is busy. Retry shortly.")
            job_id, token = secrets.token_hex(16), secrets.token_urlsafe(32)
            job = {"id": job_id, "token": token, "created": time.time(), "state": "queued", "message": "Queued"}
            self.jobs[job_id] = job
        self.pool.submit(self.run, job_id, text, requested, mode)
        return {"id": job_id, "token": token}

    def purge(self):
        with self.lock:
            self.jobs = {key: job for key, job in self.jobs.items() if time.time() - job["created"] < 3600}

    def run(self, job_id, text, requested, mode):
        def progress(message):
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id].update(state="running", message=message)
        try:
            result = self.paths.lookup(text, requested, progress) if mode == "paths" else run_lookup(text, requested, self.datasets, progress)
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id].update(state="complete", message="Complete", result=result)
        except (LookupError, csv.Error, ValueError):
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id].update(state="failed", message="Lookup could not complete. Check the input and dataset availability.")
        except Exception:
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id].update(state="failed", message="Lookup service failed. Retry or check the local service.")
        finally:
            self.capacity.release()

    def read(self, job_id, token):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or time.time() - job["created"] >= 3600 or not secrets.compare_digest(job["token"], token):
                return None
            return {key: value for key, value in job.items() if key not in ("token", "created")}


class LookupHTTPServer(ThreadingHTTPServer):
    def service_actions(self):
        self.jobs.purge()


class Handler(BaseHTTPRequestHandler):
    server_version = "BGPProviderLookup/0.1"

    def log_message(self, *_):
        pass

    def reply(self, value, status=200, content_type="application/json", filename=None):
        body = value if isinstance(value, bytes) else (json.dumps(value).encode() if content_type == "application/json" else value.encode())
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
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
        if path == "/api/health":
            return self.reply({"status": "ready", "maxInputs": 1000})
        parts = path.strip("/").split("/")
        if len(parts) in (3, 4) and parts[:2] == ["api", "jobs"]:
            job = self.server.jobs.read(parts[2], self.headers.get("X-Job-Token", ""))
            if not job:
                return self.reply({"error": "Import not found or expired"}, 404)
            if len(parts) == 3:
                return self.reply(job)
            if parts[3] == "export" and job["state"] == "complete":
                exporter = path_csv_export if job["result"].get("kind") == "paths" else csv_export
                return self.reply(exporter(job["result"]), content_type="text/csv", filename="network-lookup.csv")
        self.reply({"error": "Not found"}, 404)

    def do_POST(self):
        if not self.allowed():
            return
        if self.path != "/api/jobs":
            return self.reply({"error": "Not found"}, 404)
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            return self.reply({"error": "JSON input required"}, 415)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_TEXT * 2:
                return self.reply({"error": "Import exceeds the size limit"}, 413)
            self.connection.settimeout(15)
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise LookupError("Invalid import.")
            text, requested = body.get("text"), body.get("date", "latest")
            mode = body.get("mode", "origins")
            if mode not in ("origins", "paths"):
                raise LookupError("Invalid lookup mode.")
            if mode == "paths":
                parse_import(text, parse_path_resource, MAX_PATH_INPUTS)
            else:
                parse_import(text)
            if requested != "latest":
                if not isinstance(requested, str) or not (date(2005, 5, 9) <= date.fromisoformat(requested) <= datetime.now(timezone.utc).date()):
                    raise LookupError("Choose a valid historical date.")
            job = self.server.jobs.create(text, requested, mode)
            return self.reply(job, 202)
        except LookupError as exc:
            return self.reply({"error": str(exc)}, 429 if "busy" in str(exc) else 400)
        except (ValueError, TypeError, csv.Error, TimeoutError):
            return self.reply({"error": "Invalid import or date"}, 400)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--cache", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    service_token = os.environ.get("BGP_LOOKUP_SERVICE_TOKEN", "")
    if args.host != "127.0.0.1" and len(service_token) < 32:
        parser.error("A service token of at least 32 characters is required for non-loopback binding.")
    server = LookupHTTPServer((args.host, args.port), Handler)
    server.service_token = service_token
    server.jobs = JobStore(Datasets(args.cache))
    print(f"Network Lookup: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
