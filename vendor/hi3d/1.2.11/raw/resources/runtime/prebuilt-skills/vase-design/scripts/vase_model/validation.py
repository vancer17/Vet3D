"""Read-only numerical checks on actual exports; does not certify manufacturing."""
from pathlib import Path
import numpy as np
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree


if __package__:
    from .mesh_measure import measure_mesh
else:
    from mesh_measure import measure_mesh

def mesh_metrics(ob,weld=1e-8):
    measured = measure_mesh(ob.data, weld=weld, area_epsilon=1e-16)
    result = {key: measured[key] for key in ('vertices','faces','components','boundary_edges','nonmanifold_edges')}
    result.update(zero_area_faces=measured['degenerate_faces'], signed_volume_ml=measured['signed_volume']*1e6)
    return result


def check_stl(path):
    """Import actual millimetre STL to metre-space, check welded diagnostic copy, remove imported data."""
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    before=set(bpy.data.objects);bpy.ops.wm.stl_import(filepath=str(path.resolve()));obs=[o for o in bpy.data.objects if o not in before]
    try:
        for o in obs:
            for v in o.data.vertices:v.co/=1000
        return [mesh_metrics(o) for o in obs]
    finally:
        for o in obs:bpy.data.objects.remove(o,do_unlink=True)


def passage_clearance(ob,points_mm,required_radius_mm):
    """Finite path samples: report nearest surface clearance; not a global-minimum or fluid test."""
    p=np.asarray(points_mm,float)
    if p.ndim!=2 or p.shape[1]!=3 or len(p)<2 or required_radius_mm<=0:raise ValueError('Expected >=2 xyz samples and positive clearance radius')
    bm=bmesh.new();bm.from_mesh(ob.data);bm.transform(ob.matrix_world)
    try:
        tree=BVHTree.FromBMesh(bm);distances=[tree.find_nearest(Vector(q)/1000)[3]*1000 for q in p];spacing=float(max(np.linalg.norm(np.diff(p,axis=0),axis=1)));lower=min(distances)-spacing/2
        return {'sample_count':len(p),'minimum_sample_distance_mm':min(distances),'max_sample_spacing_mm':spacing,'conservative_continuous_distance_bound_mm':lower,'required_radius_mm':required_radius_mm,'clearance_bound_pass':lower>=required_radius_mm,'limitation':'Distance alone does not establish that the path starts in the void; independently check cavity connectivity and endpoints.'}
    finally:bm.free()


def require_print_topology(results):
    """Reject defective final print exports; this gate alone is not manufacturing approval."""
    rows=[]
    def collect(value):
        if isinstance(value,list):
            for x in value:collect(x)
        elif isinstance(value,dict):
            if 'components' in value:rows.append(value)
            else:
                for x in value.values():collect(x)
    collect(results)
    if not rows:raise ValueError('No actual print export metrics supplied')
    bad=[r for r in rows if r['components']!=1 or any(r[k] for k in ['boundary_edges','nonmanifold_edges','zero_area_faces']) or r['signed_volume_ml']<=0]
    if bad:raise ValueError('Actual print export failed connectivity/closure/degeneracy checks; inspect measurement.json and preserve failed candidate')
    return True
