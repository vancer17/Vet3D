import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIP = Path(__file__).resolve().parents[3] / 'skills' / 'glb-clips' / 'scripts'
CORE = Path(__file__).resolve().parents[3] / 'skills' / 'game-save' / 'scripts' / 'hi3d-core.mjs'
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(CLIP))
import inspect_parts
import plan_config
import build_page
import check_http


def pack_glb(doc, binary=b''):
    payload = json.dumps(doc, separators=(',', ':')).encode()
    payload += b' ' * ((4 - len(payload) % 4) % 4)
    chunks = struct.pack('<I4s', len(payload), b'JSON') + payload
    if binary:
        binary += b'\x00' * ((4 - len(binary) % 4) % 4)
        chunks += struct.pack('<I4s', len(binary), b'BIN\x00') + binary
    return struct.pack('<4sII', b'glTF', 2, 12 + len(chunks)) + chunks


def two_part_glb():
    positions = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    doc = {
        'asset': {'version': '2.0'},
        'scene': 0,
        'scenes': [{'nodes': [0, 1]}],
        'nodes': [{'name': 'body', 'mesh': 0}, {'name': 'lid', 'mesh': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'material': 0}]}],
        'materials': [{'name': 'paint'}, {'name': 'trim'}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3', 'min': [0, 0, 0], 'max': [1, 1, 0]}],
        'bufferViews': [{'buffer': 0, 'byteLength': 36}],
        'buffers': [{'byteLength': 36}],
    }
    return pack_glb(doc, positions)


class ConfiguratorTests(unittest.TestCase):
    def setUp(self):
        self.styles = plan_config.load_styles(ROOT / 'references' / 'styles.json')

    def test_inspect_lists_nodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'model.glb'
            path.write_bytes(two_part_glb())
            report = inspect_parts.inspect_file(path)
            self.assertTrue(report['selectableParts'])
            self.assertEqual({n['name'] for n in report['nodes']}, {'body', 'lid'})
            self.assertEqual({m['name'] for m in report['materials']}, {'paint', 'trim'})

    def test_plan_and_price_absent(self):
        from glb_clips import read_glb
        inv = inspect_parts.inventory(read_glb(two_part_glb())[0])
        brief = {
            'schemaVersion': 1,
            'title': '示例杯',
            'colorOptions': [{'id': 'paint', 'label': '杯身', 'target': 'paint', 'swatches': ['#ff0000', '#00ff00']}],
            'visibilityOptions': [
                {'id': 'lid', 'label': '杯盖', 'target': 'lid', 'default': True},
                {'id': 'body', 'label': '杯身件', 'target': 'body', 'default': False},
            ],
            'exclusiveGroups': [{'id': 'one', 'optionIds': ['lid', 'body']}],
        }
        plan = plan_config.validate_plan(brief, inv, self.styles)
        self.assertIsNone(plan['pricing'])

    def test_need_split(self):
        inv = {'nodes': [{'name': 'only', 'mesh': 0, 'materials': ['a']}], 'materials': [{'name': 'a'}], 'selectableParts': False, 'externalTextures': []}
        with self.assertRaises(ValueError):
            plan_config.validate_plan({'schemaVersion': 1, 'title': 'x', 'colorOptions': [{'id': 'c', 'label': 'c', 'target': 'a', 'swatches': ['#111111', '#222222']}]}, inv)

    def test_build_http_and_rules(self):
        if not CORE.is_file() or not (CLIP / 'glb_clips.py').is_file():
            self.skipTest('shared cores missing')
        data = two_part_glb()
        from glb_clips import read_glb
        inv = inspect_parts.inventory(read_glb(data)[0])
        plan = plan_config.validate_plan({
            'schemaVersion': 1,
            'title': '示例杯',
            'colorOptions': [{'id': 'paint', 'label': '杯身', 'target': 'paint', 'swatches': ['#ff0000', '#00aa00']}],
            'visibilityOptions': [
                {'id': 'lid', 'label': '杯盖', 'target': 'lid', 'default': True},
                {'id': 'bodyv', 'label': '杯身件', 'target': 'body', 'default': False},
            ],
            'exclusiveGroups': [{'id': 'one', 'optionIds': ['lid', 'bodyv']}],
        }, inv, self.styles)
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / 'skill'
            (skill / 'scripts').mkdir(parents=True)
            for name in ('viewer.js', 'rules.mjs'):
                shutil.copy2(ROOT / 'scripts' / name, skill / 'scripts' / name)
            shutil.copy2(CORE, skill / 'scripts' / 'hi3d-core.mjs')
            shutil.copy2(CLIP / 'glb_clips.py', skill / 'scripts' / 'glb_clips.py')
            model = Path(tmp) / 'model.glb'
            model.write_bytes(data)
            out = Path(tmp) / 'page'
            build_page.write_page(plan, skill, model, out)
            html = (out / 'index.html').read_text(encoding='utf-8')
            self.assertIn('未实现', html)
            report = check_http.check(out)
            self.assertTrue(report['ok'], report)
            test_js = Path(tmp) / 'rules.test.mjs'
            test_js.write_text(
                "import { defaultState, displayMap, priceTotal, setColor, setVisibility } from './skill/scripts/rules.mjs';\n"
                "import assert from 'node:assert/strict';\n"
                "import test from 'node:test';\n"
                f"const plan = {json.dumps(plan, ensure_ascii=False)};\n"
                "test('color targets material', () => {\n"
                "  const state = defaultState(plan);\n"
                "  const next = setColor(plan, state, 'paint', '#00aa00');\n"
                "  assert.equal(next.ok, true);\n"
                "  assert.equal(displayMap(plan, next.state).colors.paint, '#00aa00');\n"
                "});\n"
                "test('exclusive visibility', () => {\n"
                "  let state = defaultState(plan);\n"
                "  const next = setVisibility(plan, state, 'bodyv', true);\n"
                "  assert.equal(next.ok, true);\n"
                "  assert.equal(next.state.visibility.lid, false);\n"
                "  assert.equal(next.state.visibility.bodyv, true);\n"
                "});\n"
                "test('no invented price', () => {\n"
                "  assert.equal(priceTotal(plan, defaultState(plan)), null);\n"
                "});\n",
                encoding='utf-8',
            )
            result = subprocess.run(['node', '--test', str(test_js)], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
