from __future__ import annotations

import http.server
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mdf_endpoint import (  # noqa: E402
    DEFAULT_ENDPOINT,
    DEFAULT_GATEWAY_SERVICE,
    check_gateway,
    gateway_health_url,
    resolve_endpoint,
)
from online_service_atoms import ContractViolation  # noqa: E402


class EndpointTest(unittest.TestCase):
    def test_resolution_precedence_and_empty_setting(self):
        explicit = "https://example.invalid/mdf/generate_model"
        configured = "http://example.invalid:8000/generate_model"
        self.assertEqual(resolve_endpoint(environment={}), DEFAULT_ENDPOINT)
        self.assertEqual(
            resolve_endpoint(environment={"MDF_ENDPOINT": configured}), configured
        )
        self.assertEqual(
            resolve_endpoint(explicit, environment={"MDF_ENDPOINT": configured}),
            explicit,
        )
        with self.assertRaises(ContractViolation):
            resolve_endpoint(environment={"MDF_ENDPOINT": ""})
        self.assertEqual(
            gateway_health_url(explicit), "https://example.invalid/mdf/health"
        )

    def test_secret_urls_rejected_without_echo(self):
        for endpoint in (
            "http://user:private@example.invalid/generate_model",
            "https://example.invalid/generate_model?token=private",
            "https://example.invalid/generate_model#private",
            "ftp://example.invalid/generate_model",
            "http://example.invalid:99999/generate_model",
        ):
            with (
                self.subTest(endpoint=endpoint),
                self.assertRaises(ContractViolation) as caught,
            ):
                resolve_endpoint(endpoint)
            self.assertNotIn("private", str(caught.exception))

    def test_health_is_not_downstream_readiness(self):
        for body, ready in (
            ({"status": "healthy", "service_name": DEFAULT_GATEWAY_SERVICE}, True),
            ({"status": "healthy", "service_name": "another-gateway"}, False),
            ({"status": "unhealthy", "service_name": DEFAULT_GATEWAY_SERVICE}, False),
            ([], False),
        ):

            def fake_get(url, **kwargs):
                return {"http_status": 200, "body": body}

            result = check_gateway(DEFAULT_ENDPOINT, get_json=fake_get)
            self.assertIs(result["gateway_ready"], ready)
            self.assertEqual(result["downstream_routing"], "unverified")
            self.assertEqual(result["business_execution"], "not_run")

    def test_actual_http_get_does_not_redirect_or_post(self):
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(("GET", self.path))
                if self.path == "/redirect/health":
                    self.send_response(302)
                    self.send_header("Location", "/health")
                    self.end_headers()
                else:
                    content = json.dumps(
                        {"status": "healthy", "service_name": DEFAULT_GATEWAY_SERVICE}
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = "http://127.0.0.1:%s" % server.server_port
            self.assertTrue(check_gateway(base + "/generate_model")["gateway_ready"])
            self.assertEqual(
                check_gateway(base + "/redirect/generate_model")["http_status"], 302
            )
            self.assertEqual(
                requests, [("GET", "/health"), ("GET", "/redirect/health")]
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_transport_failure_does_not_leak_headers(self):
        def fail(*args, **kwargs):
            raise OSError("Authorization: private")

        result = check_gateway(DEFAULT_ENDPOINT, get_json=fail)
        self.assertFalse(result["gateway_ready"])
        self.assertEqual(result["error_type"], "OSError")
        self.assertNotIn("private", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
