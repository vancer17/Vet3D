from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from mdf3_service_invoke import MDF3ServiceInvokeCaller  # noqa: E402
from online_service_atoms import (  # noqa: E402
    AmbiguousOutcome,
    AuditWriter,
    BusinessFailure,
    ContractViolation,
    load_jsonl,
    verify_audit_records,
)


class FakeSession:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []
        self.entered = 0
        self.exited = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited += 1
        return False

    def invoke(self, service, input_data, trace_id=None, timeout=3600.0, preferred=None):
        self.calls.append(
            {
                "service": service,
                "input_data": input_data,
                "trace_id": trace_id,
                "timeout": timeout,
                "preferred": preferred,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result


class MDF3ServiceInvokeTest(unittest.TestCase):
    def make_caller(self, directory, session):
        return MDF3ServiceInvokeCaller(
            config_path=str(SKILL_ROOT / "assets" / "config.test.yaml"),
            endpoint_alias="test-invoke",
            environment="test",
            audit=AuditWriter(Path(directory) / "audit.jsonl"),
            success_predicate=lambda result: result.get("status") == "success",
            session_factory=lambda **kwargs: session,
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
            session = FakeSession(result={"status": "success"})
            result = self.invoke(self.make_caller(directory, session))
            self.assertEqual(result["status"], "success")
            self.assertEqual(len(session.calls), 1)
            self.assertEqual(session.calls[0]["service"], "service-a")
            self.assertEqual(session.calls[0]["input_data"]["value"], 3)
            self.assertEqual(session.entered, 1)
            self.assertEqual(session.exited, 1)
            audit_path = Path(directory) / "audit.jsonl"
            self.assertNotIn("do-not-log", audit_path.read_text())
            report = verify_audit_records(
                load_jsonl(audit_path),
                trace_id="trace-1",
            )
            self.assertTrue(report.ok)

    def test_timeout_is_ambiguous_and_never_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = FakeSession(error=TimeoutError("timeout"))
            with self.assertRaises(AmbiguousOutcome):
                self.invoke(self.make_caller(directory, session))
            self.assertEqual(len(session.calls), 1)
            report = verify_audit_records(
                load_jsonl(Path(directory) / "audit.jsonl"),
                trace_id="trace-1",
            )
            self.assertEqual(report.ambiguous, 1)
            self.assertFalse(report.ok)

    def test_business_failure_and_invalid_result_are_distinct(self) -> None:
        cases = [
            ({"status": "failed"}, BusinessFailure),
            ([], ContractViolation),
        ]
        for body, error in cases:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                session = FakeSession(result=body)
                with self.assertRaises(error):
                    self.invoke(self.make_caller(directory, session))
                self.assertEqual(len(session.calls), 1)
                report = verify_audit_records(
                    load_jsonl(Path(directory) / "audit.jsonl")
                )
                self.assertEqual(report.failed, 1)
                self.assertFalse(report.ok)

    def test_session_is_closed_after_transport_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = FakeSession(error=OSError("queue down"))
            with self.assertRaises(AmbiguousOutcome):
                self.invoke(self.make_caller(directory, session))
            self.assertEqual(session.entered, 1)
            self.assertEqual(session.exited, 1)


if __name__ == "__main__":
    unittest.main()
