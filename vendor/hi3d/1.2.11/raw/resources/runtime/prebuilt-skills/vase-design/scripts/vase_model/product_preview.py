import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
if __package__:
    from .product_core import cube, mat
else:
    from product_core import cube, mat

if __package__:
 from .glb_export import export_glb as _export_glb
else:
 from glb_export import export_glb as _export_glb

if __package__:
 from .preview_scene import area_light as _area_light
else:
 from preview_scene import area_light as _area_light

def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()


def studio(target,scale,hero=(-.40,-.55,.34)):
 s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.length_unit='MILLIMETERS';s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=24;s.cycles.use_denoising=True;s.render.threads_mode='FIXED';s.render.threads=2;s.render.resolution_x=1100;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.film_transparent=False;s.view_settings.view_transform='AgX';s.world=bpy.data.worlds.new('Neutral studio');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.13,.16,.18,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.3
 for pos,power,size,c in [((-.25,-.4,.5),15,.32,(1,.88,.74)),((.35,-.12,.35),9,.26,(.67,.84,1)),((.1,.3,.45),20,.25,(1,.85,.64))]:
  _area_light('Area',pos,target,power,size,c,collection=bpy.context.collection)
 floor=cube('STUDIO floor',(0,0,-.0025),(2,2,.005),mat('Charcoal stone',(.021,.034,.040),0,.45))
 bpy.ops.object.camera_add(location=hero);cam=bpy.context.object;cam.name='Hero';cam.data.type='ORTHO';cam.data.ortho_scale=scale;cam.data.clip_start=.0005;s.camera=cam;aim(cam,target);return s,cam


def render(path,cam=None,loc=None,target=None,scale=None,samples=24):
 s=bpy.context.scene
 if cam:
  s.camera=cam
  if loc:cam.location=loc
  if target:aim(cam,target)
  if scale:cam.data.ortho_scale=scale
 s.render.resolution_percentage=100;s.cycles.samples=samples;s.render.filepath=str(path);bpy.ops.render.render(write_still=True)


def export(path,objects):
 _export_glb(path,objects,convert_curves=True,unhide=True,export_animations=False,export_apply=True)


def export_checked(path,objects):
 bpy.context.view_layer.update();export(path,objects)
 d=np.concatenate([np.array([o.matrix_world@Vector(c) for c in o.bound_box]) for o in objects]);return ((d.max(0)-d.min(0))*1000).tolist()
