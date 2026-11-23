"""Export explicit display derivatives without changing manufacturing geometry."""
from hashlib import sha256
import bpy
import numpy as np
from glb_export import export_glb


def mesh_key(obj, polygon_budget):
    """Cache plain mesh content; uncertain deformation/attribute cases bypass reuse."""
    mesh = obj.data
    if obj.modifiers or obj.vertex_groups or mesh.shape_keys or mesh.has_custom_normals:
        return None
    digest = sha256()
    formats = {'FLOAT': ('value', 1, 'f'), 'INT': ('value', 1, 'i'),
               'BOOLEAN': ('value', 1, '?'), 'FLOAT_VECTOR': ('vector', 3, 'f'),
               'FLOAT2': ('vector', 2, 'f'), 'FLOAT_COLOR': ('color', 4, 'f'),
               'BYTE_COLOR': ('color', 4, 'f'), 'INT32_2D': ('value', 2, 'i')}
    for attr in mesh.attributes:
        if attr.data_type not in formats:
            return None
        field, width, dtype = formats[attr.data_type]
        values = np.empty(len(attr.data) * width, dtype=dtype)
        try:
            attr.data.foreach_get(field, values)
        except (TypeError, AttributeError):
            return None
        digest.update(repr((attr.name, attr.domain, attr.data_type)).encode())
        digest.update(values.tobytes())
    digest.update(repr([(p.loop_start, p.loop_total, p.use_smooth, p.material_index)
                        for p in mesh.polygons]).encode())
    digest.update(repr([(m.as_pointer() if m else None) for m in mesh.materials]).encode())
    digest.update(repr([(u.name, u.active_render, u.active_clone) for u in mesh.uv_layers]).encode())
    return (mesh.as_pointer(), polygon_budget, digest.hexdigest())


def clear_mesh_cache(cache):
    """Release the cache owned by this module; never pass another cache format."""
    for mesh in cache.values():
        bpy.data.meshes.remove(mesh)
    cache.clear()


def export_derivative(path, objects, *, derivatives, collection, polygon_budget,
                      texture_limit, mesh_cache, exporter=None, **options):
    """Explicit mesh subset and budgets → GLB and per-object derivative report.

    Cache is transient, caller-owned and only populated after successful export.
    All temporary objects, node bindings, images and selection are restored on failure.
    """
    objects, derivatives = list(objects), list(derivatives)
    if (len(set(objects)) != len(objects) or len(set(derivatives)) != len(derivatives)
            or any(o not in objects or o.type != 'MESH' for o in derivatives)):
        raise ValueError('Unique export objects and a mesh derivative subset required')
    if any(type(v) is not int or v <= 0 for v in (polygon_budget, texture_limit)):
        raise ValueError('Explicit positive integer polygon and texture budgets required')
    if bpy.context.mode != 'OBJECT':
        raise ValueError('Derivative export requires Object mode')
    state = [(o, o.select_get(), o.hide_get()) for o in bpy.context.view_layer.objects]
    active = bpy.context.view_layer.objects.active
    copies, meshes, images, bindings, pending, report = [], [], [], [], {}, []
    replacements = {}
    try:
        for obj in derivatives:
            key = mesh_key(obj, polygon_budget)
            cached = mesh_cache.get(key) if key is not None else None
            copy = obj.copy(); copies.append(copy)
            copy.data = (cached or obj.data).copy(); meshes.append(copy.data)
            collection.objects.link(copy); copy.hide_set(False)
            replacements[obj] = copy
            if cached is None and len(copy.data.polygons) > polygon_budget:
                bpy.ops.object.select_all(action='DESELECT')
                copy.select_set(True); bpy.context.view_layer.objects.active = copy
                modifier = copy.modifiers.new('Web derivative only', 'DECIMATE')
                modifier.ratio = polygon_budget / len(copy.data.polygons)
                result = bpy.ops.object.modifier_apply(modifier=modifier.name)
                if 'FINISHED' not in result:
                    raise RuntimeError('Derivative decimation did not finish')
                if copy.data not in meshes:
                    meshes.append(copy.data)
            if cached is None and key is not None and key not in pending:
                pending[key] = copy.data.copy()
            report.append({'object': obj.name, 'source_polygons': len(obj.data.polygons),
                           'preview_polygons': len(copy.data.polygons), 'cache_hit': cached is not None})
        exported = [replacements.get(o, o) for o in objects]
        materials = {m for o in exported if hasattr(o.data, 'materials') for m in o.data.materials if m}
        resized = {}
        for material in materials:
            if not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if node.type != 'TEX_IMAGE' or not node.image or max(node.image.size) <= texture_limit:
                    continue
                original = node.image
                if original not in resized:
                    image = original.copy(); images.append(image)
                    factor = texture_limit / max(image.size)
                    image.scale(max(1, round(image.size[0]*factor)), max(1, round(image.size[1]*factor)))
                    resized[original] = image
                bindings.append((node, original)); node.image = resized[original]
        export_glb(path, exported, unhide=True, exporter=exporter, **options)
        mesh_cache.update(pending); pending = {}
        return report
    finally:
        for node, original in bindings:
            node.image = original
        for image in images:
            bpy.data.images.remove(image)
        for copy in copies:
            bpy.data.objects.remove(copy, do_unlink=True)
        for mesh in set(meshes) | set(pending.values()):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        for obj, selected, hidden in state:
            obj.hide_set(False); obj.select_set(selected); obj.hide_set(hidden)
        bpy.context.view_layer.objects.active = active
