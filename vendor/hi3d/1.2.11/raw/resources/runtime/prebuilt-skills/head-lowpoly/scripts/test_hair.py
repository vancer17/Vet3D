"""Blender-only integration check for explicit hair import, UV preservation and binding."""
from pathlib import Path
import sys
import tempfile
import bpy
import numpy as np
from mathutils import Quaternion

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_io import load_source,coordinates,material
from low_rig import attach_hair,build_rig


def check():
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'hair_fixture.glb'
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=.5)
        face=bpy.context.object;face.name='Face'
        face.data.materials.append(material('Face material'))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=24,radius=.55,location=(0,0,.05))
        hair=bpy.context.object;hair.name='Hair'
        hair.data.materials.append(material('Hair material',(.05,.02,.01,1)))
        parent=bpy.data.objects.new('Input transform',None);bpy.context.scene.collection.objects.link(parent)
        parent.location=(.3,-.2,.1);parent.rotation_euler=(0,.15,0)
        face.parent=parent;hair.parent=parent;bpy.context.view_layer.update()
        original=coordinates(hair)@np.asarray(hair.matrix_world)[:3,:3].T+np.asarray(hair.matrix_world)[:3,3]
        bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB')
        try:
            load_source(path,'Face',['missing'])
        except ValueError:
            pass
        else:
            raise AssertionError('Missing hair name must fail')
        load_source(path,'Face',['Hair'])
        source=bpy.data.objects['Source_Hair_Hair']
        # glTF may split vertices at UV/normal seams; compare positions, not counts.
        distances = np.linalg.norm(coordinates(source)[:, None] - original[None, :], axis=2)
        assert float(distances.min(1).max()) < 1e-6
        rig=build_rig({'joints':{'Root':[[0,0,-.1],[0,0,0],None],'Head':[[0,0,0],[0,0,.2],'Root']}})
        reports=attach_hair(rig,100)
        hair=bpy.data.objects[reports[0]['object']]
        assert reports[0]['output_faces']<=100 and reports[0]['uv_layers']>0
        assert hair.data.materials[0].name.startswith('Hair material')
        assert source.hide_render and hair.parent==rig
        assert all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in hair.data.vertices)
        neutral=coordinates(hair).astype(float)
        bone=rig.pose.bones['Head'];bone.rotation_mode='QUATERNION';bone.rotation_quaternion=Quaternion((0,0,1),.2)
        bpy.context.view_layer.update()
        m=np.asarray(bone.matrix@bone.bone.matrix_local.inverted())
        expected=neutral@m[:3,:3].T+m[:3,3]
        evaluated=hair.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        actual=np.array([v.co[:] for v in mesh.vertices]);evaluated.to_mesh_clear()
        np.testing.assert_allclose(actual,expected,atol=1e-6)
        print('HAIR_IMPORT_UV_SIMPLIFICATION_BINDING_PASSED',reports,flush=True)


if __name__=='__main__':check()
