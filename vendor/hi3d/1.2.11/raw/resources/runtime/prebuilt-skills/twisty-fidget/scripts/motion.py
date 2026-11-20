"""Pure axial screw kinematics; lengths in mm, angles in degrees."""
import math


def offsets(count, travel_mm, mode):
    if isinstance(count, bool) or not isinstance(count, int) or count < 3:
        raise ValueError('count must be an integer >= 3')
    if not math.isfinite(travel_mm) or travel_mm < 0:
        raise ValueError('travel_mm must be finite and nonnegative')
    if mode == 'staircase':
        weights = [min(i, count-i) for i in range(count)]
    elif mode == 'wave':
        weights = [1-math.cos(2*math.pi*i/count) for i in range(count)]
    else:
        raise ValueError('mode must be staircase or wave')
    return [travel_mm*w/max(weights) for w in weights]


def screw_pose(offset_mm, progress, k_deg_per_mm):
    if not all(math.isfinite(x) for x in (offset_mm, progress, k_deg_per_mm)):
        raise ValueError('pose values must be finite')
    if not 0 <= progress <= 1:
        raise ValueError('progress must lie in [0, 1]')
    z = offset_mm*progress
    return z, k_deg_per_mm*z


def adjacent_overlap(intervals, displacements):
    """Overlap of caller-supplied rail intervals, not a proof of capture."""
    if len(intervals) != len(displacements) or len(intervals) < 3:
        raise ValueError('one interval per petal is required')
    moved = []
    for (lo, hi), z in zip(intervals, displacements):
        if not all(math.isfinite(v) for v in (lo, hi, z)) or hi <= lo:
            raise ValueError('rail intervals must be finite and increasing')
        moved.append((lo+z, hi+z))
    rows = []
    for i, a in enumerate(moved):
        j = (i+1) % len(moved)
        lo, hi = max(a[0], moved[j][0]), min(a[1], moved[j][1])
        rows.append({'parts': [i+1, j+1], 'adjacent_step_mm': abs(displacements[i]-displacements[j]),
                     'overlap_mm': max(0., hi-lo), 'interval_mm': [lo, hi] if hi > lo else None})
    return rows


def stop_travel_limits(displacements, interfaces):
    """Check each owner-minus-receiver endpoint for linear screw progress 0..1.

    This independent range check prevents sparse collision samples from jumping
    completely over a thin stop wall. It does not prove that the wall exists.
    """
    if len(displacements) == 0 or not all(math.isfinite(v) for v in displacements):
        raise ValueError('finite nonempty displacements required')
    rows = []
    for spec in interfaces:
        a, b = spec['owner'], spec['receiver']
        if any(isinstance(i, bool) or not isinstance(i, int) or not 1 <= i <= len(displacements) for i in (a, b)) or a == b:
            raise ValueError('invalid stop pair')
        neg, pos = float(spec['negative_travel_mm']), float(spec['positive_travel_mm'])
        if not all(math.isfinite(v) and v > 0 for v in (neg, pos)):
            raise ValueError('positive finite contact limits required')
        d = displacements[a-1]-displacements[b-1]
        rows.append({'owner': a, 'receiver': b, 'relative_offset_mm': d,
                     'allowed_interval_mm': [-neg, pos], 'within_limits': -neg <= d <= pos})
    return rows
