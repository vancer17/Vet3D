import bpy, bmesh, numpy as np, math, json, struct, os, pathlib
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
MM = S = .001
if __package__:
    from .product_core import active
else:
    from product_core import active

def stl(path,objects):
 # Triangulate a disposable numerical-cleanup copy, preserving native surfaces.
 copies=[];dg=bpy.context.evaluated_depsgraph_get()
 for source in objects:
  me=bpy.data.meshes.new_from_object(source.evaluated_get(dg));o=bpy.data.objects.new(source.name+' STL numerical cleanup',me);bpy.context.collection.objects.link(o);o.matrix_world=source.matrix_world.copy();copies.append(o)
  active(o);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
  bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-8);bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY');bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-6);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
 bpy.ops.object.select_all(action='DESELECT')
 for o in copies:o.select_set(True)
 bpy.context.view_layer.objects.active=copies[0];bpy.ops.wm.stl_export(filepath=str(path),export_selected_objects=True,global_scale=1000,apply_modifiers=True)
 for o in copies:bpy.data.objects.remove(o,do_unlink=True)

def export_parts(output, parts):
    """Write named metre-profile parts and return raw topology metrics per part."""
    if __package__:
        from .product_audit import topo
    else:
        from product_audit import topo
    output=Path(output);output.mkdir(parents=True,exist_ok=True);result={}
    for name,ob in parts.items():
        if Path(name).name!=name or not name:raise ValueError('part names must be file stems')
        stl(output/(name+'.stl'),[ob]);result[name]=topo(ob)
    return result
