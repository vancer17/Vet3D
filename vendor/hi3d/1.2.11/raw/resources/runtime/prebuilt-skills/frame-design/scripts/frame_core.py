import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
def applymods(o):
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def boolean(o, c, op='UNION'):
    applymods(o)
    applymods(c)
    bpy.context.view_layer.objects.active = o
    m = o.modifiers.new(op + ' actual solid', 'BOOLEAN')
    m.operation = op
    m.solver = 'MANIFOLD'
    m.object = c
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(c, do_unlink=True)


def cylinder(name, r, d, loc, mat, axis=None, n=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=n, radius=r * MM, depth=d * MM, location=np.array(loc) * MM)
    o = bpy.context.object
    o.name = name
    if axis is not None:
        o.rotation_euler = Vector(axis).to_track_quat('Z', 'Y').to_euler()
    if mat:
        o.data.materials.append(mat)
    return o


def hole(o, xy, r, z0, z1):
    boolean(o, cylinder('Bore cutter', r, z1 - z0, [*xy, (z0 + z1) / 2], None), 'DIFFERENCE')


def smoothmesh(o):
    for p in o.data.polygons:
        p.use_smooth = True
