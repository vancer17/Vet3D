"""Real MDF3 session and loopback TCP, with TaskQueue mocked; no online jobs."""
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mdf3_service_invoke import MDF3ServiceInvokeCaller, default_session_factory
from mdf_call import main as call_main
from mdf_probe import probe_service
from online_service_atoms import AmbiguousOutcome, AuditWriter, load_jsonl, verify_audit_records


def has_full_sdk():
    try:
        return importlib.util.find_spec("mdf3.service_invoke_tool") is not None
    except ModuleNotFoundError:
        return False


@unittest.skipUnless(has_full_sdk(), "Requires the full MDF3 SDK")
class SDKIntegrationTest(unittest.TestCase):
    def setUp(self):
        from mdf3 import service_invoke_tool as sdk

        self.sdk = sdk
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = self.root / "config.yaml"
        # No Nacos, Kafka, TOS, Feishu or authentication settings are needed.
        self.config.write_text("task_queue:\n  endpoints: ['http://127.0.0.1:9']\n")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(sdk, "get_local_ip", return_value="127.0.0.1"))
        self.http = self.stack.enter_context(patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("Offline integration must not issue HTTP requests"),
        ))
        server_class = sdk.ControllerTcpServer

        def loopback_server(**kwargs):
            kwargs["host"] = "127.0.0.1"
            return server_class(**kwargs)

        self.stack.enter_context(patch.object(sdk, "ControllerTcpServer", side_effect=loopback_server))

    def install_worker(self, result):
        from mdf3 import TcpClient, dumps, loads

        self.received = []

        def push(**kwargs):
            with TcpClient(kwargs["controller_ip"], kwargs["controller_port"],
                           timeout=2, connect_retries=0) as client:
                fetched = loads(client.request(dumps({
                    "type": "fetch", "task_hash": kwargs["task_hash"],
                })))
                self.assertTrue(fetched["ok"])
                self.received.append(fetched)
                response = result(fetched["input_data"]) if callable(result) else result
                ack = loads(client.request(dumps({
                    "type": "result", "task_hash": kwargs["task_hash"], "result": response,
                })))
                self.assertTrue(ack["ok"])
            return True

        return self.stack.enter_context(patch.object(self.sdk.TaskQueueClient, "push_task", side_effect=push))

    def test_cli_binary_roundtrip_using_only_queue_config(self):
        from mdf3 import BinaryFile

        def respond(request):
            self.assertIsInstance(request["mesh"], BinaryFile)
            self.assertEqual(request["mesh"].field_name, "mesh")
            self.assertEqual(request["options"], {"use_skeleton": False, "use_transfer": True})
            return {"success": True, "rigged_mesh": BinaryFile(
                field_name="rigged_mesh", file_name="rigged.glb", content=request["mesh"].content,
            )}

        push = self.install_worker(respond)
        (self.root / "body.glb").write_bytes(b"sdk-binary-roundtrip")
        (self.root / "request.json").write_text(
            (Path(__file__).resolve().parents[1] / "assets/request.auto-rig.json").read_text()
        )
        with redirect_stdout(io.StringIO()):
            code = call_main([
                "--transport", "sdk", "--service", "auto-rig", "--input", str(self.root / "request.json"),
                "--run-dir", str(self.root / "run"), "--config", str(self.config), "--timeout", "2",
            ])
        self.assertEqual(code, 0)
        push.assert_called_once()
        self.http.assert_not_called()
        record = json.loads((self.root / "run/invocation.json").read_text())
        self.assertEqual(self.received[0]["trace_id"], record["trace_id"])
        self.assertEqual(self.received[0]["service_name"], "auto-rig")
        self.assertEqual(record["files"][0]["field_path"], ["rigged_mesh"])
        self.assertEqual((self.root / "run/artifacts" / record["files"][0]["file"]).read_bytes(),
                         b"sdk-binary-roundtrip")
        self.assertTrue(verify_audit_records(load_jsonl(self.root / "run/audit.jsonl")).ok)

    def test_probe_business_failure_proves_tcp_roundtrip(self):
        push = self.install_worker({"success": False, "error_info": "missing test input"})
        result = probe_service("auto-rig", transport="sdk", config_path=str(self.config),
                               run_dir=self.root, run_id="offline-sdk", timeout_sec=2)
        self.assertEqual(result["reachability"], "downstream_response_received")
        self.assertEqual(result["adapter_outcome"], "BusinessFailure")
        push.assert_called_once()
        self.http.assert_not_called()

    def test_real_sdk_timeout_keeps_one_submission_and_ambiguous_audit(self):
        push = self.stack.enter_context(patch.object(self.sdk.TaskQueueClient, "push_task", return_value=True))
        caller = MDF3ServiceInvokeCaller(config_path=str(self.config),
            audit=AuditWriter(self.root / "audit.jsonl"), success_predicate=lambda result: True)
        with self.assertRaises(AmbiguousOutcome):
            caller.call_once(service="auto-rig", input_data={}, trace_id="offline-timeout",
                             timeout_sec=0.05, run_id="offline-sdk", case_id="timeout")
        push.assert_called_once()
        self.assertEqual(verify_audit_records(load_jsonl(self.root / "audit.jsonl")).ambiguous, 1)
        self.http.assert_not_called()

    def test_partial_sdk_startup_is_stopped(self):
        with patch.object(self.sdk, "ServiceInvokeSession", autospec=True) as factory:
            factory.return_value.start.side_effect = OSError("startup failed")
            with self.assertRaises(OSError):
                with default_session_factory(config_path=self.config, environment="test"):
                    self.fail("Startup must fail before yielding")
            factory.return_value.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
