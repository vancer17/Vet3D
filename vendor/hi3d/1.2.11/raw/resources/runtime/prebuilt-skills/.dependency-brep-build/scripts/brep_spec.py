"""Validate brep-build.v1 recipes and estimate a local wall-clock budget."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCHEMA = 'brep-build.v1'
SOLID_KINDS = {
    'box', 'cylinder', 'cone', 'shell',
    'iso_metric_thread', 'iso_clearance_hole', 'iso_tapped_hole', 'import_step',
}
OP_KINDS = {'union', 'cut', 'intersect', 'fillet', 'chamfer'}
FORBIDDEN = {'mesh', 'glb', 'stl', 'fit', 'sew', 'screenshot', 'from_mesh'}
NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,63}$')
DESIGNATION_RE = re.compile(r'^M(\d+(?:\.\d+)?)(?:x(\d+(?:\.\d+)?))?$')
COARSE_PITCH = {
    1.6: 0.35, 2: 0.4, 2.5: 0.45, 3: 0.5, 3.5: 0.6, 4: 0.7, 5: 0.8, 6: 1.0,
    8: 1.25, 10: 1.5, 12: 1.75, 14: 2.0, 16: 2.0, 18: 2.5, 20: 2.5, 22: 2.5,
    24: 3.0, 27: 3.0, 30: 3.5,
}
CLEARANCE_MEDIUM = {
    1.6: 1.8, 2: 2.4, 2.5: 2.9, 3: 3.4, 4: 4.5, 5: 5.5, 6: 6.6, 8: 9.0,
    10: 11.0, 12: 13.5, 14: 15.5, 16: 17.5, 18: 20.0, 20: 22.0, 24: 26.0, 30: 33.0,
}
MAX_SOLIDS = 16
MAX_OPS = 20
MAX_THREAD_MM = 80
MAX_WALL_S = 300


def _finite(value, name, *, lo=None, hi=None, lo_inclusive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a finite number')
    value = float(value)
    if value != value or value in (float('inf'), float('-inf')):
        raise ValueError(f'{name} must be a finite number')
    if lo is not None and (value < lo if lo_inclusive else value <= lo):
        raise ValueError(f'{name} must be {"≥" if lo_inclusive else ">"} {lo}')
    if hi is not None and value > hi:
        raise ValueError(f'{name} must be <= {hi}')
    return value


def _table_get(table, major, what):
    key = int(major) if major == int(major) else major
    if key not in table:
        raise ValueError(f'no {what} for M{major:g}')
    return table[key]


def _name(value, name):
    if type(value) is not str or not NAME_RE.fullmatch(value):
        raise ValueError(f'{name} must match {NAME_RE.pattern}')
    return value


def _origin(value, name):
    if value is None:
        return [0.0, 0.0, 0.0]
    if type(value) is not list or len(value) != 3:
        raise ValueError(f'{name} must be [x, y, z] millimetres')
    return [_finite(v, name) for v in value]


def parse_designation(text):
    if type(text) is not str:
        raise ValueError('designation must be a string like M12 or M12x1.5')
    match = DESIGNATION_RE.fullmatch(text.strip())
    if not match:
        raise ValueError('designation must be M<d> or M<d>x<pitch>')
    major = float(match.group(1))
    if match.group(2) is not None:
        pitch = float(match.group(2))
    else:
        pitch = _table_get(COARSE_PITCH, major, 'coarse pitch')
    if pitch <= 0 or major <= pitch:
        raise ValueError('thread pitch must be positive and smaller than major diameter')
    return major, pitch


def clearance_diameter_mm(major):
    return _table_get(CLEARANCE_MEDIUM, major, 'medium clearance hole')


def _solid(item, ids, spec_dir):
    if type(item) is not dict:
        raise ValueError('each solid must be an object')
    ident = _name(item.get('id'), 'solid.id')
    if ident in ids:
        raise ValueError(f'duplicate solid id {ident}')
    kind = item.get('kind')
    if kind not in SOLID_KINDS:
        raise ValueError(f'unknown solid kind {kind!r}')
    allowed = {'id', 'kind', 'origin'}
    if kind == 'box':
        allowed |= {'length_mm', 'width_mm', 'height_mm'}
    elif kind == 'cylinder':
        allowed |= {'diameter_mm', 'height_mm'}
    elif kind == 'cone':
        allowed |= {'diameter_bottom_mm', 'diameter_top_mm', 'height_mm'}
    elif kind == 'shell':
        allowed |= {'source', 'thickness_mm'}
    elif kind == 'iso_metric_thread':
        allowed |= {'role', 'designation', 'length_mm', 'ends'}
    elif kind in ('iso_clearance_hole', 'iso_tapped_hole'):
        allowed |= {'designation', 'depth_mm'}
    else:
        allowed |= {'path'}
    extra = set(item) - allowed
    if extra:
        raise ValueError(f'unexpected solid fields {sorted(extra)}')
    origin = _origin(item.get('origin'), 'origin')
    record = {'id': ident, 'kind': kind, 'origin': origin}
    if kind == 'box':
        record['length_mm'] = _finite(item.get('length_mm'), 'length_mm', lo=0)
        record['width_mm'] = _finite(item.get('width_mm'), 'width_mm', lo=0)
        record['height_mm'] = _finite(item.get('height_mm'), 'height_mm', lo=0)
    elif kind == 'cylinder':
        record['diameter_mm'] = _finite(item.get('diameter_mm'), 'diameter_mm', lo=0)
        record['height_mm'] = _finite(item.get('height_mm'), 'height_mm', lo=0)
    elif kind == 'cone':
        record['diameter_bottom_mm'] = _finite(item.get('diameter_bottom_mm'), 'diameter_bottom_mm', lo=0)
        record['diameter_top_mm'] = _finite(item.get('diameter_top_mm'), 'diameter_top_mm', lo=0, lo_inclusive=True)
        record['height_mm'] = _finite(item.get('height_mm'), 'height_mm', lo=0)
    elif kind == 'shell':
        record['source'] = _name(item.get('source'), 'shell.source')
        record['thickness_mm'] = _finite(item.get('thickness_mm'), 'thickness_mm', lo=0)
    elif kind == 'iso_metric_thread':
        role = item.get('role')
        if role not in ('external', 'internal'):
            raise ValueError('iso_metric_thread.role must be external or internal')
        major, pitch = parse_designation(item.get('designation'))
        length = _finite(item.get('length_mm'), 'length_mm', lo=0)
        if length > MAX_THREAD_MM:
            raise ValueError(f'thread length_mm must be <= {MAX_THREAD_MM}')
        ends = item.get('ends', 'none')
        if ends not in ('none', 'chamfer'):
            raise ValueError('ends must be none or chamfer')
        record.update(role=role, designation=f'M{major:g}x{pitch:g}', major_mm=major, pitch_mm=pitch, length_mm=length, ends=ends)
    elif kind in ('iso_clearance_hole', 'iso_tapped_hole'):
        major, pitch = parse_designation(item.get('designation'))
        record['designation'] = f'M{major:g}x{pitch:g}'
        record['major_mm'] = major
        record['pitch_mm'] = pitch
        record['depth_mm'] = _finite(item.get('depth_mm'), 'depth_mm', lo=0)
        if kind == 'iso_clearance_hole':
            record['diameter_mm'] = clearance_diameter_mm(major)
        else:
            record['role'] = 'internal'
            record['length_mm'] = record['depth_mm']
            if record['length_mm'] > MAX_THREAD_MM:
                raise ValueError(f'tapped depth_mm must be <= {MAX_THREAD_MM}')
    else:
        path = item.get('path')
        if type(path) is not str or not path:
            raise ValueError('import_step.path must be a nonempty string')
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = spec_dir / resolved
        if resolved.suffix.lower() != '.step' and resolved.suffix.lower() != '.stp':
            raise ValueError('import_step.path must be a .step/.stp file')
        if not resolved.is_file():
            raise ValueError(f'missing STEP {resolved}')
        record['path'] = str(resolved)
    return record


def _op(item, solid_ids):
    if type(item) is not dict:
        raise ValueError('each op must be an object')
    kind = item.get('op')
    if kind not in OP_KINDS:
        raise ValueError(f'unknown op {kind!r}')
    if kind in ('union', 'cut', 'intersect'):
        a = _name(item.get('a'), 'op.a')
        b = _name(item.get('b'), 'op.b')
        out = _name(item.get('out'), 'op.out')
        if a not in solid_ids or b not in solid_ids:
            raise ValueError('boolean operands must name existing solids')
        solid_ids.add(out)
        extra = set(item) - {'op', 'a', 'b', 'out'}
        if extra:
            raise ValueError(f'unexpected op fields {sorted(extra)}')
        return {'op': kind, 'a': a, 'b': b, 'out': out}
    solid = _name(item.get('solid'), 'op.solid')
    if solid not in solid_ids:
        raise ValueError('fillet/chamfer solid must already exist')
    radius = _finite(item.get('radius_mm'), 'radius_mm', lo=0)
    edges = item.get('edges')
    if type(edges) is not str or not edges:
        raise ValueError('fillet/chamfer requires a nonempty edges selector; * means all edges')
    extra = set(item) - {'op', 'solid', 'radius_mm', 'edges'}
    if extra:
        raise ValueError(f'unexpected op fields {sorted(extra)}')
    return {'op': kind, 'solid': solid, 'radius_mm': radius, 'edges': edges}


def validate_spec(raw, *, spec_dir='.'):
    if type(raw) is not dict:
        raise ValueError('spec must be a JSON object')
    bad = FORBIDDEN.intersection(raw)
    if bad:
        raise ValueError(f'spec must not reverse-fit meshes; remove {sorted(bad)}')
    if raw.get('schema') != SCHEMA:
        raise ValueError(f'schema must be {SCHEMA}')
    if raw.get('units') != 'mm':
        raise ValueError('units must be mm')
    tess = _finite(raw.get('tessellation_mm', 0.2), 'tessellation_mm', lo=0.049999, hi=2)
    solids_in = raw.get('solids')
    if type(solids_in) is not list or not solids_in:
        raise ValueError('solids must be a nonempty list')
    if len(solids_in) > MAX_SOLIDS:
        raise ValueError(f'at most {MAX_SOLIDS} solids')
    spec_dir = Path(spec_dir)
    ids = set()
    solids = []
    for item in solids_in:
        record = _solid(item, ids, spec_dir)
        ids.add(record['id'])
        solids.append(record)
    for item in solids:
        if item['kind'] == 'shell' and item['source'] not in ids:
            raise ValueError(f'shell source {item["source"]} is not a solid id')
    ops_in = raw.get('ops', [])
    if type(ops_in) is not list:
        raise ValueError('ops must be a list')
    if len(ops_in) > MAX_OPS:
        raise ValueError(f'at most {MAX_OPS} ops')
    live = set(ids)
    ops = [_op(item, live) for item in ops_in]
    export = raw.get('export')
    if type(export) is not list or not export:
        raise ValueError('export must be a nonempty list of solid ids')
    seen = set()
    names = []
    for ident in export:
        ident = _name(ident, 'export id')
        if ident in seen:
            raise ValueError(f'duplicate export id {ident}')
        if ident not in live:
            raise ValueError(f'export id {ident} is not a built solid')
        seen.add(ident)
        names.append(ident)
    budget_in = raw.get('budget') or {}
    if type(budget_in) is not dict:
        raise ValueError('budget must be an object when present')
    extra_budget = set(budget_in) - {'max_wall_s', 'extend_used', 'heartbeat_s'}
    if extra_budget:
        raise ValueError(f'unexpected budget fields {sorted(extra_budget)}')
    extra_top = set(raw) - {'schema', 'units', 'tessellation_mm', 'solids', 'ops', 'export', 'budget'}
    if extra_top:
        raise ValueError(f'unexpected spec fields {sorted(extra_top)}')
    spec = {
        'schema': SCHEMA,
        'units': 'mm',
        'tessellation_mm': tess,
        'solids': solids,
        'ops': ops,
        'export': names,
        'budget': {
            'extend_used': bool(budget_in.get('extend_used', False)),
        },
    }
    if 'heartbeat_s' in budget_in:
        spec['budget']['heartbeat_s'] = _finite(budget_in['heartbeat_s'], 'heartbeat_s', lo=0, hi=60)
    if 'max_wall_s' in budget_in:
        spec['budget']['max_wall_s'] = _finite(budget_in['max_wall_s'], 'max_wall_s', lo=0, hi=MAX_WALL_S)
    return spec


def score_spec(spec):
    score = 0.0
    for solid in spec['solids']:
        kind = solid['kind']
        if kind in ('box', 'cylinder', 'cone'):
            score += 1
        elif kind == 'shell':
            score += 4
        elif kind == 'iso_metric_thread':
            score += 2 + solid['length_mm'] / 10.0
        elif kind == 'iso_tapped_hole':
            score += 2 + solid['length_mm'] / 10.0
        elif kind == 'iso_clearance_hole':
            score += 2
        else:
            score += 3
    for op in spec['ops']:
        score += 8 if op['op'] in ('fillet', 'chamfer') else 2
    if spec['tessellation_mm'] < 0.1:
        score += 4
    return score


def estimate_budget(spec):
    score = score_spec(spec)
    if score <= 4:
        band, default_s, needs_confirm = 'low', 30, False
    elif score <= 12:
        band, default_s, needs_confirm = 'mid', 60, True
    elif score <= 24:
        band, default_s, needs_confirm = 'high', 120, True
    else:
        raise ValueError('recipe exceeds the high budget band; split ops or enlarge tessellation_mm')
    override = spec.get('budget', {}).get('max_wall_s')
    max_wall_s = default_s if override is None else override
    if max_wall_s > 30:
        needs_confirm = True
    if spec.get('budget', {}).get('extend_used') and override is None:
        raise ValueError('extend_used requires an explicit budget.max_wall_s')
    heartbeat_s = spec.get('budget', {}).get('heartbeat_s', 5)
    return {
        'band': band,
        'score': round(score, 3),
        'max_wall_s': max_wall_s,
        'heartbeat_s': heartbeat_s,
        'needs_confirm': needs_confirm,
        'extend_used': bool(spec.get('budget', {}).get('extend_used')),
        'default_s': default_s,
    }


def spec_digest(spec):
    blob = json.dumps(spec, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()


def load_spec(path):
    path = Path(path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    return validate_spec(raw, spec_dir=path.parent)
