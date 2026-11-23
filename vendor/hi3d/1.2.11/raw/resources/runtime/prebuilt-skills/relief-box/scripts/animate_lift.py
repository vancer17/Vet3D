"""Basic lift-lid/tray assembly animation, independent of any ornament theme."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,json
from types import SimpleNamespace
import bpy
from box_runtime import cli_arguments, validate_paths
from planar_core import MM

def keyframe_translation(obj, keys, base_location):
    """Apply explicit frame/XYZ-mm offsets to one object (Blender side effect)."""
    for frame,delta in keys:
        obj.location=base_location
        obj.location.x+=delta[0]*MM;obj.location.y+=delta[1]*MM;obj.location.z+=delta[2]*MM
        obj.keyframe_insert(data_path='location',frame=frame)

def animate(*, scene, output, frames=None, render=False):
    """Load a basic box scene+measurement groups; export complete open/close action."""
    a=SimpleNamespace(scene=scene,output=output);validate_paths(a)
    if render and frames is None:raise ValueError('Explicit --frames directory required when rendering')
    frame_dir=Path(frames).resolve() if frames else None
    if frame_dir:validate_paths(SimpleNamespace(output=frame_dir))
    data=json.loads((a.scene.parent/'measurements.json').read_text());groups=data['animation_groups']
    if not groups:raise ValueError('No explicit lid/tray animation groups')
    bpy.ops.wm.open_mainfile(filepath=str(a.scene));s=bpy.context.scene
    s.frame_start=1;s.frame_end=160;s.render.fps=24
    parts=[o for o in s.objects if o.type=='MESH' and o.get('product_part')]
    if not parts:raise ValueError('Scene does not contain tagged product parts from basic builder')
    base={o.name:o.location.copy() for o in parts}
    for group in groups:
        variant=next(v for v in data['variants'] if v['id']==group['kind'])
        # Separate the lid entirely before lifting the tray; return tray first.
        lift=max(90,float(variant['outer_mm'][2])+65)
        for role,keys in [('lid',[(1,(0,0,0)),(12,(0,0,0)),(44,(0,0,lift)),(112,(0,0,lift)),(148,(0,0,0)),(160,(0,0,0))]),('tray',[(1,(0,0,0)),(46,(0,0,0)),(70,(0,0,45)),(90,(0,0,45)),(110,(0,0,0)),(160,(0,0,0))])]:
            for name in group[role]:keyframe_translation(bpy.data.objects[name],keys,base[name])
    s.frame_set(1);a.output.mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.export_scene.gltf(filepath=str(a.output/'motion.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='SCENE',export_force_sampling=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(a.output/'motion.blend'))
    result={'frames':[1,160],'fps':24,'groups':groups,'end_state':'closed and tray reseated','motion':'vertical manual lift, not a hinge or physical retention test'}
    (a.output/'animation.json').write_text(json.dumps(result,indent=2))
    if render:
        frame_dir.mkdir(parents=True,exist_ok=True);s.render.image_settings.file_format='PNG';s.render.filepath=str(frame_dir/'frame-');bpy.ops.render.render(animation=True)
    return result

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--scene',required=True);p.add_argument('--output',required=True);p.add_argument('--frames');p.add_argument('--render',action='store_true')
    print(json.dumps(animate(**vars(p.parse_args(sys.argv[sys.argv.index('--')+1:] if argv is None and '--' in sys.argv else cli_arguments(argv)))),indent=2))
if __name__=='__main__':main()
