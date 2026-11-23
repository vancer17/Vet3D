"""Offline contracts for collision classification and dependency-aware recovery."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from collision import segment_hits_triangle
import run


class GeometryTests(unittest.TestCase):
    def test_crossing_excludes_bvh_false_positive_and_tangency(self):
        triangle = np.array([[[0., 0, 0], [1, 0, 0], [0, 1, 0]]] * 3)
        starts = np.array([[.2, .2, -1], [.8, .8, -1], [.2, .2, 0]])
        ends = np.array([[.2, .2, 1], [.8, .8, 1], [.2, .2, 1]])
        np.testing.assert_array_equal(segment_hits_triangle(starts, ends, triangle), [True, False, False])


class WorkflowTests(unittest.TestCase):
    def test_glb_reader_change_invalidates_delivery_without_rebaking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {'output': str(root/'out'), 'blender': sys.executable,
                      'instant_meshes': sys.executable, 'remesh_face_goal': 10}
            with patch.object(run, 'SCRIPTS', root):
                stages = run.stages(config, root/'config.json')
                for stage in stages:
                    for name in stage['scripts']: (root/name).write_text('fixture')
                def hashes():
                    return {s['name']: run.stage_fingerprint(s, config,
                        {d: {'outputs': {'same': 'hash'}} for d in s['dependencies']}, {})
                        for s in stages}
                before = hashes()
                (root/'glb_clips.py').write_text('changed container reader')
                after = hashes()
                self.assertNotEqual(before['deliver'], after['deliver'])
                for name in ['bake', 'prepare', 'package_review']:
                    self.assertEqual(before[name], after[name])

    def test_sheet_source_invalidates_packaging_without_repeating_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config={'output':str(root/'out'),'blender':sys.executable,'instant_meshes':sys.executable,'remesh_face_goal':10}
            with patch.object(run,'SCRIPTS',root):
                stages=run.stages(config,root/'config.json')
                for stage in stages:
                    for name in stage['scripts']: (root/name).write_text('fixture')
                def hashes():
                    return {s['name']:run.stage_fingerprint(s,config,{d:{'outputs':{'same':'hash'}} for d in s['dependencies']},{}) for s in stages}
                before=hashes();(root/'image_sheet.py').write_text('changed sheet');after=hashes()
                self.assertNotEqual(before['package_review'],after['package_review'])
                self.assertEqual(before['review'],after['review'])
                self.assertEqual(before['bake'],after['bake'])

    def test_encoding_source_only_invalidates_requested_video_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            face = root/'face.json'; face.write_text('{"controls":{"fields":[]}}')
            config = {'output':str(root/'out'),'blender':sys.executable,'instant_meshes':sys.executable,
                      'remesh_face_goal':10,'face_config':str(face),'video_frames_per_control':1}
            with patch.object(run,'SCRIPTS',root):
                video = run.stages(config,root/'config.json')
                static = run.stages(dict(config,video_frames_per_control=0),root/'config.json')
                for s in video:
                    for name in s['scripts']: (root/name).write_text('fixture')
                targets = [next(s for s in stages if s['name']=='package_review') for stages in [video,static]]
                def hashes():
                    return [run.stage_fingerprint(s,config,{d:{'outputs':{'same':'hash'}} for d in s['dependencies']},{}) for s in targets]
                before = hashes(); (root/'encode_sequence.py').write_text('changed codec'); after = hashes()
                self.assertNotEqual(before[0],after[0]); self.assertEqual(before[1],after[1])

    def test_head_preview_changes_invalidate_consumers_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {'output': str(root/'out'), 'blender': sys.executable,
                      'instant_meshes': sys.executable, 'remesh_face_goal': 10}
            with patch.object(run, 'SCRIPTS', root):
                stages = run.stages(config, root/'config.json')
                for stage in stages:
                    for name in stage['scripts']:
                        (root/name).write_text('fixture')
                def hashes():
                    return {s['name']: run.stage_fingerprint(s, config,
                            {d: {'outputs': {'same': 'hash'}} for d in s['dependencies']}, {})
                            for s in stages}
                before = hashes()
                (root/'head_preview.py').write_text('changed preview')
                after = hashes()
                self.assertNotEqual(before['review'], after['review'])
                self.assertNotEqual(before['prepare'], after['prepare'])
                for name in ['bake', 'remesh', 'package_review']:
                    self.assertEqual(before[name], after[name], name)

    def stage(self, root, name, dependencies=(), keys=(), fail=False):
        code = "raise SystemExit(2)" if fail else "from pathlib import Path; Path(" + repr(str(root / name)) + ").write_text('valid')"
        return dict(name=name, command=[sys.executable, '-c', code], outputs=[name],
                    dependencies=list(dependencies), keys=list(keys), scripts=[])

    def read(self, root):
        return json.loads((root / 'timing_summary.json').read_text())

    def test_shared_triangle_code_invalidates_local_consumers(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);scripts=root/'scripts';scripts.mkdir()
            config={'output':str(root/'out'),'blender':sys.executable,'instant_meshes':sys.executable,'remesh_face_goal':10}
            with patch.object(run,'SCRIPTS',scripts):
                stages=run.stages(config,root/'config.json')
                for stage in stages:
                    for name in stage['scripts']:(scripts/name).write_text('fixture source')
                targets=[s for s in stages if s['name'] in ['lowpoly_rig','lowpoly_validate','deliver','metrics','prepare']]
                def fingerprint(stage):
                    completed={d:{'outputs':{'same.stl':'same-hash'}} for d in stage['dependencies']}
                    return run.stage_fingerprint(stage,config,completed,{})
                before={s['name']:fingerprint(s) for s in targets}
                (scripts/'triangle_arrays.py').write_text('changed triangle implementation')
                after={s['name']:fingerprint(s) for s in targets}
                self.assertEqual(before['prepare'],after['prepare'])
                for name in ['lowpoly_rig','lowpoly_validate','deliver','metrics']:
                    self.assertNotEqual(before[name],after[name],name)

    def test_failure_resume_and_tampered_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config={'output':str(root)}
            bad=[self.stage(root,'a'),self.stage(root,'b',['a'],fail=True),self.stage(root,'c',['b'])]
            with patch.object(run,'stages',return_value=bad):
                with self.assertRaises(RuntimeError):run.workflow(config)
            first=self.read(root)
            self.assertEqual([r['status'] for r in first['stages']],['completed','failed','skipped'])
            self.assertTrue(all(r['elapsed_seconds']>=0 and '+' in r['started_at'] for r in first['stages']))
            good=[self.stage(root,'a'),self.stage(root,'b',['a']),self.stage(root,'c',['b'])]
            with patch.object(run,'stages',return_value=good):
                run.workflow(config)
                second=self.read(root)
                self.assertEqual(second['stages'][0]['status'],'skipped')
                self.assertEqual(second['stages'][0]['reused_attempt_id'],first['attempt_id'])
                (root/'a').write_text('tampered')
                run.workflow(config)
            third=self.read(root)
            self.assertEqual(third['stages'][0]['status'],'completed')
            self.assertEqual((root/'a').read_text(),'valid')
            # Identical restored content allows its dependents to remain cached.
            self.assertEqual([r['status'] for r in third['stages'][1:]],['skipped','skipped'])
            self.assertEqual(len((root/'timings.jsonl').read_text().splitlines()),9)

    def test_local_setting_change_preserves_unrelated_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config={'output':str(root),'texture_size':4096}
            stages=[self.stage(root,'geometry'),self.stage(root,'texture',['geometry'],['texture_size']),self.stage(root,'validation',['geometry'])]
            with patch.object(run,'stages',return_value=stages):
                run.workflow(config);config['texture_size']=2048;run.workflow(config)
                self.assertEqual([r['status'] for r in self.read(root)['stages']],['skipped','completed','skipped'])
                # An incomplete manifest must not silently accept a missing product.
                manifest=json.loads((root/'workflow.json').read_text());manifest['completed']['validation']['outputs']={}
                (root/'workflow.json').write_text(json.dumps(manifest));run.workflow(config)
                self.assertEqual(self.read(root)['stages'][-1]['status'],'completed')

    def test_unknown_interruption_retains_missing_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'workflow.json').write_text(json.dumps({'task_id':'task','attempt_id':'killed','status':'running','started_at':'2026-01-01T00:00:00+00:00'}))
            with patch.object(run,'stages',return_value=[]):run.workflow({'output':str(root)})
            record=json.loads((root/'timings.jsonl').read_text().splitlines()[0])
            self.assertEqual(record['status'],'interrupted');self.assertIsNone(record['elapsed_seconds']);self.assertIsNone(record['ended_at'])


if __name__=='__main__':unittest.main()
