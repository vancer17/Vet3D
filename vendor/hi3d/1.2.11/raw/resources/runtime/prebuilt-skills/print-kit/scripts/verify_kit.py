"""Read final STL files and verify geometry, assembly, probes and sampled paths.
Not a slicer or physical test. Returns nonzero on failed or incomplete gates.
"""
import argparse
from collections import Counter
from itertools import combinations
import json
import math
from pathlib import Path
import numpy as np
import trimesh
from kitlib import solid,transform,translation,rotation,sha,write_json,is_rigid






from motion_check import check_intersections, check_motions, check_paths, overlap, require

def check_parts(d,meshes,digests):
    """Measure loaded print meshes and compare digests; return metrics/solids/errors/warnings."""
    errors=[];warnings=[];checks={};parts={}
    for p in d['parts']:
        m=meshes[p['id']]
        bodies=len(m.split(only_watertight=False))
        flat=(np.abs(m.triangles[:,:,2]).max(axis=1)<.01)
        bed_area=float(m.area_faces[flat].sum())
        require(errors,digests[p['id']]==p['sha256'],p['id']+': hash changed')
        require(errors,m.is_watertight and m.is_winding_consistent and m.volume>0 and bodies==1,p['id']+': not one closed oriented positive body')
        require(errors,bool((m.area_faces>1e-10).all()),p['id']+': degenerate triangle')
        require(errors,abs(m.bounds[0,2])<.01,p['id']+': off bed')
        require(errors,bed_area>1,p['id']+': inadequate bed contact')
        require(errors,bool((m.extents<=np.array(d['bed_mm'])-[2*d['bed_margin_mm'],2*d['bed_margin_mm'],0]).all()),p['id']+': too large')
        down=(m.face_normals[:,2]<-math.cos(math.radians(45))) & (m.triangles_center[:,2]>.25)
        area=float(m.area_faces[down].sum())
        if area>.1:warnings.append(f"{p['id']}: {area:.2f} mm² downward-face screening area; assess bridges/support with slicer")
        parts[p['id']]=(m,solid(m));checks[p['id']]={'watertight':m.is_watertight,'bodies':bodies,
          'triangles':len(m.faces),'size_mm':m.extents.tolist(),'volume_mm3':float(m.volume),
          'bed_contact_mm2':bed_area,'downward_screening_area_mm2':area}
    return checks,parts,errors,warnings


def assemble(d,parts):
    """Transform parts into assembly space, checking quantity and rigid poses; no writes."""
    errors=[];assembled={}
    ic=Counter(i['part'] for i in d['instances'])
    require(errors,len({i['id'] for i in d['instances']})==len(d['instances']),'duplicate instance id')
    for p in d['parts']:require(errors,ic[p['id']]==p['qty'],p['id']+': quantity mismatch')
    for i in d['instances']:
        mat=np.array(i['matrix'])
        if not is_rigid(mat):raise ValueError('non-rigid assembly matrix '+i['id'])
        assembled[i['id']]=transform(parts[i['part']][1],mat)
    return assembled,errors




def check_plates(d,parts):
    """Check every printed copy, rigid bed pose and same-plate AABB separation."""
    errors=[]
    require(errors,Counter(p['instance'] for p in d['plates'])==Counter(i['id'] for i in d['instances']),'plate quantity mismatch')
    instby={i['id']:i for i in d['instances']};plate_bounds=[]
    for p in d['plates']:
        if not is_rigid(p['matrix']):raise ValueError('non-rigid plate matrix '+p['instance'])
        require(errors,isinstance(p['plate'],int) and p['plate']>0,'invalid plate number')
        m=parts[instby[p['instance']]['part']][0].copy();m.apply_transform(p['matrix']);b=m.bounds
        require(errors,(b[0,:2]>=d['bed_margin_mm']-.01).all() and (b[1,:2]<=np.array(d['bed_mm'][:2])-d['bed_margin_mm']+.01).all(),'plate bounds '+p['instance'])
        require(errors,abs(b[0,2])<.01 and b[1,2]<=d['bed_mm'][2],'plate z '+p['instance'])
        for other,ob in plate_bounds:
            if other['plate']==p['plate']:
                require(errors,not ((b[1,:2]>ob[0,:2]+1e-4)&(ob[1,:2]>b[0,:2]+1e-4)).all(),'plate overlap '+p['instance'])
        plate_bounds.append((p,b))
    return errors


def measure_features(d,assembled):
    """Ray-measure named mesh sections; return measurements and errors, no global wall claim."""
    errors=[];feature_results=[]
    # Actual exported geometry dimensions around a void or material centre.
    for f in d['features']:
        if not np.isfinite(f['axis']).all() or np.linalg.norm(f['axis'])==0 or f['span_mm']<=0 or f['expected_mm']<=0 or f.get('tolerance_mm',.025)<0:
            raise ValueError('invalid feature dimensions '+f['id'])
        c=np.array(f['center']);a=np.array(f['axis'],float);a/=np.linalg.norm(a);L=f['span_mm']
        hits=assembled[f['instance']].ray_cast((c-a*L).tolist(),(c+a*L).tolist())
        coords=sorted(float(np.dot(np.array(h.position)-c,a)) for h in hits)
        left=[x for x in coords if x< -1e-4];right=[x for x in coords if x>1e-4]
        measured=(min(right)-max(left)) if left and right else None
        ok=measured is not None and abs(measured-f['expected_mm'])<=f.get('tolerance_mm',.025)
        require(errors,ok,f"feature {f['id']}: {measured} expected {f['expected_mm']}")
        feature_results.append({'id':f['id'],'measured_mm':measured,'expected_mm':f['expected_mm'],'pass':ok})
    return feature_results,errors






def validate_plan(d,meshes,digests):
    """Compose in-memory geometry checks; malformed plans raise to the IO boundary."""
    if not d['parts'] or not d['instances'] or not d['plates']:
        raise ValueError('empty parts, instances or plates')
    if len({p['id'] for p in d['parts']})!=len(d['parts']):
        raise ValueError('duplicate part id')
    bed=np.asarray(d['bed_mm'],float)
    if bed.shape!=(3,) or not np.isfinite(bed).all() or min(bed)<=0 or not np.isfinite(d['bed_margin_mm']) or d['bed_margin_mm']<0:
        raise ValueError('invalid bed dimensions/margin')
    checks,parts,errors,warnings=check_parts(d,meshes,digests)
    require(errors,d['units']=='mm' and d['up_axis']=='Z','unsupported coordinate system')
    assembled,found=assemble(d,parts);errors.extend(found)
    pair_count,max_overlap,found=check_intersections(assembled);errors.extend(found)
    errors.extend(check_plates(d,parts))
    feature_results,found=measure_features(d,assembled);errors.extend(found)
    paths,found=check_paths(d,assembled);errors.extend(found)
    motion_results,found=check_motions(d,assembled);errors.extend(found)
    for j in d['joints']:
        require(errors,j['a'] in assembled and j['b'] in assembled,'unknown joint endpoint '+j['id'])
        require(errors,bool(j.get('retention')) and j['clearance_per_side_mm']>=0,'incomplete joint '+j['id'])
    if not d['features']:warnings.append('No mesh feature measurements specified')
    return {'status':'pass' if not errors else 'fail','errors':errors,'warnings':warnings,
      'parts':checks,'unique_parts':len(parts),'printed_instances':len(d['instances']),
      'plate_count':max(p['plate'] for p in d['plates']),'static_pairs_tested':pair_count,
      'maximum_static_overlap_mm3':max_overlap,'feature_measurements':feature_results,
      'disassembly_paths':paths,'motions':motion_results,
      'limits':['Paths/motions are discrete rigid-body samples, not continuous collision proof.',
        'No strength, elasticity, slicer toolpath, hardware installation or physical fit is proved.',
        'Ray dimensions sample named sections; not a global minimum-wall analysis.'],
      'physical_test':'not_run','slicer':d.get('evidence',{}).get('slicer','not_run')}


def load_inputs(plan_path):
    """Read JSON and referenced STL bytes; return plan, meshes and SHA256 map."""
    path=Path(plan_path);d=json.loads(path.read_text(encoding='utf-8'))
    meshes={};digests={}
    for part in d['parts']:
        source=path.parent/part['file']
        meshes[part['id']]=trimesh.load_mesh(source,process=True)
        digests[part['id']]=sha(source)
    return d,meshes,digests


def verify(plan_path):
    """Read-only entry; return pass/fail JSON, including malformed-input failures."""
    try:
        return validate_plan(*load_inputs(plan_path))
    except (ValueError,KeyError,IndexError,TypeError,OSError,OverflowError) as exc:
        return {'status':'fail','errors':[f'{type(exc).__name__}: {exc}'],
                'warnings':[],'physical_test':'not_run','slicer':'not_run'}


def main():
    """Parse CLI, run read-only validation, write report; fail exits nonzero."""
    ap=argparse.ArgumentParser();ap.add_argument('plan');ap.add_argument('--out');args=ap.parse_args()
    r=verify(args.plan)
    output=args.out or str(Path(args.plan).with_name('validation.json'))
    write_json(output,r)
    print(json.dumps({k:r[k] for k in ['status','unique_parts','printed_instances','plate_count','errors'] if k in r},ensure_ascii=False))
    return 0 if r['status']=='pass' else 1


if __name__=='__main__':raise SystemExit(main())
