"""Pure solid-equivalent mass integration and static support geometry (NumPy)."""
import numpy as np


def _points(value, width):
    result = np.asarray(value, dtype=float)
    if result.ndim != 2 or result.shape[1] != width or not len(result) or not np.isfinite(result).all():
        raise ValueError(f"Expected nonempty finite N x {width} points")
    return result


def mass_properties(vertices, triangles, *, density_g_cm3, unit_mm=1, volume_epsilon_mm3=1e-8):
    """Integrate a closed consistently wound uniform solid; no mesh repair or IO."""
    v = _points(vertices, 3)
    f = np.asarray(triangles)
    if f.ndim != 2 or f.shape[1] != 3 or not len(f) or f.dtype.kind not in 'iu' or f.min() < 0 or f.max() >= len(v):
        raise ValueError("Expected nonempty integer triangle indices within vertices")
    if not np.isfinite([density_g_cm3, unit_mm, volume_epsilon_mm3]).all() or density_g_cm3 <= 0 or unit_mm <= 0 or volume_epsilon_mm3 < 0:
        raise ValueError("Positive finite density/unit and nonnegative volume epsilon required")
    v = v * unit_mm
    origin = v.mean(axis=0)
    t = (v - origin)[f]
    weights = np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2])) / 6
    volume = weights.sum()
    if not np.isfinite(volume) or abs(volume) <= volume_epsilon_mm3:
        raise ValueError("Zero/invalid solid volume")
    center = origin + (weights[:, None] * t.sum(axis=1) / 4).sum(axis=0) / volume
    mass = abs(volume) * density_g_cm3 / 1000
    if not np.isfinite(center).all() or not np.isfinite(mass) or mass <= 0:
        raise ValueError("Invalid center or mass")
    return dict(signed_volume_mm3=float(volume), volume_mm3=float(abs(volume)), center_mm=center.tolist(), mass_g=float(mass))


def combine_mass(parts):
    """Combine explicit positive masses/centers, including known payload masses."""
    parts = list(parts)
    centers = _points([p['center_mm'] for p in parts], 3)
    masses = np.asarray([p['mass_g'] for p in parts], dtype=float)
    if not np.isfinite(masses).all() or np.any(masses <= 0) or not np.isfinite(masses.sum()):
        raise ValueError("Finite positive masses required")
    total = float(masses.sum())
    return dict(mass_g=total, center_mm=(np.sum(centers * (masses / total)[:, None], axis=0)).tolist())


def support_polygon(points_xy, *, round_digits=None):
    """Return a CCW convex hull, rejecting point/line support; no implicit rounding."""
    points = _points(points_xy, 2)
    if round_digits is not None:
        points = points.round(round_digits)
    points = sorted(set(map(tuple, points)))
    def half(sequence):
        hull = []
        for p in sequence:
            while len(hull) >= 2:
                a, b = hull[-2], hull[-1]
                if (b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0]) > 0:
                    break
                hull.pop()
            hull.append(p)
        return hull
    hull = np.asarray(half(points)[:-1] + half(points[::-1])[:-1], dtype=float)
    if len(hull) < 3:
        raise ValueError("Degenerate contact polygon")
    return hull


def signed_margins(hull, point_xy):
    """Signed perpendicular distances to CCW hull edges; positive means inside."""
    hull = _points(hull, 2)
    point = np.asarray(point_xy, dtype=float)
    if point.shape != (2,) or not np.isfinite(point).all() or len(hull) < 3:
        raise ValueError("Finite point and nondegenerate hull required")
    edge = np.roll(hull, -1, axis=0) - hull
    lengths = np.linalg.norm(edge, axis=1)
    # The ordered hull contract excludes duplicate, clockwise and concave input.
    turns = edge[:, 0]*np.roll(edge, -1, axis=0)[:, 1] - edge[:, 1]*np.roll(edge, -1, axis=0)[:, 0]
    if np.any(lengths == 0) or np.any(turns <= 0):
        raise ValueError("Strictly convex CCW hull required")
    delta = point - hull
    return (edge[:, 0]*delta[:, 1] - edge[:, 1]*delta[:, 0]) / lengths


def assess_support(parts, contacts_mm, *, gravity=(0, 0, -1), round_digits=None):
    """Project contacts and COM perpendicular to explicit gravity; static only."""
    combined = combine_mass(parts)
    contacts = _points(contacts_mm, 3)
    g = np.asarray(gravity, dtype=float)
    if g.shape != (3,) or not np.isfinite(g).all() or np.linalg.norm(g) == 0:
        raise ValueError("Finite nonzero gravity required")
    up = -g / np.linalg.norm(g)
    axis = np.eye(3)[np.argmin(np.abs(up))]
    u = axis - np.dot(axis, up) * up
    u /= np.linalg.norm(u)
    v = np.cross(up, u)
    basis = np.asarray([u, v])
    origin = contacts.mean(axis=0)
    hull = support_polygon((contacts - origin) @ basis.T, round_digits=round_digits)
    center = (np.asarray(combined['center_mm']) - origin) @ basis.T
    margins = signed_margins(hull, center)
    return dict(**combined, gravity=g.tolist(), plane_origin_mm=origin.tolist(), plane_basis=basis.tolist(),
                support_polygon_plane_mm=hull.tolist(), projected_center_mm=center.tolist(),
                edge_margins_mm=margins.tolist(), minimum_support_margin_mm=float(margins.min()),
                center_inside_support_polygon=bool(margins.min() > 0))
