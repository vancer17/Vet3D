"""Offline behavior tests; all generated files live in temporary directories."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
import calibrate
import default_head
import validate_delivery as delivery


class LocalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_head_export_closed_and_repeatable(self):
        verts, faces = default_head.build_head()
        content = default_head.obj_text(verts, faces)
        report = default_head.head_metadata(verts, faces, hashlib.sha256(content.encode()).hexdigest())
        self.assertFalse(report['personal_identity'])
        self.assertEqual(report['topology']['euler_characteristic'], 2)
        self.assertGreater(report['topology']['signed_volume_mm3'], 0)
        obj, metadata = default_head.save_head(self.root, content, report)
        parsed_v = [line for line in obj.read_text().splitlines() if line.startswith('v ')]
        parsed_f = [tuple(map(int, line.split()[1:])) for line in obj.read_text().splitlines() if line.startswith('f ')]
        self.assertEqual(len(parsed_v), len(verts))
        edges = Counter(tuple(sorted((f[i], f[(i+1)%3]))) for f in parsed_f for i in range(3))
        self.assertTrue(all(n == 2 for n in edges.values()))
        self.assertEqual(len(parsed_v)-len(edges)+len(parsed_f), 2)
        self.assertEqual(report, json.loads(metadata.read_text()))
        second = self.root/'second'
        result = subprocess.run([sys.executable, str(SCRIPTS/'default_head.py'), '--out', str(second)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(obj.read_bytes(), (second/'default-head.obj').read_bytes())
        with self.assertRaises(FileExistsError):
            default_head.save_head(self.root, 'changed', {})
        self.assertEqual(obj.read_text(), content)
        with self.assertRaises(ValueError):
            default_head.head_metadata(verts, faces[:-1], '')

    def test_head_surface_derivatives_are_continuous(self):
        # A densely sliced smooth head must not reset every profile tangent to zero.
        for z in (-108, -82, -68, -52, -22, 8, 40, 76, 106):
            left, center, right = [default_head.profile(z+d) for d in (-.001, 0, .001)]
            for i in range(3):
                self.assertAlmostEqual((center[i]-left[i])/.001, (right[i]-center[i])/.001, delta=.002)
        self.assertGreater(abs((default_head.profile(-81.999)[2]-default_head.profile(-82.001)[2])/.002), .1)

    def test_calibration_scale_conflicts_and_input_guard(self):
        row = {'name':'width', 'kind':'straight', 'model_distance':.15, 'measured_mm':150, 'uncertainty_mm':1}
        other = dict(row, name='length', model_distance=.12, measured_mm=120)
        result = calibrate.calibrate({'measurements':[row, other]})
        self.assertAlmostEqual(result['scale_mm_per_model_unit'], 1000)
        self.assertEqual(result['status'], 'landmark_scale_consistent')
        self.assertEqual(calibrate.calibrate({'measurements':[row]})['status'], 'single_dimension_only')
        other['measured_mm'] = 200
        self.assertEqual(calibrate.calibrate({'measurements':[row, other]})['status'], 'review_required')
        for bad in (dict(row, kind='circumference'), dict(row, uncertainty_mm=0), dict(row, model_distance=True), dict(row, measured_mm=float('nan'))):
            with self.assertRaises(ValueError):
                calibrate.calibrate({'measurements':[bad]})
        source = self.root/'measure.json'
        source.write_text(json.dumps({'measurements':[row, other]}))
        output = self.root/'report.json'
        run = subprocess.run([sys.executable, str(SCRIPTS/'calibrate.py'), str(source), '--out', str(output)], capture_output=True)
        self.assertEqual(run.returncode, 2)
        original = source.read_bytes()
        with self.assertRaises(FileExistsError):
            calibrate.calibrate_file(source, source)
        self.assertEqual(original, source.read_bytes())

    def manifest(self):
        data = {'project':'synthetic', 'version':'test', 'design_stage':'concept', 'source_sha256':'a'*64, 'entrypoint':'index.html', 'files':[]}
        (self.root/'index.html').write_text('<p>Synthetic integrity fixture</p>')
        for role in sorted(delivery.ROLES):
            # Integrity-only fixtures, not purported playable or wearable media.
            p = self.root/(role+'.bin')
            p.write_bytes(role.encode())
            data['files'].append({'path':p.name, 'role':role, 'bytes':p.stat().st_size, 'sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'source_sha256':'a'*64})
        return data

    def check(self, data):
        path = self.root/'manifest.json'
        path.write_text(json.dumps(data))
        return delivery.validate(path, self.root)

    def test_delivery_good_tamper_and_missing(self):
        data = self.manifest()
        self.assertEqual(self.check(data)['status'], 'passed')
        (self.root/data['files'][0]['path']).write_bytes(b'tampered')
        self.assertEqual(self.check(data)['status'], 'failed')
        self.assertEqual(self.check(dict(data, files=data['files'][1:]))['status'], 'failed')
        data['files'][0]['source_sha256'] = 'b'*64
        self.assertEqual(self.check(data)['status'], 'failed')

    def test_delivery_malformed_and_escape(self):
        for bad in ([], None, {'files':'wrong'}, {'files':[None]}, {'files':[{'role':[]}]}):
            self.assertEqual(self.check(bad)['status'], 'failed')
        data = self.manifest()
        data['entrypoint'] = str(self.root/'index.html')
        self.assertEqual(self.check(data)['status'], 'failed')
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside)/'outside.bin'
            external.write_bytes(b'external')
            (self.root/'escape.bin').symlink_to(external)
            with self.assertRaises(ValueError):
                delivery.delivery_path(self.root, 'escape.bin')
        data = self.manifest()
        data['files'].append(dict(data['files'][0]))
        self.assertEqual(self.check(data)['status'], 'failed')

    def test_media_headers_and_exclusive_reports(self):
        row = {'path':'asset.glb', 'bytes':12, 'sha256':'a'*64}
        self.assertTrue(delivery.file_errors(row, 12, 'a'*64, b'not a model!'))
        row['path'] = 'asset.mp4'
        self.assertTrue(delivery.file_errors(row, 12, 'a'*64, b'not a movie!'))
        path = self.root/'report.json'
        delivery.save_report(path, {'status':'passed'})
        with self.assertRaises(FileExistsError):
            delivery.save_report(path, {'status':'failed'})
        self.assertEqual(json.loads(path.read_text())['status'], 'passed')


if __name__ == '__main__':
    unittest.main()
