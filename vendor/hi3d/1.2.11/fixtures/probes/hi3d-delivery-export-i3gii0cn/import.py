import sys,json,bpy,numpy as np
from pathlib import Path
sys.dont_write_bytecode=True
root=Path(__file__).parent
export=json.loads((root/'export-result.json').read_text())
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.render.fps=30;scene.render.fps_base=1
bpy.ops.import_scene.gltf(filepath=str(root/'animated.glb'))
rigs=[o for o in scene.objects if o.type=='ARMATURE']
helpers={pb.custom_shape for r in rigs for pb in r.pose.bones if pb.custom_shape is not None}
mesh_inventory=[{'name':o.name,'helper':o in helpers} for o in scene.objects if o.type=='MESH']
meshes=[o for o in scene.objects if o.type=='MESH' and o not in helpers]
assert len(meshes)==1 and len(rigs)==1,(mesh_inventory,[r.name for r in rigs])
body=meshes[0];rig=rigs[0]
assert body.find_armature()==rig
samples=[]
for frame in export['scene_frames']:
    scene.frame_set(frame)
    ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    try:samples.append([[*(body.matrix_world@v.co)] for v in me.vertices])
    finally:ev.to_mesh_clear()
difference=float(np.max(np.abs(np.asarray(samples)-np.asarray(export['source_world_samples']))))
weights=[{body.vertex_groups[g.group].name:float(g.weight) for g in v.groups} for v in body.data.vertices]
result={'mesh_inventory':mesh_inventory,'mesh':body.name,'rig':rig.name,'actual_armature_link':body.find_armature()==rig,'bones':[b.name for b in rig.data.bones],'active_action':rig.animation_data.action.name if rig.animation_data and rig.animation_data.action else None,'actions':[{'name':a.name,'range':list(a.frame_range)} for a in bpy.data.actions],'fps':scene.render.fps/scene.render.fps_base,'frames_checked':export['scene_frames'],'max_world_coordinate_difference':difference,'world_samples':samples,'weight_sums':[sum(row.values()) for row in weights],'weights':weights,'preserve_volume':[m.use_deform_preserve_volume for m in body.modifiers if m.type=='ARMATURE'],'material_slots':[m.name if m else None for m in body.data.materials]}
(root/'import-result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('IMPORT_PROBE',json.dumps({k:v for k,v in result.items() if k not in ['world_samples','weights']}))
assert difference<1e-5
