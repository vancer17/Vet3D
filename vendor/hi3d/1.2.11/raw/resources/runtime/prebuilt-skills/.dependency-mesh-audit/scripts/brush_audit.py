import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
def bounds(objects):
 v=np.array([o.matrix_world@Vector(c) for o in objects for c in o.bound_box]);return {'min_mm':(v.min(0)/MM).tolist(),'max_mm':(v.max(0)/MM).tolist(),'dimensions_mm':(np.ptp(v,axis=0)/MM).tolist()}
