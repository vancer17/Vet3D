"""Fresh GLB solid-equivalent center of mass and real desk contacts, no load test."""
import bpy,sys,argparse,json,numpy as np,hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support_core import mass_properties, combine_mass, support_polygon, signed_margins
from frame_runtime import cli_arguments
from frame_diy_runtime import prepare_paths,require_distinct_outputs

def check(source,output):
 destination=Path(output).expanduser().resolve()
 _,inputs=prepare_paths(output=destination.parent,derived_inputs={'source':source})
 require_distinct_outputs(inputs.values(),[destination])
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(inputs['source']))
 objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
 expected=['Main lunar','Twin dovetail','Independent paper photograph','Stationary keyed photograph backing','Bayonet locking back ring']
 if len(objects)!=5:raise ValueError('This adapter requires the five exported recipe meshes, no props')
 for prefix in expected:
  if sum(o.name.startswith(prefix) for o in objects)!=1:raise ValueError('Missing/duplicate recipe mesh: '+prefix)
 rows=[];contacts=[];properties=[];verts=[]
 for o in bpy.context.scene.objects:
  if o.type!='MESH':continue
  m=o.data;m.calc_loop_triangles();v=np.array([o.matrix_world@p.co for p in m.vertices])*1000;verts.append(v)
  if 'photograph' not in o.name.lower() or 'backing' in o.name.lower():
   part=mass_properties(v,np.array([list(f.vertices) for f in m.loop_triangles]),density_g_cm3=1.24)
   properties.append(part);rows.append({'name':o.name,'solid_volume_mm3':part['volume_mm3'],'center_mm':part['center_mm']})
  if any(x in o.name for x in ['Main lunar','Twin dovetail']):contacts.extend(v[v[:,2]<.02].tolist())
 hull=support_polygon(np.asarray(contacts).reshape(-1,3)[:,:2],round_digits=5)
 com=np.asarray(combine_mass(properties)['center_mm']);margins=signed_margins(hull,com[:2]).tolist()
 vv=np.concatenate(verts);r={'sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),'method':'Fresh GLB world triangle signed integrals of four mechanical parts only, equal solid PLA density 1.24 g/cm3; paper photograph mass excluded. Contact vertices within 0.02 mm of desk. Infill, friction, actual force and tipping not tested.','dimensions_mm':np.ptp(vv,axis=0).tolist(),'min_z_mm':float(vv[:,2].min()),'contact_count':len(contacts),'support_polygon_xy_mm':hull.tolist(),'assumed_com_mm':com.tolist(),'minimum_support_margin_mm':min(margins),'passed':min(margins)>0,'parts':rows};destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2));return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args(cli_arguments());raise SystemExit(0 if check(a.source,a.output)['passed'] else 1)
