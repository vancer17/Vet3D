from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from online_service_atoms import (  # noqa: E402
    ArtifactValidationError,
    AuditWriter,
    ContractViolation,
    RunSpec,
    atomic_write_bytes,
    evaluate_checkpoint,
    load_jsonl,
    stable_digest,
    sha256_file,
    sha256_bytes,
    summarize_for_audit,
    validate_file,
    verify_audit_records,
)


class FakeBinary:
    def __init__(self, content: bytes) -> None:
        self.field_name = "input_mesh"
        self.file_name = "/sensitive/path/model.glb"
        self.content = content


class OnlineServiceAtomsTest(unittest.TestCase):
    def test_summary_redacts_credentials_and_hashes_binary(self) -> None:
        value = {
            "token": "do-not-log",
            "nested": {
                "private-value": "also-secret",
                "binary": FakeBinary(b"glTF-data"),
            },
            "long": "x" * 400,
        }
        summary = summarize_for_audit(
            value,
            extra_sensitive_keys=("private-value",),
        )
        encoded = json.dumps(summary, sort_keys=True)
        self.assertNotIn("do-not-log", encoded)
        self.assertNotIn("also-secret", encoded)
        self.assertNotIn("x" * 40, encoded)
        self.assertEqual(summary["nested"]["binary"]["file_name"], "model.glb")
        self.assertEqual(summary["nested"]["binary"]["size"], 9)

    def test_stable_digest_is_order_independent(self) -> None:
        self.assertEqual(
            stable_digest({"a": 1, "b": 2}),
            stable_digest({"b": 2, "a": 1}),
        )

    def test_run_spec_template_is_loadable(self) -> None:
        template = json.loads(
            (SKILL_ROOT / "assets" / "run_spec.template.json").read_text()
        )
        spec = RunSpec.from_dict(template)
        self.assertEqual(spec.schema_version, 1)
        self.assertEqual(spec.retry_policy["max_attempts"], 1)
        self.assertEqual(spec.side_effects[0]["policy"], "required")

    def test_run_spec_rejects_unsafe_retry_configuration(self) -> None:
        template = json.loads(
            (SKILL_ROOT / "assets" / "run_spec.template.json").read_text()
        )
        template["retry_policy"] = {"automatic": True, "max_attempts": 3}
        with self.assertRaises(ContractViolation):
            RunSpec.from_dict(template)

    def test_atomic_write_and_file_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.bin"
            atomic_write_bytes(path, b"artifact")
            report = validate_file(path, expected_size=8)
            self.assertEqual(report["status"], "validated")
            self.assertEqual(report["size"], 8)
            with self.assertRaises(ArtifactValidationError):
                validate_file(path, expected_sha256="0" * 64)

    def test_checkpoint_requires_exact_fingerprints_and_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.bin"
            atomic_write_bytes(path, b"artifact")
            validation = validate_file(path)
            checkpoint = {
                "status": "validated",
                "input_digest": "input-1",
                "contract_digest": "contract-1",
                "parameter_digest": "params-1",
                "artifact": {
                    "path": str(path),
                    "size": validation["size"],
                    "sha256": validation["sha256"],
                },
            }
            decision = evaluate_checkpoint(
                checkpoint,
                input_digest="input-1",
                contract_digest="contract-1",
                parameter_digest="params-1",
            )
            self.assertTrue(decision.reusable)
            atomic_write_bytes(path, b"changed")
            decision = evaluate_checkpoint(
                checkpoint,
                input_digest="input-1",
                contract_digest="contract-1",
                parameter_digest="params-1",
            )
            self.assertFalse(decision.reusable)

    def test_audit_without_call_events_is_not_success(self) -> None:
        report = verify_audit_records(
            [{"event": "case_completed", "trace_id": "trace-1"}], trace_id="trace-1"
        )
        self.assertFalse(report.ok)
        self.assertIn("no request call events selected", report.errors)

    def test_audit_writer_redacts_and_verifies_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            audit = AuditWriter(path)
            common = {
                "trace_id": "trace-1",
                "call_id": "call-1",
                "service": "service-a",
            }
            audit.write("request_sent", **dict(common, token="do-not-log", retries=0))
            audit.write("request_finished", **dict(common, status="succeeded"))
            self.assertNotIn("do-not-log", path.read_text())
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            report = verify_audit_records(load_jsonl(path), trace_id="trace-1")
            self.assertTrue(report.ok)
            self.assertEqual(report.sent, 1)
            self.assertEqual(report.succeeded, 1)

    def test_audit_ambiguous_is_terminal_but_not_success(self) -> None:
        records = [
            {
                "event": "request_sent",
                "trace_id": "trace-1",
                "call_id": "call-1",
                "retries": 0,
            },
            {
                "event": "request_ambiguous",
                "trace_id": "trace-1",
                "call_id": "call-1",
                "status": "transport_unknown",
            },
        ]
        report = verify_audit_records(records, trace_id="trace-1")
        self.assertTrue(report.complete)
        self.assertFalse(report.ok)
        self.assertEqual(report.ambiguous_call_ids, ("call-1",))

    def test_allow_incomplete_preserves_open_call_evidence(self) -> None:
        records = [
            {
                "event": "request_sent",
                "trace_id": "trace-1",
                "call_id": "call-1",
                "retries": 0,
            }
        ]
        report = verify_audit_records(
            records,
            trace_id="trace-1",
            allow_incomplete=True,
        )
        self.assertTrue(report.ok)
        self.assertFalse(report.complete)
        self.assertEqual(report.open_call_ids, ("call-1",))

    def test_checkpoint_rejects_missing_output_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.bin"
            atomic_write_bytes(path, b"artifact")
            report = validate_file(path)
            for omitted in ("size", "sha256"):
                artifact = {
                    "path": str(path),
                    "size": report["size"],
                    "sha256": report["sha256"],
                }
                del artifact[omitted]
                checkpoint = dict(
                    status="validated",
                    input_digest="i",
                    contract_digest="c",
                    parameter_digest="p",
                    artifact=artifact,
                )
                decision = evaluate_checkpoint(
                    checkpoint,
                    input_digest="i",
                    contract_digest="c",
                    parameter_digest="p",
                )
                self.assertFalse(decision.reusable)
                self.assertTrue(any(omitted in reason for reason in decision.reasons))

    def test_run_spec_requires_string_identifiers(self) -> None:
        template = json.loads(
            (SKILL_ROOT / "assets/run_spec.template.json").read_text()
        )
        for value in (None, 42, " "):
            with self.subTest(value=value), self.assertRaises(ContractViolation):
                RunSpec.from_dict(dict(template, trace_id=value))
        with self.assertRaises(ContractViolation):
            RunSpec.from_dict(
                dict(template, retry_policy={"automatic": False, "max_attempts": True})
            )

    def test_file_hash_reads_all_bytes_with_positive_chunk_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.bin"
            content = b"complete-input" * 11
            path.write_bytes(content)
            self.assertEqual(sha256_file(path, chunk_size=3), sha256_bytes(content))
            for size in (0, -1, True):
                with self.subTest(size=size), self.assertRaises(ValueError):
                    sha256_file(path, chunk_size=size)


if __name__ == "__main__":
    unittest.main()
