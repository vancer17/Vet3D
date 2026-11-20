"""Read-only Blender check of final printed segments against the actual Hi3D body mesh."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys, argparse, json, hashlib, struct, gc
from pathlib import Path
import numpy as np
from mathutils.bvhtree import BVHTree
from stage_cli import cli_arguments, StageFinished, _finish_stage

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--scene', required=True, type=Path)
    p.add_argument('--body-object', default='Hi3D anatomical body')
    p.add_argument('--parts', nargs='+', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    bpy.ops.wm.open_mainfile(filepath=str(a.scene.resolve()))
    o = bpy.data.objects.get(a.body_object)
    if o is None:
        raise ValueError('Body object missing; candidates: ' + str([x.name for x in bpy.data.objects if x.type == 'MESH']))
    o.data.calc_loop_triangles()
    v = np.array([o.matrix_world @ x.co for x in o.data.vertices]) * 1000
    f = np.array([tuple(x.vertices) for x in o.data.loop_triangles])
    body = BVHTree.FromPolygons(v.tolist(), f.tolist(), all_triangles=True, epsilon=0)
    rows = []
    for path in a.parts:
        b = path.read_bytes()
        tri = np.frombuffer(b, dtype=np.dtype([('n', '<f4', (3,)), ('v', '<f4', (3, 3)), ('a', '<u2')]), offset=84, count=struct.unpack_from('<I', b, 80)[0])['v']
        vv, ix = np.unique(tri.reshape(-1, 3), axis=0, return_inverse=True)
        ff = ix.reshape(-1, 3)
        tree = BVHTree.FromPolygons(vv.tolist(), ff.tolist(), all_triangles=True, epsilon=0)
        pairs = tree.overlap(body)
        rows.append({'file': path.name, 'sha256': hashlib.sha256(b).hexdigest(), 'triangles': len(ff), 'body_triangle_crossing_pairs': len(pairs), 'crossing_part_centroids_mm': [tri[i].mean(0).tolist() for i, j in pairs[:20]]})
        del tree
        gc.collect()
        print('BODY_CROSSINGS', path.name, len(pairs), flush=True)
    j = {'method': 'Actual final binary STL triangles in mm against world-space native Hi3D anatomical body triangles (Blender metres converted to mm). New Blender process, BVH triangle-surface overlap epsilon0. No geometry changes.', 'source_scene_sha256': hashlib.sha256(a.scene.read_bytes()).hexdigest(), 'body_object': o.name, 'body_triangles': len(f), 'body_bounds_mm': [v.min(0).tolist(), v.max(0).tolist()], 'parts': rows, 'passed': all((x['body_triangle_crossing_pairs'] == 0 for x in rows)), 'limit': 'Static digital body only; this does not test skin pressure, tissue deformation or a real wearer.'}
    a.output.write_text(json.dumps(j, indent=2))

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
