"""review native local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys, json, math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
import hashlib
from stage_cli import cli_arguments, StageFinished, _finish_stage
from scene_samples import sample_frames, world_mesh
from surface_pairs import surface_tree, pair_counts

from preview_scene import projected_bounds

def tree(o, *, tree_cache=None):
    # Compatibility argument is accepted; cross-frame matrix-only caches are unsafe.
    points, triangles, _ = world_mesh(o, evaluated=False)
    return surface_tree(points, triangles, epsilon=1e-8)

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    A = arguments
    d = Path(A[0])
    bpy.ops.wm.open_mainfile(filepath=str(d / 'motion.blend'))
    lower = next((o for o in bpy.context.scene.objects if o.name == 'Art lower shell'))
    upper = next((o for o in bpy.context.scene.objects if o.name == 'Art lid shell'))
    devlow = bpy.data.objects['Nominal original lower device']
    devtop = bpy.data.objects['Nominal original device lid']
    tip = bpy.data.objects['Connector tip']
    housing = bpy.data.objects['Connector housing']
    sc = bpy.context.scene
    objs = [lower,upper,devlow,devtop,tip,housing]
    named_pairs = [(a.name,b.name) for a,b in [(upper,lower),(lower,devlow),(upper,devtop),(tip,lower),(tip,devlow),(housing,lower),(housing,devlow)]]
    def inspect(frame):
        counts = pair_counts({o.name:tree(o) for o in objs}, named_pairs)
        pairs = [{'pair':[a,b], 'surface_intersection_pairs':counts[a+' / '+b]} for a,b in named_pairs]
        print('frame',frame,[(p['pair'],p['surface_intersection_pairs']) for p in pairs if p['surface_intersection_pairs']],flush=True)
        return {'frame':frame,'pairs':pairs}
    checks = sample_frames(sc,[1,12,24,36,48,64,80,96,108,118,128,144],inspect)
    def frame_bounds(frame):
        return {'frame':frame,**projected_bounds(sc,sc.camera,objs,evaluated=False)}
    framing = sample_frames(sc,range(1,145),frame_bounds)
    stage_hidden = sample_frames(sc,[144],lambda _:bpy.data.objects['Stage'].hide_render)[0]
    (d / 'native-motion-check.json').write_text(json.dumps({'sha256': hashlib.sha256((d / 'motion.blend').read_bytes()).hexdigest(), 'method': 'Actual full-resolution native geometry, surface triangle BVH;12 discrete poses, not continuous-path or physical certification; all144frames camera projection', 'checks': checks, 'framing': framing, 'stage_hidden': stage_hidden}, indent=2))

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
