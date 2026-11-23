"""First-hit relief sampling in source STL millimetres; masks missed rays, preserves aspect."""
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector
from .height_sampling import sample_mesh
from .height_ops import subtract_baseline, normalize_height


def sample_relief(input_path,output_path,resolution=1024):
    input_path=Path(input_path);output_path=Path(output_path)
    if not input_path.is_file():raise FileNotFoundError(input_path)
    if input_path.suffix.lower()!='.stl':raise ValueError('Sampling needs front-facing millimetre STL')
    if not 32<=resolution<=2048:raise ValueError('resolution must be 32–2048')
    before=set(bpy.data.objects);bpy.ops.wm.stl_import(filepath=str(input_path.resolve()));o=bpy.context.object;bm=bmesh.new();bm.from_mesh(o.data)
    try:
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6);xyz=np.asarray([v.co[:] for v in bm.verts]);lo=xyz.min(0);hi=xyz.max(0)
        if min(hi[:2]-lo[:2])<=0:raise ValueError('Relief needs nonzero X/Y extent')
        base=float(np.quantile(xyz[:,2],.01));nx=resolution;ny=max(16,round(nx*(hi[1]-lo[1])/(hi[0]-lo[0])))
        bm.verts.index_update()
        faces=[[v.index for v in face.verts] for face in bm.faces]
        raw, valid, _=sample_mesh(xyz,faces,resolution=(nx,ny),ray_margin=10)
        mask=valid.astype(np.uint8)
        if not mask.any():raise ValueError('No visible source relief')
        H,maximum=normalize_height(subtract_baseline(raw,base),percentile=99.9,mask=valid,positive_only=False)
        output_path.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(output_path,height=H,mask=mask,bounds_xy_mm=np.stack([lo[:2],hi[:2]]),base_z_mm=base,height_scale_mm=maximum)
        return {'shape_yx':[ny,nx],'source_bounds_mm':[lo.tolist(),hi.tolist()],'base_z_mm':base,'height_scale_mm':maximum,'mask_coverage':float(mask.mean()),'limitation':'First-hit +Z heightfield discards undercuts; source orientation must be supplied correctly'}
    finally:
        bm.free()
        for ob in [x for x in bpy.data.objects if x not in before]:bpy.data.objects.remove(ob,do_unlink=True)
