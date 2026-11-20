"""Blender BVH helper for read-only actual split-STL residual measurements."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import sys, argparse, json, struct
from pathlib import Path
import numpy as np
from mathutils.bvhtree import BVHTree
from mathutils import Vector
from stage_cli import cli_arguments, StageFinished, _finish_stage

def closest64(point, t):
    """Independently callable closest64 operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    aa, bb, cc = (t[:, 0], t[:, 1], t[:, 2])
    normal = np.cross(bb - aa, cc - aa)
    nn = np.einsum('ij,ij->i', normal, normal)
    inside = np.ones(len(t), bool)
    for u, v in [(aa, bb), (bb, cc), (cc, aa)]:
        inside &= np.einsum('ij,ij->i', np.cross(v - u, point - u), normal) >= 0
    dd = np.where(inside, np.einsum('ij,ij->i', point - aa, normal) ** 2 / np.maximum(nn, 1e-100), np.inf)
    for u, v in [(aa, bb), (bb, cc), (cc, aa)]:
        edge = v - u
        w = point - u
        q = np.clip(np.einsum('ij,ij->i', w, edge) / np.maximum(np.einsum('ij,ij->i', edge, edge), 1e-100), 0, 1)
        delta = w - q[:, None] * edge
        dd = np.minimum(dd, np.einsum('ij,ij->i', delta, delta))
    return float(np.sqrt(dd.min()))

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--samples', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--split-z-mm', type=float, required=True)
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    b = Path(a.source).read_bytes()
    r = np.frombuffer(b, dtype=np.dtype([('n', '<f4', (3,)), ('v', '<f4', (3, 3)), ('a', '<u2')]), offset=84, count=struct.unpack_from('<I', b, 80)[0])['v']
    v, index = np.unique(r.reshape(-1, 3), axis=0, return_inverse=True)
    faces = index.reshape(-1, 3)
    tree = BVHTree.FromPolygons(v.tolist(), faces.tolist(), all_triangles=True)
    result = {}
    triangles = r.astype(np.float64)
    data = np.load(a.samples)
    allowed_tri = data['__allowed_pocket_triangles']
    tri_lo = triangles.min(1)
    tri_hi = triangles.max(1)
    for label, points in data.items():
        if label.startswith('__'):
            continue
        distances = []
        raw_bvh = []
        original = []
        for point in points:
            hit = tree.find_nearest(Vector(point))
            dd = closest64(point, triangles[[hit[2]]])
            raw_bvh.append(float(hit[3]))
            original.append(dd)
            best = dd
            if label.startswith('removed_'):
                best = min(best, abs(point[2] - a.split_z_mm), closest64(point, allowed_tri))
            if best > 0.0001:
                keep = np.ones(len(triangles), bool)
                for axis in range(3):
                    keep &= (tri_lo[:, axis] <= point[axis] + best + 1e-10) & (tri_hi[:, axis] >= point[axis] - best - 1e-10)
                if keep.any():
                    best = min(best, closest64(point, triangles[keep]))
            distances.append(best)
        distance = np.array(distances)
        i = int(np.argmax(distance))
        result[label] = {'method': 'All residual vertices and face centroids. Source BVH selects a candidate, then stable float64 closest-point math uses oriented-edge tests. Any candidate distance above0.0001mm triggers a global float64 AABB shortlist containing every source triangle capable of reducing it; closest points are recomputed for every shortlisted triangle. For removed material only, the intentional split plane and all triangles of both conservative pocket envelopes are additional allowed boundaries.', 'samples': len(points), 'maximum_sampled_distance_mm': float(distance[i]), 'p99_sampled_distance_mm': float(np.percentile(distance, 99)), 'maximum_raw_float32_bvh_distance_mm': max(raw_bvh), 'allowed_new_cut_boundaries': bool(label.startswith('removed_')), 'maximum_point_mm': points[i].tolist()}
    Path(a.output).write_text(json.dumps(result, indent=2))
    print('EXACT_BVH_SAMPLE_REVIEW_COMPLETE', flush=True)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
