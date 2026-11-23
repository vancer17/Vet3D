"""Verify portable delivery bytes and failure behavior without a browser or printer."""
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import trimesh
from package_delivery import build_delivery, zip_bytes
from test_core import fixture


class PayloadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_payload = False
        self.payload = ''
        self.links = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and attrs.get('id') == 'print-kit-data':
            self.in_payload = True
        if tag == 'a' and attrs.get('id', '').startswith('download-'):
            self.links[attrs['id']] = attrs

    def handle_data(self, value):
        if self.in_payload:
            self.payload += value

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_payload = False


class DeliveryContracts(unittest.TestCase):
    def test_three_deliverables_share_exact_model_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kit = fixture(0.3)
            kit.data['title'] = '试件 </script><img src=x onerror=alert(1)>'
            plan = kit.export(root / 'model')
            source = root / 'model.py'
            source.write_text('# explicitly selected source\n')
            outputs = build_delivery(plan, root / 'deliverables', sources=[source])
            self.assertEqual(set(outputs), {'assembly_glb', 'parts_stl_zip', 'showcase'})
            page = Path(outputs['showcase']).read_text()
            parser = PayloadParser()
            parser.feed(page)
            data = json.loads(parser.payload)
            self.assertEqual(data['plan']['title'], kit.data['title'])
            self.assertNotIn('</script><img src=x onerror', page)
            self.assertNotIn('<script src=', page)
            for button, key in [('download-glb', 'assembly_glb'), ('download-stl', 'parts_stl_zip')]:
                self.assertIn(button, parser.links)
                raw = base64.b64decode(data['downloads'][button]['base64'])
                self.assertEqual(raw, Path(outputs[key]).read_bytes())
            with zipfile.ZipFile(outputs['parts_stl_zip']) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read('source/model.py'), source.read_bytes())
                for part in kit.data['parts']:
                    raw = (plan.parent / part['file']).read_bytes()
                    self.assertEqual(archive.read(part['file']), raw)
                    self.assertEqual(base64.b64decode(data['stl'][part['id']]), raw)
                self.assertEqual(json.loads(archive.read('kit.json'))['instances'], kit.data['instances'])
                self.assertIn('print_quantity', archive.read('parts.csv').decode('utf-8-sig'))
                self.assertNotIn('assembly-view-only.stl', archive.namelist())
            assembly = trimesh.load_scene(outputs['assembly_glb'])
            self.assertEqual(set(assembly.graph.nodes_geometry), {i['id'] for i in kit.data['instances']})
            for actual, expected in zip(assembly.extents * 1000, kit.data['assembled_size_mm']):
                self.assertAlmostEqual(actual, expected, places=3)

    def test_changed_geometry_and_unsafe_zip_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = fixture(0.3).export(root / 'model')
            stl = plan.parent / 'parts/male.stl'
            stl.write_bytes(stl.read_bytes() + b'changed')
            with self.assertRaises(ValueError):
                build_delivery(plan, root / 'failed')
            self.assertFalse((root / 'failed').exists())
        for name in ('../outside.stl', '/absolute.stl', 'dir\\escape.stl'):
            with self.assertRaises(ValueError):
                zip_bytes({name: b'bad'})

    def test_ascii_input_fails_before_writing_a_broken_viewer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = fixture(0.3).export(root / 'model')
            data = json.loads(plan.read_text())
            part = data['parts'][0]
            stl = plan.parent / part['file']
            stl.write_text(trimesh.load_mesh(stl).export(file_type='stl_ascii'))
            part['sha256'] = hashlib.sha256(stl.read_bytes()).hexdigest()
            plan.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'requires binary STL'):
                build_delivery(plan, root / 'failed')
            self.assertFalse((root / 'failed').exists())


if __name__ == '__main__':
    unittest.main()
