# Portable derivative; original SHA-256 is recorded in evidence-map.json.
import os
from pathlib import Path
import sys, json, hashlib, bpy
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(os.environ['HI3D_RESOURCES_ROOT']) / 'runtime/prebuilt-skills/.dependency-model-preview/scripts'))
from glb_export import export_glb
root = Path(__file__).parent
source = Path(str(Path(__file__).resolve().parents[1] / 'hi3d-reopen-retarget-03981f32224a42aea9a9e50bd3302301/result.blend'))
source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
body = bpy.data.objects['Body']
rig = bpy.data.objects['Target']
scene = bpy.context.scene
scene.render.fps = 30
scene.render.fps_base = 1.25
fps = scene.render.fps / scene.render.fps_base
frames = list(range(scene.frame_start, scene.frame_end + 1))

def sampled_world(obj, frames):
    out = []
    for frame in frames:
        scene.frame_set(frame)
        ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = ev.to_mesh()
        try:
            out.append([[*obj.matrix_world @ v.co] for v in mesh.vertices])
        finally:
            ev.to_mesh_clear()
    return out
before_samples = sampled_world(body, frames)
scene.frame_set(11, subframe=0.25)

def state():
    return {'frame': scene.frame_current, 'subframe': scene.frame_subframe, 'active': bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None, 'objects': [(o.name, o.select_get(), o.hide_get()) for o in bpy.context.view_layer.objects]}
before_state = state()
options = {'export_animations': True, 'export_skins': True, 'export_morph': True, 'export_extras': True, 'export_animation_mode': 'ACTIVE_ACTIONS', 'export_frame_range': True, 'export_force_sampling': True}
out = export_glb(root / 'fractional.glb', [body, rig], unhide=True, **options)
result = {'source_sha256': source_sha, 'source_unchanged': hashlib.sha256(source.read_bytes()).hexdigest() == source_sha, 'options': options, 'scene_frames': frames, 'fps': fps, 'active_action': rig.animation_data.action.name, 'source_meshes': [o.name for o in scene.objects if o.type == 'MESH'], 'selected_export_objects': ['Body', 'Target'], 'state_restored': state() == before_state, 'source_world_samples': before_samples, 'output_sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'output': str(out)}
(root / 'fractional-export-result.json').write_text(json.dumps(result, indent=2), encoding='utf8')
print('EXPORT_PROBE', json.dumps({k: v for k, v in result.items() if k not in ['source_world_samples']}))
