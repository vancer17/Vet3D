"""Behavioral checks for the shared timed local-build handoff."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_stage import run_build


class BuildStageTests(unittest.TestCase):
    def fixture(self, root):
        source = root / 'input.glb'
        source.write_bytes(b'SYNTHETIC_INPUT_NOT_PARSED_BY_ADAPTER')
        config = root / 'settings.json'
        config.write_text('{"setting": 4}')
        return source, config

    def test_loader_receives_explicit_paths_config_and_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source, config = self.fixture(root)
            def build(inp, settings, out, geometry_only):
                self.assertEqual(inp, source)
                self.assertEqual(settings, {'setting': 4})
                self.assertTrue(geometry_only)
                (out / 'result.txt').write_text('done')
                return 17
            result = run_build(source, config, root / 'output', package_root=root / 'package', loader=lambda: build)
            self.assertEqual(result, 17)
            record = json.loads((root / 'output/stage-time.json').read_text())
            self.assertEqual(record['status'], 'completed')
            self.assertGreaterEqual(record['elapsed_seconds'], 0)

    def test_loader_failure_propagates_and_records_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source, config = self.fixture(root)
            def loader():
                raise ValueError('synthetic-loader-failure')
            with self.assertRaises(ValueError):
                run_build(source, config, root / 'output', package_root=root / 'package', loader=loader)
            self.assertEqual(json.loads((root / 'output/stage-time.json').read_text())['status'], 'failed')

    def test_package_output_rejected_before_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source, config = self.fixture(root)
            with self.assertRaises(ValueError):
                run_build(source, config, root / 'package/output', package_root=root / 'package', loader=lambda: self.fail('loader ran'))


if __name__ == '__main__':
    unittest.main()
