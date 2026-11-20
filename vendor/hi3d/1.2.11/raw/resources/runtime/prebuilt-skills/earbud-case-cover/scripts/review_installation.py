"""review installation local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, json, hashlib, sys
from pathlib import Path
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
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
    source = d / 'installation.blend'
    bpy.ops.wm.open_mainfile(filepath=str(source))
    sc = bpy.context.scene
    names = ['Art lower shell', 'Art lid shell', 'Nominal original lower device', 'Nominal original device lid']
    objs = [bpy.data.objects[n] for n in names]
    named_pairs = [(names[a], names[b]) for a,b in [(0,1),(0,2),(0,3),(1,2),(1,3)]]
    def inspect(frame):
        counts = pair_counts({o.name:tree(o) for o in objs}, named_pairs)
        pairs = [{'pair':[a,b], 'surface_intersection_pairs':counts[a+' / '+b]} for a,b in named_pairs]
        print(frame, pairs, flush=True)
        return {'frame':frame, 'pairs':pairs}
    checks = sample_frames(sc, [1,18,32,45,60,80,94,108,120], inspect)
    def frame_bounds(frame):
        return {'frame':frame,**projected_bounds(sc,sc.camera,objs,evaluated=False)}
    framing = sample_frames(sc, range(1,121), frame_bounds)
    report = {'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'source': source.name, 'method': 'Actual full-resolution native geometry triangle BVH at 9 discrete poses; camera projects object bounds in all120frames. Not continuous collision/physical fit proof.', 'checks': checks, 'framing': framing}
    (d / 'native-installation-check.json').write_text(json.dumps(report, indent=2))

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
