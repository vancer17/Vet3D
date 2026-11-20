"""Pure indexed triangle diagnostics; no geometry edits, Blender or file access."""
import math
import numpy as np


def triangle_double_areas(vertices, triangles):
    """Return cross-product norms in input squared units, retaining NumPy precision."""
    vertices, triangles = np.asarray(vertices), np.asarray(triangles)
    return np.linalg.norm(np.cross(vertices[triangles[:, 1]] - vertices[triangles[:, 0]],
                                   vertices[triangles[:, 2]] - vertices[triangles[:, 0]]), axis=1)


def edge_incidence(triangles, *, discard_collapsed):
    """Return (undirected edges, use counts, collapsed uses); never weld vertices."""
    triangles = np.asarray(triangles)
    if triangles.ndim != 2 or triangles.shape[1] != 3 or triangles.dtype.kind not in 'iu':
        raise ValueError('Triangle indices must be an Nx3 integer array')
    edges = np.concatenate((triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]))
    edges.sort(axis=1)
    collapsed = edges[:, 0] == edges[:, 1]
    if discard_collapsed:
        edges = edges[~collapsed]
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    return unique, counts, int(np.count_nonzero(collapsed))


def edge_counts(triangles):
    _, counts, collapsed = edge_incidence(triangles, discard_collapsed=True)
    return {'unique_edges': len(counts), 'boundary_edges': int(np.count_nonzero(counts == 1)),
            'edges_over_two_faces': int(np.count_nonzero(counts > 2)), 'collapsed_edge_uses': collapsed}


def measure_indexed(coords, triangles, *, area_threshold=1e-12, exact_weld=False):
    """Raw local array profile; finite/empty diagnostics retain explicit None fields."""
    if not math.isfinite(area_threshold) or area_threshold < 0:
        raise ValueError('Finite nonnegative area threshold required')
    coords, triangles = np.asarray(coords), np.asarray(triangles)
    finite = bool(np.isfinite(coords).all())
    areas = triangle_double_areas(coords, triangles) * .5 if len(triangles) and finite else None
    result = {'vertices': len(coords), 'triangles': len(triangles),
              'finite_coordinates': finite,
              'local_bounds_min': coords.min(axis=0).tolist() if len(coords) and finite else None,
              'local_bounds_max': coords.max(axis=0).tolist() if len(coords) and finite else None,
              'degenerate_triangles': int(np.count_nonzero(areas <= area_threshold)) if areas is not None else None,
              'area_threshold_local_squared': area_threshold, 'indexed_topology': edge_counts(triangles)}
    if exact_weld and finite:
        unique, inverse = np.unique(coords, axis=0, return_inverse=True)
        result['exact_position_weld_diagnostic'] = {'vertices': len(unique), **edge_counts(inverse[triangles])}
    return result
