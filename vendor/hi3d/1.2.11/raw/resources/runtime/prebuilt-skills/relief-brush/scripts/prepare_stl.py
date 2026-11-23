"""Explicit-unit STL preprocessing for the GLB/glTF-only height extractor."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse, hashlib, json, math
from types import SimpleNamespace
import bpy
import numpy as np
from brush_runtime import cli_arguments, validate_paths


def scene_bounds_m():
    """Return actual world mesh bounds, in Blender metres; no scene/file writes."""
    points = [tuple(o.matrix_world @ v.co) for o in bpy.context.scene.objects
              if o.type == 'MESH' for v in o.data.vertices]
    if not points:
        raise ValueError('Imported asset has no mesh vertices')
    vertices = np.asarray(points, dtype=float)
    if not np.isfinite(vertices).all():
        raise ValueError('Imported coordinates are not finite')
    return np.stack([vertices.min(0), vertices.max(0)])


def convert_stl(*, source, output, meters_per_unit, unit_basis, tolerance_m=1e-6):
    """Replace scene, convert explicit-scale STL to GLB, fresh-import and compare.

    Original STL is read only. Writes output GLB and .conversion.json sidecar.
    Unit basis must label known versus assumed scale; no unit guessing occurs.
    Returned bounds match checks file conversion, not the unknown real object.
    """
    a = SimpleNamespace(source=source, output=output)
    validate_paths(a)
    scale = float(meters_per_unit)
    if a.source.suffix.lower() != '.stl' or a.output.suffix.lower() != '.glb':
        raise ValueError('Preprocessing expects a source .stl and output .glb')
    if not math.isfinite(scale) or scale <= 0 or not math.isfinite(tolerance_m) or tolerance_m <= 0:
        raise ValueError('Positive finite metres-per-unit and tolerance required')
    if unit_basis not in ('known', 'assumed'):
        raise ValueError('unit_basis must be known or assumed')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.ops.wm.stl_import(filepath=str(a.source), global_scale=scale)
    before = scene_bounds_m()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(a.output), export_format='GLB', export_animations=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(a.output))
    after = scene_bounds_m()
    error = float(np.max(np.abs(after - before)))
    report = {'source_file': a.source.name, 'source_sha256': hashlib.sha256(a.source.read_bytes()).hexdigest(),
              'meters_per_stl_unit': scale, 'unit_basis': unit_basis,
              'imported_stl_bounds_mm': (before * 1000).tolist(),
              'fresh_glb_bounds_mm': (after * 1000).tolist(),
              'max_bounds_error_m': error, 'tolerance_m': tolerance_m,
              'conversion_bounds_passed': error <= tolerance_m,
              'scope': 'Numeric conversion only; assumed units do not establish real-world fit'}
    a.output.with_suffix('.conversion.json').write_text(json.dumps(report, indent=2))
    if error > tolerance_m:
        raise ValueError('Fresh GLB bounds exceed conversion tolerance; inspect report before extraction')
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--meters-per-unit', required=True, type=float)
    p.add_argument('--unit-basis', required=True, choices=['known', 'assumed'])
    p.add_argument('--tolerance-m', type=float, default=1e-6)
    print(json.dumps(convert_stl(**vars(p.parse_args(cli_arguments(argv)))), indent=2))


if __name__ == '__main__':
    main()
