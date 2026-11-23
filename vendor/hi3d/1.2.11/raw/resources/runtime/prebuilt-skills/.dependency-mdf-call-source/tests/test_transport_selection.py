from contextlib import redirect_stdout, redirect_stderr
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from mdf_call import main
from mdf_probe import probe_service
from mdf_runtime import load_codec


class TransportSelectionTest(unittest.TestCase):
    def test_http_default_ignores_sdk_config_and_saves_binary(self):
        codec = load_codec()
        result = {"success": True, "rigged_mesh": codec.BinaryFile(
            field_name="rigged_mesh", file_name="rigged.glb", content=b"glTF-result")}
        response = Mock(status_code=200)
        response.json.return_value = {"success": True, "pickle_payload":
            base64.b64encode(codec.dumps(result)).decode()}
        post = Mock(return_value=response)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "body.glb").write_bytes(b"body-input")
            request = root / "request.json"
            request.write_text((Path(__file__).resolve().parents[1] / "assets/request.auto-rig.json").read_text())
            with patch.dict("os.environ", {"MDF3_CONFIG_PATH": "/not/available.yaml"}), \
                 patch("mdf_call.MDF3ServiceInvokeCaller") as sdk, \
                 patch("mdf_call.inspect_config") as config, redirect_stdout(io.StringIO()):
                code = main(["--service", "auto-rig", "--input", str(request),
                    "--run-dir", str(root / "call"), "--endpoint", "http://localhost/generate_model"], post=post)
            self.assertEqual(code, 0)
            sdk.assert_not_called(); config.assert_not_called(); post.assert_called_once()
            sent = post.call_args.kwargs["json"]
            self.assertEqual(sent["input_data"]["target_service"], "auto-rig")
            payload = codec.loads(base64.b64decode(sent["input_data"]["pickle_payload"]))
            self.assertEqual(payload["mesh"].content, b"body-input")
            self.assertEqual(payload["mesh"].field_name, "mesh")
            self.assertEqual(payload["options"], {"use_skeleton": False, "use_transfer": True})
            record = json.loads((root / "call/invocation.json").read_text())
            self.assertEqual(record["transport"], "http")
            self.assertEqual(record["files"][0]["field_path"], ["rigged_mesh"])
            self.assertEqual((root / "call/artifacts" / record["files"][0]["file"]).read_bytes(), b"glTF-result")

    def test_http_timeout_is_one_ambiguous_attempt_without_sdk_fallback(self):
        post = Mock(side_effect=TimeoutError("private detail"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); request = root / "request.json"; request.write_text("{}")
            with patch("mdf_call.MDF3ServiceInvokeCaller") as sdk, redirect_stdout(io.StringIO()):
                code = main(["--service", "auto-rig", "--input", str(request),
                    "--run-dir", str(root / "call")], post=post)
            self.assertEqual(code, 1); post.assert_called_once(); sdk.assert_not_called()
            record = json.loads((root / "call/invocation.json").read_text())
            self.assertEqual(record["status"], "AmbiguousOutcome")
            self.assertEqual(record["attempts"], 1)
            audit = (root / "call/audit.jsonl").read_text()
            self.assertIn(record["trace_id"], audit); self.assertNotIn("private detail", audit)

    def test_http_probe_records_downstream_error_without_sdk(self):
        codec=load_codec(); response=Mock(status_code=200)
        response.json.return_value={"success":True,"pickle_payload":base64.b64encode(
            codec.dumps({"success":False,"error_message":"private downstream detail"})).decode()}
        post=Mock(return_value=response)
        with tempfile.TemporaryDirectory() as tmp, patch("mdf_probe.MDF3ServiceInvokeCaller") as sdk:
            record=probe_service("auto-rig",run_dir=Path(tmp),run_id="test",post=post)
            self.assertEqual(record["reachability"],"downstream_response_received")
            self.assertEqual(record["adapter_outcome"],"BusinessFailure")
            self.assertEqual(record["transport"],"http")
            sdk.assert_not_called();post.assert_called_once()
            self.assertNotIn("private downstream detail",json.dumps(record))

    def test_conflicting_transport_options_fail_before_runtime_or_submission(self):
        for extra in (["--config", "/unused.yaml"], ["--transport", "sdk", "--endpoint", "http://localhost/x"]):
            with self.subTest(extra=extra), patch("mdf_call.check_runtime") as runtime, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main(["--service","auto-rig","--input","unused.json","--run-dir","unused-call"]+extra)
                runtime.assert_not_called()


if __name__ == "__main__":
    unittest.main()
