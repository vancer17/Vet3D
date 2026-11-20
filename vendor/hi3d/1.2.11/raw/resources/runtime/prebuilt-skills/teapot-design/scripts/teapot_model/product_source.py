import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
if __package__:
    from .product_core import active, clean, copy_obj, mat, mesh
else:
    from product_core import active, clean, copy_obj, mat, mesh

def import_source(path, height=None, width=None, ratio=1.0, rotation_z=0):
 path=Path(path).resolve()
 if not path.is_file(): raise FileNotFoundError(path)
 if not 0 < ratio <= 1: raise ValueError("ratio must be in (0, 1]")
 if (height is None)==(width is None): raise ValueError("provide exactly one positive height or width in metres")
 target=height if height is not None else width
 if not np.isfinite(target) or target<=0: raise ValueError("target dimension must be positive and finite")
 if not np.isfinite(rotation_z): raise ValueError("rotation_z must be finite radians")
 m=mat('Input neutral',(.5,.5,.5),0,.7)
 if path.suffix.lower()=='.npz':
  with np.load(path,allow_pickle=False) as d: o=mesh('Input mesh',d['vertices'],d['faces'],m)
 elif path.suffix.lower() in ('.glb','.gltf','.stl'):
  before=set(bpy.data.objects)
  if path.suffix.lower()=='.stl': bpy.ops.wm.stl_import(filepath=str(path))
  else: bpy.ops.import_scene.gltf(filepath=str(path))
  obs=[o for o in bpy.data.objects if o not in before and o.type=='MESH']
  if not obs: raise ValueError('Input contains no mesh')
  for ob in obs:
   mw=ob.matrix_world.copy();ob.parent=None;ob.matrix_world=mw
  bpy.ops.object.select_all(action='DESELECT')
  for ob in obs: ob.select_set(True)
  bpy.context.view_layer.objects.active=obs[0];bpy.ops.object.join();o=bpy.context.object
  bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
 else: raise ValueError('Input must be GLB, glTF, STL or vertices/faces NPZ')
 o.rotation_mode='XYZ';o.rotation_euler.z=rotation_z;active(o);bpy.ops.object.transform_apply(location=False,rotation=True,scale=False)
 v=np.asarray([p.co[:] for p in o.data.vertices]);lo=v.min(0);hi=v.max(0);axis=2 if height is not None else 0
 if hi[axis]-lo[axis]<=0: raise ValueError('Source has zero extent along scale axis')
 v=(v-np.array([(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,lo[2]]))*target/(hi[axis]-lo[axis])
 o.data.vertices.foreach_set('co',v.astype(np.float32).ravel());o.data.update()
 original=copy_obj(o,'SOURCE retained normalized original');original.hide_render=True;original.hide_set(True)
 clean(o,1e-8)
 if ratio<1:
  active(o);q=o.modifiers.new('Disclosed preview reduction','DECIMATE');q.ratio=ratio;bpy.ops.object.modifier_apply(modifier=q.name);clean(o)
 return o,original
