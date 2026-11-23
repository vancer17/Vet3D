import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = Path(__file__).resolve().parents[3] / 'skills' / 'game-save' / 'scripts' / 'hi3d-core.mjs'
sys.path.insert(0, str(ROOT / 'scripts'))
import plan_tour
import layout
import build_hall
import check_http

PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
    '0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082'
)


class ExhibitionTests(unittest.TestCase):
    def setUp(self):
        self.modes = plan_tour.load_modes(ROOT / 'references' / 'modes.json')

    def test_pending_filename_and_virtual_note(self):
        plan = plan_tour.validate_plan({
            'schemaVersion': 1,
            'title': '示例展',
            'exhibits': [
                {'id': 'a', 'file': 'alpha.png', 'kind': 'image'},
                {'id': 'b', 'kind': 'missing'},
            ],
        }, self.modes)
        self.assertTrue(plan['exhibits'][0]['pending'])
        self.assertEqual(plan['exhibits'][0]['title'], 'alpha')
        self.assertEqual(plan['space']['kind'], 'virtual')
        self.assertFalse(plan['space']['surveyed'])
        self.assertEqual(plan['mode'], 'both')
        self.assertEqual(len(layout.auto_layout(2)), 2)

    def test_existing_space_requires_file(self):
        with self.assertRaises(ValueError):
            plan_tour.validate_plan({
                'schemaVersion': 1,
                'title': '展',
                'exhibits': [{'id': 'a', 'title': 'A', 'caption': '说明', 'kind': 'missing'}],
                'space': {'kind': 'existing'},
            }, self.modes)

    def test_build_http_and_tour(self):
        if not CORE.is_file():
            self.skipTest('game-save core missing')
        plan = plan_tour.validate_plan({
            'schemaVersion': 1,
            'title': '示例展',
            'exhibits': [
                {'id': 'a', 'file': 'alpha.png', 'kind': 'image', 'title': '甲', 'caption': '甲说明'},
                {'id': 'b', 'file': 'beta.png', 'kind': 'image', 'title': '乙', 'caption': '乙说明'},
                {'id': 'c', 'kind': 'missing', 'title': '丙', 'caption': '待补'},
            ],
        }, self.modes)
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / 'skill'
            (skill / 'scripts').mkdir(parents=True)
            for name in ('hall.js', 'tour.mjs'):
                shutil.copy2(ROOT / 'scripts' / name, skill / 'scripts' / name)
            shutil.copy2(CORE, skill / 'scripts' / 'hi3d-core.mjs')
            media = Path(tmp) / 'media'
            media.mkdir()
            (media / 'alpha.png').write_bytes(PNG)
            (media / 'beta.png').write_bytes(PNG)
            out = Path(tmp) / 'hall'
            build_hall.write_hall(plan, skill, media, out)
            self.assertTrue((out / 'media' / 'alpha.png').is_file())
            report = check_http.check(out)
            self.assertTrue(report['ok'], report)
            self.assertIn('media/alpha.png', report['files'])
            test_js = Path(tmp) / 'tour.test.mjs'
            test_js.write_text(
                "import { createState, nextStop, openHotspot, pauseTour, resumeTour, returnToStart, routeComplete, startTour, userInteract } from './skill/scripts/tour.mjs';\n"
                "import assert from 'node:assert/strict';\n"
                "import test from 'node:test';\n"
                f"const plan = {json.dumps(plan, ensure_ascii=False)};\n"
                "test('hotspot matches exhibit', () => {\n"
                "  const opened = openHotspot(plan, createState(plan), 'a');\n"
                "  assert.equal(opened.ok, true);\n"
                "  assert.equal(opened.exhibit.id, 'a');\n"
                "  const missing = openHotspot(plan, createState(plan), 'c');\n"
                "  assert.equal(missing.placeholder, true);\n"
                "  assert.equal(openHotspot(plan, createState(plan), 'nope').ok, false);\n"
                "});\n"
                "test('complete route pause resume home', () => {\n"
                "  let state = startTour(plan, createState(plan)).state;\n"
                "  state = pauseTour(state);\n"
                "  assert.equal(nextStop(plan, state).ok, false);\n"
                "  state = resumeTour(state);\n"
                "  state = nextStop(plan, state).state;\n"
                "  state = nextStop(plan, state).state;\n"
                "  state = nextStop(plan, state).state;\n"
                "  assert.equal(routeComplete(plan, state), true);\n"
                "  state = returnToStart(plan, state);\n"
                "  assert.equal(state.atStart, true);\n"
                "  assert.equal(state.current, 'a');\n"
                "});\n"
                "test('manual hotspot pauses auto', () => {\n"
                "  let state = startTour(plan, createState(plan)).state;\n"
                "  state = userInteract(state);\n"
                "  assert.equal(state.paused, true);\n"
                "});\n",
                encoding='utf-8',
            )
            result = subprocess.run(['node', '--test', str(test_js)], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
