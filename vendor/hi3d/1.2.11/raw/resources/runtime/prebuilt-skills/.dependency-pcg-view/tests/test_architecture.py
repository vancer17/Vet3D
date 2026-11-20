"""Skill execution board is a task tree, not the user decision flowchart."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
YAML = Path(__file__).resolve().parents[2] / 'package-tools' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(YAML))
import architecture_ir
import html_view
import view_cli
from pcg_yaml import load


ARCH_PATH = Path(__file__).resolve().parents[3] / 'workflows' / 'hi3d-game-demo' / 'pcg' / 'architecture.yaml'


class ArchitectureBoardTests(unittest.TestCase):
    def setUp(self):
        self.arch = load(ARCH_PATH.read_text())

    def test_hi3d_game_demo_spawns_independent_entries(self):
        board = architecture_ir.compose_board(self.arch)
        self.assertEqual(board['schema'], 'pcg.board.v1')
        self.assertEqual(board['overview']['kind'], 'architecture')
        self.assertEqual(board['overview']['layout'], 'tree')
        self.assertNotIn('rail', board)
        self.assertNotIn('option_popup', board)
        by_id = {node['id']: node for node in board['overview']['nodes']}
        self.assertEqual(by_id['hi3d_game_demo']['role'], 'agent')
        self.assertEqual(by_id['brief']['role'], 'local')
        self.assertEqual(by_id['generate']['entry'], 'hi3d-api')
        self.assertEqual(by_id['lod']['entry'], 'mdf-call')
        self.assertEqual(by_id['rig']['entry'], 'rig-retarget')
        self.assertEqual(by_id['autorig']['parent'], 'rig')
        self.assertEqual(by_id['autorig']['entry'], 'mdf-call')
        self.assertEqual(by_id['publish']['entry'], 'game-deploy')
        spawn = {edge['to']: edge for edge in board['overview']['edges'] if edge['kind'] == 'spawn'}
        self.assertEqual(spawn['generate']['cost']['hi3d_submit_count'], 1)
        self.assertEqual(spawn['lod']['cost']['mdf_invoke_count'], 1)
        self.assertEqual(set(board['host_actions']['spawn_subagent']), {
            'generate', 'lod', 'rig', 'autorig', 'publish',
        })
        self.assertEqual(board['host_actions']['lod'], ['preview', 'detail'])
        local_ids = [node['id'] for node in board['overview']['nodes'] if node['role'] == 'local']
        self.assertEqual(local_ids, ['brief', 'playable'])

    def test_declared_outputs_are_leaves_and_session_keeps_traces(self):
        board = architecture_ir.compose_board(self.arch)
        by_id = {node['id']: node for node in board['overview']['nodes']}
        leaf = by_id['generate__glb']
        self.assertEqual(leaf['role'], 'artifact')
        self.assertEqual(leaf['status'], 'pending')
        self.assertEqual(leaf['parent'], 'generate')
        session = {
            'schema': 'pcg.session.v1',
            'task_id': 'demo',
            'entry': 'hi3d-game-demo',
            'route': 'main',
            'status': 'running',
            'artifacts': [{
                'path': 'runs/demo/hero.glb',
                'href': 'runs/demo/hero.glb',
                'hash': 'abc',
                'task': 'generate',
                'output': 'glb',
                'traces': [
                    {'op': 'add', 'path': 'runs/demo/tmp.glb', 'href': 'runs/demo/tmp.glb'},
                    {'op': 'sync', 'path': 'runs/demo/hero.glb', 'href': 'runs/demo/hero.glb'},
                ],
            }],
        }
        live = architecture_ir.compose_board(self.arch, session)
        glb = {node['id']: node for node in live['overview']['nodes']}['generate__glb']
        self.assertEqual(glb['status'], 'ready')
        self.assertEqual(glb['path'], 'runs/demo/hero.glb')
        self.assertEqual(len(glb['traces']), 2)
        self.assertIn('generate__glb', live['host_actions']['open_artifact'])
        page = html_view.html_document(live)
        self.assertIn('runs/demo/hero.glb', page)
        self.assertIn('href="runs/demo/hero.glb"', page)
        self.assertIn('产物目录', page)
        self.assertIn('generate__glb', [item['id'] for item in live['catalog']['artifacts']])
        self.assertIn('generate__glb', live['host_actions']['find_artifact'])

    def test_semantic_purge_skips_keep_slots(self):
        session = {
            'schema': 'pcg.session.v1', 'task_id': 'demo', 'entry': 'hi3d-game-demo',
            'route': 'main', 'status': 'running',
            'artifacts': [
                {'path': 'hero.glb', 'task': 'generate', 'output': 'glb', 'href': 'hero.glb'},
                {'path': 'hero_lod.glb', 'task': 'lod', 'output': 'mesh', 'href': 'hero_lod.glb'},
            ],
        }
        targets = architecture_ir.select_purge(self.arch, session, semantics=['lod'])
        ids = [item['id'] for item in targets]
        self.assertIn('lod__mesh', ids)
        self.assertNotIn('generate__glb', ids)
        purged = {
            'schema': 'pcg.session.v1', 'task_id': 'demo', 'entry': 'hi3d-game-demo',
            'route': 'main', 'status': 'running',
            'artifacts': [{
                'path': 'hero_lod.glb', 'href': 'hero_lod.glb', 'task': 'lod', 'output': 'mesh',
                'purged': True,
                'traces': [
                    {'op': 'add', 'path': 'hero_lod.glb'},
                    {'op': 'purge', 'path': 'hero_lod.glb'},
                ],
            }],
        }
        board = architecture_ir.compose_board(self.arch, purged)
        leaf = next(node for node in board['overview']['nodes'] if node['id'] == 'lod__mesh')
        self.assertEqual(leaf['status'], 'purged')
        self.assertTrue(leaf['findable'])
        self.assertEqual(leaf['path'], 'hero_lod.glb')

    def test_html_board_is_not_the_routes_decision_page(self):
        board = architecture_ir.compose_board(self.arch)
        page = html_view.html_document(board)
        self.assertIn('class="board-detail"', page)
        self.assertIn('data-lod="preview"', page)
        self.assertIn('data-lod-btn="detail"', page)
        self.assertIn('class="tree-glyphs"', page)
        self.assertIn('polygon', page)
        self.assertIn('<circle', page)
        self.assertIn('产物目录', page)
        self.assertNotIn('class="rail"', page)
        self.assertNotIn('data-surface="popup"', page)
        self.assertNotIn('请选择', page)

    def test_subagent_requires_entry_and_one_tree(self):
        broken = {
            'schema': 'pcg.architecture.v1',
            'entry': 'demo',
            'kind': 'agent_workflow',
            'tasks': [
                {'id': 'root', 'parent': None, 'role': 'agent', 'label': '根'},
                {'id': 'child', 'parent': 'root', 'role': 'subagent', 'label': '缺入口'},
            ],
        }
        with self.assertRaisesRegex(ValueError, 'entry'):
            architecture_ir.compose_board(broken)
        broken['tasks'][1]['entry'] = 'hi3d-api'
        broken['tasks'].append({'id': 'orphan', 'parent': None, 'role': 'local', 'label': '第二根'})
        with self.assertRaisesRegex(ValueError, 'one tree'):
            architecture_ir.compose_board(broken)

    def test_every_skill_and_workflow_has_architecture(self):
        repo = Path(__file__).resolve().parents[3]
        missing = []
        for kind in ('skills', 'workflows'):
            for routes in sorted((repo / kind).glob('*/pcg/routes.yaml')):
                arch = routes.parent / 'architecture.yaml'
                if not arch.is_file():
                    missing.append(routes.parent.parent.name)
                    continue
                doc = load(arch.read_text())
                board = architecture_ir.compose_board(doc)
                self.assertEqual(board['schema'], 'pcg.board.v1')
        self.assertEqual(missing, [], 'missing architecture.yaml: ' + ', '.join(missing))

    def test_skill_board_is_linear_with_rollback(self):
        path = Path(__file__).resolve().parents[3] / 'skills' / 'gray-resin' / 'pcg' / 'architecture.yaml'
        doc = load(path.read_text())
        self.assertEqual(doc['layout'], 'linear')
        board = architecture_ir.compose_board(doc)
        self.assertEqual(board['overview']['layout'], 'linear')
        self.assertEqual(board['host_actions']['lod'], ['detail'])
        self.assertEqual(board['host_actions']['advance'], ['input', 'run', 'review'])
        rollback = [edge for edge in board['overview']['edges'] if edge['kind'] == 'rollback']
        self.assertEqual({(edge['from'], edge['to']) for edge in rollback}, {('run', 'input'), ('review', 'run')})
        page = html_view.html_document(board)
        self.assertIn('线形进程', page)
        self.assertIn('回退', page)
        self.assertNotIn('data-surface="popup"', page)

    def test_assembly_and_product_architecture_samples(self):
        root = Path(__file__).resolve().parents[3] / 'workflows'
        assembly = load((root / 'image-to-assembly' / 'pcg' / 'architecture.yaml').read_text())
        product = load((root / 'product-design' / 'pcg' / 'architecture.yaml').read_text())
        assembled = architecture_ir.compose_board(assembly)
        designed = architecture_ir.compose_board(product)
        self.assertEqual(assembled['host_actions']['spawn_subagent'], ['D'])
        by_a = {node['id']: node for node in assembled['overview']['nodes']}
        self.assertEqual(by_a['D']['entry'], 'hi3d-api')
        self.assertTrue(by_a['D']['optional'])
        self.assertEqual(set(designed['host_actions']['spawn_subagent']), {
            'concept_hi3d', 'print_plan', 'review',
        })
        by_p = {node['id']: node for node in designed['overview']['nodes']}
        self.assertEqual(by_p['print_plan']['entry'], 'print-plan')
        self.assertEqual(by_p['review']['entry'], 'delivery-review')

    def test_cli_architecture_json(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        src = Path(temp.name) / 'arch.json'
        out = Path(temp.name) / 'board.json'
        src.write_text(json.dumps(self.arch))
        self.assertEqual(view_cli.main(['--architecture', str(src), '--format', 'json', '--output', str(out)]), 0)
        board = json.loads(out.read_text())
        self.assertEqual(board['schema'], 'pcg.board.v1')
        self.assertEqual(board['entry'], 'hi3d-game-demo')
        session = Path(temp.name) / 'session.json'
        live = Path(temp.name) / 'live.json'
        session.write_text(json.dumps({
            'schema': 'pcg.session.v1', 'task_id': 'demo', 'entry': 'hi3d-game-demo',
            'route': 'main', 'status': 'running',
            'artifacts': [{'path': 'out.glb', 'task': 'generate', 'output': 'glb', 'href': 'out.glb'}],
        }))
        self.assertEqual(view_cli.main([
            '--architecture', str(src), '--session', str(session),
            '--format', 'json', '--output', str(live),
        ]), 0)
        bound = json.loads(live.read_text())
        glb = next(node for node in bound['overview']['nodes'] if node['id'] == 'generate__glb')
        self.assertEqual(glb['path'], 'out.glb')

    def test_board_projects_to_g6_graph_with_our_data(self):
        import g6_graph
        board = architecture_ir.compose_board(self.arch)
        packed = g6_graph.board_to_g6(board, lod='preview')
        self.assertEqual(packed['schema'], 'pcg.g6.v1')
        self.assertEqual(packed['layout'], 'tree')
        self.assertEqual(packed['graph']['layout']['rankdir'], 'TB')
        self.assertIn('level-of-detail', packed['graph']['behaviors'])
        by_id = {node['id']: node for node in packed['g6']['nodes']}
        generate = by_id['generate']
        self.assertEqual(generate['type'], 'pcg-subagent')
        self.assertEqual(generate['data']['entry'], 'hi3d-api')
        self.assertEqual(generate['data']['name'], generate['data']['label'])
        self.assertEqual(generate['data']['level'], 'overview')
        self.assertEqual(generate['data']['lod'], 'preview')
        self.assertNotIn('phone', generate['data'])
        spawn = next(edge for edge in packed['g6']['edges'] if edge['data']['kind'] == 'spawn' and edge['target'] == 'generate')
        self.assertEqual(spawn['source'], 'hi3d_game_demo')
        self.assertEqual(spawn['data']['cost']['hi3d_submit_count'], 1)
        skill = load((Path(__file__).resolve().parents[3] / 'skills' / 'gray-resin' / 'pcg' / 'architecture.yaml').read_text())
        linear = g6_graph.board_to_g6(architecture_ir.compose_board(skill))
        self.assertEqual(linear['layout'], 'linear')
        self.assertEqual(linear['graph']['layout']['rankdir'], 'LR')
        self.assertNotIn('level-of-detail', linear['graph']['behaviors'])
        self.assertTrue(any(edge['data']['kind'] == 'rollback' for edge in linear['g6']['edges']))
        out = Path(tempfile.mkdtemp()) / 'board.g6.json'
        src = Path(tempfile.mkdtemp()) / 'arch.json'
        src.write_text(json.dumps(self.arch))
        self.assertEqual(view_cli.main([
            '--architecture', str(src), '--format', 'g6', '--lod', 'detail', '--output', str(out),
        ]), 0)
        live = json.loads(out.read_text())
        self.assertEqual(live['g6']['nodes'][0]['data']['level'], 'detailed')


if __name__ == '__main__':
    unittest.main()
