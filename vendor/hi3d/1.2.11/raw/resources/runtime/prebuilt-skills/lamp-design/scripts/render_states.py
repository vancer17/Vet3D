"""Render reproducible OFF/ON stills or explicitly requested turntables without changing exposure or studio light."""
import argparse,sys,math,json,time,hashlib
from pathlib import Path
import bpy
from mathutils import Vector

def configured_sources(cfg):
    lights=[];emissions=[]
    for name,energy in cfg.get('lights',{}).items():
        o=bpy.data.objects.get(name)
        if o is None or o.type!='LIGHT' or not math.isfinite(energy) or energy<=0:raise ValueError(f'Invalid luminaire light: {name}')
        lights.append((o.data,energy))
    if not lights:raise ValueError('Require at least one real scene light')
    for name,strength in cfg.get('emissions',{}).items():
        m=bpy.data.materials.get(name);b=m.node_tree.nodes.get('Principled BSDF') if m and m.use_nodes else None
        if not b or not math.isfinite(strength) or strength<=0:raise ValueError(f'Invalid emissive material: {name}')
        emissions.append((b.inputs['Emission Strength'],strength))
    return lights,emissions

def configure_render(s,samples,resolution,fps):
    s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=samples;s.cycles.use_denoising=True
    s.render.resolution_x=s.render.resolution_y=resolution;s.render.resolution_percentage=100
    s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.fps=fps

def render_states(input_path,cfg,out,frames=1,fps=24,resolution=1080,samples=32):
    if min(frames,fps,resolution,samples)<=0:raise ValueError('Positive render settings required')
    if len(cfg.get('target_m',[]))!=3 or not all(math.isfinite(v) for v in cfg['target_m']):
        raise ValueError('target_m must contain three finite coordinates in metres')
    if not math.isfinite(cfg.get('orbit_degrees',360)):raise ValueError('Finite orbit required')
    start=time.monotonic();out=Path(out).resolve()
    if out.exists() and any(out.iterdir()):raise FileExistsError('Use a fresh render output directory')
    bpy.ops.wm.open_mainfile(filepath=str(Path(input_path).resolve()))
    s=bpy.context.scene
    if not s.camera:raise ValueError('Scene must have an authored camera')
    lights,emissions=configured_sources(cfg)
    out.mkdir(parents=True,exist_ok=True)
    configure_render(s,samples,resolution,fps)
    cam=s.camera;target=Vector(cfg['target_m']);startloc=cam.location.copy();delta=startloc-target
    states={}
    for state in ['off','on']:
        folder=out/state;folder.mkdir(exist_ok=True);on=state=='on'
        for data,e in lights:data.energy=e if on else 0
        for socket,e in emissions:socket.default_value=e if on else 0
        for i in range(frames):
            angle=math.radians(cfg.get('orbit_degrees',360))*i/max(frames,1)
            d=Vector((delta.x*math.cos(angle)-delta.y*math.sin(angle),delta.x*math.sin(angle)+delta.y*math.cos(angle),delta.z))
            cam.location=target+d;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
            s.render.filepath=str(folder/f'{i:04d}.png');bpy.ops.render.render(write_still=True)
        states[state]={'frames':frames,'lamp_energies':{d.name:d.energy for d,e in lights},'emission_strengths':[socket.default_value for socket,e in emissions]}
    cam.location=startloc;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'render-scene.blend'))
    manifest={'blender':bpy.app.version_string,'engine':s.render.engine,'device':'CPU','fps':fps,'resolution':[resolution,resolution],
      'samples':samples,'denoise':True,'view_transform':s.view_settings.view_transform,'exposure':s.view_settings.exposure,
      'input_sha256':hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),'states':states,'elapsed_seconds':round(time.monotonic()-start,2),
      'comparison':'Identical camera path and studio; only luminaire lamps and emitter material strengths change',
      'limitation':'Visual optical approximation, not photometry, electrical startup or temperature prediction'}
    return manifest

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--frames',type=int,default=1,help='Images per light state; default 1. Multiple frames are for explicitly requested video');p.add_argument('--fps',type=int,default=24)
    p.add_argument('--resolution',type=int,default=1080);p.add_argument('--samples',type=int,default=32)
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    a=p.parse_args(args)
    cfg=json.loads(Path(a.config).read_text())
    manifest=render_states(a.input,cfg,a.output,a.frames,a.fps,a.resolution,a.samples)
    (Path(a.output)/'render-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest),flush=True)

if __name__=='__main__':main()
