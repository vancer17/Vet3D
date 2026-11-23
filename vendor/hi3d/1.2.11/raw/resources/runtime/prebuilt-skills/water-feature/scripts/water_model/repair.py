"""Targeted cleanup of near-collinear faces after millimetre STL quantization."""
from pathlib import Path
import json,bpy,bmesh


def repair_stl(input_path,output_path,area_threshold_mm2=.0001,weld_mm=.00001,max_iterations=6):
    """Read actual STL and write a separate locally repaired file; fails if closure is not preserved."""
    inp=Path(input_path).resolve();out=Path(output_path).resolve()
    if inp==out:raise ValueError('Repair output must differ from input')
    if not inp.is_file():raise FileNotFoundError(inp)
    if area_threshold_mm2<=0 or weld_mm<=0 or max_iterations<1:raise ValueError('Invalid cleanup thresholds')
    before=set(bpy.data.objects);bpy.ops.wm.stl_import(filepath=str(inp));ob=bpy.context.object;bm=bmesh.new();bm.from_mesh(ob.data);rows=[]
    try:
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=weld_mm)
        for attempt in range(max_iterations):
            bad=[f for f in bm.faces if f.calc_area()<area_threshold_mm2];rows.append({'iteration':attempt,'small_faces':len(bad)})
            if not bad:break
            for f in bad:
                if not f.is_valid:continue
                edges=sorted([e for e in f.edges if e.is_manifold],key=lambda e:e.calc_length(),reverse=True)
                if edges:
                    middle=next(v for v in f.verts if v not in edges[0].verts);bmesh.ops.dissolve_verts(bm,verts=[middle],use_face_split=False,use_boundary_tear=False)
            bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>3]);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=weld_mm*10);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        final={'small_faces':sum(f.calc_area()<area_threshold_mm2 for f in bm.faces),'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges)}
        if any(final.values()):raise ValueError('Local cleanup did not yield a closed clean surface; preserve source and inspect')
        bm.to_mesh(ob.data);out.parent.mkdir(parents=True,exist_ok=True);bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.wm.stl_export(filepath=str(out),export_selected_objects=True)
        return {'units':'millimetres','iterations':rows,'final':final,'limitation':'Local numerical correction only; inspect fine features and actual repaired file'}
    finally:
        bm.free()
        for o in [x for x in bpy.data.objects if x not in before]:bpy.data.objects.remove(o,do_unlink=True)
