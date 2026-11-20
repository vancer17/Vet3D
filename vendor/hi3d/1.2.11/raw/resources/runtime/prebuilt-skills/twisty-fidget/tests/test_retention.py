"""Gate behavior tests: review assertions are synthetic, not physical certification."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_stops import ring_fixture
from run import digest, write_json, export_parts
from retention import connection_report, check_evidence, require_stops
from test_capture import synthetic_report

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'


class RetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        root = cls.root
        (root/'source').mkdir()
        parts, interfaces = ring_fixture()
        rows, _ = export_parts(parts, root/'source')
        manifest = {'schema': 'twisty.assembly.v1', 'unit': 'mm', 'axis': 'Z', 'origin_xy_mm': [0, 0],
                    'count': 3, 'k_deg_per_mm': 2., 'parts': rows}
        write_json(root/'source/assembly.json', manifest)
        motions = [{'mode': m, 'travel_mm': 2} for m in ('staircase', 'wave')]
        write_json(root/'stops.json', {'assembly_method': 'print_in_place', 'step_mm': .2,
                                     'interfaces': interfaces, 'retained_motions': motions})
        cls.cli('add-stops', '--assembly', 'source/assembly.json', '--spec', 'stops.json',
                '--contact-probe-mm', '.2', '--overlap-tolerance-mm3', '.00001', '--out', 'stopped')
        cls.manifest = json.loads((root/'stopped/assembly.json').read_text())
        cls.assembly_hash = digest(root/'stopped/assembly.json')
        write_json(root/'intervals.json', {'assembly_sha256': cls.assembly_hash, 'intervals_mm': [[0, 40]]*3})
        (root/'synthetic-section.txt').write_text('Synthetic review evidence for gate tests only.')
        review = {'status': 'passed', 'reviewer': 'synthetic test reviewer',
                  'findings': 'Synthetic assertions; no claim of geometric capture or wall measurement.',
                  'artifacts': [cls.ref('synthetic-section.txt')]}
        bundle = {'schema': 'twisty.evidence.v1', 'assembly_sha256': cls.assembly_hash,
                  'stop_contacts': cls.ref('stopped/stop_contacts.json'), 'intervals': cls.ref('intervals.json'),
                  'motions': [], 'reviews': {k: copy.deepcopy(review) for k in ('capture', 'walls', 'sections', 'assembly')}}
        write_json(root/'capture.json', synthetic_report(cls.manifest, cls.assembly_hash))
        bundle['capture_measurement'] = cls.ref('capture.json')
        pairs = [[1, 2], [2, 3], [3, 1]]
        bundle['reviews']['capture']['interfaces'] = [{'parts': p, 'captured': True} for p in pairs]
        bundle['reviews']['walls']['interfaces'] = [{'parts': p, 'minimum_mm': 1.5, 'required_mm': 1.2} for p in pairs]
        bundle['reviews']['assembly']['method'] = 'print_in_place'
        bundle['reviews']['fit'] = dict(copy.deepcopy(review), process_status='assumed',
            basis='Synthetic gap and coupon evidence for gate tests only.',
            coupon_artifacts=[cls.ref('synthetic-section.txt')],
            interfaces=[dict(parts=p, minimum_gap_mm=.35, maximum_gap_mm=.4, required_range_mm=[.3,.45]) for p in pairs])
        for case in motions:
            mode = case['mode']
            cls.cli('validate', '--assembly', 'stopped/assembly.json', '--intervals', 'intervals.json',
                    '--travel-mm', '2', '--mode', mode, '--samples', '3', '--overlap-tolerance-mm3', '.00001', '--out', mode)
            (root/f'{mode}.glb').write_bytes(b'Synthetic animation artifact for report binding tests.')
            write_json(root/f'{mode}-reimport.json', {'passed': True, 'assembly_sha256': cls.assembly_hash,
                **case, 'glb_sha256': digest(root/f'{mode}.glb'), 'sample_frames': [1, 2, 3],
                'checks': [{'frame': f, 'part': f'Petal_{i:03d}', 'position_error_mm': 0,
                            'rotation_error_deg': 0, 'screw_error_deg': 0} for f in (1, 2, 3) for i in (1, 2, 3)]})
            bundle['motions'].append({**case, 'validation': cls.ref(f'{mode}/validation.json'),
                'reimport': cls.ref(f'{mode}-reimport.json'), 'glb': cls.ref(f'{mode}.glb'),
                'visual_review': copy.deepcopy(review)})
        cls.bundle = bundle

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def cli(cls, *args, success=True):
        result = subprocess.run([sys.executable, str(SCRIPTS/'run.py'), *args, '--task-id', 'retention-fixture'],
                                cwd=cls.root, capture_output=True, text=True)
        if (result.returncode == 0) != success:
            raise AssertionError(result.stdout+result.stderr)
        return result

    @classmethod
    def ref(cls, name):
        return {'file': name, 'sha256': digest(cls.root/name)}

    def check(self, bundle=None, overrides=None):
        def verify(ref):
            path = self.root/ref['file']
            if not path.is_file() or path.stat().st_size == 0 or digest(path) != ref['sha256']:
                raise ValueError('stale or missing evidence')
        def read(ref):
            verify(ref)
            return (overrides or {}).get(ref['file'], json.loads((self.root/ref['file']).read_text()))
        return check_evidence(self.manifest, self.assembly_hash, bundle or self.bundle, read, verify)

    def test_whole_ring_connectivity_and_wrap(self):
        interfaces = self.manifest['axial_stops']['interfaces']
        self.assertTrue(connection_report(3, interfaces)['complete'])
        for rows in ([], interfaces[:1], interfaces[:-1], interfaces+[interfaces[0]],
                     interfaces+[dict(interfaces[0], owner=2, receiver=1)]):
            self.assertFalse(connection_report(3, rows)['complete'])
        disjoint = [{'owner': a, 'receiver': b} for a, b in [(1, 2), (2, 3), (3, 1), (4, 5), (5, 6), (6, 4)]]
        self.assertEqual(len(connection_report(6, disjoint)['components']), 2)
        with self.assertRaises(ValueError):
            connection_report(3, [{'owner': True, 'receiver': 2}])

    def test_missing_stops_or_motion_declaration_fails(self):
        for key in ('axial_stops',):
            manifest = copy.deepcopy(self.manifest); del manifest[key]
            with self.assertRaises(ValueError):
                require_stops(manifest)
        manifest = copy.deepcopy(self.manifest)
        manifest['axial_stops']['retained_motions'] = []
        with self.assertRaises(ValueError):
            require_stops(manifest)

    def test_default_validation_rejects_unstopped_or_unbound_inputs(self):
        base = ['validate', '--travel-mm', '2', '--mode', 'wave', '--samples', '3', '--overlap-tolerance-mm3', '.00001']
        self.cli(*base, '--assembly', 'source/assembly.json', '--out', 'unstopped-default', success=False)
        self.cli(*base, '--assembly', 'stopped/assembly.json', '--out', 'no-intervals', success=False)
        self.cli(*base, '--assembly', 'source/assembly.json', '--study-only', '--out', 'study')
        report = json.loads((self.root/'study/validation.json').read_text())
        self.assertEqual(report['purpose'], 'study_only')

    def test_complete_bound_evidence_and_cli_acceptance(self):
        self.assertTrue(self.check()['connection']['complete'])
        write_json(self.root/'complete-evidence.json', self.bundle)
        self.cli('accept', '--assembly', 'stopped/assembly.json', '--evidence', 'complete-evidence.json', '--out', 'accepted')
        self.assertTrue(json.loads((self.root/'accepted/acceptance.json').read_text())['passed'])

    def test_missing_evidence_and_pending_reviews_fail(self):
        bundle = copy.deepcopy(self.bundle); del bundle['capture_measurement']
        with self.assertRaises(KeyError): self.check(bundle)
        for category in ('capture', 'walls', 'sections', 'assembly', 'fit'):
            for mutation in ('missing', 'pending', 'no_artifacts'):
                with self.subTest(category=category, mutation=mutation):
                    bundle = copy.deepcopy(self.bundle)
                    if mutation == 'missing': del bundle['reviews'][category]
                    elif mutation == 'pending': bundle['reviews'][category]['status'] = 'pending'
                    else: bundle['reviews'][category]['artifacts'] = []
                    with self.assertRaises((ValueError, KeyError)):
                        self.check(bundle)

    def test_stale_artifacts_and_failure_report(self):
        for ref in ('stop_contacts', 'intervals'):
            bundle = copy.deepcopy(self.bundle); bundle[ref]['sha256'] = '0'*64
            with self.assertRaises(ValueError): self.check(bundle)
        bundle = copy.deepcopy(self.bundle)
        bundle['reviews']['sections']['artifacts'][0]['file'] = 'missing.png'
        write_json(self.root/'incomplete.json', bundle)
        self.cli('accept', '--assembly', 'stopped/assembly.json', '--evidence', 'incomplete.json', '--out', 'rejected', success=False)
        self.assertFalse(json.loads((self.root/'rejected/acceptance.json').read_text())['passed'])
        self.assertEqual(json.loads((self.root/'rejected/timing_summary.json').read_text())['status'], 'failed')

    def test_assembled_print_file_is_bound(self):
        write_json(self.root/'assembled-evidence.json', self.bundle)
        path = self.root/'stopped/assembled_mm.stl'
        original = path.read_bytes()
        try:
            path.write_bytes(original+b'changed')
            self.cli('accept', '--assembly', 'stopped/assembly.json', '--evidence', 'assembled-evidence.json',
                     '--out', 'stale-assembled', success=False)
            self.assertFalse(json.loads((self.root/'stale-assembled/acceptance.json').read_text())['passed'])
        finally:
            path.write_bytes(original)

    def test_incomplete_contact_evidence_cannot_hide_behind_all_passed(self):
        path = self.bundle['stop_contacts']['file']
        original = json.loads((self.root/path).read_text())
        for mutation in ('direction', 'states', 'overtravel', 'attachments', 'duplicate'):
            report = copy.deepcopy(original)
            if mutation == 'direction': report['contacts'].pop()
            elif mutation == 'states': report['contacts'][0]['states'].pop()
            elif mutation == 'overtravel': report['contacts'][0]['states'][-1]['overlap_mm3'] = 0
            elif mutation == 'attachments': report['attachments'].pop()
            else: report['contacts'].append(report['contacts'][0])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.check(overrides={path: report})

    def test_all_declared_motions_and_raw_coverage_required(self):
        bundle = copy.deepcopy(self.bundle); bundle['motions'].pop()
        with self.assertRaises(ValueError): self.check(bundle)
        path = self.bundle['motions'][0]['validation']['file']
        original = json.loads((self.root/path).read_text())
        for mutation in ('study', 'parts', 'empty', 'pairs', 'ranges', 'overlap', 'stale', 'nan'):
            report = copy.deepcopy(original)
            if mutation == 'study': report['purpose'] = 'study_only'
            elif mutation == 'parts': report['part_sha256'].pop()
            elif mutation == 'empty': report['states'] = []
            elif mutation == 'pairs': report['states'][1]['pair_checks'] = 1
            elif mutation == 'ranges': report['stop_travel_limits'] = []
            elif mutation == 'overlap': report['rail_overlap'] = None
            elif mutation == 'stale': report['assembly_sha256'] = '0'*64
            else: report['states'][1]['max_overlap_mm3'] = float('nan')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.check(overrides={path: report})

    def test_capture_walls_and_animation_must_cover_all_parts(self):
        for kind in ('capture', 'walls'):
            bundle = copy.deepcopy(self.bundle); bundle['reviews'][kind]['interfaces'].pop()
            with self.assertRaises(ValueError): self.check(bundle)
        bundle = copy.deepcopy(self.bundle); bundle['reviews']['walls']['interfaces'][0]['minimum_mm'] = .1
        with self.assertRaises(ValueError): self.check(bundle)
        path = self.bundle['motions'][0]['reimport']['file']
        report = json.loads((self.root/path).read_text()); report['checks'].pop()
        with self.assertRaises(ValueError): self.check(overrides={path: report})
        report = json.loads((self.root/path).read_text()); report['glb_sha256'] = '0'*64
        with self.assertRaises(ValueError): self.check(overrides={path: report})
        report = json.loads((self.root/path).read_text()); report['sample_frames'] = [1, 2, float('nan')]
        with self.assertRaises(ValueError): self.check(overrides={path: report})

    def test_fit_measurements_and_actual_coupon_required(self):
        for mutation in ('missing_interface', 'missing_coupon', 'tight', 'loose', 'unattributed'):
            bundle = copy.deepcopy(self.bundle)
            fit = bundle['reviews']['fit']
            if mutation == 'missing_interface': fit['interfaces'].pop()
            elif mutation == 'missing_coupon': fit['coupon_artifacts'] = []
            elif mutation == 'tight': fit['interfaces'][0]['minimum_gap_mm'] = .1
            elif mutation == 'loose': fit['interfaces'][0]['maximum_gap_mm'] = 1
            else: fit['basis'] = ''
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.check(bundle)


if __name__ == '__main__':
    unittest.main()
