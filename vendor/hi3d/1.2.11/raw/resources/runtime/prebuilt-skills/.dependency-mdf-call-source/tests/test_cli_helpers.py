from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import json
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]


class CliHelpersTest(unittest.TestCase):
    def run_script(self, name, *args):
        return subprocess.run(
            [sys.executable, str(SKILL_ROOT / "scripts" / name)] + list(args),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    def test_validate_artifact_parses_json(self) -> None:
        result = self.run_script(
            "validate_artifact.py",
            str(SKILL_ROOT / "assets" / "run_spec.template.json"),
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"status": "validated"', result.stdout)
        self.assertIn('"json_type": "dict"', result.stdout)

    def test_runtime_inspector_redacts_sensitive_labels(self) -> None:
        result = self.run_script(
            "inspect_runtime.py",
            "--module",
            "json",
            "--label",
            "api_token=do-not-log",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("do-not-log", result.stdout)
        self.assertIn("<redacted>", result.stdout)

    def test_audit_cli_reports_outcomes_and_incomplete_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            common = dict(call_id="c", trace_id="t")
            sent = dict(common, event="request_sent", retries=0)
            for status, expected in [("succeeded", 0), ("failed", 1)]:
                path.write_text(
                    json.dumps(sent)
                    + "\n"
                    + json.dumps(dict(common, event="request_finished", status=status))
                    + "\n"
                )
                result = self.run_script(
                    "verify_audit.py", str(path), "--trace-id", "t"
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(json.loads(result.stdout)["ok"], expected == 0)
            path.write_text(json.dumps(sent) + "\n")
            self.assertEqual(
                self.run_script("verify_audit.py", str(path)).returncode, 1
            )
            result = self.run_script("verify_audit.py", str(path), "--allow-incomplete")
            self.assertEqual(result.returncode, 0)
            self.assertFalse(json.loads(result.stdout)["complete"])


if __name__ == "__main__":
    unittest.main()
