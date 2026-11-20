"""Read-only topology metrics for the legacy metre profile."""
import bpy, bmesh


if __package__:
    from .mesh_measure import measure_mesh
else:
    from mesh_measure import measure_mesh

def topo(o):
    evaluated = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        measured = measure_mesh(o.data if o.type == 'MESH' else mesh)
        return {'vertices':measured['vertices'], 'triangles':measured['triangles'],
                'boundary_edges':measured['boundary_edges'], 'nonmanifold_edges':measured['nonmanifold_edges'],
                'volume_ml':abs(measured['signed_volume'])*1e6}
    finally:
        evaluated.to_mesh_clear()
