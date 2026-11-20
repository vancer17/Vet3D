"""Verify packaged resources and the custom-template boundary without network/DNA."""
import hashlib,json,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from template_defaults import ASSETS,resolve_template_config

class TemplateDefaultsTests(unittest.TestCase):
    def test_packaged_mesh_and_atlases_are_real_and_intact(self):
        manifest=json.loads((ASSETS/'manifest.json').read_text())
        for name,expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ASSETS/name).read_bytes()).hexdigest(),expected['sha256'])
        with np.load(ASSETS/'template.npz',allow_pickle=False) as mesh:
            self.assertEqual(mesh['vertices'].shape,(24049,3))
            self.assertEqual(mesh['quads'].shape,(24002,4))
            self.assertEqual(mesh['quad_uvs'].shape,(24002,4,2))
            self.assertTrue(np.isfinite(mesh['vertices']).all())
            self.assertTrue(np.isfinite(mesh['quad_uvs']).all())
            self.assertGreaterEqual(mesh['quads'].min(),0)
            self.assertLess(mesh['quads'].max(),len(mesh['vertices']))
        for name in ['head_color_map.tga','eyes_color_map.tga','teeth_color_map.tga']:
            with Image.open(ASSETS/name) as image:
                image.load();self.assertEqual(image.size,(1024,1024))
    def test_default_static_configuration_needs_no_dna(self):
        original={'output':'/task/result'};result=resolve_template_config(original)
        self.assertEqual(original,{'output':'/task/result'})
        self.assertTrue(Path(result['template']).is_file())
        self.assertTrue(Path(result['template_albedo']).is_file())
        self.assertNotIn('dna',result)
        self.assertNotIn('template_eye_albedo',result)
    def test_custom_template_never_inherits_default_atlases(self):
        original={'template':'/custom/head.npz'}
        self.assertEqual(resolve_template_config(original),original)
    def test_explicit_texture_and_disabled_fusion_are_preserved(self):
        result=resolve_template_config({'template_albedo':None,'dna':'/custom/matching.dna','template_eye_albedo':'/custom/eyes.png'})
        self.assertIsNone(result['template_albedo'])
        self.assertEqual(result['template_eye_albedo'],'/custom/eyes.png')
        self.assertTrue(Path(result['template_teeth_albedo']).is_file())

if __name__=='__main__':unittest.main()
