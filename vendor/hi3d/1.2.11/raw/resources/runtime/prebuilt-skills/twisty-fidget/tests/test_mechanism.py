import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import trimesh

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
from motion import offsets, screw_pose, adjacent_overlap
from geometry import adapt_profile, helical_parts, measure_states, section_loops, require_solid
from timing import stage


def synthetic_profile(count=8):
    radii = [2., 4., 6., 8., 10., 40.]
    bends = [0., 0., 7., 7., 0., 0.]
    polar = [(r, -180/count+b) for r, b in zip(radii, bends)]
    polar += list(reversed([(r, 180/count+b) for r, b in zip(radii, bends)]))
    return [[r*math.cos(math.radians(a)), r*math.sin(math.radians(a))] for r, a in polar]


def make_inputs(root):
    target = trimesh.creation.cylinder(radius=16, height=30, sections=48)
    target.apply_translation([0, 0, 15])
    target.export(root/'target.ply')
    (root/'profile.json').write_text(json.dumps({'source_count': 8, 'points_xy_mm': synthetic_profile()}))
    job = {'mesh': 'target.ply', 'profile': 'profile.json', 'scale_to_mm': 1,
           'count': 8, 'k_deg_per_mm': 3., 'step_mm': .5, 'radial_scale': 1,
           'inset_mm': .15, 'profile_sample_mm': .5}
    (root/'job.json').write_text(json.dumps(job))
    return job


class MotionTests(unittest.TestCase):
    def test_even_and_odd_ring_closure(self):
        for n in (7, 8, 24):
            for mode in ('staircase', 'wave'):
                d = offsets(n, 40., mode)
                self.assertAlmostEqual(max(d), 40.)
                self.assertEqual(d[0], 0.)
                rows = adjacent_overlap([[0., 70.]]*n, d)
                self.assertEqual(rows[-1]['parts'], [n, 1])
                self.assertGreater(min(r['overlap_mm'] for r in rows), 0)

    def test_large_rotation_and_disengagement(self):
        self.assertEqual(screw_pose(180., 1., -1.25), (180., -225.))
        rows = adjacent_overlap([[0., 10.]]*4, [0., 12., 24., 12.])
        self.assertTrue(all(r['overlap_mm'] == 0 and r['interval_mm'] is None for r in rows))
        for call in [lambda: offsets(2, 1, 'wave'), lambda: offsets(8, float('nan'), 'wave'),
                     lambda: screw_pose(1, 1.1, 2), lambda: offsets(8, -1, 'wave')]:
            with self.assertRaises(ValueError):
                call()


class GeometryTests(unittest.TestCase):
    def test_partition_and_reachable_motion(self):
        with tempfile.TemporaryDirectory() as td:
            make_inputs(Path(td))
            mesh = trimesh.load(Path(td)/'target.ply')
            profile, gap = adapt_profile(synthetic_profile(), 8, 8, 1., .15, .5)
            self.assertGreater(gap, 0.)
            parts = helical_parts(mesh, profile, 8, 3., .5)
            self.assertEqual(len(parts), 8)
            for part in parts:
                self.assertTrue(require_solid(part)['watertight'])
            states = measure_states(parts, offsets(8, 12, 'staircase'), 3., [0., .37, 1.], 1e-5)
            self.assertTrue(all(not r['collisions'] for r in states))
            self.assertGreater(states[-1]['dimensions_mm'][2], states[0]['dimensions_mm'][2]+10)
            self.assertTrue(section_loops(parts[0], [15.])[0]['loops_xy_mm'])

    def test_containment_is_collision(self):
        outer = trimesh.creation.box(extents=[10, 10, 10])
        inner = trimesh.creation.box(extents=[1, 1, 1])
        result = measure_states([outer, inner], [0, 0], 2, [0], 1e-6)[0]
        self.assertAlmostEqual(result['max_overlap_mm3'], 1.)
        self.assertEqual(result['collisions'][0]['parts'], [1, 2])

    def test_finer_partition(self):
        mesh = trimesh.creation.cylinder(radius=16, height=30, sections=48)
        profile, gap = adapt_profile(synthetic_profile(), 8, 16, 1.3, .12, .5)
        parts = helical_parts(mesh, profile, 16, -2., .5)
        self.assertGreater(gap, 0)
        self.assertEqual(len(parts), 16)
        states = measure_states(parts, offsets(16, 25, 'staircase'), -2., [0., 1.], 1e-5)
        self.assertTrue(all(not s['collisions'] for s in states))

    def test_bad_profile_and_open_mesh_rejected(self):
        with self.assertRaises(ValueError):
            adapt_profile([[0, 0], [2, 2], [0, 2], [2, 0]], 8, 8, 1, .1, .5)
        with self.assertRaises(ValueError):
            adapt_profile(synthetic_profile(), 8, 8, 1, 50, .5)
        mesh = trimesh.creation.box()
        mesh.update_faces(np.arange(len(mesh.faces)-1))
        with self.assertRaises(ValueError):
            require_solid(mesh)


class EntryTests(unittest.TestCase):
    def run_cli(self, root, *args, success=True):
        result = subprocess.run([sys.executable, str(SCRIPTS/'run.py'), *args,
                                 '--task-id', 'fixture'], cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout+result.stderr)
        return result

    def test_real_entrypoints_and_stale_export(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_inputs(root)
            self.run_cli(root, 'inspect', '--input', 'target.ply', '--scale-to-mm', '1',
                         '--sections', '15', '--out', 'inspect')
            self.run_cli(root, 'build', '--job', 'job.json', '--out', 'build')
            self.run_cli(root, 'validate', '--assembly', 'build/assembly.json', '--travel-mm', '12',
                '--mode', 'wave', '--samples', '3', '--overlap-tolerance-mm3', '0.00001', '--study-only', '--out', 'valid')
            report = json.loads((root/'valid/validation.json').read_text())
            self.assertTrue(report['sampled_collision_free'])
            self.assertIsNone(report['rail_overlap'])
            self.assertEqual(report['pair_check_total'], 84)
            (root/'intervals.json').write_text(json.dumps({'intervals_mm': [[0, 1]]*8}))
            self.run_cli(root, 'validate', '--assembly', 'build/assembly.json', '--travel-mm', '12',
                '--mode', 'staircase', '--samples', '2', '--overlap-tolerance-mm3', '0.00001',
                '--intervals', 'intervals.json', '--study-only', '--out', 'disengaged', success=False)
            failed = json.loads((root/'disengaged/validation.json').read_text())
            self.assertTrue(failed['sampled_collision_free'])
            self.assertTrue(any(p['overlap_mm'] == 0 for p in failed['rail_overlap']))
            self.run_cli(root, 'build', '--job', 'job.json', '--out', 'build', success=False)
            with (root/'build/parts/petal_001.stl').open('ab') as f:
                f.write(b'changed')
            self.run_cli(root, 'validate', '--assembly', 'build/assembly.json', '--travel-mm', '12',
                '--mode', 'wave', '--samples', '3', '--overlap-tolerance-mm3', '0.00001', '--out', 'stale', success=False)
            events = [json.loads(s) for s in (root/'stale/timings.jsonl').read_text().splitlines()]
            self.assertEqual(events[1]['status'], 'failed')
            self.assertTrue(any(e['status'] == 'skipped' for e in events))

    def test_failure_timing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'timings.jsonl'
            with self.assertRaises(RuntimeError):
                with stage(path, 'fixture', 'attempt', 'failure', 'prior'):
                    raise RuntimeError('synthetic failure')
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([r['status'] for r in events], ['running', 'failed'])
            self.assertIn('+00:00', events[-1]['ended_at'])
            self.assertGreaterEqual(events[-1]['elapsed_seconds'], 0)
            self.assertEqual(events[-1]['previous_attempt_id'], 'prior')


if __name__ == '__main__':
    unittest.main()
