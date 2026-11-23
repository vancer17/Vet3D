"""Blender: validate pressure screw/head/key sweeps, nuts and local walls.

blender -b file.blend --python hi3d-verify-pressure-access-1.py -- --out report.json
Optional --presets rebuilds the five V5 B10 presets from the adjacent source.
Engineering envelopes only: no thread strength or physical assembly claim.
"""
from pathlib import Path
import argparse,importlib.util,json,math,sys
import bpy,bmesh
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'src/hi3d-frame-builder-1.py'
if not source.exists():source=ROOT/'hi3d-frame-builder-1.py'
spec=importlib.util.spec_from_file_location('pressure_access_builder',source)
fb=importlib.util.module_from_spec(spec);spec.loader.exec_module(fb)
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--presets',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])


def volume(o):
    bm=bmesh.new();bm.from_mesh(o.data);v=abs(bm.calc_volume(signed=True));bm.free();return v


def intersection(a,b,collection):
    bpy.context.view_layer.update()
    aa=bpy.data.objects.new('check overlap',a.data.copy());collection.objects.link(aa)
    aa.data.transform(a.matrix_world);aa.matrix_world=Matrix.Identity(4)
    bb=bpy.data.objects.new('check cutter',b.data.copy());collection.objects.link(bb)
    bb.data.transform(b.matrix_world);bb.matrix_world=Matrix.Identity(4)
    bpy.context.view_layer.objects.active=aa
    mod=aa.modifiers.new('check','BOOLEAN');mod.operation='INTERSECT';mod.solver='EXACT';mod.object=bb
    bpy.ops.object.modifier_apply(modifier=mod.name)
    value=volume(aa)
    bpy.data.objects.remove(aa,do_unlink=True);bpy.data.objects.remove(bb,do_unlink=True)
    return value


def ray_intervals(tree,origin,direction,limit):
    origin=Vector(origin);direction=Vector(direction).normalized();distances=[];offset=0
    while offset<limit:
        hit,normal,index,distance=tree.ray_cast(origin+direction*offset,direction,limit-offset)
        if hit is None:break
        t=offset+distance
        if not distances or abs(t-distances[-1])>1e-4:distances.append(t)
        offset=t+1e-4
    return distances


def check_current(p):
    scene=bpy.data.scenes['01_ASSEMBLY'];bpy.context.window.scene=scene
    d=fb.derived(p);access=fb.pressure_access_spec(p,d)
    parts=[o for o in scene.objects if o.type=='MESH' and o.get('printable')]
    rails=[o for o in parts if 'RAIL_' in o.name]
    obstacles=[o for o in parts if o.name not in ['11_BACK_LED_TRAY','14_U_STAND']]
    bars=[o for o in parts if 'PRESSURE_BAR' in o.name]
    locations=[o.location.copy() for o in bars]
    col=bpy.data.collections.new('PRESSURE_ACCESS_TEST');scene.collection.children.link(col);fb.WORK=col
    rows=[];maximum=0
    # Retained back-fixing nuts remain present when the tray/screws are removed.
    back_nuts=[]
    for x,y,nx,ny,owner in fb.back_screw_specs(p):
        back_nuts.append(fb.cyl('actual retained M3 nut',5.5*2/math.sqrt(3),2.4,
            (x,y,d['back_front']-3.5),vertices=6,phase=30 if nx else 0))
    for sx in [-1,1]:
        rail=next(o for o in rails if ('RIGHT' if sx>0 else 'LEFT') in o.name)
        tree=BVHTree.FromPolygons([rail.matrix_world@v.co for v in rail.data.vertices],
                                 [tuple(poly.vertices) for poly in rail.data.polygons])
        for yy in [-d['clamp_y'],d['clamp_y']]:
            xx=sx*d['pressure_x'];station={'xy_mm':[xx,yy],'endpoint_checks':[]}
            for thickness in [p['panel_min'],p['panel_max']]:
                for bar,loc in zip(bars,locations):bar.location.z=loc.z+thickness-p['preview_thickness']
                tip=d['seat']+thickness+1.5
                under=tip+d['pressure_screw_length'];top=under+d['pressure_head_h']
                far=d['depth']+5
                envelopes=[
                    fb.cyl('screw shaft complete insertion sweep',d['pressure_d'],far-tip,(xx,yy,(far+tip)/2),vertices=64),
                    fb.cyl('socket head complete insertion sweep',d['pressure_head_d'],far-under,(xx,yy,(far+under)/2),vertices=64),
                    fb.cyl('long straight hex-key envelope',d['pressure_tool_af']*2/math.sqrt(3),far-(top-1),
                           (xx,yy,(far+top-1)/2),vertices=6)]
                overlaps=[]
                for envelope in envelopes:
                    overlap=sum(intersection(envelope,o,col) for o in obstacles+back_nuts)
                    overlaps.append(round(overlap,7));maximum=max(maximum,overlap)
                    bpy.data.objects.remove(envelope,do_unlink=True)
                nut_t=1.6 if d['pressure_d']==2 else 2.4
                nut_lo=11+(d['pressure_nut_t']-nut_t)/2;nut_hi=nut_lo+nut_t
                engagement=max(0,min(under,nut_hi)-max(tip,nut_lo))
                station['endpoint_checks'].append(dict(thickness_mm=thickness,tip_z_mm=tip,
                    under_head_z_mm=under,head_top_z_mm=top,
                    shaft_head_key_sweep_overlap_mm3=overlaps,
                    nut_engagement_mm=engagement,
                    required_straight_key_reach_mm=far-(top-1),
                    pass_=max(overlaps)<=.02 and engagement>=nut_t-.001))
            # Nut insertion, shoulder retention and resistance to a 30-degree turn.
            nut_af=4 if d['pressure_d']==2 else 5.5;nut_t=1.6 if d['pressure_d']==2 else 2.4
            nut=fb.cyl('actual pressure nut',nut_af*2/math.sqrt(3),nut_t,
                (xx,yy,11+d['pressure_nut_t']/2),vertices=6,phase=30)
            original=nut.matrix_world.copy();loading=[]
            for offset in [7,5,3,1,0]:
                nut.matrix_world=Matrix.Translation(Vector((-sx*offset,0,0)))@original
                loading.append(intersection(nut,rail,col))
            nut.matrix_world=Matrix.Translation(Vector((0,0,.5)))@original
            retained=intersection(nut,rail,col)
            nut.matrix_world=original;nut.rotation_euler.z+=math.radians(30)
            rotation_stop=intersection(nut,rail,col)
            bpy.data.objects.remove(nut,do_unlink=True)
            walls=[]
            for z in [16,20,25]:
                hits=ray_intervals(tree,(xx,yy,z),(sx,0,0),8)
                walls.append({'z_mm':z,'material_hits_mm':hits,
                    'outer_wall_mm':hits[1]-hits[0] if len(hits)>=2 else None})
            inner=ray_intervals(tree,(xx,yy,20),(-sx,0,0),d['pressure_x']-access['chamber_inner_x']-.05)
            local_web=None
            if sx<0 and yy<0 and p['height']==100 and d['pressure_d']==2:
                hits=ray_intervals(tree,(xx,yy,20),(0,-1,0),5)
                local_web=hits[1]-hits[0] if len(hits)>=2 else None
            station.update(nut_loading_overlap_mm3=[round(v,7) for v in loading],
                nut_axial_lift_0_5_contact_mm3=retained,nut_rotation_30_contact_mm3=rotation_stop,
                preserved_roof_above_nut_trap_mm=15.6-(11+d['pressure_nut_t']),
                outer_wall_samples=walls,inward_neck_obstructions_mm=inner,
                local_switch_separator_mm=local_web)
            station['pass']=all(x['pass_'] for x in station['endpoint_checks']) and max(loading)<=.02 and retained>.02 and rotation_stop>.02 and not inner and all(x['outer_wall_mm'] is not None and x['outer_wall_mm']>=1.25 for x in walls) and (local_web is None or local_web>=.75)
            rows.append(station)
    for bar,loc in zip(bars,locations):bar.location=loc
    for ob in back_nuts:bpy.data.objects.remove(ob,do_unlink=True)
    bpy.data.collections.remove(col)
    return dict(frame_mm=[p['width'],p['height']],parts=len(parts),access=access,
        pressure_screw_length_mm=d['pressure_screw_length'],stations=rows,
        max_envelope_overlap_mm3=maximum,pass_=all(x['pass'] for x in rows),
        assembly_condition='LED tray and its four M3 screws removed; captive nuts retained',
        scope='geometric sweeps and local wall measurements; no physical assembly/load test')


scene=bpy.data.scenes['01_ASSEMBLY']
p=json.loads(scene['parameters_json']);results=[check_current(p)]
if args.presets:
    for w,h in [(150,100),(100,150),(180,130),(200,150),(250,200)]:
        if [w,h]==[p['width'],p['height']]:continue
        q={**p,'width':w,'height':h};print('PRESSURE_PRESET',w,h,flush=True)
        fb.generate(q,reviews=False);results.append(check_current(q))
report={'version':'V5.1','units':'mm','overlap_tolerance_mm3':.02,
        'results':results,'pass':all(x['pass_'] for x in results)}
args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n')
print('PRESSURE_ACCESS_RESULT',json.dumps({'pass':report['pass'],'presets':len(results),'maximum_overlap_mm3':max(r['max_envelope_overlap_mm3'] for r in results)}),flush=True)
if not report['pass']:raise RuntimeError('Pressure access check failed; see report')
