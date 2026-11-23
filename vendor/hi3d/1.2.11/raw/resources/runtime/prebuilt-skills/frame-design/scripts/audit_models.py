"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse, sys, json, hashlib
from glb_clips import read_glb
from pathlib import Path
import bpy, numpy as np
from mathutils import Vector
from types import SimpleNamespace
from functools import partial
from frame_runtime import cli_arguments, validate_paths

def audit(*, input, output):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(input=input, output=output)
    validate_paths(a)
    rows = []
    paths=[a.input] if a.input.is_file() and a.input.suffix=='.glb' else sorted(a.input.glob('*.glb'))
    if not paths:raise ValueError('No GLB inputs')
    for path in paths:
        data = path.read_bytes()
        doc, _ = read_glb(data)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
        s = bpy.context.scene
        obs = [o for o in s.objects if o.type == 'MESH']
        v = np.concatenate([np.array([o.matrix_world @ x.co for x in o.data.vertices]) * 1000 for o in obs])
        lo = v.min(0)
        hi = v.max(0)
        animated = bool(doc.get('animations'))
        nf = 1
        if animated:
            end = max((int(round(ac.frame_range[1])) for ac in bpy.data.actions), default=1)
            nf = end
            for f in range(1, end + 1):
                s.frame_set(f)
                bpy.context.view_layer.update()
                q = np.array([o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]) * 1000
                lo = np.minimum(lo, q.min(0))
                hi = np.maximum(hi, q.max(0))
        rows.append({'file': path.name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'MiB': len(data) / 1048576, 'animated': animated, 'animation_count': len(doc.get('animations', [])), 'meshes': len(obs), 'triangles': sum((sum((len(p.vertices) - 2 for p in o.data.polygons)) for o in obs)), 'dimensions_mm': (hi - lo).tolist(), 'min_mm': lo.tolist(), 'max_mm': hi.tolist(), 'bounds_method': 'All imported animation integer-frame transformed bounding-box corners; conservative world envelope' if animated else 'Actual freshly imported mesh world vertices', 'sampled_frames': nf})
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps({'models': rows}, indent=2))
    print('MODEL_AUDIT_COMPLETE', [(r['file'], round(r['MiB'], 2)) for r in rows])

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    options=p.parse_args(cli_arguments(argv))
    return audit(**vars(options))

if __name__ == "__main__":
    main()
