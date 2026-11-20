"""Local non-adjacent triangle diagnostics; not a whole-model certificate."""
import numpy as np
from mathutils.bvhtree import BVHTree
from blender_ops import world_mesh


def segment_hit(origin, end, triangle):
    direction = end-origin
    e1, e2 = triangle[1]-triangle[0], triangle[2]-triangle[0]
    p = np.cross(direction, e2); det = np.dot(e1, p)
    if abs(det) < 1e-12: return False
    t = origin-triangle[0]; u = np.dot(t, p)/det
    if not -1e-8 <= u <= 1+1e-8: return False
    q = np.cross(t, e1); v = np.dot(direction, q)/det; distance = np.dot(e2, q)/det
    return v >= -1e-8 and u+v <= 1+1e-8 and 1e-7 < distance < 1-1e-7


def triangle_relation(a, b):
    if any(segment_hit(a[k], a[(k+1)%3], b) or segment_hit(b[k], b[(k+1)%3], a) for k in range(3)):
        return 'cross'
    na = np.cross(a[1]-a[0], a[2]-a[0]); nb = np.cross(b[1]-b[0], b[2]-b[0])
    if np.linalg.norm(na) < 1e-12 or np.linalg.norm(nb) < 1e-12:
        return 'ambiguous'
    na /= np.linalg.norm(na); nb /= np.linalg.norm(nb)
    if np.linalg.norm(np.cross(na, nb)) < 1e-8 and abs(np.dot(na, b[0]-a[0])) < 1e-7:
        return 'ambiguous'  # Coplanar candidates need a planar/contact review.
    return 'clear'


def local_crossings(body, operand, padding_mm):
    vertices, triangles = world_mesh(body)
    ov, _ = world_mesh(operand)
    coords = np.asarray(vertices)*1000; tri = np.asarray(triangles, dtype=np.int32)
    low = np.min(ov, axis=0)*1000-padding_mm
    high = np.max(ov, axis=0)*1000+padding_mm
    points = coords[tri]
    selected = np.all(points.max(1)>=low, axis=1) & np.all(points.min(1)<=high, axis=1)
    local = tri[selected]
    tree = BVHTree.FromPolygons(vertices, local.tolist(), all_triangles=True)
    candidates = tree.overlap(tree); crosses=[]; ambiguous=[]
    for i, j in candidates:
        if j <= i or set(local[i]) & set(local[j]): continue
        relation = triangle_relation(coords[local[i]], coords[local[j]])
        if relation == 'cross': crosses.append([int(i), int(j)])
        if relation == 'ambiguous': ambiguous.append([int(i), int(j)])
    return dict(status='fail' if crosses else 'not_tested' if ambiguous else 'local_clear',
                triangle_count=len(local), bvh_candidate_pairs=len(candidates),
                crossing_pairs=crosses, unresolved_pairs=ambiguous,
                bounds_mm=[low.tolist(), high.tolist()],
                scope='World-coordinate local non-adjacent triangle tests; shared-vertex folds and global source self-intersection are not covered. Compare source for provenance.')
