"""Export real flat-bed orientations separately from assembly coordinates."""
import sys,argparse,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
import math
from frame_print import export_stl
from planar_audit import bounds
from planar_core import MM
from planar_preview import camera, save, stage
from planar_render import render
from mathutils import Matrix
from frame_runtime import cli_arguments
from frame_diy_runtime import prepare_paths, require_distinct_outputs
from frame_diy_scene import load_flat_parts

def orient(obj,flip):
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:key.value=0
    original=obj.matrix_world.copy();rotation=Matrix.Rotation(math.pi,4,'X') if flip else Matrix.Identity(4);obj.matrix_world=rotation@original;bpy.context.view_layer.update()
    bb=bounds([obj]);obj.location.z-=bb['min_mm'][2]*MM;bpy.context.view_layer.update()
    relative=obj.matrix_world@original.inverted()
    return {'rotation_x_degrees':180 if flip else 0,'translation_z_mm':relative.translation.z/MM,'matrix_m':list(map(list,relative)),'matrix_definition':'Assembly world metres to print world metres; not object-local mesh coordinates','bounds_mm':bounds([obj])}

def run(*,source,coupons,output,render_layout=False):
    paths,inputs=prepare_paths(output=output,derived_inputs={'source':source,'coupons':coupons,'manifest':Path(coupons).with_name('coupon-manifest.json')})
    out=paths['output'];records=[]
    expected={r['file'] for r in json.loads(inputs['manifest'].read_text())}
    if len(expected)!=12 or any(Path(n).name!=n for n in expected):raise ValueError('Expected 12 unique local coupon filenames')
    require_distinct_outputs(inputs.values(),[out/'print-layout.blend',out/'print-orientation.json'])
    bpy.ops.wm.open_mainfile(filepath=str(inputs['coupons']))
    names=[o.name.replace(' ','-') for o in bpy.data.objects if o.type=='MESH']
    normalized=[(n[:-5] if n.endswith('-male-base') else n)+'-mm.stl' for n in names]
    if set(normalized)!=expected or len(normalized)!=12:raise ValueError('Coupon scene must exactly match its 12-part manifest')
    parts,_=load_flat_parts(inputs['source'])
    out.mkdir(parents=True,exist_ok=True);(out/'parts').mkdir(exist_ok=True);(out/'coupons').mkdir(exist_ok=True)
    notes={'frame':'Back plane on bed. Local support/bridge trial under bayonet-slot ceilings. Do not support against visible relief.', 'locking_ring':'Flat rear face on bed. Three outward ears start above bed; bridge/support must match bayonet coupon. Keep the radial spring slit clear.', 'backing':'Photograph support face on bed. Thin 1.2 mm panel; do not iron away its dimensional height.', 'stand':'Male rail heads on bed; use removable supports below pads, long beam, and leg overhangs. Keep release gap clear. Beam length follows XY layers; remove supports before testing.'}
    for role,obj in parts.items():
        placement=orient(obj,role in ['backing','stand']);path=out/'parts'/(role+'-mm.stl');export_stl(path,[obj]);records.append({'file':str(path.relative_to(out)),'role':role,'quantity':1,**placement,'print_notes':notes[role],'support_status':'planned; not sliced or printed'})
    if render_layout:
        # Comparison board, not a claim that all pieces fit a single build plate.
        positions={'frame':(-100,65),'locking_ring':(85,80),'backing':(-105,-115),'stand':(85,-100)}
        for role,o in parts.items():o.location.x+=positions[role][0]*MM;o.location.y+=positions[role][1]*MM
        for o in list(bpy.data.objects):
            if o not in parts.values():bpy.data.objects.remove(o,do_unlink=True)
        cam=stage((0,-12,18),370);camera(cam,(0,-15,13),(180,-220,550),490);render(out/'print-layout.png',1500,1300,24);save(out/'print-layout.blend')
    bpy.ops.wm.open_mainfile(filepath=str(Path(coupons).resolve()));coupon_objs=[o for o in bpy.data.objects if o.type=='MESH']
    for o in coupon_objs:
        label=o.name.replace(' ','-');label=label[:-5] if label.endswith('-male-base') else label;flip=(label=='stand-slide-release' or (label.startswith('dovetail-fit-') and label.endswith('male') and not label.endswith('female')))
        placement=orient(o,flip);path=out/'coupons'/(label+'-mm.stl');export_stl(path,[o]);records.append({'file':str(path.relative_to(out)),'role':'coupon','quantity':1,**placement,'print_notes':'Match the final mating part orientation and material. Measure before assembly; no universal machine-fit claim.'})
    (out/'print-orientation.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));print('PRINT_ORIENTATIONS_COMPLETE',len(records))
    return records

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--coupons',required=True);p.add_argument('--output',required=True);p.add_argument('--render-layout',action='store_true');a=p.parse_args(cli_arguments());run(source=a.source,coupons=a.coupons,output=a.output,render_layout=a.render_layout)
if __name__=='__main__':main()
