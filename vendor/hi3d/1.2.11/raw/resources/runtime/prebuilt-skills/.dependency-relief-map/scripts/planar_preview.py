import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
if __package__:
    from .planar_core import cube, material
else:
    from planar_core import cube, material

if __package__:
 from .glb_export import export_glb as _export_glb
else:
 from glb_export import export_glb as _export_glb

if __package__:
 from .preview_scene import area_light as _area_light
else:
 from preview_scene import area_light as _area_light

def clean():
 bpy.ops.wm.read_factory_settings(use_empty=True)
 s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.length_unit='MILLIMETERS';s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=24;s.cycles.use_denoising=True;s.render.threads_mode='FIXED';s.render.threads=2;s.view_settings.view_transform='AgX'
 s.render.resolution_x=1200;s.render.resolution_y=1000;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.fps=24;s.world=bpy.data.worlds.new('Midnight studio');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.055,.068,.085,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.4


def export_glb(path,objects):
 _export_glb(path,objects,export_apply=True,export_animations=False)


def stage(target,span):
 s=bpy.context.scene;target=np.array(target)*MM;S=span*MM
 floor=material('Warm charcoal cyclorama',(.026,.034,.047),0,.56);cube('Studio floor',(span*20,span*20,2),(0,0,-4),floor,0)
 def light(name,loc,power,size,color):
  _area_light(name,target+np.array(loc)*S,target,power*S*S,size*S,color,collection=bpy.context.collection)
 light('Key softbox',(-.9,-.9,1.6),36,1.2,(1,.88,.71));light('Cool fill',(1,-.1,.9),22,.85,(.70,.83,1));light('Edge strip',(.1,1.4,1.2),40,.7,(1,.87,.69))
 bpy.ops.object.camera_add(location=target+np.array((.8,-1.1,1.3))*S);cam=bpy.context.object;cam.name='Hero camera';cam.data.type='ORTHO';cam.data.ortho_scale=S*1.35;cam.data.clip_start=.001;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();s.camera=cam;return cam


def camera(cam,target,delta,scale):
 cam.location=(np.array(target)+np.array(delta))*MM;cam.rotation_euler=(Vector(np.array(target)*MM)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale*MM


def save(path):bpy.ops.wm.save_as_mainfile(filepath=str(path))
