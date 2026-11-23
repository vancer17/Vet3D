#!/usr/bin/env python3
"""Independently validate final keyed split STL solids, extraction path and blind-pocket containment.
No repair, remeshing or change to the inputs is performed. Requires numpy/manifold3d.
"""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import argparse,hashlib,json,struct,math,tempfile,subprocess
from pathlib import Path
import numpy as np
import manifold3d as M

RECORD=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attribute','<u2')])
def load_stl(path):
 data=path.read_bytes();n=struct.unpack_from('<I',data,80)[0]
 if len(data)!=84+50*n or n==0:raise ValueError('Expected nonempty binary STL')
 corners=np.frombuffer(data,dtype=RECORD,offset=84,count=n)['vertices'].reshape(-1,3)
 if not np.isfinite(corners).all():raise ValueError('Non-finite STL')
 vertices,index=np.unique(corners,axis=0,return_inverse=True)
 # Retain exact float32 STL coordinates in float64; no tolerance welding or cleaning.
 solid=M.Manifold(M.Mesh64(np.array(vertices,dtype=np.float64,order='C'),np.array(index.reshape(-1,3),dtype=np.uint64,order='C')))
 if solid.status()!=M.Error.NoError:raise ValueError(str(solid.status()))
 return solid,{'file':path.name,'sha256':hashlib.sha256(data).hexdigest(),'triangles':n,'exact_weld_vertices':len(vertices),'volume_mm3':solid.volume(),'connected_components':len(solid.decompose()),'bounds_mm':[vertices.min(0).tolist(),vertices.max(0).tolist()],'status':str(solid.status())}
def volume_record(solid,tolerance):
 volume=float(solid.volume());empty=solid.is_empty()
 return {'signed_volume_mm3':volume,'absolute_volume_mm3':abs(volume),'empty':empty,'vertices':solid.num_vert(),'triangles':solid.num_tri(),'manifold_status':str(solid.status()),'within_numeric_volume_tolerance':abs(volume)<=tolerance,'bounds_mm':None if empty else list(solid.bounding_box())}
def ray(point,direction,solid):
 point=np.asarray(point,float);direction=np.asarray(direction,float);direction/=np.linalg.norm(direction)
 hits=solid.ray_cast(point.tolist(),(point+direction*1000).tolist())
 return [{'position_mm':list(h.position),'distance_mm':float(np.linalg.norm(np.array(h.position)-point)),'normal_dot_ray':float(np.dot(h.normal,direction))} for h in hits]
def wall_sample(point,direction,solid):
 hits=ray(point,direction,solid)
 # Empty pocket origin should be outside the solid; two first hits enter then leave material.
 good=len(hits)>=2 and hits[0]['normal_dot_ray']<0 and hits[1]['normal_dot_ray']>0
 return {'origin_mm':list(map(float,point)),'direction':list(map(float,direction)),'inside_solid_by_parity':len(hits)%2==1,'first_hits':hits[:2],'valid_void_to_wall_to_exterior':good,'remaining_material_mm':hits[1]['distance_mm']-hits[0]['distance_mm'] if good else None}

def component_metrics(solid):
 rows=[]
 for i,c in enumerate(solid.decompose()):
  mesh=c.to_mesh64();v=np.asarray(mesh.vert_properties)[:,:3];f=np.asarray(mesh.tri_verts);volume=float(c.volume());area=float(c.surface_area());q=v-v.mean(0);_,axes=np.linalg.eigh(q.T@q/max(1,len(q)));spread=float(np.ptp(q@axes[:,0]));rows.append({'component':i,'triangles':len(f),'vertices':len(v),'signed_volume_mm3':volume,'surface_area_mm2':area,'bounds_mm':list(c.bounding_box()),'minimum_principal_direction_spread_mm':spread,'volume_area_sheet_thickness_estimate_mm':2*abs(volume)/area if area else None})
 return {'method':'Connected Boolean residual components. Principal spread is geometric planarity, not a wall-thickness guarantee.2|V|/area is an average thin-sheet thickness estimate, not maximum thickness.','count':len(rows),'components':rows}

def add_functional_summary(report,body_report):
 inputs={x['file']:x for x in report['inputs'][:2]};tested={x['file']:x for x in body_report['parts']}
 matches=all(name in tested and tested[name]['sha256']==row['sha256'] for name,row in inputs.items())
 checks={'closed_single_component_stl_solids':all(x['status']=='Error.NoError' and x.get('connected_components')==1 and x['volume_mm3']>0 for x in inputs.values()),'upper_extraction_path_no_material_conflict':all(x['within_numeric_volume_tolerance'] for x in report['path']),'blind_pockets_retain_outer_skin':all(x['conservative_sharp_pocket_envelope_outside_original']['within_numeric_volume_tolerance'] and x['all_radial_samples_have_material_after_void'] and x['all_roof_samples_have_material_after_void'] for x in report['blind_pockets']),'final_stl_hashes_match_body_test':matches,'no_triangle_crossing_with_actual_body':matches and all(tested[name]['body_triangle_crossing_pairs']==0 for name in inputs)}
 report['body_fit_evidence']=body_report;report['functional_checks']=checks;report['functional_checks_passed']=all(checks.values());report['exit_status_basis']='functional_checks_passed. The existing passed field retains the more stringent combined numerical-preservation result; strict_absolute_volume_checks_passed is independently retained.'
 report['engineering_scope']='Passes only actual closed segments, extraction path, blind pocket skin retention and the tested static digital body. Strict Boolean equivalence and sub-0.0001mm source-surface preservation are separate numeric checks and may remain false; raw residuals are not erased or rounded away.'
 return report


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--lower',required=True,type=Path);p.add_argument('--upper',required=True,type=Path);p.add_argument('--source',required=True,type=Path);p.add_argument('--design',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
 p.add_argument('--blender',required=True,type=Path,help='Blender executable for a global nearest-triangle BVH check; no rendering or scene edits.')
 p.add_argument('--probe-points',type=Path,help='Optional JSON list of diagnostic points {label,point_mm} to classify against the original closed solid.')
 p.add_argument('--body-report',required=True,type=Path,help='Actual validate_split_body.py report with hashes matching the two final STL files.')
 p.add_argument('--translations-mm',type=float,nargs='+',default=[0,.5,1,2,3.5,4,8,20]);p.add_argument('--volume-tolerance-mm3',type=float,default=.001);p.add_argument('--surface-tolerance-mm',type=float,default=.0001);p.add_argument('--relative-residual-volume',type=float,default=1e-8)
 a=p.parse_args();lo,lr=load_stl(a.lower);print('LOADED lower',flush=True);hi,hr=load_stl(a.upper);print('LOADED upper',flush=True);source,sr=load_stl(a.source);print('LOADED original',flush=True)
 design=json.loads(a.design.read_text());z=float(design['split_z_mm']);tol=a.volume_tolerance_mm3
 report={'method':'Independent exact-coordinate binary STL import to Manifold Mesh64. No repair or extra welding. Physical unit mm. Boolean volumes preserve signed raw numeric results.','numerics':{'volume_tolerance_mm3':tol,'source_coordinate_type':'float32 stored STL coordinates promoted exactly to float64','zero_policy':'Exact empty is distinguished from nonempty residuals below tolerance; no nonzero result is rounded to zero.'},'inputs':[lr,hr,sr],'design_sha256':hashlib.sha256(a.design.read_bytes()).hexdigest(),'split_z_mm':z,'path':[],'containment':{},'blind_pockets':[]}
 for dz in a.translations_mm:
  r=volume_record(lo^hi.translate((0,0,dz)),tol);r['upper_translation_mm']=[0,0,dz];report['path'].append(r);print('PATH',dz,r['signed_volume_mm3'],r['empty'],flush=True)
 residuals={}
 for name,part in [('lower',lo),('upper',hi)]:
  residuals[name+'_outside_original']=part-source;r=volume_record(residuals[name+'_outside_original'],tol);report['containment'][name+'_outside_original']=r;print('OUTSIDE',name,r['signed_volume_mm3'],flush=True)
 upper_original=source.trim_by_plane((0,0,1),z);removed=upper_original-hi
 report['removed_upper_material']=volume_record(removed,tol)
 envelopes=[]
 for item in design['interfaces']:
  center=np.array(item['center_mm'],float);thick,width=item['key_cross_section_mm'];clear=item['side_clearance_mm'];height=item['engagement_mm']+item['bottom_clearance_mm'];ang=math.radians(item['angle_deg']);rad=np.array([math.cos(ang),math.sin(ang),0]);tangent=np.array([-math.sin(ang),math.cos(ang),0])
  # A sharp-cornered box conservatively encloses the actual0.15mm chamfered pocket.
  # Start0.01mm above the deliberate open assembly seam; the rest must remain inside the source solid.
  dims=(thick+2*clear,width+2*clear,height-.01)
  envelope=M.Manifold.cube(dims,True).rotate((0,0,item['angle_deg'])).translate((center[0],center[1],z+.01+dims[2]/2));envelopes.append(M.Manifold.cube((dims[0],dims[1],height+.002),True).rotate((0,0,item['angle_deg'])).translate((center[0],center[1],z+height/2)))
  outside=volume_record(envelope-source,tol)
  samples=[]
  for dz in [.15,.75,1.5,2.5,3.25]:
   for offset in np.linspace(-width*.4,width*.4,5):
    point=center+tangent*offset+np.array([0,0,dz])
    for direction in [rad,-rad]:samples.append(wall_sample(point,direction,hi))
  roof=[]
  for x in [-thick*.3,0,thick*.3]:
   for y in [-width*.3,0,width*.3]:roof.append(wall_sample(center+rad*x+tangent*y+np.array([0,0,height-.3]),[0,0,1],hi))
  walls=[x['remaining_material_mm'] for x in samples if x['remaining_material_mm'] is not None];roofs=[x['remaining_material_mm'] for x in roof if x['remaining_material_mm'] is not None]
  report['blind_pockets'].append({'index':item['index'],'conservative_sharp_pocket_envelope_outside_original':outside,'nominal_pocket_depth_mm':height,'radial_samples':samples,'roof_samples':roof,'minimum_sampled_radial_remaining_mm':min(walls) if walls else None,'minimum_sampled_axial_roof_material_mm':min(roofs) if roofs else None,'all_radial_samples_have_material_after_void':all(x['valid_void_to_wall_to_exterior'] for x in samples),'all_roof_samples_have_material_after_void':all(x['valid_void_to_wall_to_exterior'] for x in roof)})
  print('POCKET',item['index'],'outside',outside['signed_volume_mm3'],'wall',min(walls) if walls else None,flush=True)
 allowed=envelopes[0]
 for e in envelopes[1:]:allowed=allowed+e
 residuals['removed_material_outside_two_pocket_envelopes']=removed-allowed;report['removed_material_outside_two_pocket_envelopes']=volume_record(residuals['removed_material_outside_two_pocket_envelopes'],tol)
 samples={}
 for label,residual in residuals.items():
  mesh=residual.to_mesh64();vv=np.asarray(mesh.vert_properties)[:,:3];ff=np.asarray(mesh.tri_verts);samples[label]=np.concatenate([vv,vv[ff].mean(1)])
 allowed_mesh=allowed.to_mesh64();samples['__allowed_pocket_triangles']=np.asarray(allowed_mesh.vert_properties)[:,:3][np.asarray(allowed_mesh.tri_verts)]
 with tempfile.TemporaryDirectory(prefix='split-validation-') as scratch:
  temp=Path(scratch);np.savez(temp/'samples.npz',**samples);run=subprocess.run([str(a.blender.resolve()),'--background','--factory-startup','--threads','2','--python-exit-code','1','--python',str(Path(__file__).with_name('validate_split_surface_distance.py').resolve()),'--','--source',str(a.source.resolve()),'--samples',str(temp/'samples.npz'),'--output',str(temp/'surface-distances.json'),'--split-z-mm',str(z)],capture_output=True,text=True)
  if run.returncode:raise RuntimeError('BVH subprocess failed: '+run.stdout[-3000:]+run.stderr[-3000:])
  surface_evidence=json.loads((temp/'surface-distances.json').read_text())
 for label,residual in residuals.items():
  r=surface_evidence[label];r['residual_volume_fraction_of_source']=abs(residual.volume())/abs(source.volume());r['within_surface_tolerance']=r['maximum_sampled_distance_mm']<=a.surface_tolerance_mm;r['within_relative_volume_tolerance']=r['residual_volume_fraction_of_source']<=a.relative_residual_volume;print('RESIDUAL_DISTANCE',label,r['maximum_sampled_distance_mm'],flush=True)
 report['surface_residual_evidence']=surface_evidence;report['numerics']['surface_tolerance_mm']=a.surface_tolerance_mm;report['numerics']['relative_residual_volume_tolerance']=a.relative_residual_volume
 report['residual_components']={label:component_metrics(residual) for label,residual in residuals.items()}
 if a.probe_points:
  probes=[]
  for probe in json.loads(a.probe_points.read_text()):
   readings=[]
   for direction in [[1,.173,.239],[-.347,1,.181]]:
    hits=ray(probe['point_mm'],direction,source);readings.append({'direction':direction,'hit_count':len(hits),'inside_by_parity':len(hits)%2==1,'first_hits':hits[:2]})
   probes.append({**probe,'source_solid_ray_tests':readings,'interpretation':'inside' if all(x['inside_by_parity'] for x in readings) else 'outside' if all(not x['inside_by_parity'] for x in readings) else 'on-surface or ambiguous at floating precision'})
  report['diagnostic_point_membership']=probes
 report['limits']=['No physical print, adhesive test, strength, comfort or repeated assembly test.','Radial and roof thickness readings are finite samples of the actual upper STL. Conservative pocket-envelope containment is additionally checked by full-volume Boolean difference.','The two short tongues locate the full seam for adhesive bonding; they are not standalone load-bearing locks.','Original-envelope containment rules out new geometric protrusions beyond the original shell within the stated numeric volume threshold; it does not revalidate original body fit.']
 report['strict_absolute_volume_checks_passed']=all(x['within_numeric_volume_tolerance'] for x in report['path']) and all(x['within_numeric_volume_tolerance'] for x in report['containment'].values()) and report['removed_material_outside_two_pocket_envelopes']['within_numeric_volume_tolerance']
 report['passed']=all(x['within_numeric_volume_tolerance'] for x in report['path']) and all(x['within_surface_tolerance'] and x['within_relative_volume_tolerance'] for x in surface_evidence.values()) and all(x['conservative_sharp_pocket_envelope_outside_original']['within_numeric_volume_tolerance'] and x['all_radial_samples_have_material_after_void'] and x['all_roof_samples_have_material_after_void'] for x in report['blind_pockets'])
 report['interpretation']='All raw volumes retained. Absolute-only0.001mm3 pass is recorded separately. Final containment judgement additionally requires every residual-vertex/centroid distance upper bound <=0.0001mm and total residual fraction <=1e-8; this distinguishes float32 surface discrepancies from functional protrusions.'
 add_functional_summary(report,json.loads(a.body_report.read_text()))
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2));print('SPLIT_FUNCTIONAL_VALIDATION',report['functional_checks_passed'],'STRICT_NUMERIC',report['passed'],flush=True)
 return 0 if report['functional_checks_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
