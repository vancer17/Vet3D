from __future__ import annotations

import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from mdf3_generic_forward import MDF3GenericForwardCaller  # noqa: E402
from online_service_atoms import (  # noqa: E402
    AmbiguousOutcome,
    AuditWriter,
    BusinessFailure,
    ContractViolation,
    DefinitiveRejection,
    load_jsonl,
    verify_audit_records,
)


def dumps_fn(value):
    return json.dumps(value, sort_keys=True).encode("utf-8")


def loads_fn(value):
    return json.loads(value.decode("utf-8"))


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class RecordingPost:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def __call__(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


def success_body(result):
    encoded = base64.b64encode(dumps_fn(result)).decode("ascii")
    return {"success": True, "pickle_payload": encoded}


class MDF3GenericForwardTest(unittest.TestCase):
    def make_caller(self, directory, post):
        return MDF3GenericForwardCaller(
            endpoint="http://example.invalid/generate_model",
            endpoint_alias="test-forward",
            environment="test",
            audit=AuditWriter(Path(directory) / "audit.jsonl"),
            success_predicate=lambda result: result.get("status") == "success",
            post=post,
            dumps_fn=dumps_fn,
            loads_fn=loads_fn,
            transport_exceptions=(TimeoutError,),
        )

    def invoke(self, caller):
        return caller.call_once(
            service="service-a",
            input_data={"token": "do-not-log", "value": 3},
            trace_id="trace-1",
            timeout_sec=60,
            run_id="run-1",
            case_id="case-1",
        )

    def test_success_is_audited_without_request_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            post = RecordingPost(
                response=FakeResponse(200, success_body({"status": "success"}))
            )
            result = self.invoke(self.make_caller(directory, post))
            self.assertEqual(result["status"], "success")
            self.assertEqual(len(post.calls), 1)
            self.assertEqual(post.calls[0][1]["headers"]["traceid"], "trace-1")
            audit_path = Path(directory) / "audit.jsonl"
            self.assertNotIn("do-not-log", audit_path.read_text())
            report = verify_audit_records(
                load_jsonl(audit_path),
                trace_id="trace-1",
            )
            self.assertTrue(report.ok)

    def test_timeout_is_ambiguous_and_never_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            post = RecordingPost(error=TimeoutError("timeout"))
            with self.assertRaises(AmbiguousOutcome):
                self.invoke(self.make_caller(directory, post))
            self.assertEqual(len(post.calls), 1)
            report = verify_audit_records(
                load_jsonl(Path(directory) / "audit.jsonl"),
                trace_id="trace-1",
            )
            self.assertEqual(report.ambiguous, 1)
            self.assertFalse(report.ok)

    def test_http_500_is_ambiguous_and_never_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            post = RecordingPost(response=FakeResponse(500, {}))
            with self.assertRaises(AmbiguousOutcome):
                self.invoke(self.make_caller(directory, post))
            self.assertEqual(len(post.calls), 1)

    def test_http_400_is_definitive_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            post = RecordingPost(response=FakeResponse(400, {}))
            with self.assertRaises(DefinitiveRejection):
                self.invoke(self.make_caller(directory, post))
            self.assertEqual(len(post.calls), 1)
            report = verify_audit_records(
                load_jsonl(Path(directory) / "audit.jsonl"),
                trace_id="trace-1",
            )
            self.assertEqual(report.failed, 1)
            self.assertFalse(report.ok)

    def test_request_contract_and_no_redirects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            post = RecordingPost(
                response=FakeResponse(200, success_body({"status": "success"}))
            )
            caller = self.make_caller(directory, post)
            caller.headers = {"Authorization": "Bearer simulated-private"}
            caller.idempotency_header = "Idempotency-Key"
            caller.call_once(
                service="service-a",
                input_data={"value": 7},
                trace_id="trace-1",
                timeout_sec=30,
                run_id="r",
                case_id="c",
                idempotency_key="key-1",
                call_id="unique-call",
            )
            self.assertEqual(len(post.calls), 1)
            endpoint, request = post.calls[0]
            self.assertEqual(endpoint, caller.endpoint)
            self.assertIs(request["allow_redirects"], False)
            self.assertEqual(request["headers"]["Idempotency-Key"], "key-1")
            self.assertEqual(request["json"]["workflow_name"], "generic-forward")
            self.assertEqual(
                request["json"]["input_data"]["target_service"], "service-a"
            )
            encoded = request["json"]["input_data"]["pickle_payload"]
            self.assertEqual(loads_fn(base64.b64decode(encoded)), {"value": 7})
            self.assertNotIn(
                "simulated-private", (Path(directory) / "audit.jsonl").read_text()
            )

    def test_unconfirmed_responses_stay_ambiguous(self) -> None:
        cases = [
            (302, {}),
            (202, {}),
            (200, {}),
            (200, {"success": 1}),
            (200, ValueError("bad JSON")),
            (200, []),
            (200, {"success": True}),
            (200, {"success": True, "pickle_payload": "!"}),
        ]
        for status, body in cases:
            with (
                self.subTest(status=status, body=body),
                tempfile.TemporaryDirectory() as directory,
            ):
                post = RecordingPost(response=FakeResponse(status, body))
                with self.assertRaises(AmbiguousOutcome):
                    self.invoke(self.make_caller(directory, post))
                self.assertEqual(len(post.calls), 1)
                report = verify_audit_records(
                    load_jsonl(Path(directory) / "audit.jsonl")
                )
                self.assertEqual(report.ambiguous, 1)
                self.assertFalse(report.ok)

    def test_business_failure_and_invalid_result_are_distinct(self) -> None:
        cases = [
            ({"success": False}, BusinessFailure),
            (success_body({"status": "failed"}), BusinessFailure),
            (success_body([]), ContractViolation),
        ]
        for body, error in cases:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                post = RecordingPost(response=FakeResponse(200, body))
                with self.assertRaises(error):
                    self.invoke(self.make_caller(directory, post))
                self.assertEqual(len(post.calls), 1)
                report = verify_audit_records(
                    load_jsonl(Path(directory) / "audit.jsonl")
                )
                self.assertEqual(report.failed, 1)
                self.assertFalse(report.ok)

    def test_serialization_and_idempotency_preflight_do_not_submit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            post = RecordingPost()
            caller = self.make_caller(directory, post)
            caller._dumps = lambda value: "not-bytes"
            with self.assertRaises(ContractViolation):
                self.invoke(caller)
            with self.assertRaises(ContractViolation):
                caller.call_once(
                    service="s",
                    input_data={},
                    trace_id="t",
                    timeout_sec=5,
                    run_id="r",
                    case_id="c",
                    idempotency_key="unconfigured",
                )
            self.assertEqual(post.calls, [])
            self.assertFalse((Path(directory) / "audit.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
