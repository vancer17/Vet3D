"""Run in an isolated, materialized Blender package."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bpy,bmesh,numpy as np
from mathutils import Matrix
import mesh_snapshot as snapshots

class Snapshots(unittest.TestCase):
    def test_shape_keys_uv_material_and_detachment(self):
        bpy.ops.mesh.primitive_cube_add(size=2);ob=bpy.context.object
        ob.data.uv_layers.new(name='Extra UV');ob.data.materials.append(bpy.data.materials.new('fixture'))
        ob.shape_key_add(name='Basis');key=ob.shape_key_add(name='Raised')
        for v in key.data:v.co.z+=2
        key.value=.5;ob.location=(3,0,0);bpy.context.view_layer.update()
        raw=snapshots.mesh_snapshot(ob,evaluated=False,space='local',fields=('uv','materials'))
        posed=snapshots.mesh_snapshot(ob,evaluated=True,space='world')
        np.testing.assert_allclose(raw['bounds'],[[-1,-1,-1],[1,1,1]])
        np.testing.assert_allclose(posed['bounds'],[[2,-1,0],[4,1,2]])
        self.assertEqual(raw['materials'],('fixture',));self.assertEqual(raw['triangle_loops'].shape,(12,3))
        self.assertEqual(raw['uv']['Extra UV'].shape,(24,2))
        raw['vertices'][:]=99;self.assertLess(ob.data.vertices[0].co.length,2)
        with self.assertRaises(ValueError):snapshots.mesh_snapshot(ob,evaluated=True,space='world',fields=('unknown',))
        self.assertEqual(len(snapshots.mesh_snapshot(ob,evaluated=True,space='world')['triangles']),12)
    def test_armature_pose_and_triangle_indices(self):
        bpy.ops.mesh.primitive_cube_add(size=2);ob=bpy.context.object
        bm=bmesh.new();bm.from_mesh(ob.data);bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free()
        arm=bpy.data.objects.new('fixture rig',bpy.data.armatures.new('fixture rig'));bpy.context.scene.collection.objects.link(arm)
        bpy.context.view_layer.objects.active=arm;arm.select_set(True);ob.select_set(False);bpy.ops.object.mode_set(mode='EDIT')
        bone=arm.data.edit_bones.new('Move');bone.head=(0,0,0);bone.tail=(0,0,1);bpy.ops.object.mode_set(mode='OBJECT')
        group=ob.vertex_groups.new(name='Move');group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
        mod=ob.modifiers.new('Armature','ARMATURE');mod.object=arm
        arm.pose.bones['Move'].location=(0,0,3);bpy.context.view_layer.update()
        raw=snapshots.mesh_snapshot(ob,evaluated=False,space='local',triangulation='require_triangles',precision='float32')
        posed=snapshots.mesh_snapshot(ob,evaluated=True,space='local',triangulation='require_triangles')
        np.testing.assert_array_equal(raw['triangles'],posed['triangles'])
        np.testing.assert_allclose(posed['vertices']-raw['vertices'],np.tile((0,-3,0),(8,1)),atol=1e-6)
        self.assertEqual(raw['vertices'].dtype,np.float32)
    def test_cleanup_on_failure(self):
        class Source:
            def to_mesh(self):return object()
            def to_mesh_clear(self):self.cleared=True
        source=Source()
        class Object:
            type='MESH'
            def evaluated_get(self, deps):return source
        with self.assertRaises(RuntimeError):
            with snapshots.mesh_source(Object(),evaluated=True,depsgraph=object()):raise RuntimeError('fixture')
        self.assertTrue(source.cleared)

if __name__=='__main__':unittest.main(argv=[__file__])
