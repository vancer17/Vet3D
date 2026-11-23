import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001

def bounds(objects):
 deps=bpy.context.evaluated_depsgraph_get();allv=[]
 for o in objects:
  eo=o.evaluated_get(deps);m=eo.to_mesh()
  allv.extend([eo.matrix_world@v.co for v in m.vertices]);eo.to_mesh_clear()
 v=np.array(allv)/MM
 return {'min_mm':v.min(0).tolist(),'max_mm':v.max(0).tolist(),'dimensions_mm':np.ptp(v,axis=0).tolist()}
