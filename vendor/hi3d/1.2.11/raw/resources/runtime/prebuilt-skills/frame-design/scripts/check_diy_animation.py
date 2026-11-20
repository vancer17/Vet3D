"""Compare fresh imported DIY GLB key poses to its actual native animation."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse, hashlib, json, struct
import bpy
import numpy as np
from frame_runtime import cli_arguments
from frame_diy_runtime import prepare_paths, require_distinct_outputs


ROLE_PREFIXES={'frame':'Main lunar','locking_ring':'Bayonet locking back ring',
    'backing':'Stationary keyed photograph backing','stand':'Twin dovetail',
    'artwork':'Independent paper photograph'}


def mesh_roles():
    """Require exactly the five known product roles; return live Blender objects."""
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    roles={}
    for role,prefix in ROLE_PREFIXES.items():
        found=[o for o in objects if o.name.startswith(prefix)]
        if len(found)!=1:raise ValueError('Missing/duplicate recipe mesh: '+role)
        roles[role]=found[0]
    return roles


def pose_bounds(objects):
    """Actual evaluated world mesh bounds in mm, including release shape values."""
    bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();result={}
    for role,obj in objects.items():
        evaluated=obj.evaluated_get(graph);mesh=evaluated.to_mesh()
        try:
            v=np.asarray([evaluated.matrix_world@p.co for p in mesh.vertices],dtype=float)*1000
            if not len(v) or not np.isfinite(v).all():raise ValueError('Empty/nonfinite evaluated mesh')
            result[role]=np.stack((v.min(0),v.max(0)))
        finally:evaluated.to_mesh_clear()
    return result


def inspect_animation(*, source, native, output, tolerance_mm=0.001):
    """Read-only scene/GLB comparison at key poses; not continuous collision proof."""
    if not np.isfinite(tolerance_mm) or tolerance_mm<=0:raise ValueError('Positive finite tolerance required')
    destination=Path(output).expanduser().resolve()
    _,inputs=prepare_paths(output=destination.parent,derived_inputs={'source':source,'native':native})
    require_distinct_outputs(inputs.values(),[destination]);data=inputs['source'].read_bytes()
    if len(data)<20 or data[:4]!=b'glTF' or data[16:20]!=b'JSON':raise ValueError('Expected GLB')
    length=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+length])
    animations=doc.get('animations',[])
    if len(animations)!=1 or len(animations[0].get('channels',[]))!=8:raise ValueError('Expected one synchronized eight-channel product clip')
    bpy.ops.wm.open_mainfile(filepath=str(inputs['native']));scene=bpy.context.scene
    if (scene.frame_start,scene.frame_end)!=(1,289):raise ValueError('Expected complete 289-frame native sequence')
    fps=scene.render.fps/scene.render.fps_base
    if fps!=12:raise ValueError('This recipe timing requires 12 fps')
    external=[im.filepath for im in bpy.data.images if im.source not in ('GENERATED','VIEWER') and not im.packed_file and not len(im.packed_files)]
    if external or len(bpy.data.libraries):raise ValueError('Native scene has unpacked image or linked library dependencies')
    # Blender writes source frame / fps as GLB time, preserving frame 1 at 1/12 s.
    # Its importer maps seconds to frame = seconds * imported fps (no +1).
    # Require that explicit timing contract before comparing the two scenes.
    for sampler in animations[0]['samplers']:
        accessor=doc['accessors'][sampler['input']]
        if not np.allclose(accessor.get('min',[]),[1/fps],atol=1e-6) or not np.allclose(accessor.get('max',[]),[289/fps],atol=1e-6):
            raise ValueError('Unexpected GLB time origin/range for this native sequence')
    frames=[1,20,30,40,55,67,73,90,112,131,145,159,178,200,217,250,289];roles=mesh_roles();native_poses={}
    for f in frames:scene.frame_set(f);native_poses[f]=pose_bounds(roles)
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(inputs['source']))
    scene=bpy.context.scene;rate=scene.render.fps/scene.render.fps_base;roles=mesh_roles();rows=[]
    for f in frames:
        imported_frame=f*rate/fps;scene.frame_set(int(imported_frame),subframe=imported_frame%1)
        bounds=pose_bounds(roles)
        for role in roles:
            error=float(np.max(np.abs(bounds[role]-native_poses[f][role])))
            rows.append({'native_frame':f,'imported_frame':imported_frame,'role':role,'maximum_bounds_error_mm':error,'passed':error<=tolerance_mm})
    movement={role:float(max(np.max(np.abs(native_poses[f][role]-native_poses[1][role])) for f in frames)) for role in roles}
    result={'passed':all(r['passed'] for r in rows) and all(v>1 for v in movement.values()),'glb_sha256':hashlib.sha256(data).hexdigest(),'native_sha256':hashlib.sha256(inputs['native'].read_bytes()).hexdigest(),'animation_clips':1,'channels':8,'native_images_packed':True,'sampled_native_frames':frames,'glb_time_origin_seconds':1/fps,'time_mapping':'native_frame / native_fps * imported_fps','tolerance_mm':tolerance_mm,'motion_extent_mm':movement,'poses':rows,'scope':'Fresh imported evaluated mesh bounds versus 17 native poses; image/library portability. Does not prove continuous motion, fatigue, print strength or human dexterity.'}
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(result,indent=2));return result


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--native',required=True);p.add_argument('--output',required=True)
    return 0 if inspect_animation(**vars(p.parse_args(cli_arguments(argv))))['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
