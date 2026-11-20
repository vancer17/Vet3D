"""Generate back-down ball-joint clearance candidates from an explicit JSON spec."""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
import uuid

import manifold3d as mf
import numpy as np

from coupon_records import clearance_series, pair_record
from joints import BallSpec, ball_tools, pair_metrics, require_solid
from mesh_io import read_stl_solid, to_trimesh, write_3mf


def coupon_geometry(spec, support_gap_mm, support_radius_mm):
    """Three independent solids: grip+socket, ball+stem+grip, rear support post."""
    spec.validate()
    if spec.rear_flat_mm is None:
        raise ValueError("Back-down coupon requires rear flat and cleaning port")
    if not (math.isfinite(support_gap_mm) and 0 < support_gap_mm < spec.wall_mm):
        raise ValueError("Support top gap must be positive and less than wall")
    flat_radius = math.sqrt(spec.radius_mm ** 2 - spec.rear_flat_mm ** 2)
    if not (math.isfinite(support_radius_mm) and 0 < support_radius_mm
            < min(flat_radius, spec.rear_port_radius_mm) - spec.gap_mm):
        raise ValueError("Support post must clear the access port and fit the ball flat")
    shapes = ball_tools(spec)
    grip_radius = spec.stem_radius_mm + spec.wall_mm
    grip_length = 2 * spec.wall_mm + spec.radius_mm
    parent_grip = mf.Manifold.cylinder(grip_length, grip_radius, grip_radius, spec.segments)
    parent_grip = parent_grip.translate([0, 0, -spec.outer_mm - grip_length + spec.wall_mm])
    parent = (shapes['socket'] + parent_grip) - shapes['parent_cutter']
    child_grip = mf.Manifold.cylinder(grip_length, grip_radius, grip_radius, spec.segments)
    child_grip = child_grip.translate([0, 0, spec.stem_length_mm - spec.wall_mm])
    child = shapes['ball_stem'] + child_grip
    # Same rigid rotation for both parts: source rear +Y becomes print down -Z.
    parts = {'socket': parent.rotate([-90, 0, 0]), 'ball': child.rotate([-90, 0, 0])}
    min_z = min(shape.bounding_box()[2] for shape in parts.values())
    parts = {name: shape.translate([0, 0, -min_z]) for name, shape in parts.items()}
    flat_height = -spec.rear_flat_mm - min_z
    height = flat_height - support_gap_mm
    if height <= 0:
        raise ValueError("No space for separate rear support")
    parts['support'] = mf.Manifold.cylinder(height, support_radius_mm,
                                           support_radius_mm, spec.segments)
    for name, shape in parts.items():
        require_solid(shape, name)
    for first, second in [('socket', 'ball'), ('socket', 'support'), ('ball', 'support')]:
        if (parts[first] ^ parts[second]).volume() > 1e-7:
            raise ValueError(f"Coupon collision: {first}/{second}")
    return parts


def export_coupons(config, output):
    """Write candidates and actual-STL readback; caller manages timing/output directory."""
    spec = BallSpec(**config['joint']).validate()
    series=clearance_series(config['gaps_mm'],definition='Radial ball/socket gap; diametral gap is twice this value')
    all_parts, rows, cursor = {}, [], 0.0
    for sample in series:
        index,gap=sample['index'],sample['clearance_mm']
        candidate = replace(spec, gap_mm=gap).validate()
        parts = coupon_geometry(candidate, config['support_gap_mm'], config['support_radius_mm'])
        bounds = np.asarray([shape.bounding_box() for shape in parts.values()])
        dx = cursor - bounds[:, 0].min()
        cursor += bounds[:, 3].max() - bounds[:, 0].min() + 5.0
        names = {}
        for name, shape in parts.items():
            key = f'{index:02d}_{name}'
            moved = shape.translate([dx, 0, 0])
            path = output / f'{key}.stl'
            path.write_bytes(to_trimesh(moved).export(file_type='stl'))
            read_stl_solid(path)
            all_parts[key] = moved
            names[name] = path.name
        rows.append({'index': index, 'joint': asdict(candidate), 'files': names,
                     'neutral_pair': pair_metrics(parts['socket'], parts['ball'], gap * 2),
                     'support_pair': pair_metrics(parts['ball'], parts['support'], candidate.wall_mm),
                     'pair_record':pair_record(str(index),names,clearance_mm=gap,definition=sample['definition'],orientation='local +Y rear faces print -Z',source={'joint':asdict(candidate)})})
    write_3mf(output / 'clearance_coupon.3mf', all_parts, 'PIP clearance candidates')
    report = {'units': 'millimeter', 'orientation': 'local +Y rear faces print -Z',
              'candidates': rows, 'solids': len(all_parts), 'stl_readback': 'passed',
              'slicing': 'not_tested', 'physical_release': 'not_tested',
              'note': 'Keep all relative positions. Separate posts only support ball flats; '
                      'inspect other overhangs and external support in the slicer.'}
    (output / 'coupon.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New, nonexistent directory')
    parser.add_argument('--task-id', required=True)
    args = parser.parse_args()
    # Refuse overwrite; failures retain partial output and an explicit failed record.
    args.out.mkdir(parents=True, exist_ok=False)
    record = {'task_id': args.task_id, 'attempt_id': str(uuid.uuid4()),
              'stage_id': 'joints_coupon', 'scope': 'coupon CLI only', 'status': 'running',
              'started_at': datetime.now(timezone.utc).isoformat()}
    log = args.out / 'timing.jsonl'
    log.write_text(json.dumps(record) + '\n')
    start = time.monotonic()
    try:
        report = export_coupons(json.loads(args.spec.read_text()), args.out)
        record['status'] = 'passed'
        print(json.dumps({'solids': report['solids'], 'output': str(args.out.resolve())}))
    except BaseException as error:
        record['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        record['error_type'] = type(error).__name__
        raise
    finally:
        record['ended_at'] = datetime.now(timezone.utc).isoformat()
        record['elapsed_seconds'] = time.monotonic() - start
        with log.open('a') as stream:
            stream.write(json.dumps(record) + '\n')


if __name__ == '__main__':
    main()
