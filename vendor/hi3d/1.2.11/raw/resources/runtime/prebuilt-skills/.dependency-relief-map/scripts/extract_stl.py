"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys, argparse, json, hashlib, struct
from pathlib import Path
from mathutils import Vector
from height_sampling import sample_mesh
from height_ops import subtract_baseline, normalize_height, repair_pits
from triangle_arrays import edge_incidence, triangle_double_areas
import bpy
import numpy as np
from planar_core import material, mesh
from planar_preview import camera, clean, stage
from types import SimpleNamespace
from functools import partial
from frame_runtime import cli_arguments, validate_paths
from frame_diy_runtime import prepare_paths
from planar_render import render as _render_base

from cli_schemas import relief_stage

def extract(*, source, output, resolution=(769, 769), axes=(0, 1, 2), front_sign=1, pit_threshold=0.2, median_floor=0.3, no_render=False):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(source=source, output=output, resolution=resolution, no_render=no_render)
    paths,inputs=prepare_paths(output=output,raw_inputs={'source':source})
    a.output=paths['output'];a.source=inputs['source']
    if len(resolution)!=2 or any(isinstance(n,bool) or not isinstance(n,int) or n<8 for n in resolution):raise ValueError('Resolution must be two integer counts of at least 8')
    if len(axes)!=3 or set(axes)!={0,1,2} or front_sign not in (-1,1):raise ValueError('Invalid axes or front sign')
    if any(not np.isfinite(v) or not 0<=v<=1 for v in (pit_threshold,median_floor)):raise ValueError('Repair thresholds must be finite in [0,1]')
    render=partial(_render_base, enabled=not getattr(a, "no_render", False))
    out = Path(a.output).resolve()
    b = Path(a.source).read_bytes()
    if len(b)<84:raise ValueError('Expected nonempty binary STL, not GLB/glTF/ASCII STL')
    count=struct.unpack_from('<I',b,80)[0]
    if count==0 or len(b)!=84+count*50:raise ValueError('Binary STL record count/length mismatch; convert other formats first')
    dt = np.dtype([('normal', '<f4', (3,)), ('v', '<f4', (3, 3)), ('attr', '<u2')])
    tri = np.frombuffer(b, dtype=dt, offset=84, count=struct.unpack_from('<I', b, 80)[0])['v'].astype(float)
    if not np.isfinite(tri).all():raise ValueError('Nonfinite STL coordinates')
    wa,ha,da=axes
    tri=tri[:,:,list(axes)]
    tri[:,:,2]*=front_sign
    v, ix = np.unique(tri.reshape(-1, 3), axis=0, return_inverse=True)
    f = ix.reshape(-1, 3)
    lo = v.min(0)
    hi = v.max(0)
    if np.any(hi-lo<=0):raise ValueError('Source must have positive extent along all sampling axes')
    out.mkdir(parents=True, exist_ok=True)
    nx, ny = a.resolution
    raw, valid, _ = sample_mesh(v, f, resolution=(nx, ny), ray_margin=1, all_triangles=True)
    baseline = float(lo[2])
    h, mx = normalize_height(subtract_baseline(raw, baseline), percentile=99.9)
    before = h.copy()
    h, mask, _ = repair_pits(h, kernel=5, threshold=pit_threshold,
                             median_floor=median_floor, iterations=1, dtype=h.dtype)
    np.savez_compressed(out / 'heightfield.npz', height=h, raw=raw, before=before, repair_mask=mask, source_bounds=np.array([lo, hi]))
    clean()
    clay = material('Source neutral clay', (0.31, 0.33, 0.35), 0, 0.72)
    o = mesh('Measured source relief in sampling coordinates', v, f, clay)
    cam = stage((0, 0, 0), float(np.ptp(v, axis=0).max()))
    s = bpy.context.scene
    for title, delta in [('source-front', (0, 0, 80)), ('source-side', (0, -80, 8)), ('source-oblique', (35, -50, 60))]:
        camera(cam, ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0), delta, 50)
        render(out / (title + '.png'), 1000, 850, 16)
    _, counts, _ = edge_incidence(f, discard_collapsed=False)
    area = triangle_double_areas(v, f) * 0.5
    meta = {'sampling_axes':list(axes),'front_sign':front_sign,'source_sha256': hashlib.sha256(b).hexdigest(), 'source_bounds_mm': [lo.tolist(), hi.tolist()], 'triangles': len(f), 'exact_weld_vertices': len(v), 'boundary_edges': int((counts == 1).sum()), 'nonmanifold_edges': int((counts > 2).sum()), 'zero_area_faces': int((area == 0).sum()), 'resolution': [nx, ny], 'valid_ray_fraction': float(np.isfinite(raw).mean()), 'height_normalization_mm': mx, 'repair': {'kernel': 5, 'threshold': pit_threshold, 'median_floor': median_floor, 'modified_samples': int(mask.sum())}, 'mapping_limit': 'Single first-hit front surface; hidden geometry is not preserved. Original relief kept unchanged.'}
    (out / 'source-inspection.json').write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta))

def main(argv=None):
    return relief_stage(extract, cli_arguments, argv)

if __name__ == "__main__":
    main()
