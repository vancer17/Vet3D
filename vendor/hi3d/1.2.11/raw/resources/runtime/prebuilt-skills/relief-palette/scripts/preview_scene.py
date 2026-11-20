"""Explicit preview framing and camera/light operations in scene units."""
import math
import bpy
from mathutils import Vector, Quaternion
from bpy_extras.object_utils import world_to_camera_view


def bounds_points(objects, *, evaluated, require_mesh=False):
    objects=list(objects)
    if not objects:raise ValueError('Explicit nonempty object list required')
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    if require_mesh and any(o.type != 'MESH' for o in objects):
        raise ValueError('Explicit product mesh objects are required')
    sources=[o.evaluated_get(deps) if evaluated else o for o in objects]
    if require_mesh and any(not o.data.vertices for o in sources):
        raise ValueError('Cannot frame an empty object')
    return [o.matrix_world @ Vector(v) for o in sources for v in o.bound_box]


def fit_orthographic_camera(camera, objects, resolution, *, evaluated, margin=1.15):
    if camera.data.type!='ORTHO' or not math.isfinite(margin) or margin<1 or len(resolution)!=2 or min(resolution)<=0:
        raise ValueError('Orthographic camera, positive resolution and margin >= 1 required')
    bpy.context.view_layer.update()
    inv=camera.matrix_world.inverted()
    points=[inv @ p for p in bounds_points(objects,evaluated=evaluated)]
    xs,ys=[p.x for p in points],[p.y for p in points]
    width,height=max(xs)-min(xs),max(ys)-min(ys);aspect=resolution[0]/resolution[1]
    horizontal=camera.data.sensor_fit=='HORIZONTAL' or (camera.data.sensor_fit=='AUTO' and aspect>=1)
    scale=max(width,height*aspect) if horizontal else max(width/aspect,height)
    if scale<=0 or not math.isfinite(scale):raise ValueError('Nondegenerate finite projected bounds required')
    camera.location+=camera.matrix_world.to_quaternion() @ Vector(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,0))
    camera.data.ortho_scale=scale*margin
    bpy.context.view_layer.update()


def position_camera(camera, center, direction, scale, roll=0):
    center=Vector(center);camera.location=center+Vector(direction)
    q=(center-camera.location).to_track_quat('-Z','Y') @ Quaternion((0,0,1),math.radians(roll))
    camera.rotation_euler=q.to_euler();camera.data.ortho_scale=scale


def projected_bounds(scene,camera,objects,*,evaluated,check_depth=False,require_mesh=False):
    points=[world_to_camera_view(scene,camera,p) for p in bounds_points(objects,evaluated=evaluated,require_mesh=require_mesh)]
    if check_depth and (min(p.z for p in points)<=camera.data.clip_start or max(p.z for p in points)>=camera.data.clip_end):
        raise ValueError('Product crosses the camera depth clipping interval')
    return dict(min_x=min(p.x for p in points),max_x=max(p.x for p in points),
                min_y=min(p.y for p in points),max_y=max(p.y for p in points),all_in_front=all(p.z>0 for p in points))


def fit_projected_orthographic_camera(scene, camera, objects, *, evaluated, margin=.05):
    """Fit a static camera using scene pixel aspect/shift and normalized image margins."""
    if camera.type != 'CAMERA' or camera.data.type != 'ORTHO':
        raise ValueError('Automatic fitting supports orthographic cameras only')
    if camera.parent or camera.constraints or camera.animation_data:
        raise ValueError('Use an independent static camera for automatic fitting')
    if not math.isfinite(margin) or not 0 <= margin < .45:
        raise ValueError('margin must be in [0, .45)')
    objects = list(objects)
    def project():
        return projected_bounds(scene, camera, objects, evaluated=evaluated,
                                check_depth=True, require_mesh=True)
    bounds = project()
    span = max(bounds['max_x']-bounds['min_x'], bounds['max_y']-bounds['min_y'])
    if span <= 0:
        raise ValueError('Degenerate camera bounds')
    camera.data.ortho_scale *= span / (1-2*margin)
    bpy.context.view_layer.update()
    # Shift is relative to ortho_scale: center using the final camera frame.
    bounds = project()
    center = [(bounds['min_x']+bounds['max_x'])/2, (bounds['min_y']+bounds['max_y'])/2]
    frame = camera.data.view_frame(scene=scene)
    width = max(p.x for p in frame)-min(p.x for p in frame)
    height = max(p.y for p in frame)-min(p.y for p in frame)
    right = camera.matrix_world.to_quaternion() @ Vector((1, 0, 0))
    up = camera.matrix_world.to_quaternion() @ Vector((0, 1, 0))
    camera.location += right * (center[0]-.5)*width + up * (center[1]-.5)*height
    bpy.context.view_layer.update()
    result = project()
    if min(result['min_x'],result['min_y']) < margin-1e-5 or max(result['max_x'],result['max_y']) > 1-margin+1e-5:
        raise RuntimeError('Automatic framing failed')
    return result


def check_framing(scene,camera,objects,frames,*,evaluated,margin=.01):
    objects=list(objects)
    if not 0<=margin<.5:raise ValueError('Normalized frame margin must be in [0,.5)')
    if __package__:
        from .scene_samples import sample_frames
    else:
        from scene_samples import sample_frames
    def inspect(frame):
        p=projected_bounds(scene,camera,objects,evaluated=evaluated)
        return {'frame':frame,'visible_bounds':bool(p['min_x']>margin and p['max_x']<1-margin and p['min_y']>margin and p['max_y']<1-margin and p['all_in_front'])}
    rows=sample_frames(scene,frames,inspect)
    return {'all_bounds_in_frame':all(r['visible_bounds'] for r in rows),'samples':rows}


def area_light(name,location,target,energy,size,color,*,collection,shape='DISK'):
    data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.size=size;data.color=color;data.shape=shape
    obj=bpy.data.objects.new(name,data);collection.objects.link(obj);obj.location=location
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    return obj
