#!/usr/bin/env python3
"""Audit normalized millimetre polygon geometry. Does not parse fabrication formats."""
import argparse
import json
import math
import sys
from pathlib import Path

try:
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union
    from shapely.validation import explain_validity
except ImportError:
    raise SystemExit('Requires Python 3 and shapely. Use an available environment or install shapely into a task-local environment.')


def audit(data):
    errors, warnings, summaries = [], [], []
    shapes = {}

    def problem(code, where, detail, warning=False):
        (warnings if warning else errors).append({'code': code, 'where': where, 'detail': detail})

    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    def coordinates(value, where, closed):
        if not isinstance(value, list) or len(value) < (4 if closed else 2):
            problem('points', where, 'Insufficient coordinate pairs.'); return None
        if any(not isinstance(p, list) or len(p) != 2 or not all(number(v) for v in p) for p in value):
            problem('coordinates', where, 'Coordinates must be finite numeric [x,y] pairs.'); return None
        if closed and value[0] != value[-1]:
            problem('open_contour', where, 'Ring must explicitly repeat its first point.'); return None
        if any(a == b for a, b in zip(value, value[1:])):
            problem('zero_length_edge', where, 'Consecutive vertices are identical.'); return None
        return value

    def polygon(item, where):
        if not isinstance(item, dict):
            problem('polygon', where, 'Expected outer/holes object.'); return None
        outer = coordinates(item.get('outer'), where + '.outer', True)
        holes = item.get('holes', [])
        if not isinstance(holes, list):
            problem('holes', where, 'holes must be a list.'); return None
        rings = [coordinates(r, where + f'.holes[{i}]', True) for i, r in enumerate(holes)]
        if outer is None or any(r is None for r in rings): return None
        p = Polygon(outer, rings)
        if not p.is_valid or p.is_empty or p.area <= 0:
            problem('invalid_polygon', where, explain_validity(p)); return None
        return p

    def parameter(obj, key, default, where):
        v = obj.get(key, default)
        if not number(v) or v < 0:
            problem('parameter', where + '.' + key, 'Expected a finite nonnegative number.'); return default
        return v

    if not isinstance(data, dict):
        return {'status': 'FAIL', 'errors': [{'code':'schema','where':'root','detail':'Expected JSON object.'}], 'warnings':[], 'parts':[]}
    if data.get('units') != 'mm': problem('units', 'root', 'units must explicitly be mm.')
    sheet = data.get('sheet_mm')
    if not isinstance(sheet, list) or len(sheet) != 2 or not all(number(v) and v > 0 for v in sheet):
        problem('sheet', 'root', 'sheet_mm must be [positive width, positive height].'); sheet = None
    gap = parameter(data, 'min_part_gap_mm', 0, 'root')
    parts = data.get('parts')
    if not isinstance(parts, list) or not parts:
        problem('parts', 'root', 'A nonempty parts list is required.'); parts = []
    for i, item in enumerate(parts):
        where = f'parts[{i}]'
        if not isinstance(item, dict):
            problem('part', where, 'Expected part object.'); continue
        pid = item.get('id')
        if not isinstance(pid, str) or not pid or pid in shapes:
            problem('part_id', where, 'Part id must be nonempty and unique.'); continue
        raw = item.get('polygons')
        if not isinstance(raw, list) or not raw:
            problem('polygons', pid, 'A nonempty polygons list is required.'); continue
        polys = [polygon(p, f'{pid}.polygons[{j}]') for j, p in enumerate(raw)]
        if any(p is None for p in polys): continue
        g = unary_union(polys)
        # Both overlapping faces and shared cut edges need resolution before export.
        raw_length = sum(p.boundary.length for p in polys)
        merged_length = unary_union([p.boundary for p in polys]).length
        if raw_length - merged_length > 1e-6:
            problem('duplicate_cut_edge', pid, 'Polygon contours share duplicate cut segments.')
        if sum(p.area for p in polys) - g.area > 1e-6:
            problem('overlapping_faces', pid, 'Material faces overlap; union them before exporting contours.')
        expected = item.get('expected_components', 1)
        count = len(g.geoms) if g.geom_type == 'MultiPolygon' else 1
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 1:
            problem('expected_components', pid, 'Expected a positive integer.')
        elif count != expected:
            problem('component_count', pid, f'Expected {expected}, found {count}.')
        if not g.is_valid:
            problem('invalid_union', pid, explain_validity(g))
        if sheet and (g.bounds[0] < 0 or g.bounds[1] < 0 or g.bounds[2] > sheet[0] or g.bounds[3] > sheet[1]):
            problem('outside_sheet', pid, f'Bounds {list(g.bounds)} exceed sheet {sheet}.')
        inset = parameter(item, 'screen_inset_mm', 0, pid)
        inset_count = None
        if inset:
            eroded = g.buffer(-inset)
            inset_count = 0 if eroded.is_empty else len(eroded.geoms) if eroded.geom_type == 'MultiPolygon' else 1
            if inset_count != count:
                problem('inset_connectivity', pid, f'Inward offset {inset} mm changes component count {count} to {inset_count}; review narrow connections.', True)
        hole_limit = parameter(item, 'review_holes_below_mm2', 0, pid)
        for j, p in enumerate(polys):
            for k, hole in enumerate(p.interiors):
                area = Polygon(hole).area
                if 0 < area < hole_limit:
                    problem('small_hole', f'{pid}.polygons[{j}].holes[{k}]', f'Area {area:.6f} mm2 below review threshold; inspect function before editing.', True)
        shapes[pid] = g
        summaries.append({'id': pid, 'components': count, 'area_mm2': g.area, 'cut_length_mm': raw_length, 'bounds_mm': list(g.bounds), 'inset_components': inset_count})
    ids = list(shapes)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            x, y = shapes[a], shapes[b]
            if x.intersects(y): problem('part_overlap_or_touch', a + '/' + b, 'Fabrication parts overlap or touch.')
            elif x.distance(y) < gap:
                problem('part_gap', a + '/' + b, f'Gap {x.distance(y):.6f} mm below requested {gap} mm.')
    for op in ['score', 'engrave']:
        marks = data.get(op, [])
        if not isinstance(marks, list):
            problem('marks', op, 'Expected a list.'); continue
        for i, mark in enumerate(marks):
            where = f'{op}[{i}]'
            if not isinstance(mark, dict) or mark.get('part_id') not in shapes:
                problem('mark_part', where, 'A valid part_id is required.'); continue
            if op == 'score':
                points = coordinates(mark.get('points'), where, False)
                g = LineString(points) if points is not None else None
            else:
                g = polygon(mark, where)
            if g is None: continue
            material = shapes[mark['part_id']]
            if not material.covers(g):
                problem('mark_outside_material', where, 'Mark extends outside retained material or into a hole.')
            clearance = parameter(mark, 'edge_clearance_mm', 0, where)
            if clearance and material.boundary.distance(g) < clearance:
                problem('mark_edge_clearance', where, f'Mark is less than {clearance} mm from a cut edge.', True)
    return {'status': 'FAIL' if errors else 'REVIEW' if warnings else 'PASS_GEOMETRY_ONLY', 'errors': errors, 'warnings': warnings, 'parts': summaries, 'limitations': ['Normalized geometry only; no SVG/AI/XCS parsing.', 'No target-software or physical-material validation.', 'Inset screening is not a wall-thickness or strength proof.']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    ap.add_argument('--report', type=Path)
    args = ap.parse_args()
    if args.report and args.report.resolve() == args.input.resolve():
        ap.error('Report must not overwrite input.')
    try:
        result = audit(json.loads(args.input.read_text(encoding='utf-8')))
    except (OSError, json.JSONDecodeError) as e:
        ap.error(str(e))
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded, encoding='utf-8')
    print(encoded, end='')
    return 1 if result['errors'] else 2 if result['warnings'] else 0

if __name__ == '__main__':
    sys.exit(main())
