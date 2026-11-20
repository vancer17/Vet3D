"""BVH triangle-surface diagnostics, not whole-solid containment tests."""
import math
from mathutils.bvhtree import BVHTree


def bounds_overlap(a,b):
    """Strict AABB overlap; touching bounds excluded (caller chooses to use it)."""
    return all(a[0][i]<b[1][i] and a[1][i]>b[0][i] for i in range(3))


def surface_tree(points, triangles, *, epsilon=0):
    """Build Blender BVH with explicit epsilon in the coordinates' units."""
    if len(points)==0 or len(triangles)==0 or not math.isfinite(epsilon) or epsilon<0:
        raise ValueError('Nonempty surface and nonnegative epsilon required')
    return BVHTree.FromPolygons(points,triangles,all_triangles=True,epsilon=epsilon)


def pair_counts(trees,pairs):
    """Return count per explicit named pair; no intended-contact suppression."""
    result={}
    for a,b in pairs:
        if a==b or a not in trees or b not in trees:raise ValueError('Distinct existing pair names required')
        key=a+' / '+b
        if key in result:raise ValueError('Duplicate surface pair')
        result[key]=len(trees[a].overlap(trees[b]))
    return result
