import sys,unittest,tempfile,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bpy,numpy as np
from product_source import import_source

class ProductSource(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'source.glb'
        bpy.ops.mesh.primitive_cube_add(size=2);obj=bpy.context.object;obj.scale=(1,2,3)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        material=bpy.data.materials.new('fixture');obj.data.materials.append(material)
        bpy.ops.export_scene.gltf(filepath=str(self.path),export_format='GLB',export_animations=False)
    def test_quaternion_import_obeys_radian_yaw_height_and_width(self):
        before=self.path.read_bytes()
        for dimension,expected in [('height',[.2,.1,.3]),('width',[.3,.15,.45])]:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            marker=bpy.data.objects.new('Existing scene object',None);bpy.context.scene.collection.objects.link(marker)
            obj,original=import_source(self.path,**{dimension:.3},rotation_z=math.pi/2)
            for item in [obj,original]:
                points=np.array([v.co[:] for v in item.data.vertices]);lo,hi=points.min(0),points.max(0)
                np.testing.assert_allclose(hi-lo,expected,rtol=1e-5)
                np.testing.assert_allclose([(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,lo[2]],[0,0,0],atol=1e-7)
                self.assertTrue(item.data.uv_layers.active);self.assertTrue(item.data.materials)
            self.assertTrue(original.hide_render);self.assertTrue(original.hide_get());self.assertIsNot(obj.data,original.data)
            self.assertIs(bpy.data.objects.get(marker.name),marker)
        self.assertEqual(before,self.path.read_bytes())
    def test_nonfinite_angle_rejected_before_scene_changes(self):
        counts=(len(bpy.data.objects),len(bpy.data.materials))
        for angle in [float('nan'),float('inf')]:
            with self.assertRaises(ValueError):import_source(self.path,height=.3,rotation_z=angle)
        self.assertEqual(counts,(len(bpy.data.objects),len(bpy.data.materials)))

if __name__=='__main__':unittest.main(argv=[__file__])
