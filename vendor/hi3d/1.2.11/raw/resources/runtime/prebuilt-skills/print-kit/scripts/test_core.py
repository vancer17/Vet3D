"""Contract regression tests. All generated files live in temporary directories.

Run python3 scripts/test_core.py from an independently copied skill. Requires only
requirements.txt, no repository fixture, Blender, network or physical printer.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import trimesh

from kitlib import Kit, box, cyl, export_solid, write_json, is_rigid
from verify_kit import verify
from fit_coupon import build, gauge_shapes
from crop_coupon import crop
from timing import stage, skipped, summarize


def fixture(gap):
    """Return a small shoulder-pin fixture with an independently removable plate."""
    kit = Kit('fixture', 'Shoulder pin fixture', {'gap_mm': gap}, bed=(100, 80, 100),
              profile={'material': 'PLA', 'nozzle_mm': 0.4, 'layer_mm': 0.2})
    kit.add('male', box((10, 10, 3)) + cyl(2, 8.2, (5, 5, 2.8)))
    kit.add('female', box((14, 14, 6), (-2, -2, 3)) - cyl(2 + gap, 8, (5, 5, 2)))
    kit.path(['female'], [0, 0, 1], 30, step=2)
    kit.joint('pin', 'male', 'female', 'shoulder pin', gap,
              'adhesive after trial fit; physical retention untested')
    kit.probe('bore', 'female', [5, 5, 6], [1, 0, 0], 4 + 2 * gap, span=10)
    kit.probe('pin', 'male', [5, 5, 6], [1, 0, 0], 4, span=10)
    return kit


class GeometryContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_export_units_and_clearance_endpoints(self):
        measurements = []
        for gap in (0.2, 0.4):
            with self.subTest(gap=gap):
                plan = fixture(gap).export(self.root / str(gap))
                report = verify(plan)
                self.assertEqual(report['status'], 'pass', report['errors'])
                measurements.append(report['feature_measurements'][0]['measured_mm'])
                view = trimesh.load_scene(plan.parent / 'assembly.glb')
                data = json.loads(plan.read_text())
                np.testing.assert_allclose(view.extents * 1000, data['assembled_size_mm'], atol=0.002)
        self.assertAlmostEqual(measurements[1] - measurements[0], 0.4, places=3)

    def test_interference_and_blocked_path_fail(self):
        for name, kit in [('undersize', fixture(-0.1)), ('blocked', fixture(0.3))]:
            with self.subTest(name=name):
                if name == 'blocked':
                    kit.data['disassembly'][0]['direction'] = [1, 0, 0]
                report = verify(kit.export(self.root / name))
                self.assertEqual(report['status'], 'fail')

    def test_stale_hash_and_malformed_plans_fail(self):
        path = fixture(0.3).export(self.root / 'plan')
        original = json.loads(path.read_text())
        changes = [
            lambda d: d['parts'][0].update(sha256='stale'),
            lambda d: d['plates'].pop(),
            lambda d: d['instances'][0]['matrix'][3].__setitem__(3, 2),
            lambda d: d['plates'][0]['matrix'][0].__setitem__(0, 0.5),
            lambda d: d['disassembly'][0].update(max_step_mm=0),
            lambda d: d['disassembly'][0].update(instances=[]),
            lambda d: d.update(motions=[dict(id='invalid', type='rotation', instances=['female'],
                                           axis='z', pivot=[5, 5, 0], start_deg=0,
                                           end_deg=90, samples=0)]),
        ]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                data = copy.deepcopy(original)
                change(data)
                write_json(path, data)
                self.assertEqual(verify(path)['status'], 'fail')
        path.write_text('{')
        self.assertEqual(verify(path)['status'], 'fail')

    def test_production_crop_and_rejected_roi(self):
        plan = fixture(0.3).export(self.root / 'plan')
        info = crop(plan, 'female', [-1, -1, 3, 11, 11, 9], self.root / 'coupon.stl')
        np.testing.assert_allclose(info['size_mm'], [12, 12, 6], atol=0.001)
        cropped = trimesh.load_mesh(self.root / 'coupon.stl')
        self.assertAlmostEqual(cropped.bounds[0, 2], 0)
        for bounds in ([0, 0, 0, 0, 0, 0], [50, 50, 50, 60, 60, 60]):
            with self.assertRaises(ValueError):
                crop(plan, 'female', bounds, self.root / 'bad.stl')

    def test_gauges_and_export_boundaries(self):
        report = build(self.root / 'gauges')
        self.assertEqual(len(report['items']), 24)
        self.assertTrue(all(trimesh.load_mesh(self.root / 'gauges' / r['file']).is_watertight
                            for r in report['items']))
        with self.assertRaises(ValueError):
            gauge_shapes(-0.1, 1)
        with self.assertRaises(ValueError):
            export_solid(box((3, 3, 3)) + box((3, 3, 3), (10, 0, 0)), self.root / 'bad.stl')
        with self.assertRaises(ValueError):
            Kit('missing-bed', 'Missing bed')
        kit = fixture(0.3)
        kit.data['bed_mm'] = [20, 20, 30]
        with self.assertRaises(ValueError):
            kit.export(self.root / 'overflow')
        self.assertFalse(is_rigid(np.diag([1, 1, 1, 2])))


class TimingContracts(unittest.TestCase):
    def test_failure_retry_skip_and_incomplete_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / 'timing.jsonl'
            with stage(log, 'task', 'whole-task', scope='task') as parent:
                with self.assertRaises(ValueError):
                    with stage(log, 'task', 'model', parent_id=parent):
                        raise ValueError('not persisted')
                with stage(log, 'task', 'model', attempt=2, parent_id=parent):
                    pass
                skipped(log, 'task', 'physical-fit', 'No physical feedback', parent_id=parent)
            records = [json.loads(line) for line in log.read_text().splitlines()]
            report = summarize(records, 'task')
            self.assertEqual([r['status'] for r in report['attempts']],
                             ['completed', 'failed', 'completed', 'skipped'])
            self.assertGreaterEqual(report['wall_elapsed_seconds'], 0)
            self.assertNotIn('not persisted', log.read_text())
            self.assertIsNone(summarize(records[:-1], 'task')['wall_elapsed_seconds'])
            self.assertTrue(all(r.get('elapsed_seconds', 0) is None or r.get('elapsed_seconds', 0) >= 0
                                for r in records))


if __name__ == '__main__':
    unittest.main()
