"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, sys, argparse, json, numpy as np, hashlib
from pathlib import Path
from types import SimpleNamespace
from functools import partial
from frame_runtime import cli_arguments, validate_paths
from support_core import mass_properties, combine_mass, support_polygon, signed_margins

def measure_support(*, input, output):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(input=input, output=output)
    validate_paths(a)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(Path(a.input).resolve()))
    rows = []
    contacts = []
    properties = []
    verts = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        m = o.data
        m.calc_loop_triangles()
        v = np.array([o.matrix_world @ v.co for v in m.vertices]) * 1000
        verts.append(v)
        if any((x in o.name for x in ['Continuous flowing', 'Eccentric frame', 'One piece detachable', 'Removable oval'])):
            density = 0.75 if 'Removable' in o.name else 1.24
            part = mass_properties(v, np.array([list(f.vertices) for f in m.loop_triangles]), density_g_cm3=density)
            properties.append(part)
            V = part['volume_mm3']; cen = np.asarray(part['center_mm'])
            rows.append({'object': o.name, 'volume_mm3': float(abs(V)), 'center_mm': cen.tolist(), 'density_assumption_g_cm3': density})
        if any((x in o.name for x in ['Continuous flowing', 'Eccentric frame', 'One piece detachable'])):
            q = v[v[:, 2] < 0.02]
            contacts.extend(q.tolist())
    hull = support_polygon(np.asarray(contacts).reshape(-1, 3)[:, :2], round_digits=5)
    com = np.asarray(combine_mass(properties)['center_mm'])
    margins = signed_margins(hull, com[:2]).tolist()
    vv = np.concatenate(verts)
    data = {'input': str(Path(a.input).name), 'sha256': hashlib.sha256(Path(a.input).read_bytes()).hexdigest(), 'method': 'Fresh GLB, raw world-space triangle integrals and physical contact vertices within0.02mm of z=0. Solid-equivalent PLA frame/easel plus wood board density assumption; this is static geometric evidence, not a push or load test.', 'min_mm': vv.min(0).tolist(), 'max_mm': vv.max(0).tolist(), 'dimensions_mm': np.ptp(vv, axis=0).tolist(), 'min_z_mm': float(vv[:, 2].min()), 'contact_count': len(contacts), 'support_polygon_xy_mm': hull.tolist(), 'assumed_center_of_mass_mm': com.tolist(), 'minimum_support_margin_mm': min(margins), 'center_inside_support_polygon': min(margins) > 0, 'parts': rows}
    Path(a.output).write_text(json.dumps(data, indent=2))
    print(json.dumps(data, indent=2))

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    options=p.parse_args(cli_arguments(argv))
    return measure_support(**vars(options))

if __name__ == "__main__":
    main()
