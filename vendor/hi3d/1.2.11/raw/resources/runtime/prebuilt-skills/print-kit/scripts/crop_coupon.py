"""Crop real production STL in assembly coordinates, preserve print orientation.
Requires a chosen connected ROI; does not invent a generic replacement joint.
"""
import argparse,json
from pathlib import Path
import numpy as np
import trimesh
from kitlib import solid,sha,write_json,export_solid
from coupon_crop import crop_solid as _crop_solid
from coupon_records import source_record

def crop_solid(print_mesh, assembly_matrix, bounds):
    """Clip a production mesh by assembly-space ROI, return same-axis rebased solid.

    Requires a rigid 4x4 matrix and ordered six finite bounds. Rejects empty or
    disconnected ROI. Pure geometry; changes footprint/thermal history.
    """
    return _crop_solid(solid(print_mesh),assembly_matrix,bounds)


def crop(plan_path,instance,bounds,out):
    """Read one plan/STL, write clipped STL and provenance JSON; errors propagate."""
    plan=Path(plan_path);d=json.loads(plan.read_text())
    by_instance={i['id']:i for i in d['instances']};i=by_instance[instance]
    p=next(x for x in d['parts'] if x['id']==i['part'])
    source=plan.parent/p['file'];m=trimesh.load_mesh(source,process=True)
    result=crop_solid(m,i['matrix'],bounds)
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    final=export_solid(result,target)
    info={'instance':instance,'source_part':p['file'],'source_sha256':source_record(source)['sha256'],'roi_assembly_mm':bounds,
      'coupon_sha256':sha(target),'size_mm':final.extents.tolist(),'watertight':True,
      'print_orientation':'same axes as production; cropped bottom translated to Z=0',
      'limit':'Cropping changes footprint/thermal history/support conditions. Test the full longest interface after this local gauge.',
      'physical_test':'not_run'}
    write_json(target.with_suffix('.json'),info);return info

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('plan');a.add_argument('--instance',required=True);a.add_argument('--bounds',required=True,nargs=6,type=float);a.add_argument('--out',required=True);args=a.parse_args();print(json.dumps(crop(args.plan,args.instance,args.bounds,args.out)))
