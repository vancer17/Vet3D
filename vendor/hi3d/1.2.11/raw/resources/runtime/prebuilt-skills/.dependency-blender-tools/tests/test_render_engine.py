import sys
from pathlib import Path
import unittest
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render_engine import engine_identifier, set_engine, set_samples

class EngineTests(unittest.TestCase):
    def test_eevee_aliases_preserve_legacy_and_newer_hosts(self):
        for requested in ['BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT']:
            self.assertEqual(engine_identifier(requested, ['BLENDER_EEVEE_NEXT','CYCLES']), 'BLENDER_EEVEE_NEXT')
            self.assertEqual(engine_identifier(requested, ['BLENDER_EEVEE','CYCLES']), 'BLENDER_EEVEE')
        with self.assertRaises(ValueError):engine_identifier('CYCLES',['BLENDER_EEVEE'])
    def test_scene_uses_runtime_enum_and_missing_samples_are_not_claimed(self):
        scene=SimpleNamespace(render=SimpleNamespace(bl_rna=SimpleNamespace(properties={'engine':SimpleNamespace(enum_items=[SimpleNamespace(identifier='BLENDER_EEVEE_NEXT')])})))
        self.assertEqual(set_engine(scene),'BLENDER_EEVEE_NEXT')
        self.assertIsNone(set_samples(scene,16))
        scene.eevee=SimpleNamespace(taa_render_samples=4)
        self.assertEqual(set_samples(scene,16),16)
        self.assertEqual(scene.eevee.taa_render_samples,16)
