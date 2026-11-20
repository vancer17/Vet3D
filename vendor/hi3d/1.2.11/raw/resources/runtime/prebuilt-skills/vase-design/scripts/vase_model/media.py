"""Scene and export adapters for preview geometry in metres."""
from pathlib import Path
import json, math
import bpy, bmesh, numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from .product_core import active as _g_active, copy_obj as _g_copy_obj
from .product_preview import aim as _g_aim, export as _g_export, studio as _g_studio


from .preview_scene import check_framing as _check_framing
from .glb_export import export_glb as _export_glb

def bounds(objects):
    bpy.context.view_layer.update()
    xyz=np.concatenate([np.asarray([o.matrix_world@Vector(c) for c in o.bound_box]) for o in objects])
    return xyz.min(0),xyz.max(0)


def export_glb(path,objects,compress=False):
    """Write selected final objects; Draco is optional, never silently decimate."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if compress:
        _export_glb(path,objects,unhide=True,export_apply=True,export_animations=False,export_draco_mesh_compression_enable=True,export_draco_position_quantization=16,export_draco_normal_quantization=12,export_draco_texcoord_quantization=16)
    else:_g_export(path,objects)
    lo,hi=bounds(objects)
    return {'file':path.name,'bytes':path.stat().st_size,'dimensions_mm':((hi-lo)*1000).tolist(),'draco':compress,'triangle_reduction':False}


def export_section(path,body,others,axis,coordinate_mm,retained_positive=True):
    """True half-space subtraction on disposable body, no change to print original."""
    if axis not in (0,1,2):raise ValueError('section axis must be 0, 1 or 2')
    cut=_g_copy_obj(body,'DISPLAY cutaway');bpy.context.view_layer.update();_g_active(cut);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bm=bmesh.new();bm.from_mesh(cut.data);normal=[0.,0.,0.];normal[axis]=-1. if retained_positive else 1.;point=[0.,0.,0.];point[axis]=coordinate_mm/1000
    result=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-7,plane_co=point,plane_no=normal,clear_outer=True)
    edges=[v for v in result['geom_cut'] if isinstance(v,bmesh.types.BMEdge)];bmesh.ops.holes_fill(bm,edges=edges);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(cut.data);bm.free()
    if not len(cut.data.vertices):raise ValueError('section removes entire object')
    info=export_glb(path,[cut,*others]);bpy.data.objects.remove(cut,do_unlink=True)
    return info


def setup_studio(objects):
    lo,hi=bounds(objects);size=float(max(hi-lo));target=(lo+hi)/2
    s,cam=_g_studio(target,size*1.5,tuple(target+np.array([size*1.4,-size*2,size*1.1])))
    s.view_settings.exposure=-1.;s.render.resolution_x=900;s.render.resolution_y=900
    return s,cam


def render_views(output,objects,resolution=900,samples=24):
    """Create neutral multiviews from current actual objects, not a product-use scene."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True);s=bpy.context.scene;cam=s.camera
    lo,hi=bounds(objects);target=(lo+hi)/2;size=float(max(hi-lo));s.render.resolution_x=resolution;s.render.resolution_y=resolution;s.cycles.samples=samples
    views={'hero':(1.4,-2,1.1),'front':(0,-3,.45),'back':(0,3,.45),'top':(0,-.001,3)}
    for name,offset in views.items():
        cam.location=target+np.array(offset)*size;_g_aim(cam,target);cam.data.ortho_scale=size*1.4;s.render.filepath=str(output/(name+'.png'));bpy.ops.render.render(write_still=True)


def author_lift_animation(path,objects,moving,offset_mm,fps=24):
    """Author complete remove/return; offset is explicit task geometry, not evidence of clearance."""
    s=bpy.context.scene;cam=s.camera;s.frame_start=1;s.frame_end=120;s.render.fps=fps
    starts={o:o.location.copy() for o in moving};offset=Vector(offset_mm)/1000
    for f,t in [(1,0),(12,0),(42,1),(66,1),(108,0),(120,0)]:
        for o in moving:o.location=starts[o]+offset*t;o.keyframe_insert(data_path='location',frame=f)
    poses=[]
    for f in range(1,121):
        s.frame_set(f);lo,hi=bounds(objects);poses.extend([lo,hi])
    xyz=np.asarray(poses);lo=xyz.min(0);hi=xyz.max(0);target=(lo+hi)/2;size=max(hi-lo);cam.location=target+np.array([1.4,-2,1])*size;_g_aim(cam,target);cam.data.ortho_scale=size*1.55
    check=check_framing(s,cam,objects,range(1,121));s.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    for o in moving:o.animation_data_clear();o.location=starts[o]
    return {'fps':fps,'frames':[1,120],'action':'remove, hold for access, return','offset_mm':list(offset_mm),'framing':check,'collision_status':'requires actual path checks; keyframes alone do not prove assembly'}


def check_framing(scene,camera,objects,frames):
    return _check_framing(scene,camera,objects,frames,evaluated=False)


def render_frames(input_path,output,start=None,end=None,resolution=720,samples=32):
    """Open explicit animation scene; render unique frames. Existing frame names are refused."""
    input_path=Path(input_path);output=Path(output)
    if not input_path.is_file():raise FileNotFoundError(input_path)
    bpy.ops.wm.open_mainfile(filepath=str(input_path.resolve()));s=bpy.context.scene;start=s.frame_start if start is None else start;end=s.frame_end if end is None else end
    if not s.frame_start<=start<=end<=s.frame_end:raise ValueError('render range outside authored animation')
    output.mkdir(parents=True,exist_ok=True)
    if any((output/f'{f:04d}.png').exists() for f in range(start,end+1)):raise FileExistsError('Use a fresh frame directory or only the unrendered range')
    s.render.engine='CYCLES';s.cycles.samples=samples;s.render.threads_mode='FIXED';s.render.threads=2;s.render.resolution_x=resolution;s.render.resolution_y=resolution;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
    rows=[]
    for f in range(start,end+1):
        s.frame_set(f);p=output/f'{f:04d}.png';s.render.filepath=str(p);bpy.ops.render.render(write_still=True);rows.append({'frame':f,'file':p.name})
        (output/'render-record.json').write_text(json.dumps({'source':input_path.name,'fps':s.render.fps/s.render.fps_base,'frames':rows},indent=2))
    return rows
