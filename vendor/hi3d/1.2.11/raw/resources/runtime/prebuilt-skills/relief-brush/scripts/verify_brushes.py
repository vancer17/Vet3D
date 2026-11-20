"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, json, sys, numpy as np
from pathlib import Path
import argparse
from types import SimpleNamespace
from functools import partial
from brush_runtime import cli_arguments, validate_paths

def verify(*, library, output, expected_count=None):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    args=SimpleNamespace(library=library, output=output, expected_count=expected_count)
    validate_paths(args)
    if args.expected_count is not None and args.expected_count < 1:
        raise ValueError('--expected-count must be positive')
    OUT = args.output
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(args.library), link=False) as (src, dst):
        dst.brushes = [x for x in src.brushes if 'measured relief' in x.lower()]
    results = []
    for i, brush in enumerate(bpy.data.brushes):
        if 'measured relief' not in brush.name.lower():
            continue
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=192, y_subdivisions=96, size=0.1)
        o = bpy.context.object
        o.name = 'Fresh session applied ' + brush.name
        uv = o.data.uv_layers.active
        for p in o.data.polygons:
            for li in p.loop_indices:
                co = o.data.vertices[o.data.loops[li].vertex_index].co
                uv.data[li].uv = (co.x / 0.1 + 0.5, co.y / 0.1 + 0.5)
        before = np.array([v.co[:] for v in o.data.vertices])
        m = o.modifiers.new('Native image texture displacement', 'DISPLACE')
        m.texture = brush.texture
        m.texture_coords = 'UV'
        m.strength = 0.002
        m.mid_level = 0
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=m.name)
        after = np.array([v.co[:] for v in o.data.vertices])
        delta = after - before
        results.append({'brush': brush.name, 'texture': brush.texture.name, 'image_packed': bool(brush.texture.image.packed_file), 'colorspace': brush.texture.image.colorspace_settings.name, 'mapping_enum': brush.texture_slot.map_mode, 'vertex_count': len(after), 'max_displacement_mm': float(np.linalg.norm(delta, axis=1).max() * 1000), 'nonzero_vertices': int(np.count_nonzero(np.linalg.norm(delta, axis=1) > 1e-07)), 'success': bool(np.linalg.norm(delta, axis=1).max() > 0.0001)})
        o.location.x = i * 0.12
    failures = []
    if not results:
        failures.append('No matching measured-relief Brush assets were loaded')
    if args.expected_count is not None and len(results) != args.expected_count:
        failures.append('Expected %d Brush assets; loaded %d' % (args.expected_count, len(results)))
    if any((not row['success'] for row in results)):
        failures.append('At least one Brush failed to produce the required actual vertex displacement')
    report = {'target': bpy.app.version_string, 'operation': 'Append native Brush assets, reuse their packed image Texture, apply DISPLACE to fresh UV grid, measure actual changed vertices', 'expected_count': args.expected_count, 'passed': not failures, 'failures': failures, 'results': results}
    json.dump(report, open(OUT / 'brush-import-test.json', 'w'), indent=2)
    print(json.dumps(report, indent=2))
    if failures:
        raise RuntimeError('Brush verification failed: ' + '; '.join(failures))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'brush-fresh-session.blend'))

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--expected-count', type=int, help='Optional positive count of measured-relief Brush assets; region names remain unrestricted.')
    options=p.parse_args(cli_arguments(argv))
    return verify(**vars(options))

if __name__ == "__main__":
    main()
