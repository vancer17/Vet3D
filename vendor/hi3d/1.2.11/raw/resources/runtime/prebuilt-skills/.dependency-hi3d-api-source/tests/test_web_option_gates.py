"""Web option catalog: gems stay labeled; agent can select, web locks standard."""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import web_option_gates as gates


class WebOptionGatesTests(unittest.TestCase):
    def test_agent_standard_defaults_quality_with_texture(self):
        projected = gates.project_web_options('model', 'standard', surface='agent')
        self.assertEqual(projected['prompt'], '请选择您要使用的 Hi3D 生成参数')
        self.assertNotIn('quote', projected)
        selected = {
            group['id']: next(item['id'] for item in group['options'] if item['selected'])
            for group in projected['groups']
        }
        self.assertEqual(selected['model_type'], 'v3.0:quality')
        self.assertEqual(selected['generation_type'], 'both')
        labels = {
            group['id']: [item['label'] for item in group['options']]
            for group in projected['groups']
        }
        self.assertEqual(labels['model_type'], [
            'v3.0:quality', 'v3.0:master',
            'v2.1:fast', 'v2.1:quality',
            'v2.0:1536', 'v2.0:1536pro',
        ])
        self.assertNotIn('version', labels)
        self.assertFalse(any('v1.5' in label for label in labels['model_type']))
        self.assertNotIn('积分', ''.join(labels['model_type']))
        model_group = next(group for group in projected['groups'] if group['id'] == 'model_type')
        self.assertEqual(
            {item['label']: item['description'] for item in model_group['options']},
            {
                'v3.0:quality': 'v3.0 极致细节 · 高质 | 品质增强（推荐）',
                'v3.0:master': 'v3.0 极致细节 · 大师 | 极致细节',
                'v2.1:fast': 'v2.1 极速生成 · 极速 | 最快出稿（推荐）',
                'v2.1:quality': 'v2.1 极速生成 · 高质 | 品质增强',
                'v2.0:1536': 'v2.0 均衡全能 · 均衡',
                'v2.0:1536pro': 'v2.0 均衡全能 · 高质',
            },
        )
        gen_group = next(group for group in projected['groups'] if group['id'] == 'generation_type')
        self.assertEqual(
            [(item['id'], item['description']) for item in gen_group['options']],
            [('both', '几何+风格化贴图（推荐）'), ('mesh', '几何'), ('texture', '仅贴纹理（需已有 GLB）')],
        )

    def test_member_prompt_matches_standard(self):
        member = gates.project_web_options('model', 'member', surface='agent')
        standard = gates.project_web_options('model', 'standard', surface='agent')
        self.assertEqual(member['prompt'], standard['prompt'])
        self.assertNotIn('quote', member)

    def test_web_standard_cannot_request_pbr(self):
        with self.assertRaisesRegex(ValueError, 'Membership-gated'):
            gates.reject_gated_request(
                'model', 'standard', parameters={'pbr': 1}, surface='web')

    def test_agent_standard_may_request_pbr(self):
        gates.reject_gated_request(
            'model', 'standard', parameters={'pbr': 1}, surface='agent')

    def test_display_ids_become_public_api_fields(self):
        rewritten = gates.display_overrides('model', [
            'model_type=v3.0:quality',
            'generation_type=both',
            'format=glb',
        ])
        self.assertEqual(rewritten, [
            'format=glb',
            'model=hi3dv3.0',
            'resolution=2048quality',
            'request_type=3',
        ])
        mesh = gates.display_overrides('model', ['model_type=v2.1:fast', 'generation_type=mesh'])
        self.assertIn('model=hitem3dv2.1', mesh)
        self.assertIn('resolution=1536fast', mesh)
        self.assertIn('request_type=1', mesh)

    def test_flat_model_choices_all_map_and_v15_is_not_accepted(self):
        expected = {
            'v3.0:quality': ('hi3dv3.0', '2048quality'),
            'v3.0:master': ('hi3dv3.0', '2048master'),
            'v2.1:fast': ('hitem3dv2.1', '1536fast'),
            'v2.1:quality': ('hitem3dv2.1', '1536pro'),
            'v2.0:1536': ('hitem3dv2.0', '1536'),
            'v2.0:1536pro': ('hitem3dv2.0', '1536pro'),
        }
        for selected, pair in expected.items():
            with self.subTest(selected=selected):
                rewritten = gates.display_overrides('model', ['model_type=' + selected])
                self.assertEqual(rewritten, ['model=' + pair[0], 'resolution=' + pair[1]])
        for unsupported in ('v1.5:1536', 'v3.0:standard', 'v2.1:pro'):
            for rewrite in (gates.display_overrides, gates.native_display_overrides):
                with self.subTest(unsupported=unsupported, rewrite=rewrite.__name__):
                    with self.assertRaisesRegex(ValueError, 'unknown model_type'):
                        rewrite('model', ['model_type=' + unsupported])

    def test_image_member_models_are_gems(self):
        projected = gates.project_web_options('text-to-image', 'standard', surface='agent')
        self.assertIn('model:nano-banana-2', projected['gem_ids'])
        self.assertIn('model:nano-banana-2', projected['selectable_ids'])
        model = next(group for group in projected['groups'] if group['id'] == 'model')
        self.assertEqual([item['id'] for item in model['options']], [
            'gpt-image-2', 'nano-banana-pro', 'nano-banana-2', 'seedream-v4.5',
        ])
        self.assertEqual(model['options'][0]['badge_text'], '推荐')
        self.assertEqual(next(item['id'] for item in model['options'] if item['selected']),
                         'gpt-image-2')

    def test_submit_gate_needs_parameters_then_becomes_ready(self):
        first = gates.submit_choice_gate('model')
        self.assertEqual(first['result'], 'waiting_choice')
        self.assertEqual(first['stage'], 'parameters')
        self.assertEqual(first['user_interaction']['kind'], 'preference')
        self.assertEqual(first['user_interaction']['timeoutSeconds'], 60)
        self.assertEqual([item['id'] for item in first['user_interaction']['questions']],
                         ['model_type', 'generation_type'])
        questions = first['user_interaction']['questions']
        self.assertEqual([item['label'] for item in questions[0]['options']], [
            'v3.0:quality', 'v3.0:master',
            'v2.1:fast', 'v2.1:quality',
            'v2.0:1536', 'v2.0:1536pro',
        ])
        self.assertEqual(len(questions[0]['options']), 6)
        self.assertEqual(questions[0]['defaultAnswer'], 'v3.0:quality')
        self.assertEqual(questions[0]['options'][0]['description'],
                         'v3.0 极致细节 · 高质 | 品质增强（推荐）')
        self.assertEqual(questions[0]['options'][1]['description'],
                         'v3.0 极致细节 · 大师 | 极致细节')
        self.assertEqual(questions[0]['options'][2]['description'],
                         'v2.1 极速生成 · 极速 | 最快出稿（推荐）')
        self.assertEqual(questions[0]['options'][4]['description'],
                         'v2.0 均衡全能 · 均衡')
        self.assertEqual(
            [(item['label'], item['description']) for item in questions[1]['options']],
            [('both', '几何+风格化贴图（推荐）'), ('mesh', '几何'), ('texture', '仅贴纹理（需已有 GLB）')],
        )
        self.assertEqual(questions[1]['defaultAnswer'], 'both')
        selected = {
            'model_type': 'v3.0:quality',
            'generation_type': 'both',
        }
        ready = gates.submit_choice_gate('model', selected=selected)
        self.assertEqual(ready['result'], 'ready')
        self.assertNotIn('billing', ready)
        self.assertNotIn('user_interaction', ready)

    def test_complete_model_parameters_map_and_submit_without_billing_gate(self):
        for tier, native in (('quality', 'standard'), ('master', 'quality')):
            with self.subTest(tier=tier):
                gate, rewritten = gates.gate_parameter_overrides('model', overrides=[
                    'model_type=v3.0:' + tier,
                    'generation_type=both',
                ], native=True)
                self.assertEqual(gate['result'], 'ready')
                self.assertEqual(rewritten, [
                    'version=v3.0',
                    'modelType=' + native,
                    'voxelResolution=2048',
                    'generationType=both',
                ])

    def test_v20_native_tiers_submit_balanced_and_quality(self):
        for tier, native in (('1536', 'balanced'), ('1536pro', 'quality')):
            with self.subTest(tier=tier):
                gate, rewritten = gates.gate_parameter_overrides('model', overrides=[
                    'model_type=v2.0:' + tier, 'generation_type=both',
                ], native=True)
                self.assertEqual(gate['result'], 'ready')
                self.assertEqual(rewritten, [
                    'version=v2.0', 'modelType=' + native,
                    'voxelResolution=1536', 'generationType=both',
                ])

    def test_v21_native_tiers_submit_fast_and_quality(self):
        for tier in ('fast', 'quality'):
            with self.subTest(tier=tier):
                gate, rewritten = gates.gate_parameter_overrides('model', overrides=[
                    'model_type=v2.1:' + tier, 'generation_type=both',
                ], native=True)
                self.assertEqual(gate['result'], 'ready')
                self.assertEqual(rewritten, [
                    'version=v2.1', 'modelType=' + tier, 'generationType=both',
                ])

    def test_texture_only_maps_to_public_and_native_fields(self):
        public = gates.display_overrides('model', ['model_type=v3.0:quality', 'generation_type=texture'])
        self.assertEqual(public, ['model=hi3dv3.0', 'resolution=2048quality', 'request_type=2'])
        gate, native = gates.gate_parameter_overrides('model', overrides=[
            'model_type=v3.0:master', 'generation_type=texture',
        ], native=True, has_mesh=True)
        self.assertEqual(gate['result'], 'ready')
        self.assertEqual(native, [
            'version=v3.0', 'modelType=quality', 'voxelResolution=2048',
            'scene=texture', 'generationType=texture',
        ])
        self.assertNotIn('scene=texture', gates.native_display_overrides(
            'model', ['model_type=v3.0:quality', 'generation_type=both']))

    def test_texture_only_rejects_missing_mesh_and_v2_tiers(self):
        with self.assertRaisesRegex(ValueError, '--mesh'):
            gates.gate_parameter_overrides('model', overrides=[
                'model_type=v3.0:quality', 'generation_type=texture',
            ], has_mesh=False)
        # Unknown mesh presence (native --request) defers to build_plan.
        gate, _ = gates.gate_parameter_overrides('model', overrides=[
            'model_type=v3.0:quality', 'generation_type=texture',
        ], native=True, has_mesh=None)
        self.assertEqual(gate['result'], 'ready')
        for tier in ('v2.0:1536', 'v2.0:1536pro', 'v2.1:fast', 'v2.1:quality'):
            with self.subTest(tier=tier):
                with self.assertRaisesRegex(ValueError, 'v3.0'):
                    gates.submit_choice_gate('model', selected={
                        'model_type': tier, 'generation_type': 'texture',
                    }, has_mesh=True)
        # Non-texture choices are untouched by the mesh check.
        gate = gates.submit_choice_gate('model', selected={
            'model_type': 'v2.1:fast', 'generation_type': 'both',
        }, has_mesh=False)
        self.assertEqual(gate['result'], 'ready')
        with self.assertRaisesRegex(ValueError, 'generation_type must be'):
            gates.display_overrides('model', ['generation_type=color'])

    def test_image_parameters_need_no_panel_and_keep_native_mapping(self):
        projected = gates.project_web_options('text-to-image', 'standard', surface='agent')
        self.assertNotIn('image_count', [group['id'] for group in projected['groups']])
        for kind in ('text-to-image', 'image-edit'):
            for selected in ({}, {'model': 'gpt-image-2'}, {'aspect_ratio': '16:9'}):
                with self.subTest(kind=kind, selected=selected):
                    gate = gates.submit_choice_gate(kind, selected=selected)
                    self.assertEqual(gate['result'], 'ready')
                    self.assertNotIn('user_interaction', gate)
                    self.assertNotIn('web_options', gate)
                    self.assertIsNone(gates.project_parameter_interaction(kind, selected))
            gate, rewritten = gates.gate_parameter_overrides(kind, overrides=[
                'model=nano-banana-2',
                'aspect_ratio=3:4',
            ], native=True)
            self.assertEqual(gate['result'], 'ready')
            self.assertEqual(rewritten, [
                'modelName=Nano-Banana 2',
                'aspectRatio=3:4',
            ])
            with self.assertRaisesRegex(ValueError, 'aspect_ratio must be'):
                gates.gate_parameter_overrides(kind, overrides=['aspect_ratio=invalid'], native=True)

    def test_relief_and_split_still_require_their_parameter_panels(self):
        for kind, selected in (
            ('relief', {'rmbg': 'on'}),
            ('split', {'scene': 'character', 'template': 'a'}),
        ):
            with self.subTest(kind=kind):
                gate = gates.submit_choice_gate(kind)
                self.assertEqual(gate['result'], 'waiting_choice')
                interaction = gate['user_interaction']
                self.assertEqual(interaction['kind'], 'preference')
                self.assertEqual(interaction['timeoutSeconds'], 60)
                self.assertEqual({question['id'] for question in interaction['questions']}, set(selected))
                self.assertEqual(gates.submit_choice_gate(kind, selected=selected)['result'], 'ready')

    def test_session_parameter_selection_can_complete_gate(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            session = Path(root) / 'session.json'
            session.write_text(json.dumps({
                'schema': 'pcg.session.v1',
                'hi3d_options': {
                    'kind': 'model',
                    'selected': {
                        'model_type': 'v3.0:quality',
                        'generation_type': 'both',
                    },
                },
            }), encoding='utf-8')
            gate, rewritten = gates.gate_parameter_overrides('model', session=str(session))
            self.assertEqual(gate['result'], 'ready')
            self.assertEqual(rewritten, [])


if __name__ == '__main__':
    unittest.main()
