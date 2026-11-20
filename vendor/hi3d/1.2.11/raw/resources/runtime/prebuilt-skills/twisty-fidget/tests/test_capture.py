"""Regression for weak asymmetric keys, thin lips and incomplete numeric evidence."""
import copy
import sys
import unittest
from pathlib import Path
import numpy as np
import trimesh
from shapely.geometry import Polygon, box
from shapely import affinity
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from rail import t_profile
from capture import measure_section, evaluate_row, check_capture, measure_capture, section_polygon
from stops import helical_prism
from geometry import from_solid


def rail_spec():
    return dict(count=24, radius_mm=24, head_width_mm=5.4, neck_width_mm=2.6,
                stem_depth_mm=2.2, head_thickness_mm=1.2, normal_gap_mm=.35,
                corner_mm=.3, inner_radius_mm=3.3, outer_radius_mm=35,
                sample_mm=.5, k_deg_per_mm=1.25)


def capture_spec(count=3):
    probes = dict(x_window_mm=[19, 30], x_center_mm=24, head_y_mm=2.8, neck_y_mm=1,
                  shoulder_x_mm=[21.8, 26.2], y_window_mm=[-5, 15], flange_y_mm=2.8,
                  front_lip_y_mm=.6, back_wall_y_mm=4.3)
    return dict(schema='twisty.capture-spec.v1', maximum_section_step_mm=20,
                manufacturing=dict(status='assumed', basis='Synthetic gate fixture; not printer calibration',
                    extrusion_width_mm=.45, male_loss_mm=.15, female_growth_mm=.15, wear_flex_budget_mm=.1),
                thresholds_mm=dict(residual_capture=.45, maximum_neck_play=.9, root=2.25,
                    flange=1.1, front_lip=1.5, back_wall=1.65, minimum_engagement=15),
                interfaces=[dict(owner=i+1, receiver=(i+1)%count+1, angle_at_z0_deg=i*360/count,
                    heights_mm=[0, 20, 40], probes=probes) for i in range(count)])


def synthetic_report(manifest, assembly_hash):
    spec = capture_spec(manifest['count'])
    p = Polygon(t_profile(rail_spec())[0]);q = affinity.rotate(p, 15, origin=(0, 0))
    values = measure_section(p, q, spec['interfaces'][0]['probes'])
    return dict(schema='twisty.capture.v1', assembly_sha256=assembly_hash,
                part_sha256=[r['sha256'] for r in manifest['parts']], spec=spec, all_passed=True,
                measurements=[dict(owner=j['owner'], receiver=j['receiver'], z_mm=z, failures=[], **values)
                              for j in spec['interfaces'] for z in j['heights_mm']])


class CaptureTests(unittest.TestCase):
    def test_balanced_key_and_thin_receiver_lip(self):
        spec = capture_spec();p = Polygon(t_profile(rail_spec())[0]);q = affinity.rotate(p, 15, origin=(0, 0))
        row = measure_section(p, q, spec['interfaces'][0]['probes'])
        self.assertFalse(evaluate_row(row, spec))
        self.assertGreater(row['left_capture_mm'], .98)
        self.assertGreater(row['right_capture_mm'], .98)
        # Remove receiver material without changing either shoulder capture width.
        q = q.difference(box(21.6, -.1, 22, .5))
        row = measure_section(p, q, spec['interfaces'][0]['probes'])
        self.assertIn('front_lip thickness', evaluate_row(row, spec))

    def test_asymmetric_shoulder_is_not_averaged(self):
        report = synthetic_report({'count': 3, 'parts': [{'sha256': str(i)} for i in range(3)]}, 'hash')
        row = report['measurements'][0]
        row['left_capture_mm'], row['right_capture_mm'] = .29, 1.5
        self.assertIn('left shoulder reserve', evaluate_row(row, report['spec']))

    def test_budget_and_printer_scale_are_not_universal(self):
        report = synthetic_report({'count': 3, 'parts': [{'sha256': str(i)} for i in range(3)]}, 'hash')
        self.assertFalse(evaluate_row(report['measurements'][0], report['spec']))
        report['spec']['manufacturing']['male_loss_mm'] = .6
        self.assertTrue(evaluate_row(report['measurements'][0], report['spec']))
        report['spec']['manufacturing']['male_loss_mm'] = .15
        report['spec']['thresholds_mm']['root'] = 3
        self.assertIn('root thickness', evaluate_row(report['measurements'][0], report['spec']))

    def test_final_swept_mesh_section_and_wrong_frame(self):
        points, _ = t_profile(rail_spec())
        a = from_solid(helical_prism(points, 0, 5, 1.25, .125))
        b = a.copy();b.apply_transform(trimesh.transformations.rotation_matrix(np.radians(15), [0, 0, 1]))
        probe = capture_spec()['interfaces'][0]['probes']
        row = measure_section(section_polygon(a, 2.5, 3.125), section_polygon(b, 2.5, 3.125), probe)
        self.assertFalse(evaluate_row(row, capture_spec()))
        with self.assertRaises(ValueError):
            measure_section(section_polygon(a, 2.5, 90), section_polygon(b, 2.5, 90), probe)

    def test_report_coverage_and_endpoint_overlap(self):
        manifest = {'count': 3, 'parts': [{'sha256': str(i)} for i in range(3)],
                    'axial_stops': {'retained_motions': [{'mode': 'wave', 'travel_mm': 2}],
                                   'interfaces': [dict(owner=i+1, receiver=(i+1)%3+1,
                                        negative_travel_mm=8, positive_travel_mm=10) for i in range(3)]}}
        original = synthetic_report(manifest, 'hash')
        self.assertEqual(check_capture(original, manifest, 'hash', [[0, 40]]*3)['sections'], 9)
        for mutation in ('missing', 'duplicate', 'weak', 'nan', 'stale', 'one_lip', 'raw_disagreement'):
            report = copy.deepcopy(original)
            if mutation == 'missing': report['measurements'].pop()
            elif mutation == 'duplicate': report['measurements'].append(report['measurements'][0])
            elif mutation == 'weak': report['measurements'][0]['left_capture_mm'] = .29
            elif mutation == 'nan': report['measurements'][0]['root_mm'] = float('nan')
            elif mutation == 'one_lip': report['measurements'][0]['raw_intervals_mm']['front_lip'].pop()
            elif mutation == 'raw_disagreement': report['measurements'][0]['left_capture_mm'] = 1.1
            else: report['part_sha256'][0] = 'stale'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                check_capture(report, manifest, 'hash', [[0, 40]]*3)
        with self.assertRaises(ValueError):
            check_capture(original, manifest, 'hash', [[0, 41]]*3)
        with self.assertRaises(ValueError):
            check_capture(original, manifest, 'hash', [[5, 25]]*3)


if __name__ == '__main__':
    unittest.main()
