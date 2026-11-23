"""Blender adapters. Call only from an isolated background process."""
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from geometry import torus, split_ring


import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from mesh_measure import measure_mesh
from mesh_snapshot import mesh_snapshot

def material(name, color, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = (*color, 1)
    node.inputs['Metallic'].default_value = metallic
    node.inputs['Roughness'].default_value = .3 if metallic else .5
    return mat


def mesh_object(name, vertices_mm, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata((np.asarray(vertices_mm)/1000).tolist(), [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    for face in mesh.polygons:
        face.use_smooth = True
    return ob


def load_body(path, target, input_unit_mm):
    """Import source, select explicitly when ambiguous, clone and bake world scale."""
    path = Path(path)
    if path.suffix.lower() == '.blend':
        bpy.ops.wm.open_mainfile(filepath=str(path), use_scripts=False)
        imported = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render]
    else:
        scene = bpy.data.scenes.new('Keychain candidate')
        bpy.context.window.scene = scene
        before = set(bpy.data.objects)
        ext = path.suffix.lower()
        if ext in ('.glb', '.gltf'):
            bpy.ops.import_scene.gltf(filepath=str(path))
        elif ext == '.stl':
            bpy.ops.wm.stl_import(filepath=str(path))
        elif ext == '.obj':
            bpy.ops.wm.obj_import(filepath=str(path))
        else:
            raise ValueError('Unsupported mesh input')
        imported = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    selected = [o for o in imported if o.name == target] if target else imported
    if len(selected) != 1:
        raise ValueError('Select exactly one --target mesh; candidates: ' + ', '.join(o.name for o in imported))
    source = selected[0]
    if source.constraints or source.animation_data or source.data.shape_keys:
        raise ValueError('Source is animated, constrained or has shape keys: prepare an evaluated static mesh copy first')
    body = source.copy(); body.data = source.data.copy(); body.parent = None
    bpy.context.scene.collection.objects.link(body)
    transform = Matrix.Scale(input_unit_mm/1000, 4) @ source.matrix_world
    body.data.transform(transform); body.matrix_world = Matrix.Identity(4)
    # Source modifiers are not silently lost or applied to an unrelated object.
    if len(source.modifiers):
        bpy.data.objects.remove(body, do_unlink=True)
        raise ValueError('Source has modifiers: prepare an evaluated mesh copy explicitly first')
    body.name = 'Keychain body'; body.hide_render = False; body.hide_set(False)
    for ob in imported:
        ob.hide_render = True; ob.hide_set(True)
    return body


def weld_exact(mesh):
    """Merge duplicate XYZ positions only; preserve loop UVs and vertex positions."""
    bm = bmesh.new(); bm.from_mesh(mesh)
    positions, targets = {}, {}
    for vertex in bm.verts:
        key = tuple(vertex.co)
        if key in positions:
            targets[vertex] = positions[key]
        else:
            positions[key] = vertex
    bmesh.ops.weld_verts(bm, targetmap=targets)
    bm.to_mesh(mesh); bm.free(); mesh.update()


def topology(mesh):
    measured = measure_mesh(mesh, unit_mm=1000)
    result = {key: measured[key] for key in ('vertices','faces','boundary_edges',
              'inconsistent_winding_edges','components','signed_volume_mm3')}
    result['non_manifold_edges'] = measured['nonmanifold_edges']
    result['finite_coordinates'] = measured['finite']
    return result


def apply_interface(body, spec):
    """Modify only the working body. Hidden operand remains editable evidence."""
    operand = mesh_object('Construction attachment operand', *torus(spec))
    inner = material('Attachment new surfaces', (.65, .48, .34))
    body.data.materials.append(inner)
    for mat in body.data.materials:
        operand.data.materials.append(mat)
    for face in operand.data.polygons:
        face.material_index = len(body.data.materials)-1
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.select_all(action='DESELECT'); body.select_set(True)
    mod = body.modifiers.new('Keychain structural interface', 'BOOLEAN')
    mod.operation = 'DIFFERENCE' if spec['mode'] == 'tunnel' else 'UNION'
    try:
        mod.solver = spec.get('solver', 'MANIFOLD')
    except TypeError as exc:
        raise ValueError('Requested Boolean solver is unavailable in this Blender') from exc
    mod.object = operand
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bm = bmesh.new(); bm.from_mesh(body.data)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts)>3],
                         quad_method='BEAUTY', ngon_method='EAR_CLIP')
    bm.to_mesh(body.data); bm.free(); body.data.update()
    operand.hide_render = True; operand.hide_set(True)
    connector = None
    if spec.get('connector'):
        connector = mesh_object('Metal split connector', *split_ring(spec['connector'], spec['frame']))
        connector.data.materials.append(material('Silver connector', (.6, .64, .68), 1))
    return operand, connector


def world_mesh(ob):
    data = mesh_snapshot(ob, evaluated=True, space='world')
    return [Vector(row) for row in data['vertices']], [tuple(row) for row in data['triangles']]


def connector_check(body, connector):
    if connector is None:
        return {'status': 'not_tested', 'reason': 'No connector mesh supplied'}
    bv, bt = world_mesh(body); cv, ct = world_mesh(connector)
    body_tree = BVHTree.FromPolygons(bv, bt, all_triangles=True)
    ring_tree = BVHTree.FromPolygons(cv, ct, all_triangles=True)
    intersections = len(body_tree.overlap(ring_tree))
    distances = [body_tree.find_nearest(v)[3]*1000 for v in cv]
    stride = max(1, len(cv)//2000); inside = 0; ambiguous = 0
    for v in cv[::stride]:
        votes = []
        for direction in (Vector((.31,.73,.61)).normalized(), Vector((-.61,.31,.73)).normalized()):
            origin = v.copy(); count = 0
            for _ in range(128):
                hit, _, _, _ = body_tree.ray_cast(origin, direction)
                if hit is None:
                    votes.append(count%2); break
                count += 1; origin = hit + direction*1e-8
            else:
                votes.append(-1)
        if votes == [1,1]: inside += 1
        elif votes != [0,0]: ambiguous += 1
    return {'status': 'fail' if intersections or inside else 'not_tested' if ambiguous else 'sampled_clear',
            'bvh_surface_pairs': intersections, 'minimum_vertex_distance_mm': min(distances),
            'inside_body_samples': inside, 'ambiguous_samples': ambiguous, 'sample_stride': stride,
            'scope': 'Full surface BVH overlap plus connector-to-body vertex distances and two-ray parity samples; no physical fit certificate'}


def ray_intervals(body, origin_mm, direction, maximum_hits=64):
    vertices, triangles = world_mesh(body)
    tree = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    origin = Vector(origin_mm)/1000; direction = Vector(direction).normalized(); hits=[]
    for _ in range(maximum_hits):
        hit, normal, index, distance = tree.ray_cast(origin, direction)
        if hit is None: break
        hits.append({'point_mm': list(hit*1000), 'normal': list(normal)})
        origin = hit + direction*1e-8
    return {'hits': hits, 'truncated': len(hits)==maximum_hits,
            'scope': 'Ordered crossings only; caller classifies material intervals, voids, and sample region'}


def save_exports(body, connector, output, spec):
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'
    body['attachment_parameters'] = __import__('json').dumps(spec)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'assembly.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    if connector: connector.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(output/'assembly.glb'), export_format='GLB',
                             use_selection=True, export_apply=True)
    if connector: connector.select_set(False)
    bpy.ops.wm.stl_export(filepath=str(output/'body_mm.stl'), export_selected_objects=True,
                          global_scale=1000, apply_modifiers=True)
