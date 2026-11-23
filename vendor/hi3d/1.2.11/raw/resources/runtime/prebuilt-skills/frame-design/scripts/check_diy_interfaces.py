"""Independent mm STL/Manifold volume paths, including released flex geometry."""
import json,sys,argparse,hashlib
from pathlib import Path
import numpy as np
import manifold3d as M
sys.path.insert(0,str(Path(__file__).resolve().parent))
from frame_recipe import validate_recipe
from frame_stl import RECORD
from frame_diy_runtime import prepare_paths, require_distinct_outputs
import struct

def solid(path):
 path=Path(path)
 with path.open('rb') as stream:
  header=stream.read(84)
  if len(header)!=84:raise ValueError('Truncated binary STL')
  count=struct.unpack('<I',header[80:84])[0]
  if count==0 or path.stat().st_size!=84+count*50:raise ValueError('Nonempty binary STL record count required')
  r=np.fromfile(stream,dtype=RECORD,count=count)
 if not np.isfinite(r['vertices']).all():raise ValueError('Nonfinite STL vertices')
 v,inv=np.unique(r['vertices'].reshape(-1,3),axis=0,return_inverse=True)
 result=M.Manifold(M.Mesh(np.ascontiguousarray(v,dtype=np.float32),np.ascontiguousarray(inv.reshape(-1,3),dtype=np.uint32)))
 if result.status()!=M.Error.NoError or result.volume()<=0:raise ValueError('Positive closed Manifold solid required')
 return result
def inspect_interfaces(*,source,output):
 p=Path(source).expanduser().resolve();destination=Path(output).expanduser().resolve()
 files={k:p/'print'/(k+'-mm.stl') for k in ['frame','backing','locking_ring','stand']}
 files.update({k+'_pressed':p/'verification'/(k+'-pressed-mm.stl') for k in ['locking_ring','stand']})
 files['measurements']=p/'measurements.json'
 prepare_paths(output=destination.parent,derived_inputs=files)
 require_distinct_outputs(files.values(),[destination])
 validate_recipe(json.loads(files['measurements'].read_text())['configuration'])
 a={k:solid(p/'print'/(k+'-mm.stl')) for k in ['frame','backing','locking_ring','stand']};press={k:solid(p/'verification'/(k+'-pressed-mm.stl')) for k in ['locking_ring','stand']};rows=[]
 def check(name,objs):
  for i,(an,av) in enumerate(objs):
   for bn,bv in objs[i+1:]:
    iv=(av^bv).volume();rows.append({'pose':name,'pair':[an,bn],'intersection_mm3':iv})
 check('closed',list(a.items()))
 for rot in np.linspace(-12,0,25):
  check('pressed rotation %.2f'%rot,[('frame',a['frame']),('backing',a['backing']),('ring',press['locking_ring'].rotate([0,0,float(rot)]))])
 for z in [0,-.1,-.25,-.5,-1,-2,-3,-5,-10,-25]:
  check('ring removal %.2f'%z,[('frame',a['frame']),('backing',a['backing']),('ring',press['locking_ring'].rotate([0,0,-12]).translate([0,0,z]))])
 for y in np.linspace(-30,0,61):
  check('pressed stand %.2f'%y,[('frame',a['frame']),('backing',a['backing']),('ring',a['locking_ring']),('stand',press['stand'].translate([0,float(y),0]))])
 for z in [0,-.1,-.5,-1,-2,-3,-5,-10,-25]:
  check('backing removal %.2f'%z,[('frame',a['frame']),('backing',a['backing'].translate([0,0,z]))])
 retention=[]
 for label,k,trans,rot in [('ring axial retained','locking_ring',[0,0,-.5],[0,0,0]),('ring reverse blocked','locking_ring',[0,0,0],[0,0,-1]),('stand withdrawal blocked','stand',[0,-1,0],[0,0,0]),('stand normal retained','stand',[0,0,-.5],[0,0,0])]:
  volume=(a['frame']^a[k].rotate(rot).translate(trans)).volume();retention.append({'test':label,'deliberate_blocked_motion_intersection_mm3':volume,'passed':volume>1e-4})
 distinct={k:hashlib.sha256((p/'print'/(k+'-mm.stl')).read_bytes()).hexdigest()!=hashlib.sha256((p/'verification'/(k+'-pressed-mm.stl')).read_bytes()).hexdigest() for k in press}
 r={'retention':retention,'free_and_pressed_exports_differ':distinct,'source_sha256':{str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*.stl')},'absolute_volume_tolerance_mm3':1e-5,'checks':rows,'maximum_intersection_mm3':max(x['intersection_mm3'] for x in rows)};r['passed']=r['maximum_intersection_mm3']<=1e-5 and all(distinct.values()) and all(x['passed'] for x in retention)
 destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(r,indent=2));print('MAX',r['maximum_intersection_mm3']);print(json.dumps(sorted(rows,key=lambda x:x['intersection_mm3'],reverse=True)[:12],indent=2));return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();raise SystemExit(0 if inspect_interfaces(source=a.source,output=a.output)['passed'] else 1)
