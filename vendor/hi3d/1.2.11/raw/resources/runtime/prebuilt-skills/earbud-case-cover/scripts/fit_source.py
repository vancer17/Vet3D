"""Fit an art source to a requested envelope; does not assert device compatibility."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

from pathlib import Path
import json,shutil,numpy as np
from stage_cli import cli_arguments
from path_safety import validate_write_roots

def fit_vertices(vertices, width_mm, depth_mm, rear_depth_scale=1.0, transition_mm=5.0):
    """Return fitted Nx3 mm vertices and transform metadata; no mutation or file I/O."""
    v=np.asarray(vertices,dtype=float).copy()
    if v.ndim!=2 or v.shape[1]!=3 or len(v)==0 or not np.isfinite(v).all():
        raise ValueError('Expected finite nonempty Nx3 millimetre vertices')
    extent=np.ptp(v,axis=0)
    if min(width_mm,depth_mm,rear_depth_scale,transition_mm)<=0 or min(extent[:2])<=0:
        raise ValueError('Envelope, rear scale and transition must be positive')
    factors=np.array([width_mm/extent[0],depth_mm/extent[1],1.0])
    v*=factors
    y=v[:,1].copy();t=np.clip(y/transition_mm,0,1)
    v[:,1]=y*(1-(1-rear_depth_scale)*t*t*(3-2*t))
    return v,{'scale_xyz':factors.tolist(),'back_half_smooth_y_scale':rear_depth_scale,'back_transition_mm':transition_mm,'target_extent_mm':np.ptp(v,axis=0).tolist(),'global_remesh':False,'source_decimation':False}

def fit_prepared_source(prepared, fitted, configuration):
    """Read source.npz/blend, preserve topology/UV and write new fitted NPZ plus transform record."""
    prepared = Path(prepared).resolve()
    fitted = validate_write_roots({'fitted': fitted}, package_root=Path(__file__).resolve().parents[1], protected_inputs=[prepared])['fitted']
    with np.load(prepared/'source.npz') as mesh:
        v,record=fit_vertices(mesh['vertices'],configuration['outer_width_mm'],configuration['outer_depth_mm'],configuration.get('rear_depth_scale',1),configuration.get('rear_transition_mm',5))
        fitted.mkdir(parents=True,exist_ok=True)
        np.savez(fitted/'source.npz',vertices=v,faces=mesh['faces'],uv=mesh['uv'],material_index=mesh['material_index'])
    shutil.copy2(prepared/'source.blend',fitted/'source.blend')
    (fitted/'fit-transform.json').write_text(json.dumps(record,indent=2))
    return record

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('prepared',type=Path);p.add_argument('fitted',type=Path);p.add_argument('config',type=Path)
    a=p.parse_args(cli_arguments(argv))
    return fit_prepared_source(a.prepared,a.fitted,json.loads(a.config.read_text()))

if __name__=='__main__': main()
