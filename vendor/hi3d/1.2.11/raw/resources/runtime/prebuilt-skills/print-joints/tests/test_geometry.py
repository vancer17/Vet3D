"""Observable geometry and file invariants using generated, non-user fixtures."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import manifold3d as mf
import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from joints import (BallSpec, attach_ball_joint, ball_tools, joint_frame,
                    pair_metrics, rotation_about)
from coupon import coupon_geometry
from mesh_io import read_stl_solid, to_trimesh, write_3mf


def sample_spec():
    return BallSpec(4.0, 0.5, 1.6, 2.0, 12.0, 3.35, 0.1, 2.4, 2.4, 64)


class GeometryTests(unittest.TestCase):
    def test_clearances_and_support(self):
        measured = []
        for gap in [0.35, 0.5, 0.65]:
            spec = replace(sample_spec(), gap_mm=gap)
            parts = coupon_geometry(spec, 0.2, 1.3)
            pair = pair_metrics(parts['socket'], parts['ball'], 2)
            self.assertEqual(pair['overlap_mm3'], 0)
            self.assertAlmostEqual(pair['gap_mm'], gap, delta=0.012)
            measured.append(pair['gap_mm'])
            support = pair_metrics(parts['ball'], parts['support'], 1)
            self.assertAlmostEqual(support['gap_mm'], 0.2, places=5)
            self.assertEqual(support['overlap_mm3'], 0)
            self.assertAlmostEqual(parts['support'].bounding_box()[2], 0, places=6)
        self.assertEqual(measured, sorted(measured))

    def test_local_attachment_at_a_and_t_axes(self):
        parent = mf.Manifold.cube([14, 14, 12]).translate([-7, -7, -12])
        child = mf.Manifold.cube([8, 8, 20]).translate([-4, -4, 0])
        original_volume = parent.volume()
        for axis in [[0.5, 0, -0.866], [1, 0, 0]]:
            frame = joint_frame([31, -17, 93], axis, [0, 1, 0])
            a, b = attach_ball_joint(parent.transform(frame), child.transform(frame),
                                    sample_spec(), [31, -17, 93], axis, [0, 1, 0])
            self.assertEqual(len(a.decompose()), 1)
            self.assertEqual(len(b.decompose()), 1)
            self.assertEqual((a ^ b).volume(), 0)
            self.assertGreater(pair_metrics(a, b, 1)['gap_mm'], 0.1)
        self.assertEqual(parent.volume(), original_volume)

    def test_rotation_keeps_anchor_and_detects_collision(self):
        tools = ball_tools(sample_spec())
        centered = rotation_about([15, -8, 30], [0, 1, 0], 80)
        np.testing.assert_allclose(centered[:, :3] @ [15, -8, 30] + centered[:, 3],
                                   [15, -8, 30], atol=1e-10)
        rotated = tools['ball_stem'].transform(rotation_about([0, 0, 0], [1, 0, 0], 70))
        self.assertGreater(pair_metrics(tools['socket'], rotated, 1)['overlap_mm3'], 0.1)
        self.assertTrue(pair_metrics(tools['socket'], tools['socket'].translate([100, 0, 0]), 1)
                        ['gap_is_lower_bound'])

    def test_failures_are_not_silent_repairs(self):
        for kwargs in [{'gap_mm': 0}, {'radius_mm': float('nan')}, {'mouth_radius_mm': 4},
                       {'stem_radius_mm': 3.3}, {'rear_port_radius_mm': 3.8},
                       {'rear_flat_mm': None}, {'segments': 31}]:
            with self.assertRaises(ValueError):
                replace(sample_spec(), **kwargs).validate()
        with self.assertRaises(ValueError):
            joint_frame([0, 0, 0], [1, 0, 0], [1, 0, 0])
        with self.assertRaises(ValueError):
            coupon_geometry(sample_spec(), 0.2, 3)
        with self.assertRaises(ValueError):
            far = mf.Manifold.cube([2, 2, 2]).translate([50, 50, 50])
            attach_ball_joint(far, far, sample_spec(), [0, 0, 0], [0, 0, 1], [0, 1, 0])

    def test_stl_and_3mf_actual_roundtrip(self):
        parts = coupon_geometry(sample_spec(), 0.2, 1.3)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, shape in parts.items():
                path = root / f'{name}.stl'
                to_trimesh(shape).export(path)
                read = read_stl_solid(path)
                np.testing.assert_allclose(read.bounding_box(), shape.bounding_box(), atol=1e-5)
            # An open surface must fail actual file validation.
            damaged = to_trimesh(parts['socket'])
            damaged.update_faces(np.arange(len(damaged.faces) - 1))
            damaged.export(root / 'broken.stl')
            with self.assertRaises(ValueError):
                read_stl_solid(root / 'broken.stl')
            path = root / 'pair.3mf'
            write_3mf(path, parts, 'Ball & socket <test>')
            with self.assertRaises(FileExistsError):
                write_3mf(path, parts, 'overwrite')
            with zipfile.ZipFile(path) as archive:
                self.assertIsNone(archive.testzip())
                model = ET.fromstring(archive.read('3D/3dmodel.model'))
            ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
            self.assertEqual(model.attrib['unit'], 'millimeter')
            self.assertEqual(len(model.findall('m:resources/m:object', ns)), 1)
            vertices = np.array([[float(v.attrib[k]) for k in ['x', 'y', 'z']]
                                 for v in model.findall('.//m:vertex', ns)])
            faces = np.array([[int(f.attrib[k]) for k in ['v1', 'v2', 'v3']]
                             for f in model.findall('.//m:triangle', ns)], np.uint32)
            read = mf.Manifold(mf.Mesh(vertices.astype(np.float32), faces))
            self.assertEqual(read.status(), mf.Error.NoError)
            self.assertEqual(len(read.decompose()), 3)
            self.assertEqual(len(faces), sum(s.num_tri() for s in parts.values()))
            expected = np.concatenate([to_trimesh(s).vertices for s in parts.values()])
            np.testing.assert_allclose(vertices, expected, atol=1e-7)

    def test_cli_success_failure_and_timing(self):
        from dataclasses import asdict
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {'joint': asdict(sample_spec()), 'gaps_mm': [0.35, 0.5, 0.65],
                      'support_gap_mm': 0.2, 'support_radius_mm': 1.3}
            spec = root / 'spec.json'
            spec.write_text(json.dumps(config))
            cmd = [sys.executable, str(SCRIPTS / 'coupon.py'), '--spec', str(spec),
                   '--out', str(root / 'out'), '--task-id', 'test-figure']
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root / 'out/coupon.json').read_text())
            self.assertEqual(report['solids'], 9)
            self.assertEqual(report['physical_release'], 'not_tested')
            records = [json.loads(line) for line in (root / 'out/timing.jsonl').read_text().splitlines()]
            self.assertEqual([r['status'] for r in records], ['running', 'passed'])
            self.assertGreater(records[-1]['elapsed_seconds'], 0)
            self.assertTrue(records[-1]['ended_at'].endswith('+00:00'))
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            config['gaps_mm'] = [-1]
            spec.write_text(json.dumps(config))
            cmd[cmd.index('--out') + 1] = str(root / 'failed')
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            failed = json.loads((root / 'failed/timing.jsonl').read_text().splitlines()[-1])
            self.assertEqual(failed['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
