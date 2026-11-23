"""Measured planar capture on final meshes; no force or friction certification.

The caller chooses a local joint frame and probe lines from reviewed sections.
Both shoulders are measured separately. Finite samples are not a continuous
surface proof. Thresholds and manufacturing budgets belong to the task.
"""
import math
import numpy as np
from shapely.geometry import Polygon, LineString
from shapely import affinity
from motion import adjacent_overlap, offsets


def finite(value, minimum=0, strict=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('finite numeric capture parameter required')
    if value < minimum or (strict and value == minimum):
        raise ValueError('capture parameter below allowed range')
    return value


def section_polygon(mesh, z, angle_deg):
    section = mesh.section(plane_normal=[0, 0, 1], plane_origin=[0, 0, z])
    if section is None:
        raise ValueError('missing mesh section')
    result = Polygon()
    for line in section.discrete:
        if np.linalg.norm(line[0]-line[-1]) > 1e-5:
            raise ValueError('open section loop')
        poly = Polygon(line[:, :2])
        if not poly.is_valid or poly.area <= 0:
            raise ValueError('invalid section polygon')
        result = result.symmetric_difference(poly)  # Preserve holes by parity.
    return affinity.rotate(result, -angle_deg, origin=(0, 0))


def interval(shape, axis, coordinate, window, probe, free=False):
    lo, hi = window
    if not lo < probe < hi:
        raise ValueError('probe must be inside its finite window')
    line = LineString([(lo, coordinate), (hi, coordinate)] if axis == 'x'
                      else [(coordinate, lo), (coordinate, hi)])
    clipped = line.difference(shape) if free else line.intersection(shape)
    segments = list(getattr(clipped, 'geoms', [clipped]))
    index = 0 if axis == 'x' else 1
    candidates = []
    for segment in segments:
        if segment.geom_type != 'LineString' or segment.is_empty:
            continue
        bounds = [segment.bounds[index], segment.bounds[index+2]]
        if bounds[0] < probe < bounds[1]:
            candidates.append(bounds)
    if len(candidates) != 1:
        raise ValueError('probe does not identify one unambiguous interval')
    a, b = candidates[0]
    if a <= lo+1e-6 or b >= hi-1e-6:
        raise ValueError('interval escapes measurement window; material/capture missing')
    return [a, b]


def measure_section(owner, receiver, probes):
    """Planar dimensions at one actual mating section, with raw interval evidence."""
    window, center = probes['x_window_mm'], probes['x_center_mm']
    head = interval(owner, 'x', probes['head_y_mm'], window, center)
    neck = interval(owner, 'x', probes['neck_y_mm'], window, center)
    throat = interval(receiver, 'x', probes['neck_y_mm'], window, center, free=True)
    vertical = {}
    for name, shape in [('flange', owner), ('front_lip', receiver), ('back_wall', receiver)]:
        vertical[name] = [interval(shape, 'y', x, probes['y_window_mm'], probes[name+'_y_mm'])
                          for x in probes['shoulder_x_mm']]
    return {'raw_intervals_mm': {'head': head, 'neck': neck, 'throat': throat, **vertical},
            'left_capture_mm': throat[0]-head[0], 'right_capture_mm': head[1]-throat[1],
            'neck_play_mm': (throat[1]-throat[0])-(neck[1]-neck[0]),
            'root_mm': neck[1]-neck[0],
            **{name+'_mm': min(b-a for a, b in values) for name, values in vertical.items()}}


def validate_spec(spec, count):
    from retention import connection_report
    if spec['schema'] != 'twisty.capture-spec.v1' or not connection_report(count, spec['interfaces'])['complete']:
        raise ValueError('capture specification must cover the whole ring exactly once')
    process = spec['manufacturing']
    if process['status'] not in ('assumed', 'calibrated') or not process['basis'].strip():
        raise ValueError('manufacturing assumptions/calibration and basis required')
    finite(process['extrusion_width_mm'], strict=True)
    for key in ('male_loss_mm', 'female_growth_mm', 'wear_flex_budget_mm'):
        finite(process[key])
    thresholds = spec['thresholds_mm']
    for key in ('residual_capture', 'maximum_neck_play', 'root', 'flange', 'front_lip', 'back_wall', 'minimum_engagement'):
        finite(thresholds[key], strict=True)
    finite(spec['maximum_section_step_mm'], strict=True)
    for joint in spec['interfaces']:
        z = joint['heights_mm']
        for h in z:
            finite(h, minimum=-math.inf)
        if len(z) < 3 or any(b <= a or b-a > spec['maximum_section_step_mm']+1e-9 for a, b in zip(z, z[1:])):
            raise ValueError('ordered dense capture sections required')
        finite(joint['angle_at_z0_deg'], minimum=-math.inf)
        probes = joint['probes']
        if len(probes['shoulder_x_mm']) != 2 or probes['shoulder_x_mm'][0] >= probes['x_center_mm'] or probes['shoulder_x_mm'][1] <= probes['x_center_mm']:
            raise ValueError('one thickness probe on each shoulder required')
    return spec


def evaluate_row(row, spec):
    m, t = spec['manufacturing'], spec['thresholds_mm']
    budget = m['male_loss_mm']+m['female_growth_mm']+m['wear_flex_budget_mm']
    errors = []
    for side in ('left', 'right'):
        value = finite(row[side+'_capture_mm'], minimum=-1e10)-budget
        if value < t['residual_capture']:
            errors.append(side+' shoulder reserve')
    play = finite(row['neck_play_mm'])
    if play > t['maximum_neck_play']:
        errors.append('neck play')
    for key in ('root', 'flange', 'front_lip', 'back_wall'):
        if finite(row[key+'_mm']) < t[key]:
            errors.append(key+' thickness')
    return errors


def measure_capture(meshes, manifest, spec, assembly_hash):
    validate_spec(spec, len(meshes))
    rows = []
    for joint in spec['interfaces']:
        a, b = joint['owner'], joint['receiver']
        for z in joint['heights_mm']:
            row = {'owner': a, 'receiver': b, 'z_mm': z}
            try:
                angle = joint['angle_at_z0_deg']+manifest['k_deg_per_mm']*z
                owner = section_polygon(meshes[a-1], z, angle)
                receiver = section_polygon(meshes[b-1], z, angle)
                row.update(measure_section(owner, receiver, joint['probes']))
                row['failures'] = evaluate_row(row, spec)
            except ValueError as exc:
                row['failures'] = [str(exc)]
            rows.append(row)
    return {'schema': 'twisty.capture.v1', 'assembly_sha256': assembly_hash,
            'part_sha256': [p['sha256'] for p in manifest['parts']], 'spec': spec,
            'measurements': rows, 'all_passed': all(not row['failures'] for row in rows),
            'scope': 'Actual final-mesh planar sections and caller-specified dimensional budgets. '
                     'No elastic, friction, continuous-surface or physical-print certification.'}


def check_capture(report, manifest, assembly_hash, intervals):
    """Recompute numeric gates and exact section coverage, never trust all_passed alone."""
    if report['schema'] != 'twisty.capture.v1' or report['assembly_sha256'] != assembly_hash or report['part_sha256'] != [p['sha256'] for p in manifest['parts']]:
        raise ValueError('stale capture measurement')
    spec = validate_spec(report['spec'], manifest['count'])
    expected = {(j['owner'], j['receiver'], z) for j in spec['interfaces'] for z in j['heights_mm']}
    seen = set()
    for row in report['measurements']:
        key = (row['owner'], row['receiver'], row['z_mm'])
        if key not in expected or key in seen or row['failures'] or evaluate_row(row, spec):
            raise ValueError('failed, duplicate or unexpected capture section')
        raw = row['raw_intervals_mm']
        for name in ('head', 'neck', 'throat'):
            if len(raw[name]) != 2 or any(not math.isfinite(v) for v in raw[name]) or raw[name][0] >= raw[name][1]:
                raise ValueError('invalid raw horizontal interval')
        for name in ('flange', 'front_lip', 'back_wall'):
            if len(raw[name]) != 2 or any(len(v) != 2 or not all(math.isfinite(x) for x in v) or v[0] >= v[1] for v in raw[name]):
                raise ValueError('both shoulder thickness intervals required')
        head, neck, throat = (raw[k] for k in ('head', 'neck', 'throat'))
        derived = {'left_capture_mm': throat[0]-head[0], 'right_capture_mm': head[1]-throat[1],
                   'root_mm': neck[1]-neck[0], 'neck_play_mm': throat[1]-throat[0]-(neck[1]-neck[0]),
                   **{k+'_mm': min(b-a for a, b in raw[k]) for k in ('flange', 'front_lip', 'back_wall')}}
        if any(not math.isclose(row[k], value, abs_tol=1e-7) for k, value in derived.items()):
            raise ValueError('capture metrics disagree with raw measured intervals')
        seen.add(key)
    if seen != expected or report['all_passed'] is not True:
        raise ValueError('missing or failed numeric capture evidence')
    if len(intervals) != manifest['count']:
        raise ValueError('missing intervals')
    for j in spec['interfaces']:
        for part in (j['owner'], j['receiver']):
            lo, hi = intervals[part-1]
            if not j['heights_mm'][0] <= lo < hi <= j['heights_mm'][-1]:
                raise ValueError('claimed engagement exceeds measured section coverage')
    required = spec['thresholds_mm']['minimum_engagement']
    for case in manifest['axial_stops']['retained_motions']:
        overlap = adjacent_overlap(intervals, offsets(manifest['count'], case['travel_mm'], case['mode']))
        if any(r['overlap_mm'] < required for r in overlap):
            raise ValueError('retained motion has insufficient capture engagement')
    # Also check independently reachable per-interface end limits.
    for j in manifest['axial_stops']['interfaces']:
        a, b = intervals[j['owner']-1], intervals[j['receiver']-1]
        for dz in (-j['negative_travel_mm'], j['positive_travel_mm']):
            if min(a[1]+dz, b[1])-max(a[0]+dz, b[0]) < required:
                raise ValueError('stop endpoint leaves insufficient capture engagement')
    return {'manufacturing_status': spec['manufacturing']['status'], 'sections': len(seen)}
