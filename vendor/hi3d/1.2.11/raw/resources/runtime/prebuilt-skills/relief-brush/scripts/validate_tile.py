"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys, argparse
from pathlib import Path
import bpy
import json
import numpy as np
from planar_core import height_mesh, material
from planar_preview import camera, clean, export_glb, stage
from planar_print import export_stl_legacy as export_stl
from types import SimpleNamespace
from functools import partial
from brush_runtime import cli_arguments, validate_paths
from brush_preview import render as _render_base

def validate_tile(*, heightfields, region, output):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(heightfields=heightfields, region=region, output=output)
    validate_paths(a)
    render=partial(_render_base, enabled=not getattr(a, "no_render", False))
    a.output.mkdir(parents=True, exist_ok=True)
    data = np.load(a.heightfields)
    tile = data[a.region]
    meta = json.load(open(a.heightfields.parent / 'metadata.json'))
    spec = meta['region_specs'][a.region]
    if spec.get('mode') != 'tile':raise ValueError('Select a tile region for repeat validation')
    u0, v0, u1, v1 = spec['crop']
    raw = data['raw']
    crop = raw[round(v0 * len(raw)):round(v1 * len(raw)), round(u0 * raw.shape[1]):round(u1 * raw.shape[1])].copy()
    crop = np.maximum(crop - np.percentile(crop, 7), 0)
    crop /= crop.max()
    b = np.concatenate([crop, crop[:, ::-1]], 1)
    old = np.concatenate([b, b[::-1]], 0)
    def check(x):
        return {'height_edge_max': float(max(abs(x[:, 0] - x[:, -1]).max(), abs(x[0] - x[-1]).max())), 'first_difference_edge_max': float(max(abs(x[:, 1] - x[:, 0] - (x[:, -1] - x[:, -2])).max(), abs(x[1] - x[0] - (x[-1] - x[-2])).max()))}
    clean()
    m = material('Matte geological ceramic', (0.39, 0.24, 0.11), 0.15, 0.52)
    cam = stage((0, 0, 0), 140)
    camera(cam, (0, 0, 0), (45, -80, 130), 145)
    for name, field in [('before', old), ('after', tile)]:
        o = height_mesh(name + ' 2x2 mirror repeat', np.tile(field, (2, 2)), 114, 114, 1.4, 2.4, m, nx=480, ny=480)
        render(a.output / ('tile-' + name + '.png'), 1100, 1000, 24)
        if name == 'after':
            export_glb(a.output / 'tile-2x2.glb', [o])
            export_stl(a.output / 'tile-2x2-mm.stl', [o])
        bpy.data.objects.remove(o, do_unlink=True)
    json.dump({'region': a.region, 'legacy': check(old), 'current': check(tile), 'method': 'Legacy same-source direct mirrored crop compared with two-sample flattened-edge mirror. Actual 2x2 closed geometry rendered.', 'visible_design': 'Four-way mirrored X junctions are intentional and visible; not random natural texture.', 'topology': '2x2 height field is one connected mesh, not four overlapping plaques.'}, open(a.output / 'tile-validation.json', 'w'), indent=2)

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--heightfields', type=Path, required=True)
    p.add_argument('--region', required=True)
    p.add_argument('--output', type=Path, required=True)
    options=p.parse_args(cli_arguments(argv))
    return validate_tile(**vars(options))

if __name__ == "__main__":
    main()
