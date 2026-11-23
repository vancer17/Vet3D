"""Explicit rigid poses and object pairs → complete-solid collision samples."""
import math
import numpy as np
import manifold3d as mf
from pose_math import is_rigid


def intersection_volume(a, b, *, aabb_epsilon=None, absolute_volume=False):
    """Measure actual Manifold intersection, optionally applying a caller's AABB gate."""
    if a.status() != mf.Error.NoError or b.status() != mf.Error.NoError:
        raise ValueError('Invalid input solid')
    if aabb_epsilon is not None:
        if not math.isfinite(aabb_epsilon) or aabb_epsilon < 0:
            raise ValueError('AABB epsilon must be finite and nonnegative')
        aa, bb = np.asarray(a.bounding_box()), np.asarray(b.bounding_box())
        if not ((aa[3:] > bb[:3]+aabb_epsilon) & (bb[3:] > aa[:3]+aabb_epsilon)).all():
            return 0.0
    intersection = a ^ b
    if intersection.status() != mf.Error.NoError:
        raise ValueError('Pair boolean failed: '+str(intersection.status()))
    volume = float(intersection.volume())
    if not math.isfinite(volume):
        raise ValueError('Pair boolean returned nonfinite volume')
    return abs(volume) if absolute_volume else volume


def sample_solids(solids, samples, pairs, *, tolerance, inclusive=False,
                  aabb_epsilon=None, absolute_volume=False):
    """Every sample supplies {value, poses:{id:4x4}} for all caller-owned solids.

    Units are those of the solids; callers of *_mm3 reports must supply millimeters.
    Returns all samples and the first collision in input sample/pair order.
    """
    if not solids or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Nonempty solids and finite nonnegative tolerance required')
    if aabb_epsilon is not None and (not math.isfinite(aabb_epsilon) or aabb_epsilon < 0):
        raise ValueError('AABB epsilon must be finite and nonnegative')
    pairs = list(pairs); seen = set()
    for a,b in pairs:
        key = frozenset((a,b))
        if a == b or a not in solids or b not in solids or key in seen:
            raise ValueError('Explicit unique pairs of existing distinct solids required')
        seen.add(key)
    rows, first, maximum = [], None, 0.0
    for index,sample in enumerate(samples):
        poses = sample['poses']
        if set(poses) != set(solids) or any(not is_rigid(m) for m in poses.values()):
            raise ValueError('Each sample must give one finite rigid matrix per solid')
        moved = {key: solid.transform(np.asarray(poses[key])[:3,:]) for key,solid in solids.items()}
        bounds = np.asarray([s.bounding_box() for s in moved.values()])
        if (not np.isfinite(bounds).all() or any(s.status() != mf.Error.NoError for s in moved.values())):
            raise ValueError('Invalid or empty transformed solid')
        collisions, peak = [], 0.0
        for a,b in pairs:
            volume = intersection_volume(moved[a],moved[b],aabb_epsilon=aabb_epsilon,absolute_volume=absolute_volume)
            peak = max(peak,volume)
            if (volume >= tolerance) if inclusive else (volume > tolerance):
                collision = dict(a=a,b=b,volume_mm3=volume)
                collisions.append(collision)
                if first is None: first = dict(collision,sample=index,value=sample['value'])
        lo,hi = bounds[:,:3].min(0), bounds[:,3:].max(0)
        rows.append(dict(value=sample['value'],pair_checks=len(pairs),max_overlap_mm3=peak,
                         collisions=collisions,bounds_mm=[lo.tolist(),hi.tolist()],dimensions_mm=(hi-lo).tolist()))
        maximum = max(maximum,peak)
    if not rows: raise ValueError('Nonempty pose samples required')
    return dict(samples=rows,max_overlap_mm3=maximum,first_collision=first)
