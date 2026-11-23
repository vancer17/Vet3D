"""Offline checks for render resume identity and explicit scene specifications."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render_video_chunks import matching_checkpoint, read_spec, render_sources


class RenderSpecTests(unittest.TestCase):
    def test_changed_frame_count_source_or_profile_cannot_reuse_cache(self):
        sources = {'render_scene.py': 'first'}
        record = dict(render_sources=sources, source_sha256='synthetic', frame_count=2, resolution=[864, 768], fps=24, engine='BLENDER_EEVEE')
        self.assertTrue(matching_checkpoint(record, 'synthetic', 2, sources))
        self.assertFalse(matching_checkpoint(record, 'different', 2, sources))
        self.assertFalse(matching_checkpoint(record, 'synthetic', 3, sources))
        self.assertFalse(matching_checkpoint(dict(record, fps=30), 'synthetic', 2, sources))

    def test_shared_render_source_invalidates_only_render_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ['render_video_chunks.py','render_frame_chunk.py','render_scene.py','render_engine.py','stage_cli.py','geometry.py']:
                (root/name).write_text('fixture')
            before = render_sources(root)
            (root/'geometry.py').write_text('unrelated modeling source')
            self.assertEqual(before, render_sources(root))
            (root/'render_engine.py').write_text('changed shared renderer')
            after = render_sources(root)
            self.assertNotEqual(before, after)
            record = dict(render_sources=before,source_sha256='same',frame_count=2,resolution=[864,768],fps=24,engine='BLENDER_EEVEE')
            self.assertTrue(matching_checkpoint(record,'same',2,before))
            self.assertFalse(matching_checkpoint(record,'same',2,after))
            del record['render_sources']
            self.assertFalse(matching_checkpoint(record,'same',2,before))

    def test_spec_rejects_ambiguous_tags_and_invalid_frame_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'spec.json'
            p.write_text(json.dumps([dict(tag='motion', frames=2)]))
            self.assertEqual(read_spec(p)[0]['frames'], 2)
            for value in [[], [dict(tag='../escape', frames=2)], [dict(tag='a', frames=True)], [dict(tag='a', frames=0)], [dict(tag='a', frames=2), dict(tag='a', frames=3)]]:
                p.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    read_spec(p)


if __name__ == '__main__':
    unittest.main()
