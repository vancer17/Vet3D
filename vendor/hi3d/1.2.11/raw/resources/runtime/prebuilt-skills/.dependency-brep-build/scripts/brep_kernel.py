"""Build validated brep-build.v1 solids with CadQuery/OCP and write STEP/STL."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from brep_spec import load_spec, spec_digest


def require_cadquery():
    try:
        import cadquery as cq
    except ImportError as exc:
        raise RuntimeError('cadquery is not installed; --check still works, build cannot write STEP') from exc
    return cq


def _placed(cq, work, origin):
    x, y, z = origin
    if x == y == z == 0:
        return work
    return work.translate((x, y, z))


def _solid_of(work):
    value = work.val() if hasattr(work, 'val') else work
    return value


def _workplane(cq, shape):
    if isinstance(shape, cq.Workplane):
        return shape
    return cq.Workplane('XY').newObject([shape])


def _thread_profile(pitch, height, internal):
    half = pitch * 0.25
    h = (5.0 / 8.0) * pitch * math.sqrt(3.0) / 2.0
    if internal:
        h = -h
    return [(-half, 0.0), (0.0, h), (half, 0.0)]


def _helical_thread(cq, major, pitch, length, internal, origin, chamfer):
    core_r = major / 2.0 - (5.0 / 8.0) * pitch * math.sqrt(3.0) / 2.0
    if core_r <= pitch * 0.2:
        raise ValueError('thread minor radius is too small for the pitch')
    if internal:
        outer = cq.Workplane('XY').circle(major / 2.0 + pitch).extrude(length)
        bore = cq.Workplane('XY').circle(major / 2.0).extrude(length)
        blank = outer.cut(bore)
        radius = major / 2.0
    else:
        blank = cq.Workplane('XY').circle(max(core_r, 0.2)).extrude(length)
        radius = (major / 2.0 + core_r) / 2.0
    helix = cq.Wire.makeHelix(pitch, length, radius)
    tooth = (
        cq.Workplane('XY')
        .polyline(_thread_profile(pitch, length, internal))
        .close()
        .sweep(helix, isFrenet=True)
    )
    if internal:
        solid = blank.cut(tooth)
    else:
        solid = blank.union(tooth)
    if chamfer:
        size = min(pitch * 0.3, length * 0.15)
        solid = _workplane(cq, _solid_of(solid)).faces('<Z or >Z').chamfer(size)
    return _placed(cq, _workplane(cq, _solid_of(solid)), origin)


def _build_solid(cq, item, built, spec_dir):
    kind = item['kind']
    origin = item['origin']
    if kind == 'box':
        work = cq.Workplane('XY').box(item['length_mm'], item['width_mm'], item['height_mm'])
        return _placed(cq, work, origin)
    if kind == 'cylinder':
        work = cq.Workplane('XY').circle(item['diameter_mm'] / 2.0).extrude(item['height_mm'])
        return _placed(cq, work, origin)
    if kind == 'cone':
        work = cq.Workplane('XY').circle(item['diameter_bottom_mm'] / 2.0)
        work = work.workplane(offset=item['height_mm']).circle(max(item['diameter_top_mm'] / 2.0, 1e-6)).loft()
        return _placed(cq, work, origin)
    if kind == 'shell':
        source = built.get(item['source'])
        if source is None:
            raise ValueError(f'shell source {item["source"]} has not been built')
        return _workplane(cq, _solid_of(source)).shell(-item['thickness_mm'])
    if kind == 'iso_metric_thread':
        return _helical_thread(
            cq, item['major_mm'], item['pitch_mm'], item['length_mm'],
            item['role'] == 'internal', origin, item['ends'] == 'chamfer',
        )
    if kind == 'iso_clearance_hole':
        work = cq.Workplane('XY').circle(item['diameter_mm'] / 2.0).extrude(item['depth_mm'])
        return _placed(cq, work, origin)
    if kind == 'iso_tapped_hole':
        return _helical_thread(cq, item['major_mm'], item['pitch_mm'], item['length_mm'], True, origin, False)
    imported = cq.importers.importStep(item['path'])
    return _placed(cq, _workplane(cq, _solid_of(imported)), origin)


def _apply_op(cq, op, built):
    kind = op['op']
    if kind in ('union', 'cut', 'intersect'):
        left = _workplane(cq, _solid_of(built[op['a']]))
        right = _workplane(cq, _solid_of(built[op['b']]))
        if kind == 'union':
            result = left.union(right)
        elif kind == 'cut':
            result = left.cut(right)
        else:
            result = left.intersect(right)
        if _solid_of(result) is None:
            raise ValueError(f'{kind} produced an empty solid')
        built[op['out']] = result
        return
    target = _workplane(cq, _solid_of(built[op['solid']]))
    selector = op['edges']
    edged = target.edges() if selector == '*' else target.edges(selector)
    if kind == 'fillet':
        result = edged.fillet(op['radius_mm'])
    else:
        result = edged.chamfer(op['radius_mm'])
    built[op['solid']] = result


def _metrics(solid):
    bbox = solid.BoundingBox()
    volume = float(solid.Volume())
    if volume <= 0:
        raise ValueError('exported solid has no positive volume')
    return {
        'volume_mm3': volume,
        'bbox_mm': {
            'xmin': bbox.xmin, 'ymin': bbox.ymin, 'zmin': bbox.zmin,
            'xmax': bbox.xmax, 'ymax': bbox.ymax, 'zmax': bbox.zmax,
        },
    }


def build_spec(spec, output):
    cq = require_cadquery()
    output = Path(output)
    parts = output / 'parts'
    parts.mkdir(parents=True, exist_ok=True)
    built = {}
    for item in spec['solids']:
        built[item['id']] = _build_solid(cq, item, built, output)
    for op in spec['ops']:
        _apply_op(cq, op, built)
    records = []
    for ident in spec['export']:
        shape = _solid_of(built[ident])
        if shape is None:
            raise ValueError(f'export {ident} is empty')
        step_path = parts / f'{ident}.step'
        stl_path = parts / f'{ident}.stl'
        cq.exporters.export(shape, str(step_path))
        cq.exporters.export(shape, str(stl_path), tolerance=spec['tessellation_mm'])
        if step_path.stat().st_size < 80:
            raise ValueError(f'{step_path.name} is too small to be a STEP solid')
        metrics = _metrics(shape)
        records.append({
            'id': ident,
            'step': f'parts/{ident}.step',
            'stl': f'parts/{ident}.stl',
            **metrics,
        })
    try:
        cq_version = cq.__version__
    except AttributeError:
        cq_version = 'unknown'
    manifest = {
        'schema': 'brep-build.manifest.v1',
        'units': 'mm',
        'tessellation_mm': spec['tessellation_mm'],
        'spec_sha256': spec_digest(spec),
        'cadquery': cq_version,
        'parts': records,
        'kind': 'cadquery_recipe',
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description='CadQuery kernel for brep-build; not a sandbox.')
    parser.add_argument('--spec', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    spec = load_spec(args.spec)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = build_spec(spec, output)
    json.dump(manifest, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1)
