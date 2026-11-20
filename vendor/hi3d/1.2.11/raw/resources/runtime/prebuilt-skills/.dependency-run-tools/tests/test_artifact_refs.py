"""Offline checks for conversation artifact aliases."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import artifact_refs
import session_schema


class ArtifactRefTests(unittest.TestCase):
    def test_mark_resolve_and_rewrite_last_token(self):
        doc = session_schema.new_session('replace-brief', task_id='task-1')
        artifact_refs.mark_ref(doc, name='statue-crop', path='crops/statue.png', label='左侧雕像', at='2026-01-01T00:00:00+00:00')
        artifact_refs.mark_ref(doc, name='overlay', path='overlay.png', at='2026-01-01T00:00:01+00:00')
        self.assertEqual(artifact_refs.resolve_ref(doc, '@statue-crop')['path'], 'crops/statue.png')
        self.assertEqual(artifact_refs.resolve_ref(doc, 'ref:last')['name'], 'overlay')
        text = artifact_refs.rewrite_instruction(
            'python x.py --image @statue-crop --note keep @unknown and mail a@b.com',
            doc,
        )
        self.assertEqual(text, 'python x.py --image crops/statue.png --note keep @unknown and mail a@b.com')
        self.assertEqual(artifact_refs.rewrite_instruction('use @last', doc), 'use overlay.png')

    def test_mark_slot_and_reject_url_or_reserved_name(self):
        doc = session_schema.new_session('replace-brief', task_id='task-1')
        session_schema.append_artifact(doc, path='crops/statue.png', task='locate', output='crops')
        artifact_refs.mark_slot(doc, name='statue-crop', task='locate', output='crops', label='裁切')
        self.assertEqual(doc['refs'][0]['path'], 'crops/statue.png')
        with self.assertRaises(ValueError):
            artifact_refs.mark_ref(doc, name='last', path='x.png')
        with self.assertRaises(ValueError):
            artifact_refs.mark_ref(doc, name='ok', path='https://example.com/a.png')
        with self.assertRaises(ValueError):
            artifact_refs.resolve_ref(doc, '@missing')

    def test_cli_round_trip_and_task_root_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            session_path = root / 'session.json'
            crop = root / 'crops'
            crop.mkdir()
            file_path = crop / 'statue.png'
            file_path.write_bytes(b'png')
            session_path.write_text(json.dumps(session_schema.new_session('replace-brief', task_id='t1')))
            self.assertEqual(artifact_refs.main([
                'mark', '--session', str(session_path),
                '--name', 'statue-crop', '--path', 'crops/statue.png',
                '--label', '左侧雕像',
            ]), 0)
            self.assertEqual(artifact_refs.main([
                'resolve', '--session', str(session_path),
                '--ref', '@statue-crop', '--task-root', str(root),
            ]), 0)
            loaded = artifact_refs.load_session(session_path)
            found = artifact_refs.resolve_ref(loaded, '@statue-crop', task_root=root)
            self.assertTrue(found['exists'])
            outside = session_schema.new_session('replace-brief', task_id='t1')
            artifact_refs.mark_ref(outside, name='escape', path=str(Path(folder).resolve().parent / 'secret.png'))
            with self.assertRaises(ValueError):
                artifact_refs.resolve_ref(outside, '@escape', task_root=root)


if __name__ == '__main__':
    unittest.main()
