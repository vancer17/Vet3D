from __future__ import annotations

from dataclasses import dataclass
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mdf_call import (  # noqa: E402
    field_equals,
    main,
    materialize_request,
    redact_summary_urls,
    save_binary_outputs,
)


READY = {
    "python": "3",
    "executable": "x",
    "business_execution": "not_run",
    "network_checked": False,
    "numpy_required": False,
    "ready": True,
}


@dataclass
class FakeBinary:
    field_name: str = ""
    file_name: str = ""
    content: bytes = b""


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
        self.calls.append(
            {
                "service": service,
                "input_data": input_data,
                "trace_id": trace_id,
                "timeout": timeout,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result


class BusinessCliTest(unittest.TestCase):
    def test_invalid_config_rejected_before_session_or_run_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.yaml").write_text("task_queue: {}\n")
            (root / "request.json").write_text("{}")
            with patch("mdf_call.check_runtime", return_value=READY), \
                    patch("mdf_call.MDF3ServiceInvokeCaller") as caller, \
                    redirect_stderr(io.StringIO()):
                code = main([
                    "--transport", "sdk", "--service", "auto-rig", "--input", str(root / "request.json"),
                    "--run-dir", str(root / "run"), "--config", str(root / "config.yaml"),
                ])
            self.assertEqual(code, 2)
            caller.assert_not_called()
            self.assertFalse((root / "run").exists())

    def test_main_submits_once_and_writes_returned_artifact(self):
        session = FakeSession(
            result={
                "success": True,
                "rigged_mesh": FakeBinary(field_name="rigged_mesh", file_name="rigged.glb", content=b"model"),
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "body.glb").write_bytes(b"body")
            (root / "request.json").write_text(
                (Path(__file__).resolve().parents[1] / "assets/request.auto-rig.json").read_text()
            )
            with (
                patch("mdf_call.check_runtime", return_value=READY),
                redirect_stdout(io.StringIO()),
            ):
                code = main(
                    [
                        "--transport", "sdk", "--service",
                        "auto-rig",
                        "--input",
                        str(root / "request.json"),
                        "--run-dir",
                        str(root / "run"),
                    ],
                    session_factory=lambda **kwargs: session,
                    binary_factory=FakeBinary,
                )
            self.assertEqual(code, 0)
            self.assertEqual(len(session.calls), 1)
            self.assertEqual(session.calls[0]["service"], "auto-rig")
            self.assertEqual(session.calls[0]["input_data"]["mesh"], FakeBinary("mesh", "body.glb", b"body"))
            self.assertEqual(session.calls[0]["input_data"]["options"], {"use_skeleton": False, "use_transfer": True})
            record = json.loads((root / "run/invocation.json").read_text())
            self.assertEqual(record["status"], "SUCCEEDED")
            self.assertEqual(record["endpoint_alias"], "mdf3-service-invoke")
            self.assertEqual(record["artifact_validation"], "not_run")
            self.assertEqual(record["files"][0]["field_path"], ["rigged_mesh"])
            self.assertEqual(
                (root / "run/artifacts" / record["files"][0]["file"]).read_bytes(),
                b"model",
            )

    def test_nested_files_resolve_against_request_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "input.png").write_bytes(b"local-input")
            result = materialize_request(
                {
                    "references": [{"$file": "input.png"}, None],
                    "seed": 0,
                },
                base_dir=base,
                binary_factory=FakeBinary,
            )
            self.assertEqual(
                result["references"][0],
                FakeBinary("references", "input.png", b"local-input"),
            )
            self.assertIsNone(result["references"][1])
            self.assertEqual(result["seed"], 0)
            with self.assertRaises(ValueError):
                materialize_request(
                    {"$file": "input.png", "typo": 1},
                    base_dir=base,
                    binary_factory=FakeBinary,
                )

    def test_output_paths_cannot_escape_and_sensitive_bytes_are_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = {
                "models": [
                    FakeBinary(file_name="../../same.glb", content=b"one"),
                    FakeBinary(file_name="..\\same.glb", content=b"two"),
                ],
                "token": b"private",
            }
            files = save_binary_outputs(
                result, directory=root / "artifacts", binary_type=FakeBinary
            )
            self.assertEqual(len(files), 2)
            self.assertNotEqual(files[0]["file"], files[1]["file"])
            self.assertEqual([f["size"] for f in files], [3, 3])
            for row in files:
                self.assertEqual(
                    (root / "artifacts" / row["file"]).resolve().parent,
                    (root / "artifacts").resolve(),
                )
            self.assertEqual(len(list(root.iterdir())), 1)

    def test_success_predicate_and_url_redaction(self):
        self.assertTrue(field_equals({"result": {"ok": True}}, "result.ok", True))
        self.assertFalse(field_equals({"result": {"ok": 1}}, "result.ok", True))
        self.assertFalse(field_equals({}, "success", None))
        self.assertEqual(
            redact_summary_urls({"url": "https://example.invalid/file?token=private"}),
            {"url": "<url-containing text omitted>"},
        )


if __name__ == "__main__":
    unittest.main()
