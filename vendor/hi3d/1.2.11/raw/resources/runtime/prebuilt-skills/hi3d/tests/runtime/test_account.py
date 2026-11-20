"""No external requests: fixtures for artifact integrity, transport isolation and validation."""
import io
from contextlib import redirect_stderr, redirect_stdout
import json
import os
from pathlib import Path
import sys
import struct
import tempfile
import unittest
import zipfile
from unittest.mock import Mock, patch

scripts = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(scripts / 'runtime' if (scripts / 'runtime' / 'hi3d_api.py').is_file() else scripts))
from hi3d_artifacts import fetch, unpack, download_job, export_image, file_record
from hi3d_client import Client, ApiError
from hi3d_parameters import build_plan, multipart
from hi3d_storage import load, save, workspace_path, QUERY_FAILURE_ACTION
from hi3d_progress import progress_snapshot, job_summary
from hi3d_jobs import (
    response_error, query_job, wait_job, job_outcome, retry_quota_view, retry_parent, retry_job,
)
from hi3d_generation_workflow import generate_task, generate_retry_task
from hi3d_api import execute, parser, main

class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {'SPARC3D_TOOL_WORKSPACE': str(self.root), 'HI3D_API_BASE_URL': 'http://127.0.0.1:1234/v1', 'HI3D_API_PROXY_TOKEN': 'fixture-token-1234567890'})
        self.env.start()
    def tearDown(self):
        self.env.stop(); self.temp.cleanup()

    def test_query_preserves_parent_and_refuses_conflicting_retry_root(self):
        from hi3d_client import BACKEND
        from hi3d_jobs import retry_root_id
        path = self.root / 'child.json'
        save(path, {'backend': BACKEND, 'kind': 'model', 'task_id': 'child', 'state': 'processing'})
        client = Mock()
        client.request.return_value = (200, {'code': 200, 'data': {'status': 1, 'parentId': 'root'}})
        job, _ = query_job(client, path)
        self.assertEqual(retry_root_id(job), 'root')
        job.update(retry=True, parent_task_id='root', state='processing')
        save(path, job)
        client.request.return_value = (200, {'code': 200, 'data': {'status': 1, 'parentId': 'foreign'}})
        job, _ = query_job(client, path)
        self.assertEqual(job['state'], 'processing')
        self.assertIn('last_query_error', job)
        self.assertEqual(retry_root_id(job), 'root')

    def test_explicit_quota_ineligibility_is_not_overridden_by_a_positive_count(self):
        self.assertFalse(retry_quota_view({'remaining': 2, 'can_retry': False})['can_retry'])

    def test_explicit_3d_failure_replaces_stale_processing_and_stops_wait(self):
        from hi3d_client import BACKEND
        path = self.root / 'model.json'
        save(path, {'backend': BACKEND, 'kind': 'model', 'task_id': 'existing-task', 'fingerprint': 'fixture',
                    'state': 'processing', 'submitted_at': '2026-01-01T00:00:00+00:00',
                    'result_observed_at': '2026-01-01T00:01:00+00:00',
                    'result': {'status': 0, 'percentage': 37, 'percentGeo': 75},
                    'last_query_error': {'code': 502}})
        client = Mock()
        client.request.return_value = (200, {'code': 1003, 'domainCode': 10030103, 'error_source': 'upstream',
            'message': 'The generation service reported that this 3D task failed. This is a terminal task failure.',
            'trace_id': 'fixture-trace'})
        events = []
        sleep = Mock(side_effect=AssertionError('Terminal failures must stop polling'))
        result, code = wait_job(client, path, sleep=sleep, on_progress=events.append)
        job = load(path)
        self.assertEqual((result['result'], code, job['state']), ('failed', 1, 'failed'))
        self.assertEqual(client.request.call_count, 1)
        self.assertEqual(job['last_query_error']['domainCode'], 10030103)
        self.assertTrue(job['last_query_error']['query_failed'])
        self.assertEqual(job['error']['phase'], 'query')
        self.assertEqual(job['error']['domainCode'], 10030103)
        self.assertEqual(job['error']['trace_id'], 'fixture-trace')
        self.assertEqual(job['task_id'], 'existing-task')
        self.assertEqual(events[-1]['state'], 'failed')
        self.assertEqual(events[-1]['stage'], 'failed')
        self.assertFalse(events[-1]['stale'])
        self.assertIsNone(events[-1]['percentage'])
        self.assertIsNone(events[-1]['geometry_percentage'])
        self.assertNotEqual(job['result_observed_at'], '2026-01-01T00:01:00+00:00')
        terminal_at = job['first_observed_terminal_at']
        elapsed = job['progress']['elapsed_seconds']
        query_job(client, path)
        self.assertEqual(load(path)['first_observed_terminal_at'], terminal_at)
        self.assertEqual(load(path)['progress']['elapsed_seconds'], elapsed)
        client.request.reset_mock()
        resumed, resumed_code = generate_task(client, {'fingerprint': 'fixture'}, path, self.root / 'out')
        self.assertEqual((resumed['result'], resumed_code), ('failed', 1))
        client.request.assert_not_called()

    def test_direct_3d_failure_accepts_string_code_and_msg(self):
        from hi3d_client import BACKEND
        path = self.root / 'direct.json'
        save(path, {'backend': BACKEND, 'kind': 'model', 'task_id': 'existing-task', 'state': 'processing'})
        client = Mock()
        client.request.return_value = (200, {'code': '1003', 'domainCode': '10030103', 'msg': '生成失败'})
        job, _ = query_job(client, path)
        self.assertEqual(job_outcome(job), ('failed', 1))
        self.assertFalse(job['progress']['stale'])

    def test_business_errors_fail_but_proxy_errors_preserve_task(self):
        from hi3d_client import BACKEND
        terminal = 'The generation service reported that this 3D task failed.'
        for kind, status, body in (
            ('model', 200, {'code': 502, 'domainCode': 10030103, 'message': terminal}),
            ('model', 200, {'code': 1003, 'domainCode': 10030103, 'message': terminal, 'error_source': 'desktop-proxy'}),
            *(( 'model', 200, {'code': 1003, 'domainCode': domain, 'message': terminal})
              for domain in (999999, True, {'raw': 'private'})),
        ):
            with self.subTest(kind=kind, status=status, body=body):
                path = self.root / 'query.json'
                save(path, {'backend': BACKEND, 'kind': kind, 'task_id': 'existing-task',
                            'state': 'processing', 'result': {'status': 0, 'percentage': 37},
                            'result_observed_at': '2026-01-01T00:00:00+00:00'})
                client = Mock()
                client.request.return_value = status, body
                job, _ = query_job(client, path)
                business = body.get('error_source') != 'desktop-proxy'
                self.assertEqual(job['state'], 'failed' if business else 'processing')
                domain = body.get('domainCode')
                if type(domain) is int:
                    self.assertEqual(load(path)['last_query_error']['domainCode'], domain)
                else:
                    self.assertNotIn('domainCode', load(path)['last_query_error'])
                self.assertEqual(job_outcome(job), ('failed', 1) if business else ('attention', 2))
                self.assertEqual(job['progress']['stale'], not business)
                self.assertEqual(job['progress']['percentage'], None if business else 37)
                if not business:
                    self.assertEqual(job['progress']['observed_at'], '2026-01-01T00:00:00+00:00')

    def test_timeout_preserves_last_observation_and_explicit_query_recovers(self):
        from hi3d_client import BACKEND
        for previous_state in ('processing', 'success', 'failed'):
            with self.subTest(state=previous_state):
                path = self.root / 'timeout.json'
                original = {'backend': BACKEND, 'kind': 'model', 'task_id': 'existing-task',
                            'state': previous_state, 'result': {'status': 0, 'percentage': 37},
                            'result_observed_at': '2026-01-01T00:00:00+00:00'}
                save(path, original)
                client = Mock()
                client.request.side_effect = TimeoutError()
                result, code = wait_job(client, path, sleep=Mock(side_effect=AssertionError('No retry')))
                self.assertEqual((result['result'], code), ('attention', 2))
                job = load(path)
                for key in ('state', 'result', 'result_observed_at', 'task_id'):
                    self.assertEqual(job[key], original[key])
                self.assertTrue(job['progress']['stale'])
                self.assertNotIn('query_failed', job['last_query_error'])
                client.request.assert_called_once()
                client.request.side_effect = None
                client.request.return_value = 200, {'code': 200, 'data': {'status': 1}}
                recovered, _ = query_job(client, path)
                self.assertEqual(job_outcome(recovered), ('success', 0))
                self.assertNotIn('last_query_error', recovered)
                self.assertFalse(recovered['progress']['stale'])

    def test_resume_cached_failure_after_query_error_rechecks_same_task(self):
        from hi3d_client import BACKEND
        for error in (TimeoutError(), ApiError(401), ApiError(409)):
            with self.subTest(error=str(error)):
                path = self.root / 'resume-failed.json'
                save(path, {'backend': BACKEND, 'kind': 'model', 'fingerprint': 'same',
                            'task_id': 'existing-task', 'state': 'failed', 'result': {},
                            'error': {'phase': 'query'}, 'last_query_error': {'query_failed': True},
                            'result_observed_at': '2026-01-01T00:00:00+00:00'})
                client = Mock()
                client.check_job.side_effect = error
                queried, _ = query_job(client, path)
                self.assertEqual(job_outcome(queried), ('attention', 2))
                self.assertNotIn('query_failed', queried['last_query_error'])
                self.assertEqual(queried['result_observed_at'], '2026-01-01T00:00:00+00:00')
                client.request.assert_not_called()
                client.check_job.side_effect = None
                client.request.return_value = 200, {'code': 200, 'data': {'status': 0}}
                resumed, code = generate_task(client, {'fingerprint': 'same'}, path, self.root / 'out', seconds=0)
                self.assertEqual((resumed['result'], code), ('pending', 0))
                client.request.assert_called_once()
                self.assertIn('jobId=existing-task', client.request.call_args.args[0])
                self.assertNotIn('last_query_error', load(path))

    def test_combined_resume_auth_failure_is_recorded_as_query_error(self):
        from hi3d_client import BACKEND
        path = self.root / 'resume-auth.json'
        save(path, {'backend': BACKEND, 'kind': 'model', 'fingerprint': 'same',
                    'task_id': 'existing-task', 'state': 'processing', 'result': {'status': 0},
                    'result_observed_at': '2026-01-01T00:00:00+00:00'})
        client = Mock()
        client.check_job.side_effect = ApiError(401)
        result, code = generate_task(client, {'fingerprint': 'same'}, path, self.root / 'out', seconds=0)
        self.assertEqual((result['result'], code), ('attention', 2))
        self.assertEqual(result['job']['state'], 'processing')
        self.assertEqual(result['job']['last_query_error']['code'], 401)
        self.assertTrue(result['job']['progress']['stale'])
        client.request.assert_not_called()

    def test_download_reports_business_rejection_or_unavailable_query(self):
        from hi3d_client import BACKEND
        for status in (200, 502):
            with self.subTest(status=status):
                path = self.root / 'download-error.json'
                save(path, {'backend': BACKEND, 'kind': 'model', 'task_id': 'existing-task',
                            'state': 'success', 'result': {'status': 1}})
                client = Mock()
                client.request.return_value = status, {'code': 1003, 'domainCode': 10030107,
                                                        'message': 'Service unavailable'}
                args = parser().parse_args(['download', '--job', str(path), '--out', str(self.root / 'out')])
                result, code = execute(args, lambda: client)
                self.assertEqual((result['result'], code), ('failed', 1) if status == 200 else ('attention', 2))
                error = result['job']['last_query_error']
                self.assertTrue(error['reason'])
                self.assertEqual(error['domainCode'], 10030107)
                if status != 200:
                    self.assertNotIn('category', error)
                    self.assertEqual(result['job']['state'], 'success')
                client.request.assert_called_once()

    def test_success_requires_http_business_code_and_valid_task_status(self):
        from hi3d_client import BACKEND
        for status, body in ((503, {'code': 200, 'data': {'status': 1}}),
                             (200, {'code': 998877, 'data': {'status': 1}}),
                             (200, {'data': {'status': 1}}),
                             (200, {'code': 200}),
                             (200, {'code': 200, 'data': {'status': True}}),
                             (200, {'code': 200, 'data': {'status': 999}})):
            with self.subTest(status=status, body=body):
                path = self.root / 'invalid-query.json'
                save(path, {'backend': BACKEND, 'kind': 'model', 'task_id': 'existing-task', 'state': 'processing'})
                client = Mock()
                client.request.return_value = status, body
                result, code = wait_job(client, path, sleep=Mock(side_effect=AssertionError('No retry')))
                business = status == 200 and body.get('code') == 998877
                self.assertEqual((result['result'], code), ('failed', 1) if business else ('attention', 2))
                self.assertEqual(load(path)['state'], 'failed' if business else 'processing')
                self.assertTrue(load(path)['last_query_error']['reason'])
                client.request.assert_called_once()

    def test_all_documented_business_errors_are_persisted_and_stop_polling(self):
        from hi3d_client import BACKEND
        cases = (
            (1003, None, 'invalid_request'),
            (1003, 10030103, 'generation_failed'),
            (1003, 10030104, 'retry_task_not_found'),
            (1003, 10030105, 'retry_limit_exceeded'),
            (1003, 10030106, 'concurrency_limit_exceeded'),
            (1003, 10030107, 'plan_quota_exhausted'),
            (1003, 10000024, 'input_content_rejected'),
            (1003, 32001, 'model_content_rejected'),
            (30010000, None, 'insufficient_credits'),
            (30010001, None, 'credit_confirmation_required'),
            (409, None, 'data_version_conflict'),
            (500, 500, 'system_error'),
        )
        for code, domain, category in cases:
            for kind, as_string in (('model', False), ('model', True), ('text-to-image', False)):
                with self.subTest(code=code, domain=domain, kind=kind, as_string=as_string):
                    path = self.root / 'all-errors.json'
                    save(path, {'backend': BACKEND, 'kind': kind, 'task_id': 'existing-task',
                                'fingerprint': 'fixture', 'state': 'processing',
                                'result': {'status': 0, 'percentage': 37},
                                'result_observed_at': '2026-01-01T00:00:00+00:00'})
                    body = {'code': str(code) if as_string else code,
                            'domainCode': str(domain) if as_string and domain is not None else domain,
                            'error_source': 'upstream', 'trace_id': 'fixture-trace',
                            'message': 'Cookie: private-value', 'detail': 'private-body'}
                    client = Mock()
                    client.request.return_value = (200, body)
                    result, exit_code = wait_job(client, path,
                        sleep=Mock(side_effect=AssertionError('Errors must stop polling')))
                    client.request.assert_called_once()
                    job = load(path)
                    error = job['last_query_error']
                    self.assertEqual(error['code'], code)
                    self.assertEqual(error.get('domainCode'), domain)
                    self.assertEqual(error['category'], category)
                    self.assertTrue(error['reason'])
                    self.assertTrue(error['next_action'])
                    self.assertEqual(error['trace_id'], 'fixture-trace')
                    self.assertNotIn('private-value', path.read_text())
                    self.assertNotIn('private-body', path.read_text())
                    self.assertEqual(job_summary(job, path)['last_query_error'], error)
                    self.assertEqual((result['result'], exit_code), ('failed', 1))
                    self.assertEqual(job['state'], 'failed')
                    self.assertFalse(job['progress']['stale'])
                    self.assertTrue(error['query_failed'])
                    self.assertEqual(job['error']['phase'], 'query')
                    self.assertEqual(job['error'].get('domainCode'), domain)
                    self.assertIsNone(job['progress']['percentage'])
                    self.assertIn('end the current turn', job_summary(job, path)['next_action'])
                    client.request.reset_mock()
                    resumed, resumed_code = generate_task(client, {'fingerprint': 'fixture'}, path, self.root / 'out')
                    self.assertEqual((resumed['result'], resumed_code), ('failed', 1))
                    client.request.assert_not_called()
                    # Only a new explicit query can recover a later successful server result.
                    client.request.return_value = (200, {'code': 200, 'data': {'status': 1, 'percentage': 100}})
                    fresh, _ = query_job(client, path)
                    self.assertEqual(job_outcome(fresh), ('success', 0))
                    self.assertNotIn('last_query_error', fresh)
                    self.assertNotIn('error', fresh)
                    self.assertFalse(fresh['progress']['stale'])

    def test_submission_errors_retain_business_guidance_without_reposting(self):
        from hi3d_jobs import submit_job
        for code, domain in ((1003, None), (1003, 10030103), (1003, 10030104),
                             (1003, 10030105), (1003, 10030106), (1003, 10030107),
                             (1003, 10000024), (1003, 32001), (30010000, None),
                             (30010001, None), (409, None), (500, 500)):
            with self.subTest(code=code, domain=domain):
                path = self.root / f'submit-{code}-{domain}.json'
                client = Mock()
                client.context = {'environment': 'test', 'owner_id': 'fixture-owner'}
                client.request.return_value = (200, {'code': code, 'domainCode': domain})
                planned = build_plan('text-to-image')
                for _ in range(2):
                    result = submit_job(client, path, planned)
                    self.assertTrue(result['job']['error']['category'])
                    self.assertTrue(result['job']['error']['next_action'])
                    self.assertEqual(result['job']['error'].get('domainCode'), domain)
                client.request.assert_called_once()

    def test_download_refresh_business_error_remains_failed_in_combined_result(self):
        from hi3d_client import BACKEND
        path = self.root / 'download-error.json'
        job = {'backend': BACKEND, 'kind': 'model', 'task_id': 'existing-task', 'state': 'success'}
        save(path, job)
        client = Mock()
        client.request.return_value = (200, {'code': 1003, 'domainCode': 10030107})
        def downloader(*args):
            query_job(client, path)
            raise ValueError('No successful download result')
        with patch('hi3d_generation_workflow.submit_job', return_value={'job': job}):
            result, code = generate_task(client, {}, path, self.root / 'out',
                waiter=lambda *a: ({'result': 'success', 'job': job}, 0), downloader=downloader)
        self.assertEqual((result['result'], code, result['phase']), ('failed', 1, 'download'))
        self.assertEqual(result['job']['last_query_error']['category'], 'plan_quota_exhausted')
        self.assertEqual(result['job']['state'], 'failed')
        self.assertIn('end the current turn', result['job']['next_action'])
        client.request.assert_called_once()

    def test_v30_model_tiers_reach_native_requests_without_network(self):
        image_url = "https://files.test/input.png"
        default = build_plan("model", image_url=image_url)
        self.assertEqual(default["parameters"]["request"]["otherParam"]["modelType"], "standard")
        for tier, resolution, model_type in (
            ("quality", "2048quality", "standard"),
            ("master", "2048master", "quality"),
        ):
            with self.subTest(tier=tier):
                legacy = build_plan("model", image_url=image_url, overrides=[
                    "model=hi3dv3.0", "resolution=" + resolution,
                ])
                result, code = execute(parser().parse_args([
                    "generate-3d", "--image-url", image_url,
                    "--set", "model_type=v3.0:" + tier,
                    "--set", "generation_type=both",
                    "--job", str(self.root / (tier + ".json")),
                    "--out", str(self.root / tier), "--dry-run",
                ]), client_factory=lambda: self.fail("Dry-run must stay offline"))
                self.assertEqual(code, 0)
                self.assertEqual(result["consent"]["result"], "ready")
                for request in (legacy["parameters"]["request"], result["request"]):
                    self.assertEqual(request["version"], "v3.0")
                    self.assertEqual(request["otherParam"]["modelType"], model_type)
                    self.assertEqual(str(request["otherParam"]["voxelResolution"]), "2048")
                    self.assertEqual(request["otherParam"]["generationType"], "both")
                native = build_plan("model", image_url=image_url, request=result["request"])
                self.assertEqual(native["parameters"]["request"], result["request"])
                legacy_native = build_plan("model", image_url=image_url, request=legacy["parameters"]["request"])
                self.assertEqual(legacy_native["fingerprint"], legacy["fingerprint"])
                if tier == "quality":
                    self.assertEqual(default["fingerprint"], legacy["fingerprint"])
        override = build_plan("model", image_url=image_url, overrides=[
            "resolution=2048quality", "modelType=quality",
        ])
        self.assertEqual(override["parameters"]["request"]["otherParam"]["modelType"], "quality")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_corrected_v30_default_preserves_existing_job_and_image_plans(self):
        from hi3d_parameters import load_defaults
        from hi3d_jobs import submit_job

        previous_defaults = load_defaults()
        previous_defaults["parameters"]["model"]["otherParam"]["modelType"] = "quality"
        image_url = "https://files.test/input.png"
        previous = build_plan("model", image_url=image_url, defaults=previous_defaults)
        corrected = build_plan("model", image_url=image_url)
        self.assertNotEqual(previous["fingerprint"], corrected["fingerprint"])
        jobpath = self.root / "existing.json"
        save(jobpath, {**previous, "task_id": "existing-task", "state": "queueing"})
        before = jobpath.read_bytes()
        with self.assertRaisesRegex(ValueError, "different plan; preserve it"):
            submit_job(None, jobpath, corrected)
        self.assertEqual(jobpath.read_bytes(), before)
        for kind in ("text-to-image", "image-edit"):
            self.assertEqual(build_plan(kind)["fingerprint"],
                             build_plan(kind, defaults=previous_defaults)["fingerprint"])

    def test_image_prompt_limit_applies_to_final_native_request(self):
        from hi3d_image_workflow import image_plan
        for kind, edit_type in (("text-to-image", "TEXT_TO_IMAGE"), ("image-edit", "EDIT")):
            for prompt in ("x" * 4000, "发" * 4000, "😀" * 4000, "中a😀\n" * 1000):
                request = {"editTaskType": edit_type, "prompt": prompt, "modelName": "Native Model",
                           "imageCount": 2, "aspectRatio": "4:3"}
                with self.subTest(kind=kind, length=len(prompt)):
                    result = build_plan(kind, request=request)
                    self.assertEqual(result["parameters"]["request"]["prompt"], prompt)
                    # Native DTO keeps its existing precedence over convenience args.
                    plan = image_plan("short", "nano-banana-2", "1:1", 1, kind=kind, request=request)
                    self.assertEqual(plan["fingerprint"], result["fingerprint"])
                    with self.assertRaisesRegex(ValueError, "maximum is 4000"):
                        build_plan(kind, request={**request, "prompt": prompt + "x"})
                    with self.assertRaisesRegex(ValueError, "maximum is 4000"):
                        build_plan(kind, request={**request, "prompt": "short"}, overrides=["prompt=" + prompt + "x"])
                    with self.assertRaisesRegex(ValueError, "maximum is 4000"):
                        image_plan("short", "nano-banana-2", "1:1", 1, kind=kind,
                                   request={**request, "prompt": prompt + "x"})
            with self.assertRaisesRegex(ValueError, "must be a string"):
                build_plan(kind, request={"editTaskType": edit_type, "prompt": 1000})
            request = {"editTaskType": edit_type, "prompt": "x" * 4001}
            corrected = build_plan(kind, request=request, overrides=["prompt=已改短"])
            self.assertEqual(corrected["parameters"]["request"]["prompt"], "已改短")
            self.assertEqual(request["prompt"], "x" * 4001)

    def test_image_cli_defaults_and_prompt_budget_are_offline(self):
        def no_client():
            self.fail("Local planning must not create an API client")

        defaults, code = execute(parser().parse_args(["defaults"]), client_factory=no_client)
        self.assertEqual(code, 0)
        for kind in ("text-to-image", "image-edit"):
            self.assertEqual(defaults["parameters"][kind]["modelName"], "GPT Image 2")
            for prompt in ("发" * 1165, "x" * 4000, "😀" * 4000):
                arguments = ["generate-image", "--kind", kind, "--prompt", prompt,
                             "--job", str(self.root / "job.json"),
                             "--out", str(self.root / "output"), "--dry-run"]
                result, code = execute(parser().parse_args(arguments), client_factory=no_client)
                self.assertEqual(code, 0)
                self.assertEqual(result["model"], "GPT Image 2")
                self.assertEqual(result["consent"]["result"], "ready")
                self.assertNotIn("user_interaction", result["consent"])
                self.assertEqual(result["request"]["prompt"], prompt)
                with self.assertRaises(ValueError):
                    execute(parser().parse_args(arguments + ["--set", "prompt=" + "x" * 4001]),
                            client_factory=no_client)
            result, code = execute(parser().parse_args([
                "submit", kind, "--set", "prompt=" + "发" * 1165,
                "--job", str(self.root / "job.json"), "--dry-run",
            ]), client_factory=no_client)
            self.assertEqual(code, 0)
            self.assertEqual(result["consent"]["result"], "ready")
            self.assertNotIn("user_interaction", result["consent"])
            self.assertEqual(result["parameters"]["request"]["modelName"], "GPT Image 2")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_image_prompt_file_check_counts_exact_text_offline(self):
        def no_client():
            self.fail("Prompt checks must not create an API client")

        path = self.root / "hi3d-prompt.txt"
        for prompt, expected_code in (("中a😀\n" * 1000, 0), ("发" * 4001, 1),
                                      ("x" * 3998 + "\r\n", 0), ("x" * 4000 + "\n", 1)):
            with self.subTest(characters=len(prompt)):
                path.write_bytes(prompt.encode("utf-8"))
                before = path.read_bytes()
                result, code = execute(parser().parse_args([
                    "check-image-prompt", "--prompt-file", str(path),
                ]), client_factory=no_client)
                self.assertEqual((result, code), ({"characters": len(prompt), "max_characters": 4000,
                                                  "valid": expected_code == 0}, expected_code))
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(list(self.root.iterdir()), [path])
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["check-image-prompt", "--prompt-file", str(path)]), expected_code)
                self.assertEqual(json.loads(output.getvalue()), result)

    def test_oversize_images_are_blocked_before_formal_submission(self):
        def no_client():
            self.fail("Oversize prompts must be blocked before creating an API client")

        for kind in ("text-to-image", "image-edit"):
            for command in ("generate-image", "submit"):
                with self.subTest(kind=kind, command=command):
                    arguments = ([command, "--kind", kind, "--prompt", "短提示词",
                                  "--out", str(self.root / "unused-out")]
                                 if command == "generate-image" else [command, kind])
                    arguments += ["--set", "prompt=" + "中" * 4001, "--job", str(self.root / "unused-job.json")]
                    with self.assertRaisesRegex(ValueError, "4001 characters; maximum is 4000"):
                        execute(parser().parse_args(arguments), client_factory=no_client)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_runtime_parameter_panels_block_incomplete_submissions(self):
        def no_client():
            self.fail("Incomplete display parameters must not construct an API client")

        cases = (
            ["generate-3d", "--image-url", "https://files.test/input.png"],
            ["generate-3d", "--kind", "relief", "--image-url", "https://files.test/input.png"],
            ["generate-3d", "--kind", "split", "--mesh-url", "https://files.test/input.glb"],
        )
        for index, command in enumerate(cases):
            with self.subTest(command=command[0]):
                arguments = [
                    *command,
                    "--job", str(self.root / ("blocked-%s.json" % index)),
                    "--out", str(self.root / ("blocked-%s" % index)),
                ]
                result, code = execute(parser().parse_args(arguments), client_factory=no_client)
                self.assertEqual((code, result["result"], result["stage"]),
                                 (2, "waiting_choice", "parameters"))
                self.assertEqual(result["user_interaction"]["kind"], "preference")

    def test_image_cli_explicit_model_and_native_overrides_take_precedence(self):
        request_path = self.root / "request.json"
        save(request_path, {"editTaskType": "TEXT_TO_IMAGE", "modelName": "Native Model", "prompt": "native"})
        arguments = ["generate-image", "--prompt", "fixture", "--job", str(self.root / "job.json"),
                     "--out", str(self.root / "output"), "--dry-run"]
        for options, expected in (
            (["--model", "gpt-image-2"], "GPT Image 2"),
            (["--model", "nano-banana-2"], "Nano-Banana 2"),
            (["--model", "nano-banana-2", "--request", str(request_path)], "Native Model"),
            (["--request", str(request_path), "--set", "modelName=Override Model"], "Override Model"),
        ):
            with self.subTest(options=options):
                result, code = execute(parser().parse_args(arguments + options),
                                       client_factory=lambda: self.fail("Dry-run must stay offline"))
                self.assertEqual(code, 0)
                self.assertEqual(result["model"], expected)

    def test_image_plan_merges_partial_requests_without_changing_inputs(self):
        from hi3d_image_workflow import image_plan
        for request in ({}, {"imageCount": 2}, {"modelName": "Native Model", "prompt": "native"}):
            original = json.loads(json.dumps(request))
            expected = {"editTaskType": "TEXT_TO_IMAGE", "modelName": "GPT Image 2",
                        "prompt": "fixture", "imageCount": 1, "aspectRatio": "1:1", **request}
            planned = image_plan("fixture", "gpt-image-2", "1:1", 1, request=request)
            self.assertEqual(planned["parameters"]["request"], expected)
            # Moving request assembly out of desktop preserves existing job fingerprints.
            self.assertEqual(planned["fingerprint"], build_plan("text-to-image", request=expected)["fingerprint"])
            self.assertEqual(request, original)
            path = self.root / "partial.json"
            save(path, request)
            self.assertEqual(image_plan("fixture", "gpt-image-2", "1:1", 1, request=path), planned)
        for invalid in ([], 3):
            with self.assertRaisesRegex(ValueError, "JSON object"):
                image_plan("fixture", "gpt-image-2", "1:1", 1, request=invalid)

    def test_business_error_summary_is_bounded_and_redacts_credentials(self):
        self.assertEqual(response_error(502, {'code': 502, 'msg': 'upload failed', 'trace_id': 'trace-0123456789', 'error_source': 'upstream'}), {'http_status': 502, 'code': 502, 'message': 'upload failed', 'trace_id': 'trace-0123456789', 'error_source': 'upstream'})
        self.assertNotIn('trace_id', response_error(502, {'trace_id': 'invalid\ntrace'}))
        self.assertEqual(response_error(200, {'code': 1003, 'msg': 'unknown modelName: nano-banana-2'})['message'], 'unknown modelName: nano-banana-2')
        self.assertEqual(response_error(400, {'message': 'invalid aspect ratio'})['message'], 'invalid aspect ratio')
        self.assertEqual(response_error(400, {'error': {'message': 'invalid image'}})['message'], 'invalid image')
        for message in ['Cookie: MM_AIGC=fixture-cookie', 'Authorization: Bearer fixture-bearer', 'api_key=fixture-key', 'Fe26.fixture-sealed']:
            result = response_error(500, {'msg': message})
            self.assertEqual(result['message'], '[redacted sensitive error details]')
        result = response_error(500, {'msg': 'Download failed: https://example.test/file?signature=private-value'})
        self.assertEqual(result['message'], 'Download failed: [redacted URL]')
        self.assertNotIn('abcdefgh.ijklmnop.qrstuvwx', response_error(500, {'msg': 'invalid abcdefgh.ijklmnop.qrstuvwx'})['message'])
        self.assertNotIn('message', response_error(500, {'msg': {'private': 'nested'}, 'message': 123}))
        self.assertLessEqual(len(response_error(500, {'msg': 'long error ' * 100})['message']), 500)
        self.assertEqual(response_error(500, {'msg': 'invalid\nimage\x00'})['message'], 'invalid image')
    def test_transport_context_and_no_cookie(self):
        calls = []
        class Opener:
            def open(self, request, timeout):
                calls.append(request)
                response = io.BytesIO(json.dumps({'code': 200, 'data': {'environment': 'pre', 'owner_id': 'owner'}}).encode())
                response.status = 200
                return response
        client = Client(Opener()); client.auth()
        client.request('/model3d/result?jobId=one')
        self.assertEqual(calls[-1].get_header('Authorization'), 'Bearer fixture-token-1234567890')
        self.assertEqual(calls[-1].get_header('X-hi3d-environment'), 'pre')
        self.assertIsNone(calls[-1].get_header('Cookie'))
        with self.assertRaises(ApiError): client.check_job({'environment': 'prod', 'owner_id': 'owner'})
        for base in ['https://remote.test/v1', 'http://localhost:10/v1', 'http://127.0.0.1:10/v1?x=1']:
            with patch.dict(os.environ, {'HI3D_API_BASE_URL': base}):
                with self.assertRaises(ValueError): Client()
    def test_request_correlation_is_per_client_for_generation_query_and_mesh(self):
        calls = []
        class Opener:
            def open(self, request, timeout):
                calls.append(request)
                response = io.BytesIO(json.dumps({'code': 200, 'data': {'environment': 'pre', 'owner_id': 'owner'}}).encode())
                response.status = 200
                return response
        clients = []
        for index in range(2):
            with patch.dict(os.environ, {'SPARC3D_TOOL_SESSION_ID': f'session-{index}', 'SPARC3D_TOOL_TURN_ID': f'turn-{index}'}):
                clients.append(Client(Opener()))
        for index, client in enumerate(clients):
            client.auth()
            client.request('/model3d/submit', 'POST', b'{"scene":"general"}')
            client.request('/model3d/result?jobId=one')
            client.send('/mesh/invoke', 'POST', b'fixture', 'multipart/form-data; boundary=fixture')
            for request in calls[-4:]:
                self.assertEqual(request.get_header('X-session-id'), f'session-{index}')
                self.assertEqual(request.get_header('X-turn-id'), f'turn-{index}')
            self.assertEqual(calls[-3].data, b'{"scene":"general"}')
        with patch.dict(os.environ, {'SPARC3D_TOOL_SESSION_ID': '', 'SPARC3D_TOOL_TURN_ID': ''}):
            Client(Opener()).auth()
        self.assertIsNone(calls[-1].get_header('X-session-id'))
        self.assertIsNone(calls[-1].get_header('X-turn-id'))
        for variable in ('SPARC3D_TOOL_SESSION_ID', 'SPARC3D_TOOL_TURN_ID'):
            for value in ('bad id', 'bad\r\nheader', 'x' * 129, '无效'):
                with self.subTest(variable=variable, value=value), patch.dict(os.environ, {variable: value}):
                    with self.assertRaisesRegex(ValueError, 'Invalid request correlation ID'):
                        Client(Opener())

    def test_workspace_upload_identity_and_url_validation(self):
        image = self.root / 'input.png'; image.write_bytes(b'original')
        planned = build_plan('model', images=[image])
        image.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            with multipart(planned['parameters'], planned['files']): pass
        with self.assertRaises(ValueError): workspace_path(self.root / '../outside')
        if os.name != 'nt':
            link = self.root / 'link'; link.symlink_to(self.root)
            with self.assertRaises(ValueError): workspace_path(link / 'input.png')
        with self.assertRaises(ValueError): build_plan('model', image_url='http://insecure.test/a.png')
        with self.assertRaises(ValueError): build_plan('model', request={'scene': 'general', 'version': 'v3.0', 'otherParam': {'userId': 'forged'}})
    def test_model_multipart_declares_webp_content_type_explicitly(self):
        image = self.root / 'input.webp'; image.write_bytes(b'RIFF\x08\x00\x00\x00WEBP')
        planned = build_plan('model', images=[image])
        from hi3d_parameters import multipart
        with multipart(planned['parameters'], planned['files']) as (body, content_type, length):
            raw = body.read()
        self.assertIn(b'filename="input-0.webp"', raw)
        self.assertIn(b'Content-Type: image/webp', raw)
        self.assertIn(image.read_bytes(), raw)
        self.assertTrue(content_type.startswith('multipart/form-data; boundary=hi3d-'))
        self.assertEqual(length, len(raw))
    def test_download_has_no_credentials_rejects_oversized_and_archive_escape(self):
        class Opener:
            def open(inner, request, timeout):
                self.assertIsNone(request.get_header('Authorization'))
                self.assertIsNone(request.get_header('Cookie'))
                result = io.BytesIO(b'artifact'); result.headers = {'Content-Length': str(2 * 1024**3)}
                return result
        with self.assertRaises(ValueError): fetch('https://files.test/a.png?signature=fixture', self.root / 'a.png', Opener())
        self.assertFalse((self.root / 'a.png').exists())
        archive = self.root / 'bad.zip'
        with zipfile.ZipFile(archive, 'w') as z: z.writestr('../escape', 'bad')
        with self.assertRaises(ValueError): unpack(archive, self.root / 'unpacked')
    def test_cached_artifact_still_requires_original_account_and_image_is_immutable(self):
        from PIL import Image
        source = self.root / 'original.webp'
        Image.new('RGB', (3, 4), 'blue').save(source)
        with self.assertRaises(ValueError):
            export_image(source, self.root / 'out.png')
        exported = export_image(source, self.root / 'hi3d-out.png')
        self.assertEqual((exported['width'], exported['height']), (3, 4))
        self.assertEqual(exported, export_image(source, self.root / 'hi3d-out.png'))
        (self.root / 'hi3d-out.png').write_bytes(b'user-content')
        with self.assertRaises(FileExistsError): export_image(source, self.root / 'hi3d-out.png')
        jobpath = self.root / 'job.json'; save(jobpath, {'artifact': {'path': str(source), 'files': []}})
        class SignedOut:
            def check_job(self, job): raise ApiError(401)
        with self.assertRaises(ApiError): download_job(SignedOut(), jobpath, self.root)
    def test_download_queries_fresh_urls_and_keeps_manifest_without_signed_urls(self):
        from PIL import Image
        jobpath = self.root / 'job.json'
        save(jobpath, {'environment': 'test', 'owner_id': 'owner', 'state': 'success'})
        class ClientFixture:
            def check_job(self, job): pass
        def fetcher(url, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (2, 2), 'red').save(target, format='PNG')
        data = {'resultImageUrls': ['https://files.test/opaque-result?private-signature=fixture']}
        with patch('hi3d_artifacts.query_job', return_value=(load(jobpath), data)):
            result = download_job(ClientFixture(), jobpath, self.root / 'originals', fetcher)
        self.assertFalse(result['cached'])
        self.assertTrue(result['artifact']['path'].endswith('.png'))
        self.assertTrue(Path(result['artifact']['path']).name.startswith('hi3d-'))
        self.assertNotIn('private-signature', jobpath.read_text())
        self.assertTrue(download_job(ClientFixture(), jobpath, self.root / 'originals')['cached'])
        Path(result['artifact']['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError): download_job(ClientFixture(), jobpath, self.root / 'originals')

    def test_successful_image_can_start_quality_revision_without_stopping(self):
        from PIL import Image
        for kind in ('text-to-image', 'image-edit'):
            with self.subTest(kind=kind):
                calls = []
                class Fixture:
                    context = {'environment': 'test', 'owner_id': 'owner'}
                    def auth(self): pass
                    def check_job(self, job): pass
                    def request(self, path, method='GET', *args, **kwargs):
                        calls.append(method)
                        data = ({'taskId': f'candidate-{calls.count("POST")}'} if method == 'POST'
                                else {'status': 1, 'percentage': 100})
                        return 200, {'code': 200, 'data': data}
                def downloader(client, path, output):
                    folder = Path(output)
                    folder.mkdir()
                    image = folder / 'candidate.png'
                    Image.new('RGB', (2, 2), (calls.count('POST'), 0, 0)).save(image)
                    return {'artifact': {'files': [{'path': str(image)}]}}
                client = Fixture()
                originals = {}
                for revision, prompt in enumerate(('full portrait', 'correct the profile direction')):
                    jobpath = self.root / f'{kind}-{revision}.json'
                    result, code = generate_task(
                        client, build_plan(kind, overrides=['prompt=' + prompt]), jobpath,
                        self.root / f'{kind}-{revision}', seconds=0, downloader=downloader)
                    self.assertEqual((code, result['result']), (0, 'success'))
                    self.assertEqual(result['task_id'], f'candidate-{revision + 1}')
                    self.assertNotIn('next_action', result)
                    # Visual review is separate from the successful service task.
                    reviewed = {**load(jobpath), 'review_status': 'fail'}
                    self.assertNotIn('next_action', job_summary(reviewed, jobpath))
                    self.assertEqual(reviewed['state'], 'success')
                    for path, content in originals.items():
                        self.assertEqual(path.read_bytes(), content)
                    originals[jobpath] = jobpath.read_bytes()
                    image = Path(result['files'][0])
                    originals[image] = image.read_bytes()
                self.assertEqual(calls, ['POST', 'GET', 'POST', 'GET'])

    def test_image_terminal_failure_preserves_reason_and_never_resubmits(self):
        for kind in ('text-to-image', 'image-edit'):
            for field in ('failReason', 'failureReason', 'errorMessage', 'errorMsg', 'message', 'msg', 'error'):
                with self.subTest(kind=kind, field=field):
                    jobpath = self.root / (kind + '-' + field + '.json')
                    calls = []
                    reason = 'Unsupported image size: https://files.test/result?signature=private-value'
                    failure = {'status': 2, 'errorCode': 4201, field: reason,
                               'debug': 'Authorization: Bearer fixture-private'}
                    class Fixture:
                        context = {'environment': 'test', 'owner_id': 'owner'}
                        def auth(self): pass
                        def check_job(self, job): pass
                        def request(self, path, method='GET', *args, **kwargs):
                            calls.append(method)
                            return (200, {'code': 200, 'data': {'taskId': 'failed-task'} if method == 'POST' else failure})
                    planned = build_plan(kind)
                    client = Fixture()
                    no_download = lambda *a: self.fail('A failed task cannot download')
                    result, code = generate_task(client, planned, jobpath, self.root / 'failed-out',
                                                 seconds=0, downloader=no_download)
                    repeated, repeated_code = generate_task(client, planned, jobpath, self.root / 'failed-out',
                                                           seconds=0, downloader=no_download)
                    self.assertEqual((code, repeated_code), (1, 1))
                    self.assertEqual(result, repeated)
                    self.assertEqual(calls, ['POST', 'GET'])
                    self.assertEqual(result['job']['error']['message'], 'Unsupported image size: [redacted URL]')
                    self.assertEqual(result['job']['error']['code'], 4201)
                    self.assertEqual(result['job']['error']['phase'], 'generation')
                    self.assertEqual(result['job']['task_id'], 'failed-task')
                    self.assertEqual(result['job']['job_file'], str(jobpath))
                    self.assertIn('user explicitly asks', result['job']['next_action'])
                    self.assertNotIn('result', result['job'])
                    for forbidden in ('private-value', 'fixture-private'):
                        self.assertNotIn(forbidden, json.dumps(result) + jobpath.read_text())

    def test_legacy_failed_image_summary_is_safe_and_handles_missing_reason(self):
        for data, expected in (
            ({'error': {'code': 4301, 'message': 'invalid reference image'}}, 'invalid reference image'),
            ({'failReason': 'Cookie: fixture-private'}, '[redacted sensitive error details]'),
            ({'message': {'raw': 'fixture-private'}}, 'Image generation failed; the service returned no failure reason.'),
            ({}, 'Image generation failed; the service returned no failure reason.'),
        ):
            with self.subTest(data=data):
                job = {'kind': 'image-edit', 'state': 'failed', 'task_id': 'legacy-task', 'result': data}
                original = json.dumps(job)
                summary = job_summary(job, self.root / 'legacy.json')
                self.assertEqual(summary['error']['message'], expected)
                self.assertNotIn('fixture-private', json.dumps(summary))
                self.assertEqual(json.dumps(job), original)

    def test_image_submission_uncertainty_stops_without_a_second_post(self):
        for kind in ('text-to-image', 'image-edit'):
            calls = []
            class Fixture:
                context = {'environment': 'test', 'owner_id': 'owner'}
                def auth(self): pass
                def check_job(self, job): pass
                def request(self, path, method='GET', *args, **kwargs):
                    calls.append(method)
                    raise TimeoutError('Authorization: Bearer fixture-private')
            client = Fixture()
            jobpath = self.root / (kind + '-uncertain.json')
            planned = build_plan(kind)
            for _ in range(2):
                result, code = generate_task(client, planned, jobpath, self.root / 'uncertain-out')
                self.assertEqual(code, 2)
                self.assertEqual(result['job']['state'], 'submission_uncertain')
                self.assertEqual(result['job']['error']['phase'], 'request')
                self.assertEqual(result['job']['error']['message'], 'Operation timed out.')
                self.assertIn('next_action', result['job'])
                self.assertNotIn('fixture-private', json.dumps(result))
            self.assertEqual(calls, ['POST'])

    def test_pending_image_resumes_same_task_and_query_error_stops_polling(self):
        for kind in ('text-to-image', 'image-edit'):
            calls = []
            responses = iter([
                (200, {'code': 200, 'data': {'taskId': 'pending-task'}}),
                (200, {'code': 200, 'data': {'status': 0, 'taskStatus': 1}}),
                ValueError('Invalid query response: https://files.test/result?signature=fixture-private'),
            ])
            class Fixture:
                context = {'environment': 'test', 'owner_id': 'owner'}
                def auth(self): pass
                def check_job(self, job): pass
                def request(self, path, method='GET', *args, **kwargs):
                    calls.append(method)
                    response = next(responses)
                    if isinstance(response, Exception): raise response
                    return response
            jobpath = self.root / (kind + '-pending.json')
            planned = build_plan(kind)
            client = Fixture()
            pending, code = generate_task(client, planned, jobpath, self.root / 'pending-out', seconds=0)
            self.assertEqual((code, pending['result']), (0, 'pending'))
            self.assertNotIn('next_action', pending['job'])
            attention, code = generate_task(client, planned, jobpath, self.root / 'pending-out', seconds=0)
            self.assertEqual((code, attention['result']), (2, 'attention'))
            self.assertEqual(calls, ['POST', 'GET', 'GET'])
            self.assertEqual(attention['job']['task_id'], 'pending-task')
            self.assertEqual(attention['job']['last_query_error']['phase'], 'query')
            self.assertEqual(attention['job']['last_query_error']['message'], 'Invalid query response: [redacted URL]')
            self.assertIn('next_action', attention['job'])
            self.assertNotIn('fixture-private', json.dumps(attention) + jobpath.read_text())

    def test_rejected_image_submission_stops_with_no_wait_or_download(self):
        for kind in ('text-to-image', 'image-edit'):
            calls = []
            class Fixture:
                context = {'environment': 'test', 'owner_id': 'owner'}
                def auth(self): pass
                def check_job(self, job): pass
                def request(self, path, method='GET', *args, **kwargs):
                    calls.append(method)
                    return 400, {'code': 1003, 'message': 'unknown modelName'}
            client = Fixture()
            jobpath = self.root / (kind + '-rejected.json')
            planned = build_plan(kind)
            for _ in range(2):
                result, code = generate_task(client, planned, jobpath, self.root / 'rejected-out')
                self.assertEqual((code, result['result']), (1, 'failed'))
                self.assertEqual(result['job']['state'], 'submission_rejected')
                self.assertEqual(result['job']['error']['message'], 'unknown modelName')
                self.assertEqual(result['job']['error']['code'], 1003)
                self.assertIn('next_action', result['job'])
            self.assertEqual(calls, ['POST'])

    def test_image_wait_and_download_errors_return_safe_actionable_summaries(self):
        for phase, error, expected in (
            ('wait', TimeoutError('fixture-private'), 'Operation timed out.'),
            ('download', PermissionError(13, 'fixture-private', '/private/file'), 'Permission denied'),
            ('download', ValueError('Download URL expired: https://files.test/result?signature=fixture-private'),
             'Download URL expired: [redacted URL]'),
        ):
            with self.subTest(phase=phase):
                jobpath = self.root / 'exception.json'
                job = {'kind': 'text-to-image', 'state': 'queueing', 'task_id': 'existing-task'}
                save(jobpath, job)
                def waiter(*args):
                    if phase == 'wait': raise error
                    return {'result': 'success', 'job': {**job, 'state': 'success'}}, 0
                def downloader(*args): raise error
                with patch('hi3d_generation_workflow.submit_job', return_value={'job': job}):
                    result, code = generate_task(None, {}, jobpath, self.root / 'error-out',
                                                waiter=waiter, downloader=downloader)
                self.assertEqual((code, result['phase']), (2, phase))
                self.assertEqual(result['error']['message'], expected)
                self.assertEqual(result['job']['task_id'], 'existing-task')
                self.assertIn('next_action', result)
                self.assertNotIn('fixture-private', json.dumps(result))

    def test_image_cli_validation_failure_is_reported_without_submission(self):
        jobpath = self.root / 'cli-error.json'
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(['generate-image', '--prompt', 'x' * 4001, '--job', str(jobpath),
                         '--out', str(self.root / 'cli-out'), '--dry-run'])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertIn('maximum is 4000', result['message'])
        self.assertEqual(result['phase'], 'generate-image')
        self.assertEqual(result['job_file'], str(jobpath))
        self.assertIn('next_action', result)
        self.assertFalse(jobpath.exists())

    def test_generation_returns_latest_download_query_error_without_resubmitting(self):
        for kind in ('text-to-image', 'model'):
            with self.subTest(kind=kind):
                planned = (build_plan(kind, request={'editTaskType': 'TEXT_TO_IMAGE', 'modelName': 'Nano-Banana 2', 'prompt': 'fixture'})
                           if kind == 'text-to-image' else build_plan(kind, image_url='https://files.test/input.png'))
                responses = iter([
                    (200, {'code': 200, 'data': {'environment': 'test', 'owner_id': 'owner'}}),
                    (200, {'code': 200, 'data': {'taskId': 'fixture-task', 'jobId': 'fixture-task'}}),
                    (200, {'code': 200, 'data': {'status': 1}}),
                    (502, {'code': 502, 'message': 'Upstream unavailable: https://files.test/result?signature=private-value',
                           'trace_id': 'trace-0123456789', 'error_source': 'upstream'}),
                ])
                methods = []
                class Opener:
                    def open(self, request, timeout):
                        methods.append(request.get_method())
                        status, body = next(responses)
                        response = io.BytesIO(json.dumps(body).encode())
                        response.status = status
                        return response
                jobpath = self.root / (kind + '.json')
                result, code = generate_task(Client(Opener()), planned, jobpath, self.root / kind, seconds=0)
                self.assertEqual(code, 2)
                self.assertEqual((result['result'], result['phase']), ('attention', 'download'))
                self.assertEqual(result['job']['task_id'], 'fixture-task')
                self.assertEqual(result['job']['last_query_error'], {
                    'http_status': 502, 'code': 502, 'message': 'Upstream unavailable: [redacted URL]',
                    'trace_id': 'trace-0123456789', 'error_source': 'upstream',
                    'next_action': QUERY_FAILURE_ACTION,
                    'reason': 'Upstream unavailable: [redacted URL]',
                })
                self.assertEqual(result['job']['last_query_error'], load(jobpath)['last_query_error'])
                self.assertTrue(result['job']['progress']['stale'])
                self.assertNotIn('private-value', json.dumps(result))
                self.assertEqual(methods, ['GET', 'POST', 'GET', 'GET'])

    def test_generation_retains_last_known_job_when_error_snapshot_is_unreadable(self):
        for content in (None, '{invalid JSON', '[]'):
            with self.subTest(content=content):
                jobpath = self.root / 'fallback.json'
                job = {'state': 'success', 'task_id': 'recoverable-task'}
                save(jobpath, job)
                def waiter(*args):
                    return {'result': 'success', 'job': job}, 0
                def downloader(*args):
                    if content is None:
                        jobpath.unlink()
                    else:
                        jobpath.write_text(content, encoding='utf-8')
                    raise OSError('download failed with private-value')
                with patch('hi3d_generation_workflow.submit_job', return_value={'job': job}):
                    result, code = generate_task(None, {}, jobpath, self.root / 'fallback-out',
                                                 waiter=waiter, downloader=downloader)
                self.assertEqual(code, 2)
                self.assertEqual((result['result'], result['phase'], result['error_type']), ('attention', 'download', 'OSError'))
                self.assertEqual(result['job']['task_id'], 'recoverable-task')
                self.assertNotIn('private-value', json.dumps(result))

    def test_combined_cli_downloads_images_and_models_with_live_progress_and_cache_recovery(self):
        from PIL import Image
        png = io.BytesIO()
        Image.new('RGB', (2, 3), 'blue').save(png, format='PNG')
        reference = self.root / 'reference.png'
        reference.write_bytes(png.getvalue())
        chunk = b'{"asset":{"version":"2.0"}}'
        chunk += b' ' * (-len(chunk) % 4)
        glb = struct.pack('<4sII', b'glTF', 2, 20 + len(chunk)) + struct.pack('<II', len(chunk), 0x4e4f534a) + chunk
        for kind, command, extension, content, inputs in (
            ('text-to-image', 'generate-image', 'png', png.getvalue(), [
                '--prompt', 'fixture', '--aspect-ratio', '16:9',
            ]),
            ('image-edit', 'generate-image', 'png', png.getvalue(), [
                '--kind', 'image-edit', '--prompt', 'fixture',
                '--image', str(reference), '--aspect-ratio', '3:4',
            ]),
            ('model', 'generate-3d', 'glb', glb, [
                '--image-url', 'https://files.test/input.png',
                '--set', 'model_type=v3.0:quality',
                '--set', 'generation_type=both',
            ]),
        ):
            with self.subTest(kind=kind):
                artifact_url = 'https://files.test/result.' + extension + '?signature=private-value'
                data = {'status': 1, 'percentage': 100}
                data.update({'resultImageUrls': [artifact_url]} if extension == 'png' else {'model3ds': [{'model3DGlbUrl': artifact_url}]})
                session = {'code': 200, 'data': {'environment': 'test', 'owner_id': 'owner'}}
                success = {'code': 200, 'data': data}
                responses = iter([session, {'code': 200, 'data': {'taskId': 'cli-task', 'jobId': 'cli-task'}},
                                  success, success, session, success])
                methods, downloads = [], []
                class ApiOpener:
                    def open(self, request, timeout):
                        methods.append(request.get_method())
                        response = io.BytesIO(json.dumps(next(responses)).encode())
                        response.status = 200
                        return response
                class DownloadOpener:
                    def open(self, request, timeout):
                        downloads.append(request)
                        response = io.BytesIO(content)
                        response.headers = {'Content-Length': str(len(content))}
                        return response
                jobpath = self.root / (kind + '.json')
                args = parser().parse_args([command, *inputs, '--job', str(jobpath), '--out', str(self.root / kind),
                                           '--seconds', '0', '--progress', 'json'])
                progress = io.StringIO()
                with patch('hi3d_artifacts.urllib.request.build_opener', return_value=DownloadOpener()), redirect_stderr(progress):
                    result, code = execute(args, client_factory=lambda: Client(ApiOpener()))
                    resumed, resumed_code = execute(args, client_factory=lambda: Client(ApiOpener()))
                self.assertEqual((code, resumed_code), (0, 0))
                self.assertEqual(result, resumed)
                self.assertEqual((result['result'], result['task_id']), ('success', 'cli-task'))
                self.assertEqual(Path(result['files'][0]).read_bytes(), content)
                self.assertTrue(Path(result['files'][0]).name.startswith('hi3d-'))
                self.assertEqual(methods.count('POST'), 1)
                if extension == 'png':
                    request = load(jobpath)['parameters']['request']
                    self.assertEqual(request['modelName'], 'GPT Image 2')
                    self.assertEqual(request['aspectRatio'], '16:9' if kind == 'text-to-image' else '3:4')
                    self.assertEqual(request['editTaskType'], 'TEXT_TO_IMAGE' if kind == 'text-to-image' else 'EDIT')
                else:
                    self.assertEqual(load(jobpath)['parameters']['request']['otherParam']['modelType'], 'standard')
                self.assertEqual(len(downloads), 1)
                self.assertIsNone(downloads[0].get_header('Authorization'))
                self.assertIsNone(downloads[0].get_header('Cookie'))
                self.assertNotIn('private-value', jobpath.read_text())
                events = [json.loads(line) for line in progress.getvalue().splitlines()]
                self.assertTrue(events)
                self.assertTrue(all(event['event'] == 'progress' and event['state'] == 'success' for event in events))

    def test_retry_quota_view_requires_a_remaining_count(self):
        self.assertEqual(retry_quota_view({'retryCount': 15}),
                         {'eligible': True, 'remaining': 15, 'can_retry': True})
        self.assertEqual(retry_quota_view({'remaining': 10}),
                         {'eligible': True, 'remaining': 10, 'can_retry': True})
        self.assertEqual(retry_quota_view({'remainRetryTimes': 10, 'retryLimit': 10}),
                         {'eligible': True, 'remaining': 10, 'can_retry': True, 'limit': 10})
        self.assertEqual(retry_quota_view({'eligible': True, 'remaining': 0}),
                         {'eligible': False, 'remaining': 0, 'can_retry': False})
        self.assertEqual(retry_quota_view({'eligible': True}),
                         {'eligible': False, 'remaining': 0, 'can_retry': False})
        self.assertEqual(retry_quota_view({'remaining': True}),
                         {'eligible': False, 'remaining': 0, 'can_retry': False})

    def test_retry_quota_cli_reads_task_id_and_does_not_submit(self):
        from hi3d_client import BACKEND
        jobpath = self.root / 'source.json'
        save(jobpath, {'backend': BACKEND, 'kind': 'model', 'task_id': 'parent-task',
                       'environment': 'test', 'owner_id': 'owner'})
        calls = []
        class Opener:
            def open(self, request, timeout):
                calls.append((request.get_method(), request.full_url.split('/v1', 1)[-1], request.data))
                if request.full_url.endswith('/session'):
                    body = {'code': 200, 'data': {'environment': 'test', 'owner_id': 'owner'}}
                else:
                    body = {'code': 200, 'data': {'status': 1, 'retryCount': 10}}
                response = io.BytesIO(json.dumps(body).encode())
                response.status = 200
                return response
        args = parser().parse_args(['retry-quota', '--job', str(jobpath)])
        result, code = execute(args, client_factory=lambda: Client(Opener()))
        self.assertEqual((code, result['remaining'], result['can_retry'], result['task_id']), (0, 10, True, 'parent-task'))
        self.assertEqual([item[0] for item in calls], ['GET', 'GET'])
        self.assertTrue(calls[-1][1].startswith('/model3d/result?jobId='))
        self.assertIn('jobId=parent-task', calls[-1][1])
        self.assertIsNone(calls[-1][2])

    def test_retry_posts_parent_job_id_into_a_new_job(self):
        from hi3d_client import BACKEND
        parent = self.root / 'parent.json'
        save(parent, {'backend': BACKEND, 'kind': 'model', 'task_id': 'parent-task',
                      'environment': 'test', 'owner_id': 'owner', 'fingerprint': 'original'})
        calls = []
        class Opener:
            def open(self, request, timeout):
                calls.append((request.get_method(), request.full_url.split('/v1', 1)[-1], request.data))
                if request.full_url.endswith('/session'):
                    body = {'code': 200, 'data': {'environment': 'test', 'owner_id': 'owner'}}
                elif request.get_method() == 'POST':
                    body = {'code': 200, 'data': {'jobId': 'retry-task'}}
                else:
                    body = {'code': 200, 'data': {'status': 1, 'model3ds': []}}
                response = io.BytesIO(json.dumps(body).encode())
                response.status = 200
                return response
        client = Client(Opener())
        client.auth()
        with self.assertRaises(ValueError):
            retry_job(client, parent, retry_parent('model', 'parent-task', load(parent)))
        jobpath = self.root / 'retry.json'
        planned = retry_parent('model', 'parent-task', load(parent))
        submitted = retry_job(client, jobpath, planned)
        self.assertFalse(submitted['reused'])
        self.assertEqual(submitted['job']['task_id'], 'retry-task')
        self.assertEqual(submitted['job']['parent_task_id'], 'parent-task')
        self.assertEqual(json.loads(calls[-1][2].decode()), {'parentGenerateId': 'parent-task'})
        self.assertEqual(calls[-1][1], '/model3d/retry')
        reused = retry_job(client, jobpath, planned)
        self.assertTrue(reused['reused'])
        self.assertEqual(sum(1 for method, path, _ in calls if method == 'POST' and path == '/model3d/retry'), 1)

    def test_retry_cli_dry_run_and_limit_errors_do_not_hide_the_parent(self):
        from hi3d_client import BACKEND
        parent = self.root / 'parent.json'
        save(parent, {'backend': BACKEND, 'kind': 'model', 'task_id': 'parent-task',
                      'environment': 'test', 'owner_id': 'owner'})
        dry = parser().parse_args(['retry', '--parent-job', str(parent), '--job', str(self.root / 'retry.json'),
                                   '--out', str(self.root / 'retry-out'), '--dry-run'])
        result, code = execute(dry, client_factory=lambda: (_ for _ in ()).throw(AssertionError('dry-run')))
        self.assertEqual((code, result['dry_run'], result['parent_task_id'], result['fingerprint']),
                         (0, True, 'parent-task', 'retry:parent-task'))
        calls = []
        class Opener:
            def open(self, request, timeout):
                calls.append(request.get_method())
                if request.full_url.endswith('/session'):
                    body = {'code': 200, 'data': {'environment': 'test', 'owner_id': 'owner'}}
                    status = 200
                else:
                    body = {'code': 1003, 'domainCode': 10030105, 'message': 'retry limit', 'error_source': 'upstream'}
                    status = 200
                response = io.BytesIO(json.dumps(body).encode())
                response.status = status
                return response
        args = parser().parse_args(['retry', '--parent-job', str(parent), '--job', str(self.root / 'retry-limit.json'),
                                    '--out', str(self.root / 'retry-limit-out'), '--seconds', '0'])
        result, code = execute(args, client_factory=lambda: Client(Opener()))
        self.assertEqual((code, result['result']), (1, 'failed'))
        self.assertEqual(result['job']['error']['category'], 'retry_limit_exceeded')
        self.assertEqual(load(parent)['task_id'], 'parent-task')
        self.assertEqual(calls.count('POST'), 1)
        waiter = Mock(side_effect=AssertionError('Rejected retry must not wait'))
        with patch('hi3d_generation_workflow.wait_job', waiter):
            blocked, blocked_code = generate_retry_task(
                Client(Opener()), retry_parent('model', 'parent-task'),
                self.root / 'retry-limit-2.json', self.root / 'retry-limit-2-out', seconds=0)
        self.assertEqual((blocked_code, blocked['result']), (1, 'failed'))
        waiter.assert_not_called()

    def test_retry_child_uses_root_and_emits_acceptance_before_the_first_query(self):
        from hi3d_client import BACKEND
        parent = self.root / 'child.json'
        save(parent, {'backend': BACKEND, 'kind': 'model', 'task_id': 'child-task',
                      'retry': True, 'parent_task_id': 'root-task',
                      'environment': 'test', 'owner_id': 'owner'})
        trace = []
        class FixtureClient:
            context = {'environment': 'test', 'owner_id': 'owner'}
            def auth(self):
                pass
            def check_job(self, job):
                self.assert_bound(job)
            def assert_bound(self, job):
                if job.get('owner_id') != 'owner':
                    raise ValueError('foreign account')
            def request(self, path, method='GET', payload=None, *args, **kwargs):
                if method == 'POST':
                    trace.append(('submit', json.loads(payload)))
                    return 200, {'code': 200, 'data': {'jobId': 'new-task', 'retryCount': 2}}
                trace.append(('query', path))
                raise TimeoutError('fixture')
        args = parser().parse_args(['retry', '--parent-job', str(parent), '--job', str(self.root / 'new.json'),
                                    '--out', str(self.root / 'new-out'), '--progress', 'json', '--seconds', '0'])
        stream = io.StringIO()
        with redirect_stderr(stream):
            result, code = execute(args, client_factory=FixtureClient)
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(trace[0], ('submit', {'parentGenerateId': 'root-task'}))
        self.assertEqual(load(self.root / 'new.json')['submitted_retry_quota']['remaining'], 2)
        self.assertEqual(events[0]['event'], 'submitted')
        self.assertEqual(events[0]['task_id'], 'new-task')
        self.assertEqual(load(self.root / 'new.json')['parent_task_id'], 'root-task')
        self.assertEqual((code, result['result']), (2, 'attention'))

    def test_quota_checks_parent_account_and_submission_flags_survive(self):
        from hi3d_client import BACKEND
        parent = self.root / 'foreign.json'
        save(parent, {'backend': BACKEND, 'kind': 'model', 'task_id': 'foreign',
                      'environment': 'prod', 'owner_id': 'other'})
        client = Mock()
        client.check_job.side_effect = ValueError('foreign account')
        args = parser().parse_args(['retry-quota', '--job', str(parent)])
        with self.assertRaises(ValueError):
            execute(args, client_factory=lambda: client)
        client.request.assert_not_called()
        error = response_error(200, {'code': 1003, 'domainCode': 10030105,
                                     'submission_has_task_id': True})
        self.assertTrue(error['submission_has_task_id'])

if __name__ == '__main__': unittest.main()
