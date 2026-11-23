"""Offline checks for package-external session and short tool results."""
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import session_schema
import tool_result


class SessionAndToolResultTests(unittest.TestCase):
    def test_new_session_stays_outside_the_pack(self):
        doc = session_schema.new_session('lamp-design', task_id='task-1')
        session_schema.validate_session(doc)
        self.assertEqual(doc['schema'], 'pcg.session.v1')
        self.assertEqual(doc['status'], 'running')
        self.assertEqual(doc['refs'], [])
        self.assertEqual(doc['popup_reasons'], [])
        self.assertEqual(doc['injected'], [])
        self.assertEqual(doc['stream']['status'], 'idle')
        with self.assertRaises(ValueError):
            session_schema.new_session('', task_id='task-1')
        legacy = session_schema.new_session('lamp-design', task_id='task-1')
        del legacy['refs']
        session_schema.validate_session(legacy)
        self.assertEqual(legacy['refs'], [])
        del legacy['popup_reasons']
        session_schema.validate_session(legacy)
        self.assertEqual(legacy['popup_reasons'], [])
        del legacy['injected']
        del legacy['stream']
        session_schema.validate_session(legacy)
        self.assertEqual(legacy['injected'], [])
        self.assertEqual(legacy['stream']['status'], 'idle')

    def test_popup_reasons_are_once_per_checkpoint(self):
        doc = session_schema.new_session('lamp-design', task_id='task-1')
        session_schema.mark_popup_reason(doc, reason='stall', checkpoint='build')
        session_schema.mark_popup_reason(doc, reason='stall', checkpoint='build')
        self.assertEqual(session_schema.asked_popup_reasons(doc, 'build'), ['stall'])
        session_schema.mark_popup_reason(doc, reason='exhausting', checkpoint='build')
        self.assertEqual(session_schema.asked_popup_reasons(doc, 'build'), ['stall', 'exhausting'])
        self.assertEqual(session_schema.asked_popup_reasons(doc, 'review'), [])

    def test_injected_load_and_stream_incomplete_are_resumable(self):
        doc = session_schema.new_session('taubin-smooth', task_id='task-1')
        load = ['SKILL.md', 'references/contract.md']
        session_schema.mark_injected(doc, ['SKILL.md'])
        self.assertEqual(session_schema.pending_inject(doc, load), ['references/contract.md'])
        session_schema.mark_stream(doc, status='in_flight', response_id='resp_1')
        session_schema.mark_stream(
            doc, status='incomplete', response_id='resp_1', reason='stream_disconnected')
        self.assertEqual(doc['status'], 'interrupted')
        self.assertEqual(doc['stream']['status'], 'incomplete')
        self.assertEqual(doc['stream']['response_id'], 'resp_1')
        session_schema.mark_stream(doc, status='settled')
        self.assertEqual(doc['stream']['status'], 'settled')
        session_schema.clear_injected(doc)
        self.assertEqual(session_schema.pending_inject(doc, load), load)
        with self.assertRaisesRegex(ValueError, 'package-relative'):
            session_schema.mark_injected(doc, ['../secret'])

    def test_tool_result_is_short_and_typed(self):
        payload = tool_result.tool_result(
            status='ok', summary='submitted geometry', artifacts=['out.glb'],
            next_checkpoint='repair', irreversible=['hi3d.submit'])
        self.assertEqual(payload['schema'], 'pcg.tool_result.v1')
        with self.assertRaises(ValueError):
            tool_result.tool_result(status='ok', summary='')
        with self.assertRaises(ValueError):
            tool_result.tool_result(status='maybe', summary='x')

    def test_append_artifact_keeps_traces_and_rejects_signed_href(self):
        doc = session_schema.new_session('hi3d-game-demo', task_id='task-1')
        session_schema.append_artifact(
            doc, path='runs/a.glb', task='generate', output='glb', href='runs/a.glb', tool='hi3d-api')
        session_schema.append_artifact(
            doc, path='runs/b.glb', task='generate', output='glb', href='runs/b.glb', digest='ff')
        slot = doc['artifacts'][0]
        self.assertEqual(slot['path'], 'runs/b.glb')
        self.assertEqual([event['op'] for event in slot['traces']], ['add', 'sync'])
        session_schema.apply_tool_result(doc, {
            'artifacts': [{'path': 'runs/c.glb', 'task': 'generate', 'output': 'glb', 'href': 'runs/c.glb'}],
        })
        self.assertEqual(len(doc['artifacts'][0]['traces']), 3)
        with self.assertRaisesRegex(ValueError, 'signed'):
            session_schema.append_artifact(
                doc, path='x', href='https://x?X-Amz-Signature=abc', task='generate', output='glb')

    def test_purge_under_root_deletes_cache_file_and_keeps_trace(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        cache = root / 'lod.glb'
        cache.write_bytes(b'lod')
        keep = root / 'hero.glb'
        keep.write_bytes(b'keep')
        doc = session_schema.new_session('hi3d-game-demo', task_id='task-1')
        session_schema.append_artifact(doc, path='lod.glb', task='lod', output='mesh', href='lod.glb')
        removed = session_schema.purge_under_root(doc, [
            {'path': 'lod.glb', 'task': 'lod', 'output': 'mesh', 'retain': 'cache'},
        ], task_root=root)
        self.assertTrue(removed)
        self.assertFalse(cache.exists())
        self.assertTrue(keep.exists())
        self.assertTrue(doc['artifacts'][0]['purged'])
        self.assertEqual(doc['artifacts'][0]['traces'][-1]['op'], 'purge')
        with self.assertRaisesRegex(ValueError, 'keep'):
            session_schema.purge_under_root(doc, [
                {'path': 'hero.glb', 'retain': 'keep'},
            ], task_root=root)

    def test_hi3d_options_accept_agent_surface(self):
        doc = session_schema.new_session('lamp-design', task_id='task-1')
        doc['hi3d_options'] = {
            'identity': 'standard',
            'surface': 'agent',
            'kind': 'model',
            'selected': {'model_type': 'quality'},
        }
        session_schema.validate_session(doc)
        doc['hi3d_options']['surface'] = 'desktop'
        with self.assertRaisesRegex(ValueError, 'surface'):
            session_schema.validate_session(doc)

    def test_hi3d_two_stage_grant_and_once_consume(self):
        doc = session_schema.new_session('lamp-design', task_id='task-1')
        session_schema.begin_hi3d_waiting(doc, checkpoint='generate', kind='model', stage='parameters')
        self.assertEqual(doc['status'], 'waiting_choice')
        self.assertEqual(session_schema.hi3d_waiting_stage(doc), 'parameters')
        session_schema.record_hi3d_selected(doc, kind='model', selected={'version': 'v3.0'})
        self.assertEqual(session_schema.hi3d_waiting_stage(doc), 'billing')
        session_schema.grant_hi3d(doc, scope='once')
        self.assertEqual(doc['status'], 'running')
        self.assertTrue(session_schema.hi3d_submit_ready(doc))
        session_schema.consume_hi3d_once(doc)
        self.assertFalse(session_schema.hi3d_submit_ready(doc))
        session_schema.grant_hi3d(doc, scope='conversation')
        self.assertTrue(session_schema.hi3d_conversation_granted(doc))
        self.assertTrue(session_schema.hi3d_submit_ready(doc, kind='relief'))
        session_schema.revoke_hi3d_grants(doc)
        self.assertEqual(doc['status'], 'waiting_choice')
        self.assertFalse(session_schema.hi3d_conversation_granted(doc))


if __name__ == '__main__':
    unittest.main()
