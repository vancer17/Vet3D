"""Pure geometry and timing invariants; no network or Blender dependencies."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from collections import Counter
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from geometry import Thread, thread_radius, threaded_ring, screw_lift, revolved_solid, profile_volume_ml, profile_radius
from timing import stage, skipped

SPEC = Thread(12, .6, 3, .2, .8, .25, .15)


def signed_volume(vertices, faces):
    total = 0
    for face in faces:
        a = vertices[face[0]]
        for i in range(1, len(face)-1):
            b, c = vertices[face[i]], vertices[face[i+1]]
            total += (a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2]) + a[2]*(b[0]*c[1]-b[1]*c[0]))/6
    return total


class GeometryTests(unittest.TestCase):
    def test_screw_law_for_both_hands(self):
        for hand in (-1, 1):
            spec = replace(SPEC, hand=hand, phase_mm=.43)
            for angle in [.13, .71, 1.9, 7.3]:
                lift = screw_lift(spec.pitch_mm, angle, hand)
                for theta in [.1, .81, 3.7]:
                    self.assertAlmostEqual(thread_radius(spec, 2.17+lift, theta+angle), thread_radius(spec, 2.17, theta))
                    self.assertAlmostEqual(thread_radius(spec, 2.17, theta), thread_radius(spec, 2.17, theta+math.tau))

    def test_female_envelope_and_lead(self):
        for z in [i*.053 for i in range(120)]:
            for theta in [0, .3, 1.1, 5.8]:
                self.assertGreaterEqual(thread_radius(SPEC, z, theta, True)-thread_radius(SPEC, z, theta), SPEC.radial_clearance_mm-1e-12)
        vertices, _ = threaded_ring(SPEC, 0, 6, 9, segments=32, rows_per_pitch=12, lead_mm=.5)
        self.assertTrue(all(abs(math.hypot(x, y)-SPEC.root_radius_mm)<1e-10 for x, y, _ in vertices[:32]))

    def test_meshes_have_consistent_closed_edges_and_volume(self):
        meshes = [threaded_ring(SPEC, 0, 6, 9, segments=32, rows_per_pitch=12),
                  threaded_ring(SPEC, 0, 7, 15, female=True, segments=32, rows_per_pitch=12),
                  revolved_solid([[3, 0], [5, 4], [5, 10]], 32)]
        for vertices, faces in meshes:
            directed = Counter((f[i], f[(i+1)%len(f)]) for f in faces for i in range(len(f)))
            self.assertTrue(all(count==1 and directed[(b,a)]==1 for (a,b), count in directed.items()))
            self.assertGreater(signed_volume(vertices, faces), 0)

    def test_profile_and_bad_geometry(self):
        self.assertAlmostEqual(profile_volume_ml([[5, 0], [5, 10]], 6), math.pi*25*6/1000)
        self.assertEqual(profile_radius([[2, 0], [4, 10]], 5), 3)
        for changes in [{'pitch_mm': 0}, {'depth_mm': float('nan')}, {'axial_relief_mm': .8}, {'hand': 0}, {'radial_clearance_mm': 0}]:
            with self.assertRaises(ValueError): replace(SPEC, **changes)
        for kwargs in [dict(low_mm=2, high_mm=1, wall_radius_mm=9), dict(low_mm=0,high_mm=1,wall_radius_mm=15), dict(low_mm=0,high_mm=1,wall_radius_mm=9,lead_mm=1)]:
            with self.assertRaises(ValueError): threaded_ring(SPEC, **kwargs)
        with self.assertRaises(ValueError): revolved_solid([[1, 2], [2, 1]])
        with self.assertRaises(ValueError): profile_radius([[1, 0], [2, 1]], 3)

    def test_failed_stage_is_appended_without_exception_body(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'timing.jsonl'
            with self.assertRaises(RuntimeError):
                with stage(path, 'synthetic', 'attempt', 'geometry'):
                    raise RuntimeError('private error body')
            skipped(path, 'synthetic', 'attempt', 'render', 'geometry failed')
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([r['status'] for r in rows], ['running', 'failed', 'skipped'])
            self.assertGreaterEqual(rows[1]['elapsed_seconds'], 0)
            self.assertTrue(rows[0]['started_at'].endswith('+00:00'))
            self.assertNotIn('private error body', path.read_text())


if __name__ == '__main__':
    unittest.main()
