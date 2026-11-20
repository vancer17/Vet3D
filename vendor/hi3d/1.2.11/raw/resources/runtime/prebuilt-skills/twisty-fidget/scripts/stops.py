"""Finite helical tongues and closed-ended pockets; pure geometry in mm.

Features are placed by the caller on a reviewed mating interface. This module
never infers the joint, minimum wall thickness, radial capture or printability.
"""
import math
import numpy as np
import manifold3d as mf
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from geometry import to_solid, from_solid


def helical_prism(points, lo, hi, k, step):
    """Sweep one simple XY polygon, anchored at world z=0; no file effects."""
    values = (lo, hi, k, step)
    if not all(math.isfinite(v) for v in values) or hi <= lo or k == 0 or step <= 0 or abs(k)*step >= 180:
        raise ValueError('finite bounds, positive height/step and nonzero k required')
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError('footprint must be finite Nx2 coordinates')
    polygon = Polygon(p)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('footprint must be one simple positive-area polygon')
    # Shapely buffers can reverse winding. Positive fill must not silently vanish.
    cs = mf.CrossSection([np.asarray(orient(polygon, sign=1).exterior.coords)[:-1]])
    return cs.rotate(k*lo).extrude(hi-lo, n_divisions=math.ceil((hi-lo)/step)-1,
        twist_degrees=k*(hi-lo)).translate((0, 0, lo))


def stop_features(spec, k, step):
    """Return integral tongue and its swept clearance pocket for a single joint.

    negative/positive_travel_mm are the actual contact positions of the owner
    relative to the receiver, with no extra axial clearance added to the limits.
    """
    z, height, neg, pos, gap = (float(spec[key]) for key in (
        'z_center_mm', 'lug_height_mm', 'negative_travel_mm', 'positive_travel_mm', 'xy_clearance_mm'))
    if not all(math.isfinite(v) for v in (z, height, neg, pos, gap)) or min(height, neg, pos, gap) <= 0:
        raise ValueError('positive finite height, both travels and XY clearance required')
    points = spec['footprint_xy_mm']
    tongue = helical_prism(points, z-height/2, z+height/2, k, step)
    enlarged = Polygon(points).buffer(gap, quad_segs=8)
    pocket = helical_prism(np.asarray(enlarged.exterior.coords)[:-1],
        z-height/2-neg, z+height/2+pos, k, step)
    return tongue, pocket


def apply_stops(meshes, interfaces, k, step):
    """Union each tongue to its owner, cut only its receiver; reject loose lugs.

    One-based part numbers; all specs are in assembled world XY. Returns new
    meshes and attachment measurements, never modifies inputs. Attachment is
    necessary but not sufficient: validate both end walls on the final meshes.
    """
    if not interfaces:
        raise ValueError('at least one stop interface required')
    source = [to_solid(m) for m in meshes]
    result = list(source)
    features, rows, seen = [], [], set()
    for spec in interfaces:
        a, b = spec['owner'], spec['receiver']
        if any(isinstance(i, bool) or not isinstance(i, int) or not 1 <= i <= len(source) for i in (a, b)) or a == b:
            raise ValueError('owner/receiver must be distinct one-based part numbers')
        if (a, b) in seen:
            raise ValueError('duplicate directed stop interface')
        seen.add((a, b))
        lug, pocket = stop_features(spec, k, step)
        root, bearing = abs((lug ^ source[a-1]).volume()), abs((lug ^ source[b-1]).volume())
        if min(root, bearing) <= 1e-8:
            raise ValueError('tongue must overlap its owner and the receiver bearing region')
        features.append((a-1, b-1, lug, pocket))
        rows.append({'owner': a, 'receiver': b, 'root_overlap_mm3': root,
                     'receiver_bearing_volume_mm3': bearing})
    for a, b, lug, pocket in features:
        result[a] = result[a] + lug
    # Cut after all unions, including features that might cut a different tongue.
    for a, b, lug, pocket in features:
        result[b] = result[b] - pocket
    return [from_solid(s) for s in result], rows


def measure_stop_contacts(meshes, interfaces, k, probe_mm, tolerance_mm3):
    """Check final-mesh pairs immediately before, at, and beyond both endpoints.

    Returns evidence, including failures. Only the named owner moves. The
    overtravel test is deliberate interference, never a reachable animation.
    This tests axial barriers along the screw path, not forces or radial escape.
    """
    if not all(math.isfinite(v) for v in (k, probe_mm, tolerance_mm3)) or k == 0 or probe_mm <= 0 or tolerance_mm3 < 0:
        raise ValueError('nonzero k, positive probe and nonnegative tolerance required')
    solids = [to_solid(m) for m in meshes]
    rows = []
    for spec in interfaces:
        a, b = spec['owner']-1, spec['receiver']-1
        if not 0 <= a < len(solids) or not 0 <= b < len(solids) or a == b:
            raise ValueError('invalid contact pair')
        for side, sign in [('negative', -1), ('positive', 1)]:
            limit = float(spec[side+'_travel_mm'])
            if not math.isfinite(limit) or limit <= probe_mm:
                raise ValueError('probe must be smaller than each positive contact limit')
            states = []
            for state, magnitude in [('before', limit-probe_mm), ('contact', limit), ('overtravel', limit+probe_mm)]:
                dz = sign*magnitude
                moved = solids[a].rotate((0, 0, k*dz)).translate((0, 0, dz))
                intersection = moved ^ solids[b]
                if intersection.status() != mf.Error.NoError:
                    raise ValueError('stop contact boolean failed')
                volume = abs(intersection.volume())
                if not math.isfinite(volume):
                    raise ValueError('nonfinite contact intersection')
                states.append({'state': state, 'relative_offset_mm': dz, 'overlap_mm3': volume})
            rows.append({'owner': a+1, 'receiver': b+1, 'direction': side, 'states': states,
                'passed': all(s['overlap_mm3'] <= tolerance_mm3 for s in states[:2]) and
                          states[2]['overlap_mm3'] > tolerance_mm3})
    return rows
