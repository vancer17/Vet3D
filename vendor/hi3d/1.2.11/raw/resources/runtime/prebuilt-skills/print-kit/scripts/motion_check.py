"""Discrete rigid-solid path checks in mm; containment is included."""
import math
from itertools import combinations
import numpy as np
from pose_math import axis_pose, is_rigid
from solid_samples import intersection_volume, sample_solids

def translation(v):
    m=np.eye(4);m[:3,3]=v;return m

def rotation(axis, deg, pivot=(0,0,0)):
    if axis not in ('x','y','z'):raise ValueError(axis)
    direction=np.eye(3)['xyz'.index(axis)]
    return axis_pose(pivot,direction,math.radians(deg))

def transform(s,m):
    return s.transform(np.asarray(m)[:3,:])

def overlap(a,b):
    return intersection_volume(a,b,aabb_epsilon=1e-6,absolute_volume=False)

def require(errors,condition,message):
    """Append a failed gate to the caller-owned error list."""
    if not condition:errors.append(message)

def check_intersections(assembled):
    """Test all static solid pairs including containment; return count/max/errors."""
    errors=[]
    max_overlap=0;pair_count=0
    for a,b in combinations(assembled,2):
        v=overlap(assembled[a],assembled[b]);max_overlap=max(max_overlap,v);pair_count+=1
        require(errors,v<.01,f'assembly collision {a}/{b}: {v:.5f} mm³')
    return pair_count,max_overlap,errors

def check_paths(d,assembled):
    """Sample ordered straight disassembly paths; raise on invalid path parameters."""
    errors=[]
    # Disassembly is the reverse of a constructive assembly sequence. Remove groups in order.
    remaining=dict(assembled);paths=[]
    for stage in d['disassembly']:
        ids=stage['instances'];require(errors,bool(ids) and all(i in remaining for i in ids),'bad path instance/order')
        if not ids or len(set(ids))!=len(ids) or not all(i in remaining for i in ids):
            raise ValueError('invalid path instance group')
        vec=np.array(stage['direction'],float);norm=np.linalg.norm(vec)
        require(errors,norm>0 and stage['distance_mm']>0 and stage['max_step_mm']>0,'invalid path distance')
        if not np.isfinite([norm,stage['distance_mm'],stage['max_step_mm']]).all() or norm<=0 or stage['distance_mm']<=0 or stage['max_step_mm']<=0:
            raise ValueError('invalid path distance or step')
        vec/=norm;travel=stage['distance_mm'];n=max(1,math.ceil(travel/stage['max_step_mm']))
        moving={i:remaining[i] for i in ids};stationary={i:s for i,s in remaining.items() if i not in ids}
        samples = ({'value':float(t),'poses':{key:translation(vec*t) if key in moving else np.eye(4)
                    for key in remaining}} for t in np.linspace(0,travel,n+1))
        measured = sample_solids(remaining,samples,[(a,b) for a in moving for b in stationary],
                                 tolerance=.01,aabb_epsilon=1e-6)
        maxv = measured['max_overlap_mm3']; hit = measured['first_collision']
        first = None if hit is None else dict(a=hit['a'],b=hit['b'],offset_mm=hit['value'],volume_mm3=hit['volume_mm3'])
        # End must leave the stationary assembly's bounding envelope, conservative AABB check.
        if stationary:
            sb=np.array([s.bounding_box() for s in stationary.values()]);sb=np.r_[sb[:,:3].min(0),sb[:,3:].max(0)]
            for a,s in moving.items():
                b=np.array(s.translate((vec*travel).tolist()).bounding_box())
                require(errors,not ((b[3:]>sb[:3])&(sb[3:]>b[:3])).all(),'path endpoint not outside assembly envelope '+a)
        require(errors,first is None,'path collision '+str(first))
        paths.append({'instances':ids,'samples':n+1,'max_step_mm':travel/n,'max_overlap_mm3':maxv,'first_collision':first})
        for i in ids:remaining.pop(i)
    require(errors,len(remaining)<=1,'assembly path incomplete: '+','.join(remaining))
    return paths,errors

def check_motions(d,assembled):
    """Sample declared travel/rotation against all stationary parts; no elastic model."""
    errors=[]
    motion_results=[]
    for motion in d.get('motions',[]):
        if not isinstance(motion['samples'],int) or motion['samples']<2:
            raise ValueError('motion requires at least two samples')
        if not motion['instances'] or len(set(motion['instances']))!=len(motion['instances']):
            raise ValueError('invalid motion instance group')
        mx=0;first=None
        ids=motion['instances'];others={k:s for k,s in assembled.items() if k not in ids}
        if motion['type']=='translation' and (np.linalg.norm(motion['direction'])==0 or not np.isfinite(motion['direction']).all() or not np.isfinite(motion['distance_mm'])):
            raise ValueError('invalid motion translation')
        if motion['type']=='rotation':
            if not np.isfinite([motion['start_deg'],motion['end_deg'],*motion['pivot']]).all():
                raise ValueError('invalid motion rotation')
            vals=np.linspace(motion['start_deg'],motion['end_deg'],motion['samples'])
            mats=[rotation(motion['axis'],v,motion['pivot']) for v in vals]
        elif motion['type']=='translation':
            vals=np.linspace(0,motion['distance_mm'],motion['samples']);axis=np.array(motion['direction'],float);axis/=np.linalg.norm(axis)
            mats=[translation(axis*v) for v in vals]
        else:raise ValueError('unsupported motion '+motion['type'])
        samples = ({'value':float(val),'poses':{key:mat if key in ids else np.eye(4) for key in assembled}}
                   for val,mat in zip(vals,mats))
        measured = sample_solids(assembled,samples,[(a,b) for a in ids for b in others],
                                 tolerance=.01,aabb_epsilon=1e-6)
        mx = measured['max_overlap_mm3']; hit = measured['first_collision']
        first = None if hit is None else dict(a=hit['a'],b=hit['b'],position=hit['value'],volume_mm3=hit['volume_mm3'])
        require(errors,first is None,'motion collision '+str(first))
        motion_results.append({'id':motion['id'],'samples':len(vals),'max_overlap_mm3':mx,'first_collision':first})
    return motion_results,errors
