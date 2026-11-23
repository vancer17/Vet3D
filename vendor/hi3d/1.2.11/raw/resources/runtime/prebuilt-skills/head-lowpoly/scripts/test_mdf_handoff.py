"""Verify offline Runtime handoff, provenance checks and the workflow pause boundary."""
import hashlib
import json
from pathlib import Path
import tempfile
import sys
import unittest
import zipfile
from unittest.mock import patch

import mdf_handoff as handoff
import run


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = {'retopology_backend': 'runtime', 'output': str(self.root), 'remesh_face_goal': 20000}
        (self.root / 'working_surface.glb').write_bytes(b'fixture working geometry')

    def result(self, status='SUCCEEDED'):
        plan = handoff.request_plan(self.config)
        artifact = Path(plan['outputDir']) / 'hi3d-model_obj.zip'
        artifact.parent.mkdir(exist_ok=True)
        artifact.write_bytes(b'fixture result geometry')
        record = {'status': status, 'httpStatus': 200, 'outputDir': plan['outputDir'],
                  'request': {'capability': plan['capability'], 'params': plan['params']},
                  'response': {'code': 0, 'status': status, 'requestId': 'fixture'},
                  'downloads': {'model_obj': {'path': str(artifact), 'sha256': handoff.digest(artifact)}}}
        record['fingerprint'] = hashlib.sha256(json.dumps({
            'capability': plan['capability'], 'params': plan['params'],
            'fileHash': handoff.digest(plan['file']), 'output': plan['outputDir']}, sort_keys=True).encode()).hexdigest()
        job = Path(plan['jobPath'])
        job.write_text(json.dumps(record))
        return record, job, artifact

    def test_missing_result_writes_plan_without_creating_a_job(self):
        with self.assertRaises(handoff.WaitingForRetopology):
            handoff.prepare_handoff(self.config)
        plan = json.loads((self.root / 'retopology-request.json').read_text())
        self.assertEqual(plan['tool'], 'mdf_api')
        self.assertEqual(plan['arguments']['params'], {'face': 20000, 'face_type': 'quads', 'topology_method': 'standard'})
        self.assertFalse(Path(plan['arguments']['jobPath']).exists())

    def test_success_is_read_only_and_bound_to_actual_artifact(self):
        record, job, artifact = self.result()
        original = job.read_bytes()
        self.assertEqual(handoff.prepare_handoff(self.config), artifact)
        self.assertEqual(job.read_bytes(), original)
        artifact.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'missing or changed'):
            handoff.resolve_result(self.config)

    def test_changed_input_or_budget_cannot_reuse_the_remote_job(self):
        self.result()
        self.config['remesh_face_goal'] = 10000
        with self.assertRaisesRegex(ValueError, 'does not match'):
            handoff.resolve_result(self.config)
        self.config['remesh_face_goal'] = 20000
        (self.root / 'working_surface.glb').write_bytes(b'different input')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            handoff.resolve_result(self.config)

    def test_unknown_response_is_retained_and_download_failure_can_resume(self):
        record, job, artifact = self.result('UNKNOWN')
        original = job.read_bytes()
        with self.assertRaisesRegex(handoff.WaitingForRetopology, 'do not resubmit'):
            handoff.prepare_handoff(self.config)
        self.assertEqual(job.read_bytes(), original)
        record['status'] = record['response']['status'] = 'SUCCEEDED'
        record['downloads'] = {}
        job.write_text(json.dumps(record))
        with self.assertRaisesRegex(handoff.WaitingForRetopology, 'download'):
            handoff.resolve_result(self.config)

    def test_success_requires_exact_status_and_safe_download_path(self):
        record, job, artifact = self.result()
        record['response']['code'] = False
        job.write_text(json.dumps(record))
        with self.assertRaises(handoff.WaitingForRetopology):handoff.resolve_result(self.config)
        record['response']['code'] = 0
        record['downloads']['model_obj']['path'] = str(self.root / 'outside.zip')
        job.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'artifact path'):handoff.resolve_result(self.config)

    def test_workflow_pauses_before_remesh_and_does_not_run_bake(self):
        stages = [dict(name='remesh', command=['unused'], outputs=['source_quads.obj'], keys=[], scripts=[], dependencies=[]),
                  dict(name='bake', command=['unused'], outputs=[], keys=[], scripts=[], dependencies=['remesh'])]
        with patch.object(run, 'stages', return_value=stages), patch.object(run, 'run_stage') as execute:
            with self.assertRaises(handoff.WaitingForRetopology):run.workflow(self.config)
            execute.assert_not_called()
        summary = json.loads((self.root / 'timing_summary.json').read_text())
        self.assertEqual(summary['status'], 'waiting_retopology')
        self.assertEqual([row['status'] for row in summary['stages']], ['waiting', 'skipped'])

    def test_stage_graph_retains_original_high_bake(self):
        config = dict(self.config, blender='blender', diagnostic_previews=False)
        stages = {s['name']: s for s in run.stages(config, self.root / 'resolved_config.json')}
        self.assertIn('working_surface.glb', stages['working_surface']['outputs'])
        self.assertIn('import', stages['remesh']['command'])
        self.assertIn('mdf_handoff.py', stages['remesh']['scripts'])
        self.assertTrue(any(arg.endswith('bake.py') for arg in stages['bake']['command']))
        self.assertIn('textures/Lowpoly_Normal.png', stages['bake']['outputs'])

    def test_obj_zip_reads_only_geometry_and_requires_one_obj(self):
        archive = self.root / 'model.zip'
        target = self.root / 'geometry.obj'
        with zipfile.ZipFile(archive, 'w') as package:
            package.writestr('../head.obj', 'mtllib ../../external.mtl\nv 0 0 0\nf 1 2 3 4\n')
            package.writestr('../../unexpected.txt', 'do not extract')
        handoff.unpack_geometry(archive, target)
        self.assertEqual(target.read_text(), 'v 0 0 0\nf 1 2 3 4\n')
        with zipfile.ZipFile(archive, 'a') as package:
            package.writestr('second.obj', 'v 0 0 0')
        with self.assertRaisesRegex(ValueError, 'exactly one OBJ'):
            handoff.unpack_geometry(archive, target)

    def test_old_glb_only_record_cannot_resume_as_quads(self):
        record, job, artifact = self.result()
        record['downloads']['model_glb'] = record['downloads'].pop('model_obj')
        job.write_text(json.dumps(record))
        with self.assertRaises(handoff.WaitingForRetopology):
            handoff.resolve_result(self.config)

    def test_resume_reuses_preparation_and_import_cache(self):
        def stage(name, filename, dependencies=(), keys=()):
            return dict(name=name, command=[sys.executable, '-c',
                'from pathlib import Path; Path(' + repr(str(self.root / filename)) + ').write_bytes(b"fixture working geometry")'],
                outputs=[filename], dependencies=list(dependencies), keys=list(keys), scripts=[])
        stages = [stage('working_surface', 'working_surface.glb'),
                  stage('remesh', 'source_quads.obj', ['working_surface'], ['retopology_job', 'retopology_obj']),
                  stage('deliver', 'delivery.json', ['remesh'])]
        with patch.object(run, 'stages', return_value=stages):
            with self.assertRaises(handoff.WaitingForRetopology):run.workflow(self.config)
            self.result()
            self.config['retopology_job'] = handoff.request_plan(self.config)['jobPath']
            run.workflow(self.config)
            summary = json.loads((self.root / 'timing_summary.json').read_text())
            self.assertEqual([r['status'] for r in summary['stages']], ['skipped', 'completed', 'completed'])
            run.workflow(self.config)
            summary = json.loads((self.root / 'timing_summary.json').read_text())
            self.assertEqual([r['status'] for r in summary['stages']], ['skipped'] * 3)


if __name__ == '__main__':
    unittest.main()
