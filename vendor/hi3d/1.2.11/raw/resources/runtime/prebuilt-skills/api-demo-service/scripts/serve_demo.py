"""Loopback demo HTTP server. Request bodies never become shell strings."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from contract import field_errors, normalize_values


def _json(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class JobStore:
    def __init__(self, limit):
        self.limit = int(limit)
        self.lock = threading.Lock()
        self.active = 0
        self.jobs = {}

    def try_acquire(self):
        with self.lock:
            if self.active >= self.limit:
                return False
            self.active += 1
            return True

    def release(self):
        with self.lock:
            self.active = max(0, self.active - 1)

    def put(self, job):
        with self.lock:
            self.jobs[job['id']] = job

    def get(self, job_id):
        with self.lock:
            return dict(self.jobs[job_id]) if job_id in self.jobs else None


def parse_json_body(handler):
    length = int(handler.headers.get('Content-Length') or 0)
    raw = handler.rfile.read(length) if length else b''
    if not raw:
        return {}, {}
    ctype = (handler.headers.get('Content-Type') or '').split(';')[0].strip()
    if ctype != 'application/json':
        raise ValueError('use application/json')
    data = json.loads(raw.decode('utf-8'))
    if not isinstance(data, dict):
        raise ValueError('body must be an object')
    files = {}
    for key, value in list(data.items()):
        if isinstance(value, dict) and 'data' in value and 'name' in value:
            blob = value['data']
            if isinstance(blob, str):
                blob = blob.encode('utf-8')
            elif isinstance(blob, list):
                blob = bytes(value['data'])
            files[key] = {'name': value['name'], 'data': blob}
            data.pop(key)
    return data, files


def execute_algorithm(root: Path, plan, payload):
    argv = plan.get('argv') or [sys.executable, str(root / 'runner.py'), '--plan', str(root / 'plan.json')]
    timeout = float(plan['limits']['timeoutSeconds'])
    try:
        completed = subprocess.run(
            argv,
            input=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            cwd=str(root),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {'ok': False, 'kind': 'timeout', 'error': '执行超时'}
    if completed.returncode != 0:
        message = completed.stderr.decode('utf-8', errors='replace').strip() or 'algorithm failed'
        return {'ok': False, 'kind': 'execution', 'error': message}
    try:
        result = json.loads(completed.stdout.decode('utf-8'))
    except json.JSONDecodeError:
        return {'ok': False, 'kind': 'execution', 'error': '算法未返回 JSON 对象'}
    if not isinstance(result, dict):
        return {'ok': False, 'kind': 'execution', 'error': '算法未返回 JSON 对象'}
    return {'ok': True, 'kind': 'ok', 'result': result}


def prepare_payload(root: Path, plan, values, files):
    errors = field_errors(plan, values, files)
    if errors:
        return {'ok': False, 'kind': 'validation', 'errors': errors}
    payload = normalize_values(plan, values)
    work = root / 'uploads'
    work.mkdir(exist_ok=True)
    for field in plan.get('fields') or []:
        if field['type'] != 'file' or field['id'] not in files:
            continue
        upload = files[field['id']]
        dest = work / (field['id'] + Path(upload['name']).suffix)
        dest.write_bytes(upload['data'])
        payload[field['id']] = {'name': dest.name, 'path': dest.name}
    return {'ok': True, 'payload': payload}


def make_handler(root: Path, plan, store: JobStore, page: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in ('/', '/index.html'):
                body = page.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == '/plan.json':
                body = (root / 'plan.json').read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path.startswith('/jobs/'):
                job = store.get(parsed.path.split('/')[-1])
                if not job:
                    _json(self, 404, {'ok': False, 'kind': 'execution', 'error': '任务不存在'})
                    return
                _json(self, 200, job)
                return
            self.send_error(404)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != '/run':
                self.send_error(404)
                return
            if not store.try_acquire():
                _json(self, 409, {'ok': False, 'kind': 'busy', 'error': '已有任务执行中，请勿重复提交'})
                return
            handed_off = False
            try:
                try:
                    values, files = parse_json_body(self)
                except (ValueError, json.JSONDecodeError) as error:
                    _json(self, 400, {'ok': False, 'kind': 'validation', 'error': str(error)})
                    return
                prepared = prepare_payload(root, plan, values, files)
                if not prepared.get('ok'):
                    _json(self, 400, prepared)
                    return
                if plan['mode'] == 'background':
                    job_id = uuid.uuid4().hex[:12]
                    job = {'id': job_id, 'status': 'running', 'ok': None}
                    store.put(job)

                    def worker():
                        try:
                            outcome = execute_algorithm(root, plan, prepared['payload'])
                            job.update(outcome)
                            job['status'] = 'done' if outcome.get('ok') else 'failed'
                            store.put(job)
                        finally:
                            store.release()

                    threading.Thread(target=worker, daemon=True).start()
                    handed_off = True
                    _json(self, 202, {'ok': True, 'jobId': job_id, 'status': 'running'})
                    return
                outcome = execute_algorithm(root, plan, prepared['payload'])
                status = 200 if outcome.get('ok') else (400 if outcome.get('kind') == 'validation' else 500)
                _json(self, status, outcome)
            finally:
                if not handed_off:
                    store.release()

    return Handler


def serve(root: Path, plan, host='127.0.0.1', port=0):
    page = (root / 'index.html').read_text(encoding='utf-8')
    store = JobStore(plan['limits']['concurrency'])
    server = ThreadingHTTPServer((host, port), make_handler(root, plan, store, page))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Serve api-demo-service')
    parser.add_argument('--root', required=True)
    args = parser.parse_args(argv)
    root = Path(args.root)
    plan = json.loads((root / 'plan.json').read_text(encoding='utf-8'))
    server = serve(root, plan, port=8765)
    host, port = server.server_address
    print(f'http://{host}:{port}/')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
