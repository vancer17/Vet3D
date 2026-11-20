"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, sys, argparse, json, struct, numpy as np, math, hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from types import SimpleNamespace
from functools import partial
from frame_runtime import cli_arguments, validate_paths

def measure_mount_walls(*, input, output):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(input=input, output=output)
    validate_paths(a)
    D = Path(a.input)
    candidates = [D / 'print' / name for name in ('continuous-flowing-frame-and-integral-feather-leaves.stl', 'eccentric-frame-with-measured-relief.stl')]
    found = [p for p in candidates if p.is_file()]
    if len(found) != 1:
        raise ValueError('Expected one frame export from the selected recipe')
    S = found[0]
    b = S.read_bytes()
    t = np.frombuffer(b, dtype=np.dtype([('n', '<f4', (3,)), ('v', '<f4', (3, 3)), ('a', '<u2')]), offset=84, count=struct.unpack_from('<I', b, 80)[0])['v'].astype(float)
    v, inv = np.unique(t.reshape(-1, 3), axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)
    tree = BVHTree.FromPolygons(v.tolist(), f.tolist(), all_triangles=True)
    M = json.loads((D / 'measurements.json').read_text())
    rows = []
    for xy in M['easel_mounts_mm']:
        vals = []
        for deg in range(0, 360, 3):
            d = Vector((math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0))
            h = tree.ray_cast(Vector((*xy, 2)), d, 400)
            if h[0] is None:
                raise ValueError('Open radial bore breakout')
            h2 = tree.ray_cast(h[0] + d * 0.0001, d, 400)
            if h2[0] is None:
                raise ValueError('Missing outer wall hit')
            vals.append({'direction_deg': deg, 'bore_radius_mm': h[3], 'wall_mm': h2[3] + 0.0001})
        rows.append({'pivot_mm': xy, 'sample_z_mm': 2, 'minimum_radial_wall_mm': min((q['wall_mm'] for q in vals)), 'samples': vals})
    result = {'stl_sha256': hashlib.sha256(b).hexdigest(), 'method': 'Independent binary STL XY ray sections through the two actual rear mounting bores; first inner/second outer intersections every3degrees at z2mm. Not a load test.', 'mounts': rows}
    Path(a.output).write_text(json.dumps(result, indent=2))
    print([(r['pivot_mm'], r['minimum_radial_wall_mm']) for r in rows])

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    options=p.parse_args(cli_arguments(argv))
    return measure_mount_walls(**vars(options))

if __name__ == "__main__":
    main()
