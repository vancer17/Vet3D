import unittest
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import plan_app
import build_app
import check_http

CORE_SRC = Path(__file__).resolve().parents[3] / 'skills' / 'game-save' / 'scripts' / 'hi3d-core.mjs'


class AppPlanTests(unittest.TestCase):
    def setUp(self):
        self.examples = plan_app.load_examples(ROOT / 'references' / 'examples.json')

    def test_preset_keeps_example_flag(self):
        plan = plan_app.validate_brief({'schemaVersion': 1, 'examplePreset': 'appointment'}, self.examples)
        self.assertEqual(plan['layout'], 'adaptive')
        self.assertTrue(all(item.get('example') is True for item in plan['records']))

    def test_rejects_example_as_real(self):
        brief = {
            'schemaVersion': 1,
            'actor': '前台',
            'scene': '到店',
            'entity': '预约',
            'primaryAction': '确认',
            'fields': [{'id': 'guest', 'label': '姓名', 'type': 'string', 'required': True}],
            'records': [{'id': '1', 'guest': 'A', 'example': True}],
        }
        with self.assertRaises(ValueError):
            plan_app.validate_brief(brief)

    def test_user_record_without_example_ok(self):
        brief = {
            'schemaVersion': 1,
            'actor': '前台',
            'scene': '到店',
            'entity': '预约',
            'primaryAction': '确认',
            'fields': [{'id': 'guest', 'label': '姓名', 'type': 'string', 'required': True}],
            'records': [{'id': '1', 'guest': '张三'}],
        }
        plan = plan_app.validate_brief(brief)
        self.assertEqual(plan['dataSource'], 'user')


class AppBuildTests(unittest.TestCase):
    def test_http_and_records(self):
        if not CORE_SRC.is_file():
            self.skipTest('game-save core missing')
        plan = plan_app.validate_brief({'schemaVersion': 1, 'examplePreset': 'works'}, plan_app.load_examples(ROOT / 'references' / 'examples.json'))
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / 'skill'
            skill.mkdir()
            (skill / 'scripts').mkdir()
            shutil.copy2(ROOT / 'scripts' / 'app.js', skill / 'scripts' / 'app.js')
            shutil.copy2(ROOT / 'scripts' / 'records.mjs', skill / 'scripts' / 'records.mjs')
            shutil.copy2(CORE_SRC, skill / 'scripts' / 'hi3d-core.mjs')
            out = Path(tmp) / 'app'
            build_app.write_app(plan, skill, out)
            self.assertTrue((out / 'index.html').is_file())
            html = (out / 'index.html').read_text(encoding='utf-8')
            self.assertIn('未实现', html)
            self.assertNotRegex(html, r'<button[^>]*>登录')
            report = check_http.check(out)
            self.assertTrue(report['ok'])
            self.assertEqual(report['files']['records.mjs']['status'], 200)
            test_js = Path(tmp) / 'records.test.mjs'
            test_js.write_text(
                "import { createRecord, exportBackup, fieldErrors, importBackup, loadState } from './skill/scripts/records.mjs';\n"
                "import { encode } from './skill/scripts/hi3d-core.mjs';\n"
                "import assert from 'node:assert/strict';\n"
                "import test from 'node:test';\n"
                f"const plan = {json.dumps(plan, ensure_ascii=False)};\n"
                "const store = new Map();\n"
                "const storage = { getItem: (k) => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, v) };\n"
                "test('required field', () => {\n"
                "  const errors = fieldErrors(plan, { title: '' });\n"
                "  assert.ok(errors.title);\n"
                "});\n"
                "test('create persist reload', () => {\n"
                "  const created = createRecord(storage, plan, { title: '新作品', status: '草稿' });\n"
                "  assert.equal(created.ok, true);\n"
                "  const again = loadState(storage, plan);\n"
                "  assert.ok(again.records.some((r) => r.id === created.record.id));\n"
                "});\n"
                "test('import failure keeps previous', () => {\n"
                "  const before = exportBackup(storage, plan);\n"
                "  const bad = importBackup(storage, plan, '{not json');\n"
                "  assert.equal(bad.ok, false);\n"
                "  assert.equal(exportBackup(storage, plan), before);\n"
                "  const other = encode('other-game', 1, { records: [], nextId: 1 });\n"
                "  const mismatch = importBackup(storage, plan, other);\n"
                "  assert.equal(mismatch.ok, false);\n"
                "  assert.equal(exportBackup(storage, plan), before);\n"
                "});\n",
                encoding='utf-8',
            )
            result = subprocess.run(['node', '--test', str(test_js)], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
