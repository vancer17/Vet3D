"""Actual paired solids and entry paths for the bayonet recipe's fit coupons."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from check_diy_interfaces import solid
from frame_diy_runtime import prepare_paths, require_distinct_outputs


def inspect_coupons(*, source, output):
    source=Path(source).expanduser().resolve();destination=Path(output).expanduser().resolve()
    manifest=source/'coupon-manifest.json'
    data=json.loads(manifest.read_text())
    if not isinstance(data,list) or len(data)!=12:
        raise ValueError('This recipe requires all 12 declared paired coupons')
    files={r['file']:source/r['file'] for r in data}
    prepare_paths(output=destination.parent,derived_inputs={**files,'manifest':manifest})
    require_distinct_outputs([*files.values(),manifest],[destination])
    def mesh(name):
        if name not in files:raise ValueError(f'Missing paired coupon: {name}')
        return solid(files[name])
    rows=[]
    for female,male in [('bayonet-female','bayonet-male'),('ring-release-female','ring-release-male'),('stand-receiver','stand-slide-release')]:
        volume=(mesh(female+'-mm.stl') ^ mesh(male+'-mm.stl')).volume()
        rows.append({'pair':[female,male],'pose':'nominal paired geometry','intersection_mm3':volume})
    for value in (15,25,35):
        name=f'dovetail-fit-{value:03d}'
        female=mesh(name+'-female-mm.stl');male=mesh(name+'-male-mm.stl')
        for shift in np.linspace(-25,0,51):
            volume=(female ^ male.translate([0,float(shift),0])).volume()
            rows.append({'pair':name,'pose':{'y_shift_mm':float(shift)},'intersection_mm3':volume})
    tolerance=1e-5;maximum=max(row['intersection_mm3'] for row in rows)
    result={'passed':maximum<=tolerance,'absolute_volume_tolerance_mm3':tolerance,
            'maximum_intersection_mm3':maximum,'checks':rows,
            'scope':'Three cropped pairs in nominal coordinates plus three rigid dovetail ladders over 51 entry positions; no physical friction/strength proof',
            'inputs_sha256':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in files.items()}}
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(result,indent=2))
    return result


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    return 0 if inspect_coupons(**vars(p.parse_args(argv)))['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
