"""Explicit millimetre T rail; candidate generator, not automatic print approval."""
import math
import numpy as np
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely import affinity


def t_profile(spec):
    """Return a sampled CCW profile and key, before phase rotation.

    Radial seam clearance uses the local helicoid normal factor. Key clearance
    uses a conservative outer-radius factor, so the actual three-dimensional
    gap must still be measured. No angular compression or global inset follows.
    """
    n = spec['count']
    if isinstance(n, bool) or not isinstance(n, int) or n < 3:
        raise ValueError('integer count >=3 required')
    names = ('radius_mm', 'head_width_mm', 'neck_width_mm', 'stem_depth_mm',
             'head_thickness_mm', 'normal_gap_mm', 'corner_mm',
             'inner_radius_mm', 'outer_radius_mm', 'sample_mm')
    values = [spec[key] for key in names]
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('positive finite millimetre dimensions required')
    r, head, neck, depth, thickness, gap, corner, inner, outer, step = values
    k = math.radians(spec['k_deg_per_mm'])
    if not math.isfinite(k) or k == 0 or not (inner < r-head/2 < r+head/2 < outer) or neck >= head or 2*corner >= min(head, thickness):
        raise ValueError('invalid rail dimensions or twist rate')
    radii = np.linspace(inner, outer, math.ceil((outer-inner)/step)+1)
    def side(radius, upper):
        half = math.asin(gap*math.sqrt(1+(k*radius)**2)/(2*radius))
        if 2*half >= 2*math.pi/n:
            raise ValueError('clearance consumes the sector')
        a = -half if upper else -2*math.pi/n+half
        return [radius*math.cos(a), radius*math.sin(a)]
    sector = Polygon([side(v, False) for v in radii]+[side(v, True) for v in radii[::-1]])
    cap = box(r-head/2, depth, r+head/2, depth+thickness).buffer(-corner).buffer(corner, quad_segs=8)
    key = cap.union(box(r-neck/2, -max(1., gap), r+neck/2, depth+thickness/2))
    key = key.buffer(corner, quad_segs=8).buffer(-corner, quad_segs=8)
    key_gap = gap*math.sqrt(1+(k*(r+head/2+gap))**2)
    profile = sector.union(key).difference(affinity.rotate(key.buffer(key_gap, quad_segs=16), -360/n, origin=(0, 0)))
    if profile.geom_type != 'Polygon' or not profile.is_valid or profile.interiors:
        raise ValueError('key/cavity splits the petal or creates an internal hole')
    profile = orient(profile, sign=1)
    if min(profile.distance(affinity.rotate(profile, 360*i/n, origin=(0, 0))) for i in range(1, n)) <= 0:
        raise ValueError('neighboring profiles touch')
    points = np.asarray(profile.exterior.coords)[:-1]
    sampled = []
    for a, b in zip(points, np.roll(points, -1, axis=0)):
        subdivisions = max(1, math.ceil(np.linalg.norm(b-a)/step))
        sampled.extend(a+(b-a)*t/subdivisions for t in range(subdivisions))
    return np.asarray(sampled), key
