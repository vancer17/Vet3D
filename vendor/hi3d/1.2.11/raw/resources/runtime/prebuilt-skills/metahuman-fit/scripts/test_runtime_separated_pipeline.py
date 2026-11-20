"""Offline regression for supported part/texturing handoffs."""
import tempfile
import unittest
from pathlib import Path
if (Path(__file__).resolve().parents[1] / '.runtime-profile.json').is_file():
    from parts_generation import part_config
    from texture_pipeline import run
else:
    from runtime_parts_generation import part_config
    from runtime_texture_pipeline import run


class SeparatedTests(unittest.TestCase):
    def test_hidden_hair_and_view_order(self):
        with tempfile.TemporaryDirectory() as temp:
            image=Path(temp)/'hair.png';image.write_bytes(b'image')
            config={'output':str(Path(temp)/'out'),'parts':{'hair':{'gray_views':{'front':str(image)}}}}
            with self.assertRaisesRegex(ValueError,'behind'):
                part_config(config,'hair')
            config['parts']['hair']['occluded_hair_completed']=True
            config['parts']['hair']['gray_views']['back']=str(image)
            plan=part_config(config,'hair')
            self.assertEqual(plan['views'],['front','back'])
            self.assertEqual(plan['settings']['request_type'],1)

    def test_uv_handoff_uses_actual_result_without_submitting(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);mesh=root/'mesh.glb';mesh.write_bytes(b'model')
            image=root/'front.png';image.write_bytes(b'image')
            config={'part':'bald','high_glb':str(mesh),'color_views':{'front':str(image),'back':str(image)},'output':str(root/'out')}
            plan=run(config)
            self.assertEqual(plan['uv']['arguments']['capability'],'unwrap-uv')
            self.assertFalse(plan['uv']['arguments']['params']['need_repair'])
            self.assertIsNone(plan['texture']['arguments']['mesh'])
            self.assertEqual(plan['meshFrom'],'uv.files.uv_mesh_glb')
            self.assertEqual(len(plan['texture']['arguments']['images']),1)
            self.assertFalse((root/'out').exists())
            config['has_uv']=True
            plan=run(config)
            self.assertIsNone(plan['uv'])
            self.assertEqual(plan['texture']['arguments']['mesh'],str(mesh.resolve()))
            self.assertEqual(plan['texture']['arguments']['settings']['request_type'],2)


if __name__=='__main__':unittest.main()
