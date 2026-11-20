import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('roblox_api', Path(__file__).parents[1] / 'scripts/hi3d-roblox-api.py')
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)
XML = b'<roblox version="4"><Item class="Workspace" referent="RBX1"><Properties><string name="Name">Workspace</string></Properties><Item class="Part" referent="RBX2"><Properties><string name="Name">TestPart</string></Properties></Item></Item></roblox>'


class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.job = self.root / 'hi3d-publish.json'
        self.plan = api.publish_plan(XML, '.rbxlx', '12', '34')
        self.calls = []

    def transport(self, plan, data):
        self.calls.append((plan, data))
        return 200, b'{"versionNumber":7}'

    def upload(self, transport=None, **kw):
        return api.upload_once(self.plan, XML, self.job, transport or self.transport,
                               authorized=True, studio_reviewed=True, **kw)

    def test_static_is_not_runtime(self):
        facts = api.inspect_place(XML)
        self.assertEqual(facts['part_count'], 1)
        self.assertFalse(facts['runtime_tested'])
        self.assertIsNone(facts['native_part_triangles'])

    def test_ids(self):
        self.assertEqual(api.positive_id(9223372036854775807), '9223372036854775807')
        for value in (True, False, 0, -1, '0', '01', '1/2', '12?x=1', ' 12', '1e3',
                      9223372036854775808, '9' * 20):
            with self.subTest(value=value), self.assertRaises(ValueError):
                api.positive_id(value)

    def test_entities_rejected(self):
        with self.assertRaises(ValueError):
            api.parse_place(b'<!DOCTYPE roblox [<!ENTITY x "bad">]><roblox version="4"/>')

    def test_wrong_root_rejected(self):
        with self.assertRaises(ValueError):
            api.parse_place(b'<html/>')

    def test_binary_requires_studio(self):
        p = api.publish_plan(b'<roblox!\x89\xff\r\n\x1a\n' + b'\x00' * 20, '.rbxl', 1, 2)
        self.assertEqual(p['inspection'], 'studio_required')

    def test_content_no_signed_urls_in_report(self):
        x = XML.replace(b'</Properties></Item>', b'<Content name="TextureID"><url>https://example.invalid/a?token=SYNTHETIC</url></Content></Properties></Item>')
        self.assertNotIn('SYNTHETIC', json.dumps(api.inspect_place(x)))

    def test_local_mesh_path_blocks_cloud(self):
        x = XML.replace(b'</Properties></Item>', b'<Content name="MeshId"><url>file:///tmp/model.fbx</url></Content></Properties></Item>')
        self.assertTrue(api.inspect_place(x)['invalid_local_content'])
        with self.assertRaises(ValueError):
            api.publish_plan(x, '.rbxlx', 1, 2)

    def test_unsupported_classes_use_studio(self):
        for cls in api.UNSUPPORTED_CLOUD_CLASSES:
            with self.subTest(cls=cls), self.assertRaises(ValueError):
                api.publish_plan(XML.replace(b'class="Part"', f'class="{cls}"'.encode()), '.rbxlx', 1, 2)

    def test_duplicate_referents_block(self):
        with self.assertRaises(ValueError):
            api.publish_plan(XML.replace(b'RBX2', b'RBX1'), '.rbxlx', 1, 2)

    def test_no_authorization_no_intent_or_network(self):
        with self.assertRaises(ValueError):
            api.upload_once(self.plan, XML, self.job, self.transport)
        self.assertFalse(self.job.exists())
        self.assertEqual(self.calls, [])

    def test_no_studio_review_no_network(self):
        with self.assertRaises(ValueError):
            api.upload_once(self.plan, XML, self.job, self.transport, authorized=True)
        self.assertEqual(self.calls, [])

    def test_intent_precedes_upload_and_replay_is_readonly(self):
        def send(plan, data):
            self.assertEqual(json.loads(self.job.read_text())['state'], 'submitting')
            return self.transport(plan, data)
        result = self.upload(send)
        self.assertEqual(result['state'], 'uploaded')
        self.assertFalse(result['public_verified'])
        self.assertEqual(self.upload(), result)
        self.assertEqual(len(self.calls), 1)

    def test_timeout_is_unknown_never_retried(self):
        def timeout(plan, data):
            self.calls.append(1)
            raise TimeoutError('SYNTHETIC_PRIVATE_ERROR')
        result = self.upload(timeout)
        self.assertEqual(result['state'], 'submission_uncertain')
        self.assertEqual(self.upload(), result)
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('SYNTHETIC_PRIVATE_ERROR', self.job.read_text())

    def test_interrupted_submitting_never_posts(self):
        api.save_new_json(self.job, {'schema': 'roblox.publish-receipt.v1', 'plan': self.plan, 'state': 'submitting'})
        self.assertEqual(self.upload()['state'], 'submitting')
        self.assertEqual(self.calls, [])

    def test_rejected_does_not_retry(self):
        result = self.upload(lambda *_: (403, b'PRIVATE_ERROR'))
        self.assertEqual(result['state'], 'rejected')
        self.upload()
        self.assertEqual(self.calls, [])
        self.assertNotIn('PRIVATE_ERROR', self.job.read_text())

    def test_invalid_success_is_unknown(self):
        for body in (b'{}', b'{"versionNumber":true}', b'{"versionNumber":0}', b'not json', b'[]'):
            self.job = self.root / ('hi3d-' + str(len(list(self.root.iterdir()))) + '.json')
            self.assertEqual(self.upload(lambda *_: (200, body))['state'], 'submission_uncertain')

    def test_redirect_and_server_failure_unknown(self):
        for status in (302, 408, 500, 503):
            self.job = self.root / f'hi3d-{status}.json'
            self.assertEqual(self.upload(lambda *_: (status, b''))['state'], 'submission_uncertain')

    def test_changed_bytes_and_target_refused(self):
        with self.assertRaises(ValueError):
            api.upload_once(self.plan, XML + b' ', self.job, self.transport, authorized=True, studio_reviewed=True)
        altered = {**self.plan, 'url': 'https://example.invalid/steal'}
        with self.assertRaises(ValueError):
            api.upload_once(altered, XML, self.job, self.transport, authorized=True, studio_reviewed=True)
        self.assertEqual(self.calls, [])

    def test_existing_other_plan_refused(self):
        self.upload()
        other = api.publish_plan(XML, '.rbxlx', 12, 99)
        with self.assertRaises(ValueError):
            api.upload_once(other, XML, self.job, self.transport, authorized=True, studio_reviewed=True)
        self.assertEqual(len(self.calls), 1)

    def test_symlink_intent_refused(self):
        dest = self.root / 'hi3d-original.json'
        dest.write_text('original')
        self.job.symlink_to(dest)
        with self.assertRaises(ValueError):
            self.upload()
        self.assertEqual(dest.read_text(), 'original')
        self.assertEqual(self.calls, [])

    def test_dryrun_does_not_read_credentials(self):
        source = self.root / 'hi3d-place.rbxlx'
        source.write_bytes(XML)
        with patch.object(api.os, 'environ', {}), patch.object(api, 'api_key_transport', side_effect=AssertionError('network')), patch('builtins.print'):
            self.assertEqual(api.main(['publish-place', '--place', str(source), '--universe-id', '12', '--place-id', '34']), 0)
        self.assertFalse(self.job.exists())

    def test_transport_refuses_redirect(self):
        self.assertIsNone(api.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.invalid'))

    def test_transport_refuses_foreign_origin_before_network(self):
        with patch.object(api, 'build_opener') as build:
            send = api.api_key_transport('SYNTHETIC_TEST_KEY')
            for field, value in [('url', 'https://example.invalid/steal'), ('method', 'GET'), ('content_type', 'text/plain')]:
                with self.subTest(field=field), self.assertRaises(ValueError):
                    send({**self.plan, field: value}, XML)
            build.return_value.open.assert_not_called()

    def test_transport_sends_raw_place_to_canonical_endpoint(self):
        with patch.object(api, 'build_opener') as build:
            response = build.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"versionNumber":9}'
            send = api.api_key_transport('SYNTHETIC_TEST_KEY')
            self.assertEqual(send(self.plan, XML), (200, b'{"versionNumber":9}'))
            request = build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, self.plan['url'])
            self.assertEqual(request.data, XML)
            self.assertEqual(request.get_method(), 'POST')
            self.assertEqual(request.get_header('Content-type'), 'application/xml')
            self.assertEqual(request.get_header('X-api-key'), 'SYNTHETIC_TEST_KEY')
            build.return_value.open.assert_called_once()

    def test_receipt_write_failure_preserves_intent_and_no_retry(self):
        with patch.object(api, 'replace_record', side_effect=OSError('synthetic disk error')):
            with self.assertRaises(OSError):
                self.upload()
        self.assertEqual(json.loads(self.job.read_text())['state'], 'submitting')
        self.assertEqual(self.upload()['state'], 'submitting')
        self.assertEqual(len(self.calls), 1)

    def test_empty_and_oversized_place_refused(self):
        with self.assertRaises(ValueError):
            api.publish_plan(b'', '.rbxlx', 1, 2)
        with patch.object(api, 'MAX_PLACE_BYTES', 10), self.assertRaises(ValueError):
            api.publish_plan(XML, '.rbxlx', 1, 2)


if __name__ == '__main__':
    unittest.main()
