"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, sys, argparse, json, hashlib
from pathlib import Path
from scene_samples import sample_frames, world_mesh
from surface_pairs import surface_tree, pair_counts
from types import SimpleNamespace
from functools import partial
from box_runtime import cli_arguments, validate_paths

from cli_schemas import inspection_stage

def inspect_motion(*, input, output):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(input=input, output=output)
    validate_paths(a)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(Path(a.input).resolve()))
    s = bpy.context.scene
    meshes = [o for o in s.objects if o.type == 'MESH']
    def find(prefix):
        return next((o for o in meshes if o.name.startswith(prefix)))
    body = find('Elliptical travel shell')
    tray = find('One piece removable divided')
    lid = find('Relief domed travel lid')
    card = find('Removable earring card')
    spool = find('Removable necklace winding')
    foam = [o for o in meshes if 'capture foam' in o.name or o.name.startswith('Replaceable underside')]
    screws = [o for o in meshes if o.name.startswith('M3 removable')]
    frames=[1,7,14,18,24,29,34,40,45,50,55,60,65,70,75,80,82,88,93,97,102,110,116,120,126,131,136,142,146,150,155,160]
    by_import_frame={(f-1)/16*s.render.fps+1:f for f in frames}
    objects=[body,tray,lid,card,spool,*foam,*screws]
    pairs=[(x.name,y.name) for x in [lid,*foam,*screws] for y in [body,tray,card,spool]]
    pairs += [(x.name,y.name) for x,y in [(tray,body),(card,tray),(spool,tray)]]
    def inspect(bf):
        f=by_import_frame[bf]
        trees={o.name:surface_tree(*world_mesh(o,evaluated=False)[:2]) for o in objects}
        return {'source_frame_at_16fps':f,'time_seconds':(f-1)/16,'pairs':pair_counts(trees,pairs)}
    rows=sample_frames(s,by_import_frame,inspect)
    result = {'input_sha256': hashlib.sha256(Path(a.input).read_bytes()).hexdigest(), 'method': 'Fresh final GLB import, all synchronized transforms evaluated at32 semantic and intermediate times; exact triangle BVH. Coplanar screw seats are interpreted separately if encountered.', 'import_fps': s.render.fps, 'actions': len(bpy.data.actions), 'samples': rows}
    Path(a.output).write_text(json.dumps(result, indent=2))
    print('MOTION_CHECK_NONZERO', sum((v > 0 for r in rows for v in r['pairs'].values())))

def main(argv=None):
    return inspection_stage(inspect_motion, cli_arguments, argv)

if __name__ == "__main__":
    main()
