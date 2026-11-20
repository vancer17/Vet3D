"""Pure array operations for measured height fields; no file or Blender effects."""
import numpy as np
from height_ops import median_filter, repair_pits, subtract_baseline, normalize_height



def crop_region(array, bounds):
    if len(bounds)!=4 or not (0<=bounds[0]<bounds[2]<=1 and 0<=bounds[1]<bounds[3]<=1):
        raise ValueError('Crop must be normalized positive bounds')
    a=np.asarray(array); u0,v0,u1,v1=bounds
    b=a[round(v0*a.shape[0]):round(v1*a.shape[0]),round(u0*a.shape[1]):round(u1*a.shape[1])].copy()
    if min(b.shape)<8: raise ValueError('Each crop axis needs at least 8 samples')
    return b

def edge_fade(array, fx, fy):
    if not 0 < fx <= .5 or not 0 < fy <= .5: raise ValueError('Fade fractions must be in (0,.5]')
    a=np.asarray(array); yy,xx=np.mgrid[0:1:complex(a.shape[0]),0:1:complex(a.shape[1])]
    t=np.clip(np.minimum(np.minimum(xx,1-xx)/fx,np.minimum(yy,1-yy)/fy),0,1)
    return a*t*t*(3-2*t)

def periodic_mirror(array):
    """C1-discrete seam by reflection, not a natural/random seamless synthesis."""
    a=np.asarray(array).copy()
    for axis in (0,1):
        b=np.moveaxis(a,axis,0); b[:2]=b[:2].mean(axis=0); b[-2:]=b[-2:].mean(axis=0)
    b=np.concatenate([a,a[:,::-1]],1)
    return np.concatenate([b,b[::-1]],0)

def seam_metrics(array):
    t=np.asarray(array)
    return {'seam_value_max':float(max(abs(t[:,0]-t[:,-1]).max(),abs(t[0]-t[-1]).max())),
      'seam_first_difference_max':float(max(abs(t[:,1]-t[:,0]-(t[:,-1]-t[:,-2])).max(),abs(t[1]-t[0]-(t[-1]-t[-2])).max()))}

def prepare_regions(raw, config):
    """Process raw rays; return arrays/masks/report without changing files.

    Required config: named regions with crop/mode. Source pits and region pits
    are reported separately; NaN ray misses remain measurable in the report.
    """
    raw=np.asarray(raw,dtype=float)
    if raw.ndim!=2 or not np.isfinite(raw).any(): raise ValueError('No finite source rays')
    regions=config['regions']
    if not regions: raise ValueError('At least one explicit region required')
    baseline=float(np.nanpercentile(raw,config.get('baseline_percentile',6)))
    h=subtract_baseline(raw,baseline)
    h,source_mask,source_stats=repair_pits(h,kernel=int(config.get('source_pit_kernel',3)),
       threshold=float(config.get('source_pit_threshold',0.004)),median_floor=0,iterations=int(config.get('source_pit_iterations',1)))
    h,_=normalize_height(h,percentile=config.get('height_percentile',99.8))
    before={}; result={}; masks={'source':source_mask}; stats={'source':source_stats}; specs={}
    repair=config.get('repair',{})
    for name,spec in regions.items():
        if not name.replace('_','').isalnum() or name in ('raw','source'): raise ValueError('Invalid/reserved region name')
        if not isinstance(spec,dict): raise ValueError('Each region needs explicit crop and mode')
        mode=spec['mode']; a=crop_region(h,spec['crop'])
        if mode=='tile': a=np.maximum(a-np.percentile(a,7),0)
        elif mode in ('stamp','border'): a=edge_fade(a,*spec.get('fade',[.06,.08]))
        else: raise ValueError('mode must be stamp, tile or border')
        if a.max()<=1e-10: raise ValueError(f'{name} has no measured relief')
        a/=a.max()
        repeats=int(spec.get('repair_iterations',repair.get('tile_iterations',1) if mode=='tile' else repair.get('iterations',3)))
        fixed,mask,stat=repair_pits(a,kernel=int(repair.get('kernel',5)),threshold=float(repair.get('normalized_threshold',.12)),median_floor=float(repair.get('median_floor',.2)),iterations=repeats)
        before[name]=periodic_mirror(a) if mode=='tile' else a
        result[name]=periodic_mirror(fixed) if mode=='tile' else fixed
        masks[name]=mask; stats[name]=stat; specs[name]=spec
        if mode=='tile': stats[name].update(seam_metrics(result[name]),periodic_method='reflected crop with two-sample flattened join strips; four-way repetition remains visible')
    before['raw']=h; result['raw']=h
    return {'fields':result,'before':before,'masks':masks,'repair':stats,'region_specs':specs,'baseline':baseline,'valid_ray_fraction':float(np.isfinite(raw).mean())}

def warp_surface(points, kind, radius_mm):
    """Map millimetre points by arc length onto plane/cylinder/double curvature."""
    v=np.asarray(points,dtype=float)
    if kind=='plane': return v.copy()
    r=float(radius_mm)
    if r<=0: raise ValueError('Positive radius required')
    x,y,d=v.T; u=x/r
    if kind=='cylinder': return np.column_stack([(r-d)*np.sin(u),y,r-(r-d)*np.cos(u)])
    if kind=='double-curvature':
        q=y/r
        return np.column_stack([(r-d)*np.sin(u)*np.cos(q),(r-d)*np.sin(q),r-(r-d)*np.cos(u)*np.cos(q)])
    raise ValueError('Unsupported receiving surface')
