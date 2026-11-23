from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mdf_endpoint import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    DEFAULT_ENVIRONMENT,
    check_config,
    inspect_config,
    resolve_config_path,
    validate_queue_url,
)
from online_service_atoms import ContractViolation  # noqa: E402


MINIMAL_CONFIG = """
task_queue:
  endpoints:
    - "http://127.0.0.1:7780"
nacos:
  nacos_server_addresses: "127.0.0.1:8848"
"""


class EndpointTest(unittest.TestCase):
    def write_config(self, directory, name="config.test.yaml", body=MINIMAL_CONFIG):
        path = Path(directory) / name
        path.write_text(body)
        return path

    def test_resolution_precedence_and_empty_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            explicit = self.write_config(directory, "explicit.yaml")
            configured = self.write_config(directory, "from-env.yaml")
            bundled = resolve_config_path(environ={})
            self.assertEqual(bundled, DEFAULT_CONFIG_PATH.resolve())
            self.assertEqual(
                resolve_config_path(environment=DEFAULT_ENVIRONMENT, environ={
                    "MDF3_CONFIG_PATH": str(configured)
                }),
                configured.resolve(),
            )
            self.assertEqual(
                resolve_config_path(
                    explicit, environ={"MDF3_CONFIG_PATH": str(configured)}
                ),
                explicit.resolve(),
            )
            with self.assertRaises(ContractViolation):
                resolve_config_path(environ={"MDF3_CONFIG_PATH": ""})

            nested = Path(directory) / "conf"
            nested.mkdir()
            env_file = self.write_config(nested, "config.prod.yaml")
            self.assertEqual(
                resolve_config_path(
                    environment="prod",
                    environ={"MDF3_CONFIG_PATH": str(nested)},
                ),
                env_file.resolve(),
            )

    def test_secret_urls_rejected_without_echo(self):
        for endpoint in (
            "http://user:private@example.invalid:7780",
            "https://example.invalid:7780?token=private",
            "https://example.invalid:7780#private",
            "ftp://example.invalid:7780",
            "http://example.invalid:99999",
        ):
            with (
                self.subTest(endpoint=endpoint),
                self.assertRaises(ContractViolation) as caught,
            ):
                validate_queue_url(endpoint)
            self.assertNotIn("private", str(caught.exception))

    def test_non_test_environment_never_falls_back_to_test_queue(self):
        with self.assertRaises(ContractViolation):
            resolve_config_path(environment="prod", environ={})
        with tempfile.TemporaryDirectory() as directory:
            explicit = self.write_config(directory, "production.yaml")
            self.assertEqual(
                resolve_config_path(explicit, environment="prod", environ={}),
                explicit.resolve(),
            )

    def test_bundled_config_contains_only_client_connection_settings(self):
        from mdf_endpoint import load_config_mapping

        config = load_config_mapping(DEFAULT_CONFIG_PATH)
        self.assertEqual(set(config), {"task_queue", "nacos"})
        self.assertEqual(set(config["nacos"]), {"nacos_server_addresses"})
        self.assertEqual(set(config["task_queue"]), {
            "endpoints", "connect_timeout_sec", "push_timeout_sec",
            "heartbeat_timeout_sec", "pull_timeout_sec",
            "heartbeat_interval_sec", "heartbeat_ttl_sec",
        })

    def test_inspect_does_not_infer_downstream_or_echo_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_config(
                directory,
                body="""
task_queue:
  endpoints:
    - "http://127.0.0.1:7780"
tos:
  business:
    secret_key: "private-secret"
""",
            )
            result = inspect_config(path)
            self.assertTrue(result["config_ready"])
            self.assertEqual(result["task_queue_endpoint_count"], 1)
            self.assertEqual(result["downstream_routing"], "unverified")
            self.assertEqual(result["business_execution"], "not_run")
            self.assertNotIn("private-secret", json.dumps(result))

    def test_check_config_reports_missing_file_without_contents(self):
        result = check_config(
            "/tmp/missing-mdf-config.yaml", environment=DEFAULT_ENVIRONMENT
        )
        self.assertFalse(result["config_ready"])
        self.assertEqual(result["error_type"], "ContractViolation")
        self.assertNotIn("private", json.dumps(result))

    def test_bundled_test_config_is_readable(self):
        result = check_config()
        encoded = json.dumps(result)
        self.assertTrue(result["config_ready"], encoded)
        self.assertGreaterEqual(result["task_queue_endpoint_count"], 1)
        self.assertNotIn("AKLT", encoded)
        self.assertNotIn("secret_key", encoded)
        self.assertNotIn("password", encoded)


if __name__ == "__main__":
    unittest.main()
