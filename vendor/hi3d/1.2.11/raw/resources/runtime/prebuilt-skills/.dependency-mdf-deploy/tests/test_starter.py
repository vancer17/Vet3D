"""Offline behavior tests. Requires the real full MDF3 SDK; no network calls."""
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "assets" / "service"))
sys.path.insert(0, str(PACKAGE / "scripts"))

from scaffold import scaffold
from algorithm import Session
from API import infer
from config_check import check_config, validate_config
from healthcheck import check
from mdf3 import BinaryFile, ServiceBase, ServiceInvokeSession
from service import ServiceWorker, validate_request
from smoke import invoke_checks, require_result


def valid_config():
    return dict(nacos=dict(nacos_server_addresses="nacos.example:8848"),
                task_queue=dict(endpoints=["http://queue.example:7780"]),
                feishu=dict(enabled=False), agent_heartbeat=dict(container_dir="/tmp/mdf-health"))


def request(name="input.txt", content=b"hello", **options):
    return dict(input_file=BinaryFile(field_name="input_file", file_name=name, content=content), options=options)


class StarterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="mdf-deploy-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = patch.dict(os.environ, ALLOW_CPU_DEMO="1", DEVICE="cpu", MODEL_DIR=str(self.root))
        self.env.start()
        self.addCleanup(self.env.stop)

    def worker(self):
        worker = ServiceWorker()
        worker.init(0)
        self.addCleanup(worker.shutdown)
        return worker

    def test_scaffold_and_cli_outside_package(self):
        target = scaffold(self.root / "generated")
        self.assertTrue((target / ".dockerignore").is_file())
        self.assertFalse(any(target.rglob("*.pyc")))
        with self.assertRaises(FileExistsError):
            scaffold(target)
        source, output = self.root / "input.txt", self.root / "output.txt"
        source.write_text("Hello 世界\n", encoding="utf-8")
        result = subprocess.run([sys.executable, str(target / "run.py"), "--input", str(source),
                                 "--output", str(output)], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), "HELLO 世界\n")
        self.assertEqual(json.loads(result.stdout)["algorithm_profile"], "cpu-text-demo")

    def test_demo_requires_explicit_opt_in(self):
        with patch.dict(os.environ, ALLOW_CPU_DEMO="0"), self.assertRaises(RuntimeError):
            Session(self.root, "cpu")

    def test_input_contract(self):
        worker = self.worker()
        for data in ({}, request("../input.txt"), request("a\\input.txt"), request("input.glb"),
                     request(content=b""), request(uppercase="false"), request(unknown=1)):
            with self.subTest(data_type=type(data).__name__), self.assertRaises(ValueError):
                validate_request(data, worker.session, 1024)
        with self.assertRaises(ValueError):
            validate_request(request(content=b"12345"), worker.session, 4)
        file = request()
        file["input_file"].field_name = "wrong"
        with self.assertRaises(ValueError):
            validate_request(file, worker.session, 1024)

    def test_resident_success_failure_cleanup(self):
        worker = self.worker()
        original_session = worker.session
        staged = []
        original_infer = original_session.infer

        def track(source, target, options):
            staged.append(Path(source).parent)
            return original_infer(source, target, options)

        with patch.object(original_session, "infer", side_effect=track):
            first = worker.process(request(uppercase=False), "offline-1")
            second = worker.process(request(), "offline-2")
        self.assertEqual(first["output_file"].content, b"hello")
        self.assertEqual(second["output_file"].content, b"HELLO")
        self.assertEqual(first["metadata"]["session_id"], second["metadata"]["session_id"])
        self.assertIs(worker.session, original_session)

        def fail(source, target, options):
            staged.append(Path(source).parent)
            raise RuntimeError("simulated failure")

        with patch.object(original_session, "infer", side_effect=fail), patch("service.traceback.print_exc"):
            result = worker.process(request(), "offline-failure")
        self.assertIs(result["success"], False)
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertNotIn("output_file", result)
        self.assertTrue(all(not directory.exists() for directory in staged))
        worker.shutdown()
        worker.shutdown()
        self.assertTrue(original_session.closed)

    def test_atomic_output_keeps_old_valid_file(self):
        source, output = self.root / "input.txt", self.root / "output.txt"
        source.write_text("input")
        output.write_text("old valid output")
        session = Session(self.root, "cpu")
        with patch.object(session, "validate_output", side_effect=ValueError("bad output")), self.assertRaises(ValueError):
            infer(session, source, output, {})
        self.assertEqual(output.read_text(), "old valid output")
        self.assertFalse(list(self.root.glob(".mdf-output-*")))

    def test_config_policy_and_no_parser_leak(self):
        validate_config(valid_config())
        for change in (dict(feishu=dict(enabled=True)), dict(tos=dict(bucket="mock")),
                       dict(kafka=dict(bootstrap_servers="mock")), dict(agent_heartbeat=dict(container_dir="/elsewhere")),
                       dict(task_queue=dict(endpoints=["http://user:mock@queue.example"]))):
            with self.assertRaises(ValueError):
                validate_config({**valid_config(), **change})
        path = self.root / "mock.yaml"
        path.write_text("key: [mock-sensitive-content\n")
        with self.assertRaises(ValueError) as error:
            check_config(path)
        self.assertNotIn("mock-sensitive-content", str(error.exception))

    def test_heartbeat(self):
        (self.root / "heartbeat").touch()
        self.assertFalse(check(self.root))
        (self.root / "ready").touch()
        self.assertTrue(check(self.root))
        old = time.time() - 60
        os.utime(self.root / "heartbeat", (old, old))
        self.assertFalse(check(self.root))

    def test_official_sdk_signatures(self):
        parameters = inspect.signature(ServiceBase).parameters
        self.assertTrue({"algo_cls", "worker_pool_wait_ready", "worker_timeout_action", "config_path"} <= parameters.keys())
        self.assertIn("config_path", inspect.signature(ServiceInvokeSession).parameters)
        self.assertIn("trace_id", inspect.signature(ServiceInvokeSession.invoke).parameters)

    def test_smoke_with_injected_client_and_recovery(self):
        worker = self.worker()
        source = self.root / "input.txt"
        source.write_text("mixed case")

        class Client:
            calls = 0

            def invoke(self, name, data, *, trace_id, timeout):
                self.calls += 1
                return worker.process(data, trace_id)

        client = Client()
        with patch("service.traceback.print_exc"):
            out = invoke_checks(client, "offline-test", source, {}, self.root / "checks", 10)
        self.assertEqual(client.calls, 3)
        self.assertEqual(worker.requests_completed, 2)
        records = [json.loads(path.read_text()) for path in sorted(out.glob("call-*.json"))]
        self.assertEqual([record["state"] for record in records],
                         ["TRANSPORT_VALIDATED", "EXPECTED_FAILURE", "TRANSPORT_VALIDATED"])
        self.assertTrue(all(path.read_text() == "MIXED CASE" for path in out.glob("output-*.txt")))
        with self.assertRaises(FileExistsError):
            invoke_checks(client, "offline-test", source, {}, out, 10)
        self.assertEqual(client.calls, 3)

    def test_smoke_preserves_ambiguous_trace_without_retry(self):
        source = self.root / "input.txt"
        source.write_text("input")

        class Client:
            calls = 0

            def invoke(self, *args, **kwargs):
                self.calls += 1
                raise TimeoutError("simulated interruption")

        client = Client()
        with self.assertRaises(RuntimeError):
            invoke_checks(client, "offline-test", source, {}, self.root / "ambiguous", 1)
        self.assertEqual(client.calls, 1)
        record = json.loads((self.root / "ambiguous" / "call-1.json").read_text())
        self.assertEqual(record["state"], "AMBIGUOUS")
        self.assertTrue(record["trace_id"])

    def test_result_validation(self):
        with self.assertRaises(RuntimeError):
            require_result(dict(success=False))
        with self.assertRaises(ValueError):
            require_result(dict(success=True, status="success", output_file=BinaryFile(
                field_name="output_file", file_name="../escape.txt", content=b"x")))

    def test_deploy_command_scope_with_mock_docker(self):
        executable = self.root / "docker"
        executable.write_text(
            "#!" + sys.executable + "\n"
            "import json,os,sys\n"
            "with open(os.environ['DOCKER_TEST_LOG'], 'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')\n"
            "if sys.argv[1:3] == ['container','inspect']: sys.exit(0 if os.environ.get('DOCKER_TEST_EXISTS') else 1)\n")
        executable.chmod(0o755)
        config = self.root / "mock.yaml"
        config.write_text("mock-only: true\n")
        log = self.root / "docker.jsonl"
        env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                   DOCKER_TEST_LOG=str(log), IMAGE_NAME="mock:local", CONTAINER_NAME="mock-test",
                   SERVICE_NAME="mock-test", TCP_PORT="12345", MDF3_CONFIG=str(config),
                   MDF3_ENV="test", MDF3_GROUP="test", MODEL_DIR=str(self.root), DEVICE="cuda:0", GPUS="device=1")
        command = ["bash", str(PACKAGE / "assets" / "service" / "deploy.sh")]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        start = [call for call in calls if call[:2] == ["run", "-d"]]
        self.assertEqual(len(start), 1)
        self.assertIn("device=1", start[0])
        self.assertIn("type=bind,src=" + str(config) + ",dst=/config/mdf.yaml,readonly", start[0])
        self.assertFalse(any(call[0] in {"stop", "rm", "kill", "push"} for call in calls))
        log.unlink()
        result = subprocess.run(command, env=dict(env, DOCKER_TEST_EXISTS="1"), capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(any(json.loads(line)[0] == "run" for line in log.read_text().splitlines()))


if __name__ == "__main__":
    unittest.main()
