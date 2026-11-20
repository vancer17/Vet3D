import sys,unittest,tempfile,json,struct
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bpy,numpy as np
from mathutils import Vector
from preview_scene import fit_orthographic_camera,fit_projected_orthographic_camera,projected_bounds,check_framing
from glb_export import export_glb
from material_nodes import principled_material

class Preview(unittest.TestCase):
    def test_head_profile_mesh_uv_and_real_render(self):
        from head_preview import make_mesh, material, studio, render_view
        obj = make_mesh('head fixture', [(-1,0,-1),(1,0,-1),(1,0,1),(-1,0,1)],
                        [(0,1,2,3)], [(0,0),(1,0),(1,1),(0,1)])
        obj.data.materials.append(material('head material'))
        self.assertTrue(obj.data.polygons[0].use_smooth)
        self.assertEqual(len(obj.data.uv_layers.active.data), 4)
        camera, center, span = studio(((-1,-1,-1),(1,1,1)), size=32)
        self.assertAlmostEqual(camera.data.ortho_scale, 2.32, places=5)
        self.assertEqual(bpy.data.lights['Key'].energy, 720)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'front.png'
            render_view(camera, center, span, (0,-3,0), path)
            self.assertEqual(path.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(size=2);self.obj=bpy.context.object;self.obj.scale=(1,1,2)
        camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'));bpy.context.scene.collection.objects.link(camera)
        camera.data.type='ORTHO';camera.location=(0,-10,0);camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
        bpy.context.scene.camera=self.camera=camera;bpy.context.view_layer.update()
    def test_aspect_and_frame_restore(self):
        scene=bpy.context.scene
        for width,height in [(1600,900),(900,1600),(900,900)]:
            scene.render.resolution_x=width;scene.render.resolution_y=height
            fit_orthographic_camera(self.camera,[self.obj],(width,height),evaluated=True,margin=1.15)
            bounds=projected_bounds(scene,self.camera,[self.obj],evaluated=True)
            self.assertGreater(bounds['min_x'],0);self.assertLess(bounds['max_x'],1)
            self.assertGreater(bounds['min_y'],0);self.assertLess(bounds['max_y'],1)
        self.obj.location.x=0;self.obj.keyframe_insert('location',frame=1)
        self.obj.location.x=100;self.obj.keyframe_insert('location',frame=2);scene.frame_set(8,subframe=.5)
        result=check_framing(scene,self.camera,[self.obj],[1,2],evaluated=True)
        self.assertFalse(result['all_bounds_in_frame']);self.assertTrue(result['samples'][0]['visible_bounds'])
        self.assertEqual((scene.frame_current,scene.frame_subframe),(8,.5))
    def test_scene_fit_shift_pixel_aspect_evaluation_and_depth(self):
        scene=bpy.context.scene;camera=self.camera
        self.obj.modifiers.new('thickness','SOLIDIFY').thickness=.3
        for sensor in ['AUTO','HORIZONTAL','VERTICAL']:
            camera.data.sensor_fit=sensor
            for width,height in [(1600,900),(900,1600)]:
                scene.render.resolution_x=width;scene.render.resolution_y=height
                scene.render.pixel_aspect_x=1.4;scene.render.pixel_aspect_y=.8
                camera.data.shift_x=.15;camera.data.shift_y=-.2;camera.data.ortho_scale=1
                bounds=fit_projected_orthographic_camera(scene,camera,[self.obj],evaluated=True,margin=.1)
                self.assertGreaterEqual(min(bounds['min_x'],bounds['min_y']),.1-1e-5)
                self.assertLessEqual(max(bounds['max_x'],bounds['max_y']),.9+1e-5)
                self.assertAlmostEqual(bounds['min_x']+bounds['max_x'],1,places=5)
                self.assertAlmostEqual(bounds['min_y']+bounds['max_y'],1,places=5)
        with self.assertRaises(ValueError):fit_projected_orthographic_camera(scene,camera,[],evaluated=True)
        camera.parent=self.obj
        with self.assertRaises(ValueError):fit_projected_orthographic_camera(scene,camera,[self.obj],evaluated=True)
        camera.parent=None;camera.data.clip_end=1
        with self.assertRaises(ValueError):projected_bounds(scene,camera,[self.obj],evaluated=True,check_depth=True)
        # Existing non-strict projection still returns an honest front-only report.
        self.assertIn('all_in_front',projected_bounds(scene,camera,[self.obj],evaluated=True))

    def test_glb_objects_curve_and_cleanup(self):
        from blender_primitives import curve_tube
        curve=curve_tube('wire',[(0,0,0),(0,0,2)],.1,collection=bpy.context.collection)
        self.obj.hide_set(True);self.camera.select_set(True);bpy.context.view_layer.objects.active=self.camera
        def state():return [(o.name,o.select_get(),o.hide_get()) for o in bpy.context.view_layer.objects]
        before=state();counts=(len(bpy.data.objects),len(bpy.data.meshes));vertices=[v.co[:] for v in self.obj.data.vertices]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preview.glb'
            export_glb(path,[self.obj,curve],convert_curves=True,unhide=True,export_animations=False,export_apply=True)
            data=path.read_bytes();length=struct.unpack_from('<I',data,12)[0];gltf=json.loads(data[20:20+length])
            self.assertEqual(len(gltf['meshes']),2);self.assertNotIn('animations',gltf)
            self.obj.location.x=0;self.obj.keyframe_insert('location',frame=1)
            self.obj.location.x=1;self.obj.keyframe_insert('location',frame=2)
            bpy.context.scene.frame_set(8,subframe=.5)
            export_glb(path,[self.obj],unhide=True,export_animations=True,export_force_sampling=True)
            data=path.read_bytes();length=struct.unpack_from('<I',data,12)[0]
            self.assertTrue(json.loads(data[20:20+length]).get('animations'))
            self.assertEqual((bpy.context.scene.frame_current,bpy.context.scene.frame_subframe),(8,.5))
            def fail(**options):
                bpy.context.scene.frame_set(3)
                raise RuntimeError('fixture')
            with self.assertRaises(RuntimeError):export_glb(path,[self.obj,curve],convert_curves=True,unhide=True,exporter=fail)
        self.assertEqual((bpy.context.scene.frame_current,bpy.context.scene.frame_subframe),(8,.5))
        self.assertEqual(before,state());self.assertEqual(counts,(len(bpy.data.objects),len(bpy.data.meshes)))
        self.assertIs(bpy.context.view_layer.objects.active,self.camera);self.assertEqual(vertices,[v.co[:] for v in self.obj.data.vertices])
    def test_material_inputs_and_failure(self):
        mat=principled_material('fixture',(.2,.3,.4),metallic=.6,roughness=.7,inputs={'Coat Weight':.8})
        node=mat.node_tree.nodes.get('Principled BSDF');self.assertAlmostEqual(node.inputs['Coat Weight'].default_value,.8)
        np.testing.assert_allclose(mat.diffuse_color,(.2,.3,.4,1),rtol=1e-6)
        before=len(bpy.data.materials)
        with self.assertRaises(KeyError):principled_material('invalid',(1,1,1),inputs={'Unknown fixture input':1})
        self.assertEqual(before,len(bpy.data.materials))

if __name__=='__main__':unittest.main(argv=[__file__])
