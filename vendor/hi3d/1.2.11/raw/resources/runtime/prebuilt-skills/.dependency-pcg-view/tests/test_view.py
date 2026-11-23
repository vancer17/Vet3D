"""Cost hangs on zoomed nodes and edges; options reuse the PCG popup."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import html_view
import view_cli
import view_ir


ROUTES = {
    'entry': 'SKILL.md',
    'ui': {'option_buttons': True, 'choice_role': 'option'},
    'checkpoints': [
        {'id': 'brief', 'say': '确认输入', 'rollback_to': None, 'irreversible': []},
        {'id': 'form', 'say': '自由外壳', 'rollback_to': 'brief',
         'irreversible': ['hi3d.submit'], 'confirm_required': True},
        {'id': 'fdm', 'say': '打印套件', 'rollback_to': 'form', 'irreversible': []},
        {'id': 'web', 'say': '网页', 'rollback_to': 'fdm', 'irreversible': []},
    ],
    'routes': [
        {'id': 'main', 'nodes': ['brief', 'form', 'fdm', 'web']},
        {'id': 'reuse_asset', 'nodes': ['brief', 'fdm', 'web']},
    ],
    'choices_example': [
        {'id': 'new_design', 'title': '新生成外壳', 'route': 'main'},
        {'id': 'have_asset', 'title': '已有模型跳过生成', 'route': 'reuse_asset'},
        {'id': 'back', 'title': '回到输入', 'rollback_to': 'brief'},
    ],
}


class ViewTests(unittest.TestCase):
    def test_cost_is_on_edges_and_zoomed_members(self):
        view = view_ir.compose_view(ROUTES, session={
            'route': 'main', 'checkpoint': 'form', 'status': 'waiting_choice',
        })
        self.assertEqual([step['id'] for step in view['rail']], ['brief', 'form', 'fdm', 'web'])
        self.assertNotIn('board', view)
        self.assertNotIn('schemes', view)
        self.assertTrue(view['rail'][0]['resume_allowed'])
        self.assertFalse(view['rail'][1]['resume_allowed'])
        children = [node for node in view['overview']['nodes'] if node['id'] != view['overview']['root']]
        form_region = next(node for node in children if node['rail_ids'] == ['form'])
        self.assertEqual(form_region['cost']['hi3d_submit_count'], 1)
        self.assertEqual(form_region['members'][0]['billable'], ['hi3d.submit'])
        into_form = next(edge for edge in view['overview']['edges'] if edge['to'] == form_region['id'])
        self.assertEqual(into_form['cost']['hi3d_submit_count'], 1)
        by_id = {item['id']: item for item in view['option_popup']['choices']}
        self.assertTrue(view['option_popup']['visible'])
        self.assertEqual(view['option_popup']['surface'], 'popup')
        self.assertEqual(by_id['new_design']['hi3d_submit_count'], 1)
        self.assertEqual(by_id['have_asset']['hi3d_submit_count'], 0)
        self.assertEqual(by_id['back']['kind'], 'rollback')

    def test_html_shows_overview_and_popup_not_a_credit_board(self):
        running = view_ir.compose_view(ROUTES, session={'route': 'main', 'checkpoint': 'brief', 'status': 'running'})
        page = html_view.html_document(running)
        self.assertIn('class="rail"', page)
        self.assertIn('class="board overview"', page)
        self.assertIn('data-tone="billable"', page)
        self.assertNotIn('data-surface="popup"', page)
        self.assertNotIn('耗分画板', page)
        waiting = view_ir.compose_view(ROUTES, session={
            'route': 'main', 'checkpoint': 'form', 'status': 'waiting_choice',
        })
        popup_page = html_view.html_document(waiting)
        self.assertIn('data-surface="popup"', popup_page)
        self.assertIn('Hi3D 提交 × 0', popup_page)
        self.assertIn('Hi3D 提交 × 1', popup_page)
        self.assertNotIn('ETA', popup_page)

    def test_overview_groups_same_tone_stages(self):
        view = view_ir.compose_view(ROUTES, session={
            'entry': 'demo', 'route': 'main', 'checkpoint': 'form', 'status': 'waiting_choice',
        })
        overview = view['overview']
        self.assertEqual(overview['kind'], 'stage_groups')
        self.assertEqual(overview['root'], 'demo')
        children = [node for node in overview['nodes'] if node['id'] != overview['root']]
        self.assertEqual([node['label'] for node in children], ['确认输入', '自由外壳', '打印套件'])
        self.assertEqual([node['tone'] for node in children], ['reversible', 'billable', 'reversible'])
        self.assertEqual(children[1]['rail_ids'], ['form'])
        self.assertEqual(children[2]['rail_ids'], ['fdm', 'web'])
        self.assertEqual(overview['groups'][1]['source'], 'agent')
        self.assertEqual(view['host_actions']['focus_overview'], [node['id'] for node in children])
        self.assertEqual(view['color_catalog']['status'], 'placeholder')
        self.assertEqual(children[1]['color'], view_ir.COLOR_PLACEHOLDERS['billable'])

    def test_triggered_lamp_design_projects_registered_routes(self):
        repo = Path(__file__).resolve().parents[3]
        yaml_scripts = repo / 'tools' / 'package-tools' / 'scripts'
        sys.path.insert(0, str(yaml_scripts))
        import pcg_yaml
        routes = pcg_yaml.load((repo / 'workflows' / 'lamp-design' / 'pcg' / 'routes.yaml').read_text())
        view = view_ir.compose_view(routes, session={
            'schema': 'pcg.session.v1',
            'task_id': 'preview-lamp',
            'entry': 'lamp-design',
            'route': 'main',
            'checkpoint': 'concept',
            'status': 'waiting_choice',
        })
        self.assertEqual(view['overview']['kind'], 'stage_groups')
        self.assertEqual(view['overview']['root'], 'preview-lamp')
        children = [node for node in view['overview']['nodes'] if node['id'] != view['overview']['root']]
        self.assertEqual(
            [(node['function'], node['tone'], tuple(node['rail_ids'])) for node in children],
            [
                ('需求与有效约束', 'reversible', ('research',)),
                ('概念与选择（按需）', 'billable', ('concept', 'generate')),
                ('三维与结构', 'irreversible', ('form',)),
                ('连接与灯路', 'reversible', ('connect', 'fdm')),
                ('同版开关灯媒体', 'irreversible', ('media',)),
                ('最终网页与制作包', 'reversible', ('web',)),
            ],
        )
        self.assertEqual(children[1]['cost']['hi3d_submit_count'], 2)
        self.assertEqual(children[1]['state'], 'waiting_choice')
        self.assertTrue(view['option_popup']['visible'])
        page = html_view.html_document(view, title='lamp-design 已触发')
        self.assertIn('data-color="#2AA8A4"', page)
        self.assertIn('概念与选择', page)
        self.assertIn('Hi3D×2', page)
        self.assertIn('option-popup', page)

    def test_overview_agent_tree_uses_session_agents(self):
        view = view_ir.compose_view(ROUTES, session={
            'entry': 'demo', 'route': 'main', 'checkpoint': 'form', 'status': 'running',
            'agents': [
                {'id': 'host', 'parent': None, 'role': 'agent', 'label': '编排', 'entry': 'demo'},
                {'id': 'gen', 'parent': 'host', 'role': 'subagent', 'label': '生成',
                 'function': '自由外壳', 'checkpoint': 'form'},
                {'id': 'site', 'parent': 'host', 'role': 'subagent', 'label': '网页', 'checkpoint': 'web'},
            ],
        })
        overview = view['overview']
        self.assertEqual(overview['kind'], 'agent_tree')
        by_id = {node['id']: node for node in overview['nodes']}
        self.assertEqual(by_id['gen']['tone'], 'billable')
        self.assertEqual(by_id['site']['tone'], 'reversible')
        self.assertEqual(sorted(edge['to'] for edge in overview['edges']), ['gen', 'site'])
        self.assertEqual(by_id['gen']['cost']['hi3d_submit_count'], 1)

    def test_overview_rejects_two_roots(self):
        with self.assertRaises(ValueError):
            view_ir.compose_view(ROUTES, session={'agents': [
                {'id': 'a', 'parent': None, 'role': 'agent', 'label': 'A'},
                {'id': 'b', 'parent': None, 'role': 'agent', 'label': 'B'},
            ]})

    def test_cli_json_exposes_host_actions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'routes.json').write_text(json.dumps(ROUTES))
            out = root / 'view.json'
            self.assertEqual(view_cli.main([
                '--routes', str(root / 'routes.json'), '--format', 'json', '--output', str(out),
            ]), 0)
            payload = json.loads(out.read_text())
            self.assertEqual(payload['host_actions']['resume_rail'], ['brief', 'fdm', 'web'])
            self.assertEqual(payload['host_actions']['confirm_nodes'], ['form'])
            self.assertFalse(payload['host_actions']['show_option_popup'])

    def test_waiting_hi3d_popup_projects_agent_gems(self):
        view = view_ir.compose_view(ROUTES, session={
            'route': 'main', 'checkpoint': 'form', 'status': 'waiting_choice',
        })
        web = view['option_popup']['web_options']
        self.assertEqual(web['kind'], 'model')
        self.assertEqual(web['prompt'], '请选择您要使用的 Hi3D 生成参数')
        self.assertNotIn('quote', web)
        page = html_view.html_document(view)
        self.assertIn('请选择您要使用的 Hi3D 生成参数', page)
        self.assertNotIn('您目前是', page)
        self.assertNotIn('（agent可选）', page)
        self.assertIn('v3.0:quality', page)
        self.assertIn('v3.0:master', page)
        self.assertIn('v2.0:1536pro', page)
        self.assertNotIn('data-id="version"', page)
        self.assertNotIn('v1.5', page)
        self.assertNotIn('积分', page)
        self.assertIn('几何+风格化贴图（推荐）', page)
        self.assertIn('v3.0 极致细节 · 高质 | 品质增强（推荐）', page)
        self.assertIn('v2.0 均衡全能 · 均衡', page)
        self.assertIn('data-id="v3.0:quality"', page)
        self.assertNotIn('>确认</button>', page)
        self.assertIn('v2.1', page)

    def test_web_surface_locks_standard_gems(self):
        view = view_ir.compose_view(ROUTES, session={
            'route': 'main',
            'checkpoint': 'form',
            'status': 'waiting_choice',
            'hi3d_options': {'identity': 'standard', 'surface': 'web', 'kind': 'model'},
        })
        self.assertEqual(view['option_popup']['web_options']['prompt'], '请选择您要使用的 Hi3D 生成参数')
        page = html_view.html_document(view)
        self.assertIn('v3.0', page)
        self.assertNotIn('您目前是', page)
        self.assertNotIn('（agent可选）', page)

    def test_member_popup_drops_gems_and_uses_plain_prompt(self):
        view = view_ir.compose_view(ROUTES, session={
            'route': 'main',
            'checkpoint': 'form',
            'status': 'waiting_choice',
            'hi3d_options': {'identity': 'member', 'surface': 'agent', 'kind': 'model'},
        })
        page = html_view.html_document(view)
        self.assertIn('请选择您要使用的 Hi3D 生成参数', page)
        self.assertNotIn('class="gem"', page)
        self.assertNotIn('请您选择生成模型的Hi3D参数', page)

    def test_legacy_billing_stage_does_not_project_authorization_choices(self):
        view = view_ir.compose_view(ROUTES, session={
            'route': 'main',
            'checkpoint': 'form',
            'status': 'waiting_choice',
            'waiting_context': {'stage': 'billing', 'reason': 'billable', 'checkpoint': 'form'},
            'hi3d_options': {
                'kind': 'model',
                'stage': 'billing',
                'selected': {
                    'model_type': 'v3.0:quality',
                    'generation_type': 'both',
                },
            },
        })
        popup = view['option_popup']
        self.assertIsNone(popup['stage'])
        self.assertNotIn('billing', popup)
        page = html_view.html_document(view)
        self.assertNotIn('仅本次', page)
        self.assertNotIn('本次对话始终允许', page)
        self.assertNotIn('本次提交将调用 Hi3D 计费能力', page)
        self.assertNotIn('高质', page)


if __name__ == '__main__':
    unittest.main()
