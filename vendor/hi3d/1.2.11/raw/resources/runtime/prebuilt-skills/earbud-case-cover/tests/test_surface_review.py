"""Real Blender regression using synthetic scenes and package-local imports."""
import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bpy
from mathutils import Vector
from surface_pairs import surface_tree,pair_counts
from scene_samples import sample_frames
import review_installation,review_native

class SurfaceReview(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.objects=[]
        for i,name in enumerate(['Art lower shell','Art lid shell','Nominal original lower device','Nominal original device lid','Connector tip','Connector housing']):
            bpy.ops.mesh.primitive_cube_add(size=1,location=(i*.4,0,0));o=bpy.context.object;o.name=name;self.objects.append(o)
        camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));bpy.context.scene.collection.objects.link(camera)
        camera.location=(1,-10,5);camera.rotation_euler=(Vector((1,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.type='ORTHO';camera.data.ortho_scale=8;bpy.context.scene.camera=camera
        stage=bpy.data.objects.new('Stage',None);bpy.context.scene.collection.objects.link(stage)
        bpy.context.scene.frame_set(8,subframe=.5);bpy.context.view_layer.update()
    def test_reports_and_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for module,name,out,count,end in [(review_installation,'installation.blend','native-installation-check.json',9,120),(review_native,'motion.blend','native-motion-check.json',12,144)]:
                bpy.ops.wm.save_as_mainfile(filepath=str(root/name));module.execute([folder]);report=json.loads((root/out).read_text())
                self.assertEqual(len(report['checks']),count);self.assertEqual(len(report['framing']),end)
                self.assertEqual((bpy.context.scene.frame_current,bpy.context.scene.frame_subframe),(8,.5))
                self.assertTrue(any(p['surface_intersection_pairs']>0 for f in report['checks'] for p in f['pairs']))
    def test_geometry_change_and_exception_restore(self):
        a,b=self.objects[:2];cache={};first=review_native.tree(a,tree_cache=cache);other=review_native.tree(b)
        self.assertGreater(pair_counts({'a':first,'b':other},[('a','b')])['a / b'],0)
        for v in a.data.vertices:v.co.x+=100
        a.data.update();bpy.context.view_layer.update()
        updated=review_native.tree(a,tree_cache=cache)
        self.assertEqual(pair_counts({'a':updated,'b':other},[('a','b')])['a / b'],0)
        def fail(frame):raise RuntimeError('fixture')
        with self.assertRaises(RuntimeError):sample_frames(bpy.context.scene,[1,1.5],fail)
        self.assertEqual((bpy.context.scene.frame_current,bpy.context.scene.frame_subframe),(8,.5))
        with self.assertRaises(ValueError):surface_tree([(0,0,0)]*3,[(0,1,2)],epsilon=float('nan'))
        with self.assertRaises(ValueError):pair_counts({'a':updated},[('a','a')])

if __name__=='__main__':unittest.main(argv=[__file__])
