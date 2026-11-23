"""Extract true interfaces from native assembly; add explicit per-face fit ladder."""
import sys,argparse,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from build_frame_diy import annular_sector, dovetail
from frame_core import boolean
from frame_print import export_stl
from planar_core import clean_solid_mesh, cube
from planar_preview import save
from frame_runtime import cli_arguments
from frame_diy_runtime import prepare_paths, require_distinct_outputs
from frame_diy_scene import load_flat_parts
from blender_coupon import crop_object
from coupon_records import clearance_series, source_record, pair_record

def run(*,source,output):
    paths, inputs = prepare_paths(output=output, derived_inputs={'source':source})
    out=paths['output'];require_distinct_outputs(inputs.values(), [out/'coupons.blend'])
    parts,cfg=load_flat_parts(inputs['source']);out.mkdir(parents=True,exist_ok=True)
    mat=parts['frame'].data.materials[0];records=[];items=[];pairs=[];source_info=source_record(inputs['source'])
    def take(role,label,cutter):
        try:
            obj=crop_object(parts[role],cutter,name=label,
                            intersect=lambda o,c:boolean(o,c,'INTERSECT'),prepare=clean_solid_mesh)
        finally:
            mesh=cutter.data;bpy.data.objects.remove(cutter,do_unlink=True)
            if mesh.users==0:bpy.data.meshes.remove(mesh)
        export_stl(out/(label+'-mm.stl'),[obj]);records.append({'file':label+'-mm.stl','source_role':role,'purpose':'Exact cropped final interface in flat assembly coordinates; see print directions', 'nominal_clearance_mm':cfg['fit_clearance_mm'],'quantity':1});items.append(obj)
    for role,label in [('frame','bayonet-female'),('locking_ring','bayonet-male')]:
        take(role,label,annular_sector('Bayonet crop',48,65,56,85,-2,5.4,mat))
    for role,label in [('frame','ring-release-female'),('locking_ring','ring-release-male')]:
        take(role,label,annular_sector('Long release crop',47.5,64,114,151,-2,5.4,mat))
    for role,label in [('frame','stand-receiver'),('stand','stand-slide-release')]:
        take(role,label,cube('Stand interface crop',(76,35,12),(0,-68.5,-1),mat,0))
    # Female offset is stated per vertical/flank coordinate, not diametral clearance.
    definition='female each X side enlarged c; positive Z head clearance c; straight coordinate offset, not normal-distance offset on 45deg flank'
    for candidate in clearance_series([.15,.25,.35],definition=definition):
        c=candidate['clearance_mm']
        name='dovetail-fit-%03d'%round(c*100)
        female=cube(name+' female',(15,18,4.4),(0,-.5,1.0),mat,0);boolean(female,dovetail('Matching female cavity',0,-10,6.75,mat,c),'DIFFERENCE')
        male=cube(name+' male base',(13,13,2),(0,0,-3.25),mat,0);boolean(male,dovetail('Matching male head',0,-6.5,6.5,mat))
        for part,o in [('female',female),('male',male)]:
            clean_solid_mesh(o);export_stl(out/(name+'-'+part+'-mm.stl'),[o]);records.append({'file':name+'-'+part+'-mm.stl','quantity':1,'clearance_mm':c,'definition':'female each X side enlarged c; positive Z head clearance c; straight coordinate offset, not normal-distance offset on 45deg flank','purpose':'Fit ladder; final nominal is recorded separately', 'final_nominal_clearance_mm':cfg['fit_clearance_mm']});items.append(o)
        pairs.append(pair_record(name,{side:name+'-'+side+'-mm.stl' for side in ['female','male']},clearance_mm=c,definition=definition,orientation='Same flat construction axes as final recipe; see production print directions',source={'recipe':cfg,'native':source_info}))
    for name,files in [('bayonet',['bayonet-female','bayonet-male']),('ring-release',['ring-release-female','ring-release-male']),('stand',['stand-receiver','stand-slide-release'])]:
        pairs.append(pair_record(name,{'female':files[0]+'-mm.stl','male':files[1]+'-mm.stl'},clearance_mm=cfg['fit_clearance_mm'],definition='Final recipe fit_clearance_mm; no new offset applied while cropping',orientation='Flat assembly coordinates; retain production print directions',source=source_info))
    (out/'coupon-pairs.json').write_text(json.dumps(pairs,ensure_ascii=False,indent=2))
    (out/'coupon-manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    for o in list(bpy.data.objects):
        if o not in items:bpy.data.objects.remove(o,do_unlink=True)
    save(out/'coupons.blend');print('COUPONS_COMPLETE',len(records));return records
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args(cli_arguments(argv));run(source=a.source,output=a.output)
if __name__=='__main__':main()
