"""Crop real production solids in assembly space, retaining print axes."""
import argparse
import json
from pathlib import Path
import numpy as np
import manifold3d as mf
from motion_check import is_rigid, transform, translation
from mesh_io import to_trimesh, read_stl_solid
from coupon_records import source_record, pair_record


def crop_solid(solid, assembly_matrix, bounds, *, with_transform=False):
    """Clip one Manifold solid, inverse-transform and rebase at min XYZ.

    Optionally return coupon-to-assembly matrix so the pair can be reconstructed.
    """
    values=np.asarray(bounds,float)
    if values.shape!=(6,) or not np.isfinite(values).all() or not (values[3:]>values[:3]).all():
        raise ValueError('ROI needs finite min XYZ < max XYZ')
    if not is_rigid(assembly_matrix):raise ValueError('non-rigid assembly matrix')
    if solid.status()!=mf.Error.NoError or solid.is_empty() or solid.volume()<=0:
        raise ValueError('Positive valid source solid required')
    A=np.asarray(assembly_matrix,float);lo=values[:3];hi=values[3:]
    cropped=transform(solid,A)^mf.Manifold.cube(hi-lo).translate(lo)
    if len(cropped.decompose())!=1 or cropped.volume()<=0:
        raise ValueError('ROI must contain exactly one connected solid')
    printsolid=transform(cropped,np.linalg.inv(A));minimum=to_trimesh(printsolid).bounds[0]
    result=transform(printsolid,translation(-minimum))
    return (result,A@translation(minimum)) if with_transform else result


def crop_pair(paths, matrices, bounds, output, *, clearance_mm, definition):
    """Read exactly two STL sides; write new paired coupons and source mapping."""
    if len(paths)!=2 or set(paths)!=set(matrices):raise ValueError('Two sides and matching matrices required')
    if any(not isinstance(k,str) or not k or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in k) for k in paths):
        raise ValueError('Simple side identifiers required')
    sources={k:source_record(p) for k,p in paths.items()}
    # Finish all geometry/contract validation before creating the output directory.
    cropped={k:crop_solid(read_stl_solid(p),matrices[k],bounds,with_transform=True) for k,p in paths.items()}
    report=pair_record('cropped-interface',{k:k+'.stl' for k in paths},clearance_mm=clearance_mm,definition=definition,
                       orientation='Production print axes; each coupon translated to min XYZ=0',source=sources)
    report.update(roi_assembly_mm=list(bounds),coupon_to_assembly={k:m.tolist() for k,(s,m) in cropped.items()})
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    for k,(solid,matrix) in cropped.items():
        path=output/(k+'.stl');to_trimesh(solid).export(path);read_stl_solid(path)
    report['artifacts']={k:source_record(output/(k+'.stl')) for k in paths}
    (output/'coupon-pair.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--spec',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();spec=json.loads(args.spec.read_text())
    paths={k:args.spec.parent/v for k,v in spec['files'].items()}
    report=crop_pair(paths,spec['matrices'],spec['bounds_mm'],args.output,clearance_mm=spec['clearance_mm'],definition=spec['definition'])
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
