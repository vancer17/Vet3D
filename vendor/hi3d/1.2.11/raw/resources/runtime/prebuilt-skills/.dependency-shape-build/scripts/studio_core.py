
# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, math, json, pathlib, struct, sys, os
from mathutils import Vector, Matrix
from math import sin,cos,pi
S=0.001

if __package__:
 from .blender_primitives import curve_tube as _curve_tube, cylinder_object as _cylinder_object
else:
 from blender_primitives import curve_tube as _curve_tube, cylinder_object as _cylinder_object

if __package__:
 from .material_nodes import principled_material as _principled
else:
 from material_nodes import principled_material as _principled

def reset():
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1

def mat(name,col,metal=0,rough=.32):
 return _principled(name,col,metallic=metal,roughness=rough)

def tag(o,name,m=None,printable=True):
 o.name=name;o['asset']=True;o['printable']=printable
 if m:o.data.materials.clear();o.data.materials.append(m)
 return o

def apply(o,name):
 bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=name)

def smooth(o):
 if o.type=='MESH':
  for name in ['sharp_edge','sharp_face','custom_normal']:
   a=o.data.attributes.get(name)
   if a:o.data.attributes.remove(a)
  if o.data.has_custom_normals:o.data.normals_split_custom_set([(0,0,0)]*len(o.data.loops))
  for p in o.data.polygons:p.use_smooth=True
 return o

def cube(name,dim,loc,m=None,r=1,printable=True,segments=4):
 bpy.ops.mesh.primitive_cube_add(size=1,location=Vector(loc)*S);o=bpy.context.object;o.dimensions=Vector(dim)*S
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if r:
  q=o.modifiers.new('Edge radii','BEVEL');q.width=r*S;q.segments=segments;apply(o,q.name)
  q=o.modifiers.new('Weighted edge normals','WEIGHTED_NORMAL');apply(o,q.name)
 return tag(o,name,m,printable)

def cyl(name,r,d,loc,m=None,axis='Z',printable=True,n=64):
 o=_cylinder_object(name,Vector(loc)*S,r*S,d*S,collection=bpy.context.collection,axis=axis,segments=n)
 bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
 q=o.modifiers.new('Edge radii','BEVEL');q.width=min(.5,r/10)*S;q.segments=3;apply(o,q.name)
 return smooth(tag(o,name,m,printable))

def uv(name,dim,loc,m=None,printable=True):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,location=Vector(loc)*S);o=bpy.context.object;o.dimensions=Vector(dim)*S;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return smooth(tag(o,name,m,printable))

def tube(name,points,r,m=None,printable=True):
 o=_curve_tube(name,[[x*S for x in co] for co in points],r*S,collection=bpy.context.collection,spline='POLY')
 bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.convert(target='MESH');return smooth(tag(o,name,m,printable))

def bar(name,a,b,r,m=None,printable=True):
 a=Vector(a);b=Vector(b);o=cyl(name,r,(b-a).length,(a+b)/2,m,printable=printable);o.rotation_mode='QUATERNION';o.rotation_quaternion=Vector((0,0,1)).rotation_difference((b-a).normalized());return o

def empty(name,loc=(0,0,0)):
 o=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(o);o.location=Vector(loc)*S;o['asset']=True;return o

def parent(o,p):
 bpy.context.view_layer.update();mw=o.matrix_world.copy();o.parent=p;o.matrix_world=mw

def boolop(o,cutter,operation='DIFFERENCE'):
 bpy.context.view_layer.objects.active=o;m=o.modifiers.new('Precisely cut '+cutter.name,'BOOLEAN');m.operation=operation;m.solver='EXACT';m.object=cutter;apply(o,m.name);bpy.data.objects.remove(cutter,do_unlink=True);return o

def cutbox(o,dim,loc):return boolop(o,cube('cutter',dim,loc,r=0))

def hole(o,r,d,loc,axis='Z'):return boolop(o,cyl('bore',r,d,loc,axis=axis))
