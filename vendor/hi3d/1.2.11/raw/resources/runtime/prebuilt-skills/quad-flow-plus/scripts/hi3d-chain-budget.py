"""Budget planning and verification of supplied edge chains; no mesh generation."""
import argparse
import json
import math
from pathlib import Path


def integer(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'{name} must be a JSON integer')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name} must be >= {minimum}')
    return value


def number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    if positive and value <= 0:
        raise ValueError(f'{name} must be positive')
    return float(value)


def plan(data):
    original = integer(data['baseline_quads'], 'baseline_quads', 1)
    if ('target_quads' in data) == ('remaining_ratio' in data):
        raise ValueError('provide exactly one of target_quads or remaining_ratio')
    if 'target_quads' in data:
        target = integer(data['target_quads'], 'target_quads', 1)
    else:
        ratio = number(data['remaining_ratio'], 'remaining_ratio', positive=True)
        if ratio > 1:
            raise ValueError('remaining_ratio must be <= 1')
        target = max(1, math.floor(original * ratio + 0.5))
    if target > original:
        raise ValueError('target_quads cannot exceed baseline_quads for this reduction planner')
    kept = integer(data.get('preserved_quads', 0), 'preserved_quads', 0)
    if kept > original:
        raise ValueError('preserved_quads cannot exceed baseline_quads')
    closed = data['core_closed']
    if not isinstance(closed, bool):
        raise ValueError('core_closed must be a JSON boolean')
    locked = integer(data.get('protected_core_vertices', 0), 'protected_core_vertices', 0)
    chi = data.get('core_euler_characteristic')
    if chi is not None:
        chi = integer(chi, 'core_euler_characteristic')
    if not closed and chi is not None:
        raise ValueError('Euler lower bound implemented here applies only to a closed core')
    step = 2 if closed else 1
    triangles = max(0, ((target - kept) // (3 * step)) * step)
    lower = max(4, 2 * (locked - chi)) if closed and chi is not None else (4 if closed else 1)
    possible = target > kept and triangles >= lower
    output = kept + 3 * triangles
    return {
        'baseline_quads': original, 'target_quads': target,
        'preserved_quads': kept, 'core_closed': closed,
        'planned_core_triangles': triangles,
        'planned_quad_count': output,
        'planned_triangulated_preview_count': 2 * output,
        'count_lower_bound_triangles': lower,
        'protected_core_vertices': locked,
        'core_euler_characteristic': chi,
        'count_bounds_feasible': possible,
        'action': 'prepare_candidate' if possible else 'resolve_constraints',
        'count_delta_to_target': output - target,
        'geometry_quality_verified': False,
        'warning': 'Count bounds are necessary only; geometry, actual chains and attributes require independent checks.'
    }


def point(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f'{name} must contain three coordinates')
    return tuple(number(x, name) for x in value)


def verify_chains(data):
    vertices = [point(p, 'vertex') for p in data['vertices']]
    if not vertices:
        raise ValueError('vertices cannot be empty')
    def index(value):
        value = integer(value, 'vertex index', 0)
        if value >= len(vertices):
            raise ValueError('vertex index out of range')
        return value
    edges = set()
    for face in data['faces']:
        ids = [index(i) for i in face]
        if len(ids) < 3 or len(set(ids)) != len(ids):
            raise ValueError('faces must have at least three distinct vertices')
        edges.update(tuple(sorted((a, b))) for a, b in zip(ids, ids[1:] + ids[:1]))
    chains = data['chains']
    if not isinstance(chains, list) or not chains:
        raise ValueError('at least one explicit ordered chain is required')
    tolerance = number(data.get('marker_tolerance', 1e-6), 'marker_tolerance', positive=True)
    checks = []; identifiers = set()
    for chain in chains:
        name = chain['id']
        if not isinstance(name, str) or not name or name in identifiers:
            raise ValueError('chain ids must be nonempty and unique')
        identifiers.add(name)
        closed, required = chain['closed'], chain.get('required', True)
        if not isinstance(closed, bool) or not isinstance(required, bool):
            raise ValueError('closed and required must be JSON booleans')
        ids = [index(i) for i in chain['vertices']]
        valid_length = len(ids) >= (3 if closed else 2)
        unique = len(ids) == len(set(ids))
        pairs = list(zip(ids, ids[1:]))
        if closed and ids:
            pairs.append((ids[-1], ids[0]))
        missing = [[a, b] for a, b in pairs if tuple(sorted((a, b))) not in edges]
        distances = []
        for marker in chain.get('reference_markers', []):
            i = index(marker['vertex'])
            if i not in ids:
                raise ValueError('reference marker must belong to its chain')
            reference = point(marker['position'], 'reference marker')
            distances.append(math.dist(vertices[i], reference))
        maximum = max(distances) if distances else None
        valid = valid_length and unique and not missing and (maximum is None or maximum <= tolerance)
        checks.append({'id': name, 'required': required, 'closed_requested': closed,
                       'chain_valid': valid, 'simple': unique, 'vertex_count': len(ids),
                       'edge_count': len(pairs), 'missing_edges': missing,
                       'reference_marker_count': len(distances),
                       'maximum_marker_displacement': maximum})
    required_checks = [x for x in checks if x['required']]
    return {'chains': checks, 'required_chain_count': len(required_checks),
            'all_required_chains_valid': bool(required_checks) and all(x['chain_valid'] for x in required_checks),
            'marker_tolerance': tolerance, 'full_surface_quality_verified': False,
            'warning': 'A valid closed edge chain does not prove regular animation loops, global manifoldness or shape accuracy.'}


def workspace_path(value):
    root = Path.cwd().resolve(); path = Path(value).resolve()
    if not path.is_relative_to(root):
        raise ValueError('input and output must remain in the current workspace')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'verify-chains'])
    parser.add_argument('input'); parser.add_argument('output')
    args = parser.parse_args()
    try:
        source, target = workspace_path(args.input), workspace_path(args.output)
        if target.exists():
            raise ValueError('output already exists; use a new output filename')
        if not target.name.startswith('hi3d-'):
            raise ValueError('generated output filename must start with hi3d-')
        data = json.loads(source.read_text())
        result = plan(data) if args.action == 'plan' else verify_chains(data)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result.get('all_required_chains_valid') is False else 0
    except (KeyError, ValueError, TypeError, OSError) as exc:
        print(f'ERROR: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
