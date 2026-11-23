import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

scripts = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(scripts / 'runtime' if (scripts / 'runtime' / 'mdf_api.py').is_file() else scripts))
import mdf_api as api


class FakeClient:
    context = {'environment': 'test', 'owner_id': 'owner'}
    calls = []
    response = {}

    def auth(self): pass

    def check_job(self, record):
        if any(record.get(k) != v for k, v in self.context.items()):
            raise ValueError('Account changed')

    def send(self, path, method, body, content_type, length, timeout):
        data = body.read()
        self.calls.append((path, method, data, content_type, length, timeout))
        return 200, self.response


class MeshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {'SPARC3D_TOOL_WORKSPACE': str(self.root), 'SPARC3D_TOOL_STATE_DIR': str(self.root.parent / (self.root.name + '-state'))})
        self.env.start()
        self.glb = self.root / 'input.glb'
        self.glb.write_bytes(struct.pack('<4sII', b'glTF', 2, 20) + b'12345678')
        self.image = self.root / 'input.png'
        self.image.write_bytes(b'\x89PNG\r\n\x1a\n1234')
        FakeClient.calls = []
        FakeClient.response = {'code': 0, 'status': 'SUCCEEDED', 'requestId': 'mesh-id', 'data': {'files': {}}}

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def args(self, capability='unwrap-uv', params=None):
        return api.parser().parse_args(['invoke', '--capability', capability, '--file', str(self.image if capability in api.IMAGES else self.glb),
            '--params', json.dumps(params or {}), '--job', str(self.root/'jobs/call.json'), '--out', str(self.root/'exports')])

    def test_all_capabilities_validate_and_reject_unknown_fields(self):
        self.assertEqual(len(api.SCHEMA), 14)
        for capability in api.SCHEMA:
            file = self.image if capability in api.IMAGES else self.glb
            api.validate(capability, {}, file)
            for params in ({'options': {}}, {'assets': []}, {'target_service': 'x'}):
                with self.assertRaises(ValueError): api.validate(capability, params, file)
        invalid = [('unwrap-uv', {'texture_size': True}), ('auto-rig', {'num_beams': 21}),
            ('watertight', {'watertight_resolution': 3}), ('watertight', {'target_face_num': -2}),
            ('convert-3mf', {'threemf_target_size_mm': -1}), ('retopology', {'face_type': 'quad'}),
            ('pose', {'detect_persons': 1}), ('mesh-lod', {'target_face_num_list': []}),
            ('mesh-lod', {'target_face_num_list': [10, 10]}), ('mesh-lod', {'target_face_num_list': [1, 2]})]
        for capability, params in invalid:
            with self.assertRaises(ValueError): api.validate(capability, params, self.image if capability in api.IMAGES else self.glb)

    def test_header_format_size_and_paths(self):
        self.image.write_bytes(b'fake png')
        with self.assertRaises(ValueError): api.validate('pose', {}, self.image)
        with self.assertRaises(ValueError): api.validate('unwrap-uv', {}, self.image)
        with self.glb.open('r+b') as stream: stream.truncate(201 * 1024**2)
        with self.assertRaises(ValueError): api.validate('mesh-lod', {}, self.glb)
        with self.assertRaises(ValueError): api.workspace_path(self.root.parent/'outside')

    def test_lod_dynamic_pointers_and_download_only_recovery(self):
        FakeClient.response['data'] = {
            'mesh_lod_glbs': {'100': 'mesh_lod_glbs_100', '500': 'mesh_lod_glbs_500'},
            'mesh_lod_glbs_100': 'objects/a.glb', 'mesh_lod_glbs_500': 'objects/b.glb',
            'mesh_lod_metadata': {'500': {'actual_faces': 498}},
            'files': {'mesh_lod_glbs_100': {'key': 'objects/a.glb', 'url': 'https://cdn.example/a.glb'},
                      'mesh_lod_glbs_500': {'key': 'objects/b.glb', 'url': 'https://cdn.example/b.glb'}}}
        args = self.args('mesh-lod', {'target_face_num_list': [500, 100]})
        def fail(url, target): raise OSError('download failed')
        first = api.execute(args, FakeClient, fail)
        self.assertEqual(first['status'], 'SUCCEEDED')
        self.assertEqual(len(first['downloadIssues']), 2)
        self.assertEqual([item['targetFaces'] for item in first['lods']], [500, 100])
        self.assertEqual(first['lods'][0]['actualFaces'], 498)
        self.assertEqual(FakeClient.calls[0][-1], 7500)
        def fetch(url, target): target.write_bytes(self.glb.read_bytes())
        args.action = 'download'
        result = api.execute(args, FakeClient, fetch)
        self.assertEqual(len(result['files']), 2)
        self.assertFalse(result['downloadIssues'])
        self.assertTrue(all(Path(p).name.startswith('hi3d-') for p in result['files'].values()))
        api.execute(args, FakeClient, fail)
        self.assertEqual(len(FakeClient.calls), 1)
        self.assertEqual(len(api.execute(args, FakeClient, fail)['downloadIssues']), 0)
        Path(next(iter(result['files'].values()))).write_bytes(b'modified')
        self.assertEqual(len(api.execute(args, FakeClient, fetch)['downloadIssues']), 1)

    def test_unknown_reservation_changed_input_and_missing_urls_do_not_resubmit(self):
        args = self.args()
        FakeClient.response = {'code': 0, 'status': 'SUCCEEDED', 'requestId': 'no-download', 'downloadUnavailable': True,
            'data': {'uv_mesh_glb': 'objects/uv.glb', 'files': {'uv_mesh_glb': {'key': 'objects/uv.glb'}}}}
        result = api.execute(args, FakeClient)
        self.assertEqual(result['status'], 'SUCCEEDED')
        self.assertEqual(len(result['downloadIssues']), 1)
        api.execute(args, FakeClient)
        self.assertEqual(len(FakeClient.calls), 1)
        args.params = '{"texture_size":1024}'
        with self.assertRaises(ValueError): api.execute(args, FakeClient)
        self.assertEqual(len(FakeClient.calls), 1)
        record = api.load(args.job)
        record['status'] = 'UNKNOWN'
        api.save(args.job, record)
        args.params = '{}'
        self.assertEqual(api.execute(args, FakeClient)['status'], 'UNKNOWN')
        self.assertEqual(len(FakeClient.calls), 1)

    def test_signed_urls_stay_in_host_cache_and_resume_without_post(self):
        args = self.args()
        FakeClient.response['data'] = {'files': {'uv_mesh_glb': {'url': 'https://cdn.example/a.glb?signature=private-fixture', 'key': 'a.glb'}}}
        def failed(url, target): raise OSError('offline fixture')
        result = api.execute(args, FakeClient, failed)
        self.assertEqual(len(result['downloadIssues']), 1)
        self.assertNotIn('private-fixture', Path(args.job).read_text())
        self.assertNotIn('private-fixture', json.dumps(result))
        seen = []
        def download(url, target):
            seen.append(url)
            target.write_bytes(self.glb.read_bytes())
        args.action = 'download'
        api.execute(args, FakeClient, download)
        self.assertIn('signature=private-fixture', seen[0])
        self.assertEqual(len(FakeClient.calls), 1)

    def test_changed_upload_bytes_are_rejected_before_post(self):
        expected = api.digest(self.glb)
        self.glb.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            api.multipart({'capability': 'unwrap-uv'}, self.glb, expected)
        self.assertEqual(FakeClient.calls, [])

    def test_multipart_bytes_and_json_content_type(self):
        body, content_type, length = api.multipart({'capability': 'auto-rig', 'params': {'use_transfer': True}}, self.glb)
        with body: data = body.read()
        self.assertEqual(length, len(data))
        self.assertIn(b'name="request"\r\nContent-Type: application/json', data)
        self.assertIn(b'name="file"; filename="input.glb"', data)
        self.assertIn(self.glb.read_bytes(), data)
        self.assertNotIn(b'Cookie', data)
        self.assertTrue(content_type.startswith('multipart/form-data; boundary=mdf-'))


if __name__ == '__main__': unittest.main()
