import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001

def bounds(objs=None):
 objs=objs or [o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('asset')]
 vs=[o.matrix_world@Vector(v) for o in objs for v in o.bound_box]
 return Vector([min(v[i] for v in vs) for i in range(3)]),Vector([max(v[i] for v in vs) for i in range(3)])


def metric(out,extra=None):
 import bmesh
 rows=[]
 for o in bpy.context.scene.objects:
  if o.type!='MESH' or not o.get('asset'):continue
  bm=bmesh.new();bm.from_mesh(o.data)
  rows.append({'name':o.name,'printable':bool(o.get('printable')),'dimensions_mm':[round(x*1000,4) for x in o.dimensions],'vertices':len(o.data.vertices),'faces':len(o.data.polygons),'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'volume_mm3':round(abs(bm.calc_volume())*1e9,3)})
  bm.free()
 lo,hi=bounds();d={'blender':bpy.app.version_string,'unit':'mm','bounds_mm':[list(lo*1000),list(hi*1000)],'parts':rows,'physical_testing':'unverified'}
 if extra:d.update(extra)
 out.write_text(json.dumps(d,indent=2))
