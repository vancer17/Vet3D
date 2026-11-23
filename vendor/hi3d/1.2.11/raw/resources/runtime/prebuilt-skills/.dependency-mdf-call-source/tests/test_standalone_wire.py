from __future__ import annotations
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from mdf_runtime import load_codec
codec = load_codec(transport="http")
BinaryFile, dumps, loads = codec.BinaryFile, codec.dumps, codec.loads
from mdf_http import post_json


class WireTest(unittest.TestCase):
    def test_binary_wire_identity_and_state(self):
        value = BinaryFile(field_name='mesh', content=memoryview(b'glTF'))
        encoded = dumps({1000000: value, 'slots': [None, True]})
        self.assertEqual(encoded[:2], b'\x80\x04')
        self.assertIn(b'mdf3.mdf_tool', encoded)
        restored = loads(encoded)[1000000]
        self.assertEqual(restored.file_size, 4)
        self.assertEqual(restored.file_name, 'mesh_file')
        self.assertEqual(restored.content, b'glTF')
        restored.__setstate__({'content': b'older-state'})
        self.assertEqual(restored.file_size, len(b'older-state'))
        with self.assertRaises(ValueError):
            BinaryFile(content='not bytes')

    def test_copied_cli_without_site_packages_roundtrips_large_binary_once(self):
        # Exceeds the 2 MiB diagnostic ceiling; business GLB results need a
        # separate bound. -S makes private SDK/requests/site packages unavailable.
        model = b'glTF' + b'x' * (2 * 1024 * 1024)
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                request = loads(base64.b64decode(data['input_data']['pickle_payload']))
                calls.append((self.path, self.headers['traceid'], request))
                payload = {'success': True, 'mesh_lod_glbs': {1000000: BinaryFile(file_name='mesh.glb', content=model)}}
                body = json.dumps({'success': True, 'pickle_payload': base64.b64encode(dumps(payload)).decode()}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); package = root/'copied-tool';shutil.copytree(ROOT, package, ignore=shutil.ignore_patterns('__pycache__'))
                (root/'source.glb').write_bytes(b'input-model')
                (root/'request.json').write_text(json.dumps({'input_mesh_glb': {'$file': 'source.glb'}, 'target_face_num_list': [1000000]}))
                cmd = [sys.executable, '-S', str(package/'scripts/mdf_call.py'), '--service', 'mesh-lod', '--input', str(root/'request.json'), '--run-dir', str(root/'run'), '--endpoint', f'http://127.0.0.1:{server.server_port}/generate_model']
                done = subprocess.run(cmd, cwd=root, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, timeout=30)
                self.assertEqual(done.returncode, 0, done.stderr)
                record = json.loads((root/'run/invocation.json').read_text())
                self.assertEqual(record['status'], 'SUCCEEDED')
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][2]['input_mesh_glb'].content, b'input-model')
                self.assertEqual((root/'run/artifacts'/record['files'][0]['file']).read_bytes(), model)
                runtime = json.loads((root/'run/runtime.json').read_text())
                self.assertTrue(runtime['ready']);self.assertFalse(runtime['numpy_available'])
                repeated = subprocess.run(cmd, cwd=root, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, timeout=30)
                self.assertNotEqual(repeated.returncode, 0);self.assertEqual(len(calls), 1)
                check = subprocess.run([sys.executable, '-S', str(package/'scripts/check_runtime.py'), '--require-numpy'], cwd=root, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
                self.assertEqual(check.returncode, 2);self.assertFalse(json.loads(check.stdout)['ready'])
                sdk_check = subprocess.run([sys.executable, '-S', str(package/'scripts/check_runtime.py'), '--transport', 'sdk'], cwd=root, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
                self.assertEqual(sdk_check.returncode, 2)
                self.assertFalse(json.loads(sdk_check.stdout)['ready'])
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_business_transport_bound_and_redirect_rejection(self):
        count = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                count.append(self.path)
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200);self.end_headers();self.wfile.write(b'"oversized"')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread=threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        try:
            endpoint=f'http://127.0.0.1:{server.server_port}/generate_model'
            response=post_json(endpoint, headers={}, json={}, timeout=3, allow_redirects=False, max_response_bytes=3)
            with self.assertRaises(ValueError):response.json()
            with self.assertRaises(ValueError):post_json(endpoint, headers={}, json={}, timeout=3, allow_redirects=True)
            self.assertEqual(len(count),1)
        finally:
            server.shutdown();server.server_close();thread.join()

class ConfigAndCliTest(unittest.TestCase):
    def test_copied_package_keeps_bundled_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "copied-tool"
            shutil.copytree(ROOT, package, ignore=shutil.ignore_patterns("__pycache__"))
            self.assertTrue((package / "assets" / "config.test.yaml").is_file())
            self.assertTrue(
                (package / "assets" / "config.test.yaml").read_text()
                == (ROOT / "assets" / "config.test.yaml").read_text()
            )

    def test_help_does_not_submit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "request.json").write_text("{}")
            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "mdf_call.py"),
                "--help",
            ]
            done = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("--config", done.stdout)
            self.assertIn("--endpoint", done.stdout)
            self.assertIn("--transport", done.stdout)

    def test_existing_run_dir_is_rejected_before_submit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "request.json").write_text('{"ok": true}')
            run_dir = root / "run"
            run_dir.mkdir()
            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "mdf_call.py"),
                "--service",
                "mesh-lod",
                "--input",
                str(root / "request.json"),
                "--run-dir",
                str(run_dir),
            ]
            done = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("run-dir exists", done.stderr)

if __name__ == '__main__':
    unittest.main()
