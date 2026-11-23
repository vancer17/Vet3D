"""Ribbon geometry and explicit Blender adapters; coordinates are world-space."""

import math
import random

from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree


def resample_path(points, count):
    """Return evenly spaced Vectors, rejecting nonfinite/zero-length paths."""
    if count < 2 or len(points) < 2:
        raise ValueError('A guide and its resampling need at least two points')
    path = [Vector(point) for point in points]
    if any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in path):
        raise ValueError('Guide coordinates must be finite XYZ values')
    # Remove repeated adjacent control points before sampling tangents.
    clean = [path[0]]
    for point in path[1:]:
        if (point - clean[-1]).length > 1e-9:
            clean.append(point)
    lengths = [0.0]
    for a, b in zip(clean, clean[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    if lengths[-1] < 1e-7:
        raise ValueError('Zero-length hair guide')
    result, index = [], 0
    for i in range(count):
        distance = lengths[-1] * i / (count - 1)
        while index < len(clean) - 2 and lengths[index + 1] < distance:
            index += 1
        factor = (distance - lengths[index]) / (lengths[index + 1] - lengths[index])
        result.append(clean[index].lerp(clean[index + 1], factor))
    return result


def ribbon_frame(tangent, normal, previous):
    """Return a stable lateral direction and a surface-facing offset normal."""
    sideways = tangent.cross(normal)
    if sideways.length < .01:
        sideways = (previous - tangent * previous.dot(tangent)) if previous is not None else Vector((0, 0, 0))
    if sideways.length < 1e-8:
        axis = min((Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))), key=lambda a: abs(a.dot(tangent)))
        sideways = tangent.cross(axis)
    sideways.normalize()
    if previous is not None and sideways.dot(previous) < 0:
        sideways.negate()
    outward = sideways.cross(tangent).normalized()
    if outward.dot(normal) < 0:
        outward.negate()
    return sideways, outward


def transport_frames(path, root_normal):
    """Carry a root frame by minimal tangent rotation, without surface queries.

    Paths must already be smooth: resampling cannot fair a noisy input curve.
    Reject sampled tangent reversals, whose minimal rotation is ambiguous.
    """
    tangents = []
    for j in range(len(path)):
        tangent = path[min(j + 1, len(path) - 1)] - path[max(j - 1, 0)]
        if tangent.length < 1e-9:
            raise ValueError('Guide reverses direction at a sampled point')
        tangents.append(tangent.normalized())
    normal_length = math.hypot(*root_normal)
    normal = Vector(tuple(v / normal_length for v in root_normal))
    sideways, _ = ribbon_frame(tangents[0], normal, None)
    frames = [(sideways.copy(), sideways.cross(tangents[0]).normalized())]
    for before, tangent in zip(tangents, tangents[1:]):
        if before.dot(tangent) < -0.9999:
            raise ValueError('Smooth the guide before transporting a reversing frame')
        sideways = before.rotation_difference(tangent) @ sideways
        sideways = (sideways - tangent * sideways.dot(tangent)).normalized()
        frames.append((sideways.copy(), sideways.cross(tangent).normalized()))
    return frames


def build_card_geometry(paths, spec, atlas_columns, clearance, nearest_surface, seed,
                        placement='head_surface'):
    """Compute arrays only; placement selects guide transport or legacy contact.

    Does not mutate a Blender scene or the caller's random generator. Invalid
    paths fail explicitly rather than silently increasing reported card counts.
    guides uses spec.root_normal and never calls nearest_surface. head_surface
    requires nearest_surface(point) -> (point, normal), and preserves old output.
    """
    if placement not in ('guides', 'head_surface'):
        raise ValueError('Unknown placement mode')
    if placement == 'head_surface' and nearest_surface is None:
        raise ValueError('head_surface placement needs a surface query')
    rng = random.Random(seed)
    vertices, faces, uvs, card_ids = [], [], [], []
    segments, columns = spec['segments'], spec['columns']
    width, offset, lanes = spec['width'], spec['offset'], spec['lanes']
    angles = spec.get('section_angles_degrees', [0])
    for path_id, points in enumerate(paths):
        path = resample_path(points, segments + 1)
        frames = transport_frames(path, spec['root_normal']) if placement == 'guides' else None
        variation = rng.uniform(.8, 1.17)
        for section_id, degrees in enumerate(angles):
            card_id = path_id * len(angles) + section_id
            lane = lanes[card_id % len(lanes)]
            previous, base = None, len(vertices)
            for j, point in enumerate(path):
                t = j / segments
                tangent = path[min(j + 1, segments)] - path[max(j - 1, 0)]
                if tangent.length < 1e-9:
                    raise ValueError('Guide reverses direction at a sampled point')
                tangent.normalize()
                if frames is None:
                    _, normal = nearest_surface(point)
                    sideways, outward = ribbon_frame(tangent, normal, previous)
                    previous = sideways.copy()
                else:
                    sideways, outward = frames[j]
                # The clump shares one displaced centerline; rotate its sections
                # around it, rather than displacing each crossed ribbon apart.
                center = point + outward * offset * math.sin(math.pi * min(1, t * 2))
                if degrees:
                    rotation = Quaternion(tangent, math.radians(degrees))
                    sideways, outward = rotation @ sideways, rotation @ outward
                taper = (.45 + .55 * min(1, t * 9)) * (1 - .76 * t**3)
                for k in range(columns + 1):
                    x = k / columns - .5
                    vertex = center + sideways * (width * variation * taper * x)
                    arch_width = width * taper if frames is not None else width
                    vertex += outward * (arch_width * .11 * (1 - (2 * x)**2))
                    if placement == 'head_surface':
                        hit, hit_normal = nearest_surface(vertex)
                        if (vertex - hit).dot(hit_normal) < clearance:
                            vertex = hit + hit_normal * clearance
                    vertices.append(tuple(vertex))
                    uvs.append(((lane + .035 + k / columns * .93) / atlas_columns, .01 + t * .98))
                if j:
                    for k in range(columns):
                        a = base + (j - 1) * (columns + 1) + k
                        b = a + columns + 1
                        faces.append((a, b, b + 1, a + 1))
                        card_ids.append(card_id)
    return dict(vertices=vertices, faces=faces, uvs=uvs, card_ids=card_ids,
                card_count=len(paths) * len(angles))


def surface_query(surface, depsgraph):
    """Snapshot an evaluated mesh into a BVH; always release temporary mesh."""
    evaluated = surface.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        if mesh is None or not mesh.polygons:
            raise ValueError('Head surface needs evaluated mesh faces')
        tree = BVHTree.FromPolygons(
            [evaluated.matrix_world @ v.co for v in mesh.vertices],
            [p.vertices[:] for p in mesh.polygons], all_triangles=False)
    finally:
        evaluated.to_mesh_clear()

    def nearest(point):
        hit, normal, _, _ = tree.find_nearest(point)
        if hit is None or normal.length < 1e-8:
            raise ValueError('No valid surface normal found')
        return hit, normal.normalized()

    return nearest


def create_card_object(bpy, name, geometry, material, collection, uv_name):
    """Create a world-space mesh with UVs and per-face card_id; caller owns it."""
    mesh = bpy.data.meshes.new(name)
    obj = None
    try:
        mesh.from_pydata(geometry['vertices'], [], geometry['faces'])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        mesh.materials.append(material)
        uv = mesh.uv_layers.new(name=uv_name)
        for polygon in mesh.polygons:
            polygon.use_smooth = True
            for loop_id in polygon.loop_indices:
                uv.data[loop_id].uv = geometry['uvs'][mesh.loops[loop_id].vertex_index]
        attribute = mesh.attributes.new('card_id', 'INT', 'FACE')
        for item, value in zip(attribute.data, geometry['card_ids']):
            item.value = value
        obj['card_count'] = geometry['card_count']
        obj['generated_by'] = 'hair-cards'
        return obj
    except BaseException:
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise
