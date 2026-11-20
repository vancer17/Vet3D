from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mdf_endpoint import load_service_names  # noqa: E402
from mdf_probe import probe_service  # noqa: E402
from online_service_atoms import load_jsonl, verify_audit_records  # noqa: E402


class FakeSession:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def invoke(self, service, input_data, trace_id=None, timeout=3600.0, preferred=None):
        self.calls.append({"service": service, "input_data": input_data, "timeout": timeout})
        if self.error is not None:
            raise self.error
        return self.result


class ProbeTest(unittest.TestCase):
    def run_probe(self, session, directory):
        return probe_service(
            "auto-rig",
            transport="sdk",
            config_path=str(
                Path(__file__).resolve().parents[1] / "assets" / "config.test.yaml"
            ),
            run_dir=Path(directory),
            run_id="offline-test",
            timeout_sec=1,
            session_factory=lambda **kwargs: session,
        )

    def test_downstream_error_proves_roundtrip_but_not_business_success(self):
        session = FakeSession(
            result={"success": False, "error_info": "private exception content"}
        )
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_probe(session, directory)
            self.assertEqual(result["reachability"], "downstream_response_received")
            self.assertEqual(result["adapter_outcome"], "BusinessFailure")
            self.assertEqual(result["business_validation"], "not_run")
            self.assertEqual(len(session.calls), 1)
            self.assertEqual(
                session.calls[0]["input_data"],
                {"__mdf_connectivity_probe__": True},
            )
            saved = "".join(path.read_text() for path in Path(directory).iterdir())
            self.assertNotIn("private exception content", saved)
            audit = load_jsonl(next(Path(directory).glob("*.jsonl")))
            self.assertEqual(verify_audit_records(audit).failed, 1)

    def test_timeout_does_not_prove_service_absent(self):
        session = FakeSession(error=TimeoutError("private network context"))
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_probe(session, directory)
            self.assertEqual(result["reachability"], "unverified")
            self.assertEqual(len(session.calls), 1)
            self.assertEqual(result["adapter_outcome"], "AmbiguousOutcome")
            self.assertNotIn("private", json.dumps(result))

    def test_inventory_covers_documented_services_without_duplicates(self):
        names = load_service_names()
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("mesh-watertight", names)
        self.assertIn("sapiens2", names)
        self.assertIn("geometry-v4-geo2-pass1-cfg-distill-quant", names)
        self.assertIn("mesh-lod", names)
        self.assertIn("auto-rig", names)


if __name__ == "__main__":
    unittest.main()
