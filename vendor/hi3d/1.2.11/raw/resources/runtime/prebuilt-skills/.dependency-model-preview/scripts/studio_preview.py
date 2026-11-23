import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
if __package__:
    from .studio_audit import bounds
    from .studio_core import cube, mat
else:
    from studio_audit import bounds
    from studio_core import cube, mat

from render_engine import set_engine

def stage(target=None,extent=None):
 sc=bpy.context.scene
 lo,hi=bounds();target=Vector(target)*S if target is not None else (lo+hi)/2
 ext=extent*S if extent else max(hi-lo)*1.5
 sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=24;sc.cycles.use_denoising=True;sc.render.threads_mode='FIXED';sc.render.threads=2
 sc.render.resolution_x=1100;sc.render.resolution_y=1000;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.render.film_transparent=False
 sc.view_settings.view_transform='AgX';sc.world=bpy.data.worlds.new('Slate studio');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.11,.14,.18,1);sc.world.node_tree.nodes['Background'].inputs[1].default_value=.18
 floor=mat('Stage | midnight',(.025,.041,.055),0,.57);o=cube('Stage',(3000,3000,4),(0,0,-2),floor,r=0,printable=False);o['asset']=False
 def light(name,loc,power,size,col):
  d=bpy.data.lights.new(name,'AREA');d.energy=power*.12;d.shape='DISK';d.size=size*ext;d.color=col;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=target+Vector(loc)*ext;o.rotation_euler=(target-o.location).to_track_quat('-Z','Y').to_euler()
 f=(ext/.3)**2
 light('Key warm',(-1.2,-1.4,1.8),85*f,1.4,(1,.89,.72));light('Fill cool',(1.4,-.3,.8),45*f,1.2,(.64,.80,1));light('Rim',(0,1.5,1.3),100*f,1,(.87,.96,1))
 d=bpy.data.cameras.new('Hero');o=bpy.data.objects.new('Hero',d);bpy.context.collection.objects.link(o);d.type='ORTHO';d.ortho_scale=ext;sc.camera=o
 camera((1.0,-1.6,.95),target=target,scale=ext)
 return target,ext


def camera(direction,target=None,scale=None):
 sc=bpy.context.scene;lo,hi=bounds();target=target if target is not None else (lo+hi)/2
 if bpy.data.objects.get('Stage'):bpy.data.objects['Stage'].hide_render=direction[2]<.2
 ext=scale or max(hi-lo)*1.5
 sc.camera.location=target+Vector(direction).normalized()*ext*3;sc.camera.rotation_euler=(target-sc.camera.location).to_track_quat('-Z','Y').to_euler();sc.camera.data.ortho_scale=ext


def render(path,frame=1,res=1000):
 if os.environ.get('ASTRA_SKIP_STILLS')=='1':return
 sc=bpy.context.scene;sc.frame_set(frame);sc.render.resolution_x=int(res*1.15);sc.render.resolution_y=res;sc.render.filepath=str(path);bpy.ops.render.render(write_still=True)


def export(path,animated=False):
 bpy.ops.object.select_all(action='DESELECT')
 for o in bpy.context.scene.objects:
  if o.get('asset'):o.select_set(True)
 bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_animations=animated,export_current_frame=not animated,export_animation_mode='ACTIONS',export_frame_range=True,export_force_sampling=True,export_materials='EXPORT',export_yup=True)


def save(path):bpy.ops.wm.save_as_mainfile(filepath=str(path))


def animate_video(out,frame_end=96,render_now=False):
 sc=bpy.context.scene;sc.frame_start=1;sc.frame_end=frame_end;sc.render.fps=24;save(out/'scene.blend')
 if render_now:
  set_engine(sc);sc.render.resolution_x=768;sc.render.resolution_y=672;sc.cycles.samples=12
  d=out/'frames';d.mkdir(exist_ok=True)
  for f in range(1,frame_end+1):
   sc.frame_set(f);sc.render.filepath=str(d/f'{f:04d}.png');bpy.ops.render.render(write_still=True)
