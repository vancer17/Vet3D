import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
if __package__:
    from .planar_core import clean_solid_mesh
else:
    from planar_core import clean_solid_mesh
def union_solids(target, cutters, *, solver='MANIFOLD'):
 """Union overlapping solids into target; applies modifiers and removes cutters.

 Callers must remove cutter references from their product/group lists. A tangent
 contact is insufficient: tools must overlap the intended receiving solid.
 """
 for obj in [target,*cutters]:
  bpy.context.view_layer.objects.active=obj
  for mod in list(obj.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
 for obj in cutters:
  bpy.context.view_layer.objects.active=target
  mod=target.modifiers.new('Continuous tray union','BOOLEAN');mod.operation='UNION';mod.solver=solver;mod.object=obj
  bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(obj,do_unlink=True)
 clean_solid_mesh(target)
 return target


def apply(o):
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def boolean(o, c, op='UNION'):
    apply(o)
    apply(c)
    bpy.context.view_layer.objects.active = o
    m = o.modifiers.new(op + ' solid', 'BOOLEAN')
    m.operation = op
    m.solver = 'MANIFOLD'
    m.object = c
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(c, do_unlink=True)


def cyl(name, r, h, loc, mat, axis=(0, 0, 1), n=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=n, radius=r * MM, depth=h * MM, location=np.asarray(loc) * MM)
    o = bpy.context.object
    o.name = name
    o.rotation_euler = Vector(axis).to_track_quat('Z', 'Y').to_euler()
    o.data.materials.append(mat)
    return o


def hole(o, x, y, r, z0, z1):
    boolean(o, cyl('Precision bore', r, z1 - z0, (x, y, (z0 + z1) / 2), o.data.materials[0]), 'DIFFERENCE')
