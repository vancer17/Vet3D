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
import plan_review
import inspect_models
import build_board
import check_http

PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
    '0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082'
)
MP4 = struct.pack('>I', 16) + b'ftypisom' + bytes(4)


def pack_glb(doc, binary=b''):
    payload = json.dumps(doc, separators=(',', ':')).encode()
    payload += b' ' * ((4 - len(payload) % 4) % 4)
    chunks = struct.pack('<I4s', len(payload), b'JSON') + payload
    if binary:
        binary += b'\x00' * ((4 - len(binary) % 4) % 4)
        chunks += struct.pack('<I4s', len(binary), b'BIN\x00') + binary
    return struct.pack('<4sII', b'glTF', 2, 12 + len(chunks)) + chunks


def sample_glb():
    positions = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    doc = {
        'asset': {'version': '2.0'},
        'scene': 0,
        'scenes': [{'nodes': [0]}],
        'nodes': [{'name': 'body', 'mesh': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'material': 0}]}],
        'materials': [{'name': 'paint'}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3', 'min': [0, 0, 0], 'max': [1, 1, 0]}],
        'bufferViews': [{'buffer': 0, 'byteLength': 36}],
        'buffers': [{'byteLength': 36}],
    }
    return pack_glb(doc, positions)


def brief():
    return {
        'schemaVersion': 1,
        'title': '审阅样例',
        'versions': [
            {'id': 'img', 'assetId': 'hero', 'kind': 'image', 'file': 'hero_v1.png', 'label': '图 v1'},
            {'id': 'vid', 'assetId': 'hero', 'kind': 'video', 'file': 'hero_v2.mp4', 'label': '视频 v2', 'durationSeconds': 4},
            {'id': 'mdl', 'assetId': 'hero', 'kind': 'model', 'file': 'hero_v3.glb', 'label': '模型 v3'},
        ],
    }


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.review = plan_review.load_review(ROOT / 'references' / 'review.json')

    def test_ambiguous_filename_needs_asset(self):
        with self.assertRaises(ValueError):
            plan_review.validate_plan({
                'schemaVersion': 1,
                'title': 'x',
                'versions': [{'id': 'a', 'kind': 'image', 'file': 'unrelated.png'}],
            }, self.review)

    def test_mixed_inferred_versions_rejected(self):
        with self.assertRaises(ValueError):
            plan_review.validate_plan({
                'schemaVersion': 1,
                'title': 'x',
                'versions': [
                    {'id': 'a', 'kind': 'image', 'file': 'hero_v1.png'},
                    {'id': 'b', 'kind': 'model', 'file': 'hero_v2.glb'},
                ],
            }, self.review)

    def test_single_layout_and_duration_warning(self):
        plan = plan_review.validate_plan({
            'schemaVersion': 1,
            'title': '单版',
            'versions': [{'id': 'a', 'assetId': 'hero', 'kind': 'image', 'file': 'hero.png'}],
        }, self.review)
        self.assertEqual(plan['layout'], 'single')
        plan = plan_review.validate_plan({
            'schemaVersion': 1,
            'title': '时长',
            'versions': [
                {'id': 'a', 'assetId': 'hero', 'kind': 'video', 'file': 'a.mp4', 'durationSeconds': 3},
                {'id': 'b', 'assetId': 'hero', 'kind': 'video', 'file': 'b.mp4', 'durationSeconds': 8},
            ],
        }, self.review)
        self.assertIn('时长不同', plan['durationWarning'])

    def test_build_http_and_notes(self):
        if not CORE.is_file() or not (CLIP / 'glb_clips.py').is_file():
            self.skipTest('shared cores missing')
        plan = plan_review.validate_plan(brief(), self.review)
        self.assertEqual(plan['layout'], 'side_by_side')
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / 'skill'
            (skill / 'scripts').mkdir(parents=True)
            for name in ('board.js', 'notes.mjs', 'inspect_models.py', 'glb_clips.py'):
                src = ROOT / 'scripts' / name if name != 'glb_clips.py' else CLIP / 'glb_clips.py'
                shutil.copy2(src, skill / 'scripts' / name)
            shutil.copy2(CORE, skill / 'scripts' / 'hi3d-core.mjs')
            media = Path(tmp) / 'media'
            media.mkdir()
            (media / 'hero_v1.png').write_bytes(PNG)
            (media / 'hero_v2.mp4').write_bytes(MP4)
            (media / 'hero_v3.glb').write_bytes(sample_glb())
            reports = inspect_models.inspect_models(plan, media)
            self.assertTrue(all(item['ok'] for item in reports))
            out = Path(tmp) / 'board'
            build_board.write_board(plan, skill, media, out)
            html = (out / 'index.html').read_text(encoding='utf-8')
            self.assertIn('未实现', html)
            report = check_http.check(out)
            self.assertTrue(report['ok'], report)
            self.assertIn('media/hero_v1.png', report['files'])
            self.assertIn('media/hero_v2.mp4', report['files'])
            self.assertIn('media/hero_v3.glb', report['files'])
            test_js = Path(tmp) / 'notes.test.mjs'
            test_js.write_text(
                "import { addNote, editNote, exportNotes, importNotes, loadState, notesForVersion, setNoteStatus } from './skill/scripts/notes.mjs';\n"
                "import { encode } from './skill/scripts/hi3d-core.mjs';\n"
                "import assert from 'node:assert/strict';\n"
                "import test from 'node:test';\n"
                f"const plan = {json.dumps(plan, ensure_ascii=False)};\n"
                "const store = new Map();\n"
                "const storage = { getItem: (k) => store.has(k) ? store.get(k) : null, setItem: (k, v) => store.set(k, v) };\n"
                "test('bind to original version', () => {\n"
                "  const added = addNote(storage, plan, { versionId: 'img', text: '亮一点', loc: { u: 0.2, v: 0.8 } });\n"
                "  assert.equal(added.ok, true);\n"
                "  assert.equal(notesForVersion(added.state, 'vid').length, 0);\n"
                "  assert.equal(notesForVersion(added.state, 'img')[0].versionId, 'img');\n"
                "  const edited = editNote(storage, plan, added.note.id, { text: '再暗一点' });\n"
                "  assert.equal(edited.note.text, '再暗一点');\n"
                "  const done = setNoteStatus(storage, plan, added.note.id, 'done');\n"
                "  assert.equal(done.note.status, 'done');\n"
                "  const again = loadState(storage, plan);\n"
                "  assert.equal(again.notes[0].text, '再暗一点');\n"
                "});\n"
                "test('import failure keeps previous', () => {\n"
                "  const before = exportNotes(storage, plan);\n"
                "  const bad = importNotes(storage, plan, '{not json');\n"
                "  assert.equal(bad.ok, false);\n"
                "  assert.equal(exportNotes(storage, plan), before);\n"
                "  const other = encode('other-game', 1, { notes: [], nextId: 1, syncCamera: false, syncPlayback: false });\n"
                "  const mismatch = importNotes(storage, plan, other);\n"
                "  assert.equal(mismatch.ok, false);\n"
                "  assert.equal(exportNotes(storage, plan), before);\n"
                "});\n"
                "test('replace needs authorization', () => {\n"
                "  const before = exportNotes(storage, plan);\n"
                "  const empty = encode(plan.appId, 1, { notes: [], nextId: 1, syncCamera: false, syncPlayback: false });\n"
                "  const denied = importNotes(storage, plan, empty, { mode: 'replace' });\n"
                "  assert.equal(denied.ok, false);\n"
                "  assert.equal(exportNotes(storage, plan), before);\n"
                "  const replaced = importNotes(storage, plan, empty, { mode: 'replace', authorizeOverwrite: true });\n"
                "  assert.equal(replaced.ok, true);\n"
                "  assert.equal(replaced.backup, before);\n"
                "  assert.equal(loadState(storage, plan).notes.length, 0);\n"
                "});\n",
                encoding='utf-8',
            )
            result = subprocess.run(['node', '--test', str(test_js)], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
