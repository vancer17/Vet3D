"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, sys, argparse, json, numpy as np, hashlib
from pathlib import Path
from mathutils import Vector
from scene_samples import sample_frames, world_mesh
from surface_pairs import surface_tree, pair_counts
from types import SimpleNamespace
from functools import partial
from frame_runtime import cli_arguments, validate_paths

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
    frame = next((o for o in meshes if any(label in o.name for label in ('Continuous flowing', 'Eccentric frame'))))
    board = next((o for o in meshes if 'Removable oval' in o.name))
    card = next((o for o in meshes if 'Oval cotton art card' in o.name))
    stand = next((o for o in meshes if 'One piece detachable' in o.name))
    keepers = [o for o in meshes if 'Rotating rear keeper' in o.name]
    frames = [1, 10, 20, 30, 40, 46, 50, 60, 68, 76, 86, 88, 94, 102, 110, 120, 132, 140, 148, 160, 168, 190, 239]
    objects=[frame,board,card,stand,*keepers]
    pairs=[(obj.name,other.name) for obj in [board,card] for other in [frame,stand,*keepers]]
    def inspect(f):
        trees={o.name:surface_tree(*world_mesh(o)[:2],epsilon=0) for o in objects}
        return {'imported_frame_at_24fps':f,'pairs':pair_counts(trees,pairs)}
    rows=sample_frames(s,frames,inspect)
    result = {'file': str(Path(a.input).name), 'sha256': hashlib.sha256(Path(a.input).read_bytes()).hexdigest(), 'method': 'Fresh GLB import. Triangle-surface BVH crossings epsilon0, without mesh edits. Coincident bearing contacts may be separately interpreted.', 'import_fps': s.render.fps, 'action_count': len(bpy.data.actions), 'samples': rows}
    Path(a.output).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

def main(argv=None):
    return inspection_stage(inspect_motion, cli_arguments, argv)

if __name__ == "__main__":
    main()
