import json, sys, tempfile, unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
REPO = SKILL.parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(REPO / 'tools' / 'run-tools' / 'scripts'))

import brep_build
import brep_spec

BOX = {
    'schema': 'brep-build.v1',
    'units': 'mm',
    'tessellation_mm': 0.2,
    'solids': [{'id': 'block', 'kind': 'box', 'length_mm': 10, 'width_mm': 8, 'height_mm': 4}],
    'ops': [],
    'export': ['block'],
}


def _fillet_spec():
    spec = json.loads(json.dumps(BOX))
    spec['ops'] = [{'op': 'fillet', 'solid': 'block', 'radius_mm': 0.4, 'edges': '*'}]
    return spec


class BrepSpec(unittest.TestCase):
    def test_box_is_low_band(self):
        spec = brep_spec.validate_spec(BOX)
        budget = brep_spec.estimate_budget(spec)
        self.assertEqual(budget['band'], 'low')
        self.assertFalse(budget['needs_confirm'])

    def test_rejects_mesh_reverse_fields(self):
        with self.assertRaisesRegex(ValueError, 'reverse-fit'):
            brep_spec.validate_spec(dict(BOX, glb='model.glb'))

    def test_parses_coarse_and_fine_threads(self):
        self.assertEqual(brep_spec.parse_designation('M3'), (3.0, 0.5))
        self.assertEqual(brep_spec.parse_designation('M12x1.5'), (12.0, 1.5))

    def test_fillet_needs_confirm(self):
        spec = brep_spec.validate_spec(_fillet_spec())
        self.assertTrue(brep_spec.estimate_budget(spec)['needs_confirm'])

    def test_boolean_unknown_id_fails(self):
        raw = dict(BOX, ops=[{'op': 'cut', 'a': 'block', 'b': 'missing', 'out': 'cut'}])
        with self.assertRaisesRegex(ValueError, 'operands'):
            brep_spec.validate_spec(raw)

    def test_check_cli_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            spec_path = Path(td) / 'spec.json'
            spec_path.write_text(json.dumps(BOX), encoding='utf-8')
            self.assertEqual(brep_build.main(['--check', '--spec', str(spec_path)]), 0)
            self.assertEqual(list(Path(td).iterdir()), [spec_path])

    def test_mid_band_waits_without_confirm(self):
        with tempfile.TemporaryDirectory() as td:
            spec_path = Path(td) / 'spec.json'
            spec_path.write_text(json.dumps(_fillet_spec()), encoding='utf-8')
            out = Path(td) / 'out'
            result = brep_build.build_output(spec_path, out, confirm_budget=False)
            self.assertEqual(result['status'], 'waiting_choice')
            self.assertEqual(result['reason'], 'budget_confirm')
            self.assertTrue((out / 'budget.json').is_file())
            self.assertTrue((out / 'waiting.json').is_file())
            self.assertFalse((out / 'manifest.json').exists())
            self.assertFalse((out / 'parts').exists())

    def test_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as td:
            spec_path = Path(td) / 'spec.json'
            spec_path.write_text(json.dumps(BOX), encoding='utf-8')
            out = Path(td) / 'out'
            out.mkdir()
            with self.assertRaisesRegex(ValueError, 'must not exist'):
                brep_build.build_output(spec_path, out, confirm_budget=True)

    def test_timeout_writes_waiting_not_step(self):
        with tempfile.TemporaryDirectory() as td:
            raw = dict(BOX, budget={'max_wall_s': 0.3, 'heartbeat_s': 0.1})
            spec_path = Path(td) / 'spec.json'
            spec_path.write_text(json.dumps(raw), encoding='utf-8')
            out = Path(td) / 'out'
            original = brep_build.run_kernel

            def hang(spec_path, output, budget, python=sys.executable):
                brep_build.run_budgeted(
                    [sys.executable, '-c', 'import time; time.sleep(8)'],
                    output / 'kernel.log',
                    max_wall_seconds=budget['max_wall_s'],
                    heartbeat_path=output / 'progress.json',
                    heartbeat_seconds=budget['heartbeat_s'],
                    terminate_timeout=1,
                )

            brep_build.run_kernel = hang
            try:
                result = brep_build.build_output(spec_path, out, confirm_budget=True)
            finally:
                brep_build.run_kernel = original
            self.assertEqual(result['status'], 'waiting_choice')
            self.assertEqual(result['reason'], 'timeout')
            self.assertTrue((out / 'waiting.json').is_file())
            self.assertFalse((out / 'manifest.json').exists())


class BrepKernel(unittest.TestCase):
    def test_box_export_when_cadquery_present(self):
        try:
            import cadquery  # noqa: F401
        except ImportError:
            self.skipTest('cadquery is not installed')
        import brep_kernel
        with tempfile.TemporaryDirectory() as td:
            spec_path = Path(td) / 'spec.json'
            spec_path.write_text(json.dumps(BOX), encoding='utf-8')
            out = Path(td) / 'out'
            out.mkdir()
            manifest = brep_kernel.build_spec(brep_spec.load_spec(spec_path), out)
            self.assertEqual(len(manifest['parts']), 1)
            self.assertGreater((out / 'parts' / 'block.step').stat().st_size, 80)
            self.assertGreater((out / 'parts' / 'block.stl').stat().st_size, 80)
            self.assertGreater(manifest['parts'][0]['volume_mm3'], 0)


if __name__ == '__main__':
    unittest.main()
