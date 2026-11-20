"""Offline delivery policy: video is optional until actually requested."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
import validate_delivery as delivery


class DeliveryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = self.root/'delivery.json'
        (self.root/'index.html').write_text('<h1>Synthetic test page</h1>')
        self.data = {'project':'fixture', 'version':'1', 'design_stage':'concept',
                     'source_sha256':'a'*64, 'entrypoint':'index.html', 'files':[]}
        for role in ('image', 'description', 'model'):
            self.add_file(role+'.bin', role, role.encode())

    def add_file(self, filename, role, content):
        (self.root/filename).write_bytes(content)
        self.data['files'].append({'path':filename, 'role':role, 'bytes':len(content),
            'sha256':hashlib.sha256(content).hexdigest(), 'source_sha256':'a'*64})

    def add_video(self):
        # Header fixture only; this validator never claims playable media.
        self.add_file('preview.mp4', 'video', struct.pack('>I', 16)+b'ftypisom'+bytes(4))

    def check_manifest(self):
        self.manifest.write_text(json.dumps(self.data))
        return delivery.validate(self.manifest, self.root)

    def test_default_and_explicit_no_video_complete(self):
        self.assertEqual(self.check_manifest()['status'], 'passed')
        self.data['video_requested'] = False
        self.assertEqual(self.check_manifest()['status'], 'passed')
        self.assertFalse((self.root/'preview.mp4').exists())

    def test_explicit_request_requires_video(self):
        self.data['video_requested'] = True
        result = self.check_manifest()
        self.assertEqual(result['status'], 'failed')
        self.assertIn('Missing required roles: video', result['errors'])
        self.add_video()
        self.assertEqual(self.check_manifest()['status'], 'passed')

    def test_optional_existing_video_is_still_checked(self):
        self.data['video_requested'] = False
        self.add_video()
        self.assertEqual(self.check_manifest()['status'], 'passed')
        self.data['files'][-1]['source_sha256'] = 'b'*64
        self.assertEqual(self.check_manifest()['status'], 'failed')
        self.data['files'][-1]['source_sha256'] = 'a'*64
        (self.root/'preview.mp4').write_bytes(b'corrupted')
        self.assertEqual(self.check_manifest()['status'], 'failed')

    def test_request_flag_does_not_accept_truthy_strings(self):
        for flag in ('false', 'true', 0, 1, None, [], {}):
            self.data['video_requested'] = flag
            self.assertEqual(self.check_manifest()['status'], 'failed')

    def test_optional_video_does_not_waive_core_assets(self):
        self.add_video()
        for role in ('image', 'description', 'model'):
            original = self.data['files']
            self.data['files'] = [f for f in original if f['role'] != role]
            self.assertEqual(self.check_manifest()['status'], 'failed')
            self.data['files'] = original

    def test_cli_default_then_requested_failure(self):
        self.check_manifest()
        command = [sys.executable, str(SCRIPTS/'validate_delivery.py'), str(self.manifest)]
        result = subprocess.run(command, capture_output=True, text=True, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'passed')
        self.data['video_requested'] = True
        self.check_manifest()
        result = subprocess.run(command, capture_output=True, text=True, cwd=self.root)
        self.assertEqual(result.returncode, 1, result.stderr)


if __name__ == '__main__':
    unittest.main()
