"""Actual same-mesh release, disassembly, reassembly and tabletop film. Blender."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from render_engine import set_engine

from glb_clips import merge_file
from frame_recipe import validate_recipe
import bpy
import numpy as np
from frame_core import cylinder
from mathutils import Vector
from planar_core import MM, cube, loft, material
from planar_preview import camera, export_glb, save
from planar_render import render
from mathutils import Matrix
from frame_runtime import cli_arguments
from frame_diy_runtime import prepare_paths, require_distinct_outputs

def ease(f,a,b):
    u=max(0,min(1,(f-a)/(b-a)));return u*u*(3-2*u)

def assembly_state(frame):
    # One complete removal followed by exact time reversal, including release keys.
    f=frame if frame<=145 else 290-frame
    lift=40*ease(f,8,20)
    stand_press=ease(f,22,30)*(1-ease(f,53,59))
    stand=(0,-30*ease(f,31,49),-20*ease(f,49,55))
    ring_press=ease(f,59,67)*(1-ease(f,96,103))
    ring=(-135*ease(f,98,112),0,-35*ease(f,81,96))
    ring_angle=-12*ease(f,68,80)
    backing=(135*ease(f,116,131),0,-25*ease(f,103,115))
    artwork=(0,0,-70*ease(f,131,141))
    return {'lift_mm':lift,'stand':stand,'stand_press':stand_press,'locking_ring':ring,'ring_angle_deg':ring_angle,'ring_press':ring_press,'backing':backing,'artwork':artwork}

def merge_scene_animation(path):
    report = merge_file(path, path, clips='all', name='Release, replace photograph, assemble and display', in_place=True)
    return {'original_actions':report['before_clip_count'], 'final_actions':report['after_clip_count'],
            'unique_node_property_channels':report['channel_count']}

def run(*,source,output,frames=None,render_stills=True,render_animation=False):
    if render_animation and frames is None:raise ValueError('Explicit frames directory required for animation rendering')
    paths,inputs=prepare_paths(output=output,work=frames if render_animation else None,derived_inputs={'source':source,'measurement':Path(source).with_name('measurements.json')})
    validate_recipe(json.loads(inputs['measurement'].read_text())['configuration']);out=paths['output']
    require_distinct_outputs(inputs.values(),[out/n for n in ['assembly.blend','motion.glb','exploded.glb','video-manifest.json','motion-states.json','camera-framing-check.json']])
    bpy.ops.wm.open_mainfile(filepath=str(inputs['source']));s=bpy.context.scene;parts={}
    for role in ('frame','backing','locking_ring','stand','artwork'):
        found=[o for o in bpy.data.objects if o.get('assembly_role')==role]
        if len(found)!=1 or found[0].type!='MESH':raise ValueError('One mesh required for role '+role)
        parts[role]=found[0]
    basis=parts['frame'].matrix_world.copy();cam=s.camera
    if cam is None or cam.data.type!='ORTHO':raise ValueError('Expected generated display scene with orthographic camera')
    for role,o in parts.items():
        if max(abs(o.matrix_world[i][j]-basis[i][j]) for i in range(4) for j in range(4))>1e-6:
            raise ValueError('Use the unanimated display scene from build, with matching part transforms')
        if role in ('stand','locking_ring') and (not o.data.shape_keys or len(o.data.shape_keys.key_blocks)!=2):
            raise ValueError('Required basis and release shape for '+role)
    out.mkdir(parents=True,exist_ok=True)
    def place(f):
        state=assembly_state(f);lift=Matrix.Translation((0,0,state['lift_mm']*MM))
        for role,o in parts.items():
            delta=state.get(role,(0,0,0));rot=Matrix.Rotation(math.radians(state['ring_angle_deg']),4,'Z') if role=='locking_ring' else Matrix.Identity(4)
            o.matrix_world=lift@basis@Matrix.Translation(Vector(delta)*MM)@rot
            if o.data.shape_keys:o.data.shape_keys.key_blocks[1].value=state['ring_press'] if role=='locking_ring' else state['stand_press']
        bpy.context.view_layer.update();return state
    if render_stills:
        place(1);camera(cam,(-8,0,80),(72,-370,115),212);render(out/'hero.png',1200,1400,32)
        camera(cam,(-7,24,76),(170,320,150),215);render(out/'rear.png',1200,1300,28)
        camera(cam,(-7,18,80),(0,370,80),208);render(out/'rear-direct.png',1100,1200,24)
        # Real tabletop objects, matching the retained photograph and scale.
        linen=material('Oatmeal notebook cloth',(.34,.28,.20),0,.85);pages=material('Uncoated pages',(.63,.60,.52),0,.9);dark=material('Graphite pencil',(.035,.04,.05),0,.6);props=[]
        for name,dim,loc,mat in [('Notebook cover',(125,178,3),(178,46,2),linen),('Notebook pages',(121,174,10),(178,46,8),pages),('Notebook upper cover',(125,178,3),(178,46,14),linen)]:
            o=cube(name,dim,loc,mat,1.3);o.rotation_euler.z=-.18;props.append(o)
        props.append(cylinder('Graphite pencil',2.8,148,(169,-7,20),dark,(.18,1,.02),6))
        cer=material('Stoneware cup',(.36,.40,.34),0,.68);q=np.arange(96)*2*np.pi/96;rings=[]
        for rr,zz in [(23,0),(25,3),(29,49),(28,55),(25.3,55),(25.7,49),(22.3,5)]:rings.append(np.c_[rr*np.cos(q)-164,rr*np.sin(q)+86,np.full(96,zz)])
        props.append(loft('Hollow ceramic cup',rings,cer,True,True));camera(cam,(25,30,75),(180,-440,190),400);render(out/'desk.png',1500,1200,32)
        for o in props:o.hide_render=True
        # Actual release features close up, with all other assembly geometry retained.
        place(62);target=basis@Vector((-44*MM,31*MM,0))+Vector((0,0,.04));camera(cam,target/MM,(90,200,85),95);render(out/'ring-release-detail.png',1200,1000,28)
        place(22);target=basis@Vector((3*MM,-62*MM,-3.5*MM))+Vector((0,0,.04));camera(cam,target/MM,(100,260,110),105);render(out/'stand-release-detail.png',1200,1000,28)
        place(145);camera(cam,(-4,43,119),(150,420,220),465);render(out/'exploded.png',1500,1000,28)
    place(145);export_glb(out/'exploded.glb',list(parts.values()))
    s.render.fps=12;s.frame_start=1;s.frame_end=289;cam.rotation_mode='QUATERNION';framing=[];state_records=[]
    for f in range(1,290):
        state=place(f);state_records.append({'frame':f,**state})
        for o in parts.values():
            o.rotation_mode='QUATERNION';o.keyframe_insert(data_path='location',frame=f);o.keyframe_insert(data_path='rotation_quaternion',frame=f)
            if o.data.shape_keys:o.data.shape_keys.key_blocks[1].keyframe_insert(data_path='value',frame=f)
        # Orbit to the back before releasing, return to front only after complete locking.
        ef=f if f<=145 else 290-f;u=ease(ef,3,21);theta=math.radians(166*(1-u)+22*u);target=Vector((-5,25,80+state['lift_mm']*.8))*MM
        cam.location=target+Vector((380*math.sin(theta),380*math.cos(theta),120))*MM;cam.rotation_quaternion=(target-cam.location).to_track_quat('-Z','Y');bpy.context.view_layer.update()
        inv=cam.matrix_world.inverted();q=np.array([inv@(o.matrix_world@Vector(c)) for o in parts.values() for c in o.bound_box]);scale=max(228*MM,2*np.abs(q[:,0]).max()*1.12,2*np.abs(q[:,1]).max()*1.5*1.12);cam.data.ortho_scale=scale
        cam.keyframe_insert(data_path='location',frame=f);cam.keyframe_insert(data_path='rotation_quaternion',frame=f);cam.data.keyframe_insert(data_path='ortho_scale',frame=f)
        framing.append({'frame':f,'max_fill':float(max(2*np.abs(q[:,0]).max()/scale,2*np.abs(q[:,1]).max()/(scale/1.5)))})
    for act in bpy.data.actions:
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        for key in fc.keyframe_points:key.interpolation='LINEAR'
    s.frame_set(1);bpy.ops.object.select_all(action='DESELECT')
    for o in parts.values():o.select_set(True)
    bpy.context.view_layer.objects.active=parts['frame'];bpy.ops.export_scene.gltf(filepath=str(out/'motion.glb'),export_format='GLB',use_selection=True,export_apply=True,export_animations=True,export_animation_mode='SCENE',export_frame_range=True,export_force_sampling=True,export_bake_animation=True,export_nla_strips=False)
    report={'fps':12,'frames':289,'duration_seconds':289/12,'sequence':'Lift and support frame, pull the stand lever away from the frame and withdraw easel, press and rotate ring, extract ring, static backing and photograph; exact reverse rebuild; rest on table.','material_deformation':'Prescribed geometric flex morph, no force or stress simulation','not_verified':['physical print','fatigue','paper scuff','friction','actual finger force'],'camera_max_fill':max(x['max_fill'] for x in framing),'animation_export':merge_scene_animation(out/'motion.glb')}
    (out/'video-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));(out/'motion-states.json').write_text(json.dumps(state_records,indent=2));(out/'camera-framing-check.json').write_text(json.dumps(framing,indent=2));save(out/'assembly.blend')
    if render_animation:
        frame_dir=Path(frames);frame_dir.mkdir(parents=True,exist_ok=True);set_engine(s);s.render.resolution_x=1080;s.render.resolution_y=720;s.render.image_settings.file_format='PNG';s.render.filepath=str(frame_dir/'frame-');bpy.ops.render.render(animation=True)
    print('MEDIA_COMPLETE',out,flush=True)
    return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--frames');p.add_argument('--no-stills',action='store_true');p.add_argument('--render-animation',action='store_true');a=p.parse_args(cli_arguments());run(source=a.source,output=a.output,frames=a.frames,render_stills=not a.no_stills,render_animation=a.render_animation)
if __name__=='__main__':main()
