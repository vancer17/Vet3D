import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import trimesh

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
from geometry import from_solid, to_solid, require_solid
from stops import helical_prism, apply_stops, measure_stop_contacts
from run import digest
from motion import stop_travel_limits


def fixture(k=2.):
    parts = [from_solid(helical_prism(p, 0, 40, k, .2)) for p in (
        [[10, -4], [18, -4], [18, -.3], [10, -.3]],
        [[10, .3], [18, .3], [18, 4], [10, 4]])]
    spec = {'owner': 1, 'receiver': 2, 'footprint_xy_mm': [[13, -1.5], [15, -1.5], [15, 1.5], [13, 1.5]],
            'z_center_mm': 20, 'lug_height_mm': 3, 'negative_travel_mm': 8,
            'positive_travel_mm': 10, 'xy_clearance_mm': .4}
    return parts, spec


def ring_fixture():
    angles = np.radians(np.linspace(-59, 59, 60))
    polygon = [[r*np.cos(a), r*np.sin(a)] for r, aa in [(10, angles), (18, angles[::-1])] for a in aa]
    # Positive winding is normalized by the sweep primitive.
    parts, specs = [], []
    _, base = fixture()
    for i in range(3):
        angle = np.radians(i*120)
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        parts.append(from_solid(helical_prism(np.asarray(polygon) @ rotation.T, 0, 40, 2, .2)))
        angle = np.radians(60+i*120)
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        specs.append(dict(base, owner=i+1, receiver=(i+1) % 3+1,
            footprint_xy_mm=(np.asarray(base['footprint_xy_mm']) @ rotation.T).tolist()))
    return parts, specs


class StopTests(unittest.TestCase):
    def test_two_endpoints_both_handedness_and_winding(self):
        for k in [2., -2.]:
            original, spec = fixture(k)
            spec['footprint_xy_mm'].reverse()
            parts, roots = apply_stops(original, [spec], k, .2)
            self.assertGreater(roots[0]['root_overlap_mm3'], 1.)
            for p in parts:
                self.assertEqual(require_solid(p)['components'], 1)
            a, b = [to_solid(p) for p in parts]
            for dz in np.linspace(-8, 10, 13):
                self.assertLess(abs((a.rotate((0, 0, k*dz)).translate((0, 0, dz)) ^ b).volume()), 1e-5)
            rows = measure_stop_contacts(parts, [spec], k, .2, 1e-5)
            self.assertTrue(all(r['passed'] for r in rows))
            self.assertTrue(all(r['states'][2]['overlap_mm3'] > .1 for r in rows))

    def test_range_guard_includes_wrap_and_asymmetric_direction(self):
        _, s = fixture()
        self.assertTrue(stop_travel_limits([10, 0], [s])[0]['within_limits'])
        self.assertTrue(stop_travel_limits([0, 8], [s])[0]['within_limits'])
        self.assertFalse(stop_travel_limits([100, 0], [s])[0]['within_limits'])
        self.assertFalse(stop_travel_limits([0, 9], [s])[0]['within_limits'])
        wrap = dict(s, owner=3, receiver=1)
        self.assertFalse(stop_travel_limits([0, 5, 11], [wrap])[0]['within_limits'])

    def test_open_end_is_not_retention(self):
        parts, spec = fixture()
        spec['positive_travel_mm'] = 30
        revised, _ = apply_stops(parts, [spec], 2, .2)
        rows = measure_stop_contacts(revised, [spec], 2, .2, 1e-5)
        self.assertTrue(rows[0]['passed'])
        self.assertFalse(rows[1]['passed'])

    def test_invalid_or_unattached_features_fail(self):
        parts, spec = fixture()
        for change in ({'xy_clearance_mm': 0}, {'owner': 0}, {'receiver': 1},
                       {'footprint_xy_mm': [[100, 0], [101, 0], [101, 1], [100, 1]]}):
            with self.assertRaises(ValueError):
                apply_stops(parts, [dict(spec, **change)], 2, .2)
        with self.assertRaises(ValueError):
            measure_stop_contacts(parts, [spec], 2, 9, 1e-5)

    def test_cli_export_and_assembly_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            parts, specs = ring_fixture()
            rows = []
            for i, p in enumerate(parts):
                file = f'part{i}.stl';p.export(root/file)
                rows.append({'part': i+1, 'file': file, 'sha256': digest(root/file)})
            manifest = {'schema': 'twisty.assembly.v1', 'unit': 'mm', 'axis': 'Z', 'origin_xy_mm': [0, 0],
                        'count': len(parts), 'k_deg_per_mm': 2., 'parts': rows}
            (root/'input.json').write_text(json.dumps(manifest))
            job = {'assembly_method': 'print_in_place', 'step_mm': .2, 'interfaces': specs,
                   'retained_motions': [{'mode': 'staircase', 'travel_mm': 2}]}
            (root/'spec.json').write_text(json.dumps(job))
            def run(out):
                return subprocess.run([sys.executable, str(SCRIPTS/'run.py'), 'add-stops', '--assembly', 'input.json',
                    '--spec', 'spec.json', '--contact-probe-mm', '.2', '--overlap-tolerance-mm3', '.00001',
                    '--out', out, '--task-id', 'stops'], cwd=root, capture_output=True, text=True)
            result = run('built')
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root/'built/stop_contacts.json').read_text())
            self.assertTrue(report['all_passed'])
            self.assertEqual(report['assembly_sha256'], digest(root/'built/assembly.json'))
            self.assertTrue((root/'built/assembled_mm.stl').is_file())
            rejected = subprocess.run([sys.executable, str(SCRIPTS/'run.py'), 'validate', '--assembly', 'built/assembly.json',
                '--travel-mm', '100', '--mode', 'staircase', '--samples', '2', '--overlap-tolerance-mm3', '.00001',
                '--study-only', '--out', 'overtravel', '--task-id', 'stops'], cwd=root, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            report = json.loads((root/'overtravel/validation.json').read_text())
            self.assertTrue(report['sampled_collision_free'])
            self.assertFalse(report['stop_travel_limits'][0]['within_limits'])
            job['interfaces'] = specs[:1]
            (root/'spec.json').write_text(json.dumps(job))
            self.assertNotEqual(run('disconnected').returncode, 0)
            job['interfaces'] = specs
            job['assembly_method'] = 'separate_print_then_screw_in'
            (root/'spec.json').write_text(json.dumps(job))
            self.assertNotEqual(run('unsupported').returncode, 0)
            self.assertEqual(json.loads((root/'unsupported/timing_summary.json').read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
