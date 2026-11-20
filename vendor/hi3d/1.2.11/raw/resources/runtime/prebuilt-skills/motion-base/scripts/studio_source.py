import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
if __package__:
    from .studio_core import smooth, tag
else:
    from studio_core import smooth, tag

def source(label,height,loc,m=None,*,asset_dir):
 before=set(bpy.context.scene.objects);bpy.ops.import_scene.gltf(filepath=str(pathlib.Path(asset_dir)/f'{label}.glb'));os=[o for o in bpy.context.scene.objects if o not in before and o.type=='MESH']
 bpy.ops.object.select_all(action='DESELECT')
 for o in os:o.select_set(True)
 bpy.context.view_layer.objects.active=os[0]
 if len(os)>1:bpy.ops.object.join()
 o=bpy.context.object;s=height*S/o.dimensions.z;o.scale*=s;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 bounds=[o.matrix_world@Vector(v) for v in o.bound_box];mi=Vector([min(v[i] for v in bounds) for i in range(3)]);ma=Vector([max(v[i] for v in bounds) for i in range(3)])
 o.location+=Vector(loc)*S-Vector(((mi.x+ma.x)/2,(mi.y+ma.y)/2,mi.z));bpy.ops.object.transform_apply(location=True,rotation=False,scale=False)
 return smooth(tag(o,'Hi3D '+label,m))
