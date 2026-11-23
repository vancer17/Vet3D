import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import plan_demo
import build_demo
import check_http
import serve_demo

ALGO = """
import time
from pathlib import Path

def run(payload):
    if payload.get('sleep'):
        time.sleep(float(payload['sleep']))
    result = {'echo': payload['text'][::-1]}
    blob = payload.get('blob')
    if blob:
        result['bytes'] = len(Path(blob['path']).read_bytes())
    return result
"""


def brief(**overrides):
    data = {
        'schemaVersion': 1,
        'title': '反转文本',
        'entry': 'algorithm.py',
        'fields': [
            {'id': 'text', 'label': '文本', 'type': 'string', 'required': True},
            {'id': 'sleep', 'label': '睡眠', 'type': 'number', 'required': False},
            {'id': 'blob', 'label': '附件', 'type': 'file', 'required': False, 'suffixes': ['.txt']},
        ],
        'sample': {'text': 'ab'},
        'limits': {'maxBytes': 64, 'timeoutSeconds': 1, 'concurrency': 1},
    }
    data.update(overrides)
    return data


def post(base, payload, timeout=5):
    req = Request(
        base + '/run',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode('utf-8'))


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.modes = plan_demo.load_modes(ROOT / 'references' / 'modes.json')

    def test_rejects_interpolated_argv(self):
        with self.assertRaises(ValueError):
            plan_demo.validate_plan(brief(argv=['python', '-c', 'print("{text}")']), self.modes)

    def test_rejects_sync_past_timeout(self):
        with self.assertRaises(ValueError):
            plan_demo.validate_plan(brief(sampleSeconds=9, mode='sync', limits={'maxBytes': 64, 'timeoutSeconds': 1, 'concurrency': 1}), self.modes)

    def test_service_calls(self):
        plan = plan_demo.validate_plan(brief(), self.modes)
        self.assertEqual(plan['mode'], 'sync')
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / 'skill'
            (skill / 'scripts').mkdir(parents=True)
            for name in ('runner.py', 'contract.py', 'serve_demo.py', 'build_demo.py'):
                shutil.copy2(ROOT / 'scripts' / name, skill / 'scripts' / name)
            algo = Path(tmp) / 'algorithm.py'
            algo.write_text(ALGO, encoding='utf-8')
            out = Path(tmp) / 'demo'
            build_demo.write_demo(plan, skill, algo, out)
            html = (out / 'index.html').read_text(encoding='utf-8')
            self.assertIn('未实现', html)
            self.assertNotIn('password', html.lower())
            report = check_http.check(out)
            self.assertTrue(report['ok'], report)
            sys.path.insert(0, str(out))
            server = serve_demo.serve(out, plan)
            base = f'http://{server.server_address[0]}:{server.server_address[1]}'
            try:
                status, body = post(base, {'text': 'ab'})
                self.assertEqual(status, 200)
                self.assertEqual(body['kind'], 'ok')
                self.assertEqual(body['result']['echo'], 'ba')
                status, body = post(base, {})
                self.assertEqual(status, 400)
                self.assertEqual(body['kind'], 'validation')
                status, body = post(base, {'text': 'ab', 'blob': {'name': 'x.exe', 'data': [1, 2]}})
                self.assertEqual(status, 400)
                self.assertEqual(body['kind'], 'validation')
                status, body = post(base, {'text': 'ab', 'sleep': 2})
                self.assertEqual(status, 500)
                self.assertEqual(body['kind'], 'timeout')
                started = []

                def slow():
                    started.append(time.time())
                    started.append(post(base, {'text': 'zz', 'sleep': 0.4}))

                thread = threading.Thread(target=slow)
                thread.start()
                time.sleep(0.05)
                busy_status, busy_body = post(base, {'text': 'yy'})
                thread.join()
                self.assertEqual(busy_status, 409)
                self.assertEqual(busy_body['kind'], 'busy')
            finally:
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    unittest.main()
