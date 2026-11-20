"""Synthetic checks for ingest-time pcg sidecars."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import pcg_check
from pcg_yaml import dump, load


class PcgCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        for name in ('tools', 'skills', 'workflows'):
            (self.repo / name).mkdir()

    def write_entry(self, owner, *, with_pcg=True, irreversible=(), confirm=None):
        path = self.repo / owner
        path.mkdir(parents=True)
        (path / 'SKILL.md').write_text('---\nname: ' + path.name + '\ndescription: fixture\n---\n')
        (path / 'package.json').write_text(json.dumps({'schema': 1, 'files': {}, 'requires': []}))
        if not with_pcg:
            return path
        kind = 'agent_skill' if owner.startswith('skills/') else 'agent_workflow'
        run = {
            'id': 'run', 'say': '执行能力', 'rollback_to': 'input', 'load': ['SKILL.md'],
            'irreversible': list(irreversible),
        }
        if confirm is True or irreversible:
            run['confirm_required'] = True
        if confirm is False:
            run['confirm_required'] = False
        routes = {
            'kind': kind, 'partition': 'software', 'entry': 'SKILL.md',
            'ui': {'option_buttons': True},
            'checkpoints': [
                {'id': 'input', 'say': '确认输入', 'rollback_to': None, 'load': ['SKILL.md'], 'irreversible': []},
                run,
                {'id': 'review', 'say': '核对产物', 'rollback_to': 'run', 'load': ['SKILL.md'], 'irreversible': []},
            ],
            'routes': [
                {'id': 'main', 'summary': 'fixture', 'nodes': ['input', 'run', 'review']},
                {'id': 'skip', 'summary': 'skip run', 'nodes': ['input', 'review']},
            ],
            'choices_example': [
                {'id': 'go', 'title': '继续执行', 'route': 'main'},
                {'id': 'hold', 'title': '只核对', 'route': 'skip'},
            ],
        }
        (path / 'pcg').mkdir()
        (path / 'pcg' / 'routes.yaml').write_text(dump(routes))
        (path / 'pcg' / 'ops.lock.json').write_text(json.dumps({
            'schema': 'pcg.ops.lock.v1', 'skill': path.name, 'kind': kind,
            'blueprint_pcg_ops': [], 'unmapped': ['input', 'run', 'review'],
        }))
        from pcg_architecture import architecture_from_routes
        (path / 'pcg' / 'architecture.yaml').write_text(dump(architecture_from_routes(path.name, kind, routes)))
        return path

    def test_roundtrip_yaml_flow_list(self):
        text = dump({'nodes': ['a', 'b'], 'empty': []})
        self.assertEqual(load(text)['nodes'], ['a', 'b'])
        self.assertEqual(load(text)['empty'], [])

    def test_skills_and_workflows_need_pcg_tools_must_not(self):
        self.write_entry('tools/helper', with_pcg=False)
        self.write_entry('skills/atom')
        self.write_entry('workflows/result')
        self.assertEqual(pcg_check.check_repository(self.repo)['entries'], 2)
        extra = self.repo / 'tools/helper/pcg'
        extra.mkdir()
        (extra / 'routes.yaml').write_text('kind: agent_skill\n')
        with self.assertRaisesRegex(ValueError, 'tools must not'):
            pcg_check.check_repository(self.repo)

    def test_irreversible_needs_confirm_and_known_flag(self):
        self.write_entry('tools/helper', with_pcg=False)
        path = self.write_entry('skills/atom', irreversible=['hi3d.submit'])
        pcg_check.check_entry(self.repo, 'atom', 'skills/atom')
        data = load((path / 'pcg/routes.yaml').read_text())
        del data['checkpoints'][1]['confirm_required']
        (path / 'pcg/routes.yaml').write_text(dump(data))
        with self.assertRaisesRegex(ValueError, 'confirm_required'):
            pcg_check.check_entry(self.repo, 'atom', 'skills/atom')

    def test_missing_skill_pcg_fails_ingest(self):
        self.write_entry('tools/helper', with_pcg=False)
        self.write_entry('skills/atom', with_pcg=False)
        with self.assertRaisesRegex(ValueError, 'missing pcg sidecar'):
            pcg_check.check_repository(self.repo)

    def test_option_buttons_and_choice_count(self):
        self.write_entry('tools/helper', with_pcg=False)
        path = self.write_entry('skills/atom')
        data = load((path / 'pcg/routes.yaml').read_text())
        data['ui']['option_buttons'] = False
        (path / 'pcg/routes.yaml').write_text(dump(data))
        with self.assertRaisesRegex(ValueError, 'option_buttons'):
            pcg_check.check_entry(self.repo, 'atom', 'skills/atom')

    def test_architecture_must_be_one_tree_and_subagent_needs_entry(self):
        self.write_entry('tools/helper', with_pcg=False)
        path = self.write_entry('skills/atom')
        pcg_check.check_entry(self.repo, 'atom', 'skills/atom')
        arch = load((path / 'pcg' / 'architecture.yaml').read_text())
        self.assertEqual(arch['layout'], 'linear')
        by_id = {task['id']: task for task in arch['tasks']}
        self.assertEqual(by_id['input']['parent'], 'atom')
        self.assertEqual(by_id['run']['parent'], 'input')
        self.assertEqual(by_id['run']['rollback_to'], 'input')
        (path / 'pcg' / 'architecture.yaml').write_text(dump({
            'schema': 'pcg.architecture.v1',
            'entry': 'atom',
            'kind': 'agent_skill',
            'layout': 'tree',
            'tasks': [
                {'id': 'root', 'parent': None, 'role': 'agent', 'label': '编排'},
                {'id': 'work', 'parent': 'root', 'role': 'local', 'label': '本地阶段',
                 'members': [{'id': 'step', 'label': '一步'}]},
            ],
        }))
        with self.assertRaisesRegex(ValueError, 'layout'):
            pcg_check.check_entry(self.repo, 'atom', 'skills/atom')
        (path / 'pcg' / 'architecture.yaml').write_text(dump({
            'schema': 'pcg.architecture.v1',
            'entry': 'atom',
            'kind': 'agent_skill',
            'layout': 'linear',
            'tasks': [
                {'id': 'atom', 'parent': None, 'role': 'agent', 'label': '编排'},
                {'id': 'input', 'parent': 'atom', 'role': 'local', 'label': '确认输入'},
                {'id': 'run', 'parent': 'input', 'role': 'subagent', 'label': '派出'},
                {'id': 'review', 'parent': 'run', 'role': 'local', 'label': '核对产物',
                 'rollback_to': 'run'},
            ],
        }))
        with self.assertRaisesRegex(ValueError, 'entry'):
            pcg_check.check_entry(self.repo, 'atom', 'skills/atom')

    def test_missing_architecture_fails_until_seeded(self):
        self.write_entry('tools/helper', with_pcg=False)
        path = self.write_entry('skills/atom')
        (path / 'pcg' / 'architecture.yaml').unlink()
        with self.assertRaisesRegex(ValueError, 'missing pcg sidecar'):
            pcg_check.check_repository(self.repo)
        seeded = pcg_check.ensure_missing(self.repo)
        self.assertEqual(seeded, ['skills/atom/pcg/architecture.yaml'])
        pcg_check.check_entry(self.repo, 'atom', 'skills/atom')
        again = pcg_check.ensure_missing(self.repo)
        self.assertEqual(again, [])
        text = (path / 'pcg' / 'architecture.yaml').read_text()
        self.assertIn('schema: pcg.architecture.v1', text)
        self.assertIn('layout: linear', text)
        self.assertIn('id: atom', text)

    def test_seed_spawns_hi3d_from_irreversible_and_marks_optional(self):
        from pcg_architecture import architecture_from_routes
        self.write_entry('tools/helper', with_pcg=False)
        path = self.write_entry('workflows/result', irreversible=['hi3d.submit'])
        routes = load((path / 'pcg/routes.yaml').read_text())
        arch = architecture_from_routes('result', 'agent_workflow', routes)
        by_id = {task['id']: task for task in arch['tasks']}
        self.assertEqual(by_id['run']['entry'], 'hi3d-api')
        self.assertTrue(by_id['run']['optional'])
        self.assertEqual(by_id['input']['role'], 'local')
        self.assertEqual(arch['layout'], 'tree')
        self.assertEqual(by_id['run']['parent'], 'result')


if __name__ == '__main__':
    unittest.main()
