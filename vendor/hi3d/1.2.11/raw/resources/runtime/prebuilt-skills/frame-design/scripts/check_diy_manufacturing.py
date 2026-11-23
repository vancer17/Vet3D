"""Verify print placements against original assembly-coordinate STL geometry."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from scipy.spatial import cKDTree
from frame_stl import RECORD, inspect_binary_stl
from frame_diy_runtime import prepare_paths, require_distinct_outputs


def inspect_manufacturing(*, source, output, tolerance_mm=0.00002):
    """Read 16 printed STL, invert recorded rigid transforms, compare actual vertices.

    Source is the recipe result root containing print/, coupons/, manufacturing/.
    No geometry changes or slicing; tolerance covers floating serialization only.
    """
    if not np.isfinite(tolerance_mm) or tolerance_mm<=0:raise ValueError('Positive finite coordinate tolerance required')
    root=Path(source).expanduser().resolve();destination=Path(output).expanduser().resolve()
    manifest=root/'manufacturing/print-orientation.json';records=json.loads(manifest.read_text())
    if len(records)!=16 or sum(r['role']=='coupon' for r in records)!=12:
        raise ValueError('Expected four manufactured parts plus 12 matching coupons')
    original_roles={r['role'] for r in records if r['role']!='coupon'}
    if original_roles!={'frame','backing','locking_ring','stand'}:
        raise ValueError('Missing/duplicate manufacturing roles')
    files={'manifest':manifest};pairs=[]
    for i,record in enumerate(records):
        relative=Path(record['file'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Manufacturing manifest paths must stay relative')
        printed=root/'manufacturing'/relative
        original=root/('coupons' if record['role']=='coupon' else 'print')/relative.name
        files[f'printed_{i}']=printed;files[f'original_{i}']=original;pairs.append((record,original,printed))
    prepare_paths(output=destination.parent,derived_inputs=files);require_distinct_outputs(files.values(),[destination])
    expected={p.resolve() for _,_,p in pairs}
    actual={p.resolve() for folder in ('parts','coupons') for p in (root/'manufacturing'/folder).glob('*.stl')}
    if expected!=actual or len(expected)!=16:
        raise ValueError('Manufacturing files must match the 16 manifest entries exactly')
    rows=[]
    for record,original,printed in pairs:
        source_report=inspect_binary_stl(original);print_report=inspect_binary_stl(printed)
        transform=np.asarray(record['matrix_m'],dtype=float)
        if transform.shape!=(4,4) or not np.isfinite(transform).all() or not np.allclose(transform[3],[0,0,0,1],atol=1e-9):
            raise ValueError('Finite 4×4 affine placement matrix required')
        if not np.allclose(transform[:3,:3].T@transform[:3,:3],np.eye(3),atol=1e-6) or np.linalg.det(transform[:3,:3])<=0:
            raise ValueError('Manufacturing transform must be a proper rigid rotation')
        original_vertices=np.unique(np.fromfile(original,dtype=RECORD,offset=84)['vertices'].reshape(-1,3),axis=0).astype(float)
        printed_vertices=np.unique(np.fromfile(printed,dtype=RECORD,offset=84)['vertices'].reshape(-1,3),axis=0).astype(float)
        inverse=np.linalg.inv(transform);restored=printed_vertices@inverse[:3,:3].T+inverse[:3,3]*1000
        maximum=max(float(cKDTree(original_vertices).query(restored)[0].max()),float(cKDTree(restored).query(original_vertices)[0].max()))
        bounds_error=float(np.abs(np.stack([restored.min(0),restored.max(0)])-np.stack([original_vertices.min(0),original_vertices.max(0)])).max())
        volume_error=abs(print_report['volume_units3']-source_report['volume_units3'])/source_report['volume_units3']
        min_z=float(printed_vertices[:,2].min())
        passed=source_report['passed'] and print_report['passed'] and maximum<=tolerance_mm and bounds_error<=tolerance_mm and volume_error<=1e-4 and abs(min_z)<=tolerance_mm
        rows.append({'file':record['file'],'passed':bool(passed),'inverse_vertex_error_mm':maximum,'inverse_bounds_error_mm':bounds_error,'relative_material_volume_error':volume_error,'printed_min_z_mm':min_z,'source_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'printed_sha256':hashlib.sha256(printed.read_bytes()).hexdigest(),'source_topology':source_report,'printed_topology':print_report})
    result={'passed':all(r['passed'] for r in rows),'tolerance_mm':tolerance_mm,'method':'Actual STL vertices; inverse assembly-world-metres to print-world-metres matrix; bidirectional nearest vertex distance plus topology, bounds and volume. No slicing or physical fit claim.','parts':rows}
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(result,indent=2));return result


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    return 0 if inspect_manufacturing(**vars(p.parse_args(argv)))['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
