"""Read-only Blender mesh measurements with explicit coordinate and unit policy."""
import math
import bmesh


def measure_mesh(mesh, *, transform=None, unit_mm=1.0, weld=None, area_epsilon=0.0, area_inclusive=False):
    """Measure a temporary BMesh; never mutate mesh or apply object modifiers.

    transform and weld operate in native coordinates. Area thresholds use those
    squared units; unit_mm only scales returned lengths/volume, not the algorithm.
    """
    if not math.isfinite(unit_mm) or unit_mm <= 0:
        raise ValueError('Positive finite millimetres per coordinate unit required')
    if not math.isfinite(area_epsilon) or area_epsilon < 0 or (weld is not None and (not math.isfinite(weld) or weld < 0)):
        raise ValueError('Nonnegative finite area threshold and optional weld required')
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        if transform is not None:
            bm.transform(transform)
        if weld is not None:
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=weld)
        unseen, components = set(bm.verts), 0
        while unseen:
            stack = [unseen.pop()]; components += 1
            while stack:
                vertex = stack.pop()
                for edge in vertex.link_edges:
                    other = edge.other_vert(vertex)
                    if other in unseen:
                        unseen.remove(other); stack.append(other)
        bounds = [[min(v.co[i] for v in bm.verts), max(v.co[i] for v in bm.verts)] for i in range(3)] if bm.verts else None
        area_test = (lambda area: area <= area_epsilon) if area_inclusive else (lambda area: area < area_epsilon)
        volume = bm.calc_volume(signed=True)
        return dict(vertices=len(bm.verts), faces=len(bm.faces), triangles=sum(len(f.verts)-2 for f in bm.faces),
                    components=components, boundary_edges=sum(e.is_boundary for e in bm.edges),
                    nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
                    inconsistent_winding_edges=sum(e.is_manifold and not e.is_contiguous for e in bm.edges),
                    degenerate_faces=sum(area_test(f.calc_area()) for f in bm.faces),
                    finite=all(math.isfinite(x) for v in bm.verts for x in v.co),
                    signed_volume=volume, signed_volume_mm3=volume * unit_mm**3,
                    bounds=bounds, bounds_mm=[[x*unit_mm for x in row] for row in bounds] if bounds else None)
    finally:
        bm.free()
