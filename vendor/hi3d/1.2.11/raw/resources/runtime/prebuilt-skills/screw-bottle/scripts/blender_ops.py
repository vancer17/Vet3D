"""Blender mesh effects and whole-solid screw checks. Working coordinates are mm."""
import math
import bpy
import bmesh
from mathutils import Matrix, Vector
from pose_math import axis_pose
from geometry import finite, integer, screw_lift, profile_radius
from mathutils.bvhtree import BVHTree


import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from mesh_measure import measure_mesh

def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def mesh_object(name, vertices, faces, material=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces); mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if material is not None:
        mesh.materials.append(material)
    return obj


def discard(obj):
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def world_copy(obj, unit_mm=1.0):
    """Evaluate modifiers and transforms into a new mm mesh; retain original UV/materials."""
    if obj.type != 'MESH' or finite(unit_mm, 'unit_mm') <= 0:
        raise ValueError('Mesh and positive millimetres per source unit required')
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=bpy.context.evaluated_depsgraph_get())
    mesh.transform(Matrix.Scale(unit_mm, 4) @ evaluated.matrix_world)
    result = bpy.data.objects.new(obj.name + ' copy', mesh)
    bpy.context.collection.objects.link(result)
    # Exact-position weld removes glTF UV split vertices without a distance-based reshape.
    bm = bmesh.new(); bm.from_mesh(mesh)
    groups = {}; targetmap = {}
    for vertex in bm.verts:
        key = tuple(vertex.co)
        if key in groups:
            targetmap[vertex] = groups[key]
        else:
            groups[key] = vertex
    if targetmap:
        bmesh.ops.weld_verts(bm, targetmap=targetmap)
    bm.to_mesh(mesh); bm.free()
    return result


def topology(obj):
    """Local mm metrics; does not detect self intersection or certify containment."""
    measured = measure_mesh(obj.data, area_epsilon=1e-12, area_inclusive=True)
    return {key: measured[key] for key in ('vertices','faces','components','boundary_edges',
            'nonmanifold_edges','degenerate_faces','finite','signed_volume_mm3')}


def require_solid(obj):
    result = topology(obj)
    if (not result['finite'] or result['faces'] == 0 or result['nonmanifold_edges'] or
            result['degenerate_faces'] or result['signed_volume_mm3'] <= 0):
        raise ValueError('A finite, nonempty, outward closed solid is required: ' + obj.name)
    return result


def align_material_slots(target, cutter):
    """Align temporary cutter indices, so new boolean faces use their intended material."""
    originals = list(cutter.data.materials)
    indices = [p.material_index for p in cutter.data.polygons]
    mapping = {}
    for i, material in enumerate(originals):
        if material not in list(target.data.materials):
            target.data.materials.append(material)
        mapping[i] = list(target.data.materials).index(material)
    cutter.data.materials.clear()
    for material in target.data.materials:
        cutter.data.materials.append(material)
    for polygon, old in zip(cutter.data.polygons, indices):
        polygon.material_index = mapping.get(old, 0)


def boolean_copy(target, cutter, operation, name='Boolean result'):
    """Exact boolean in world mm, preserving both inputs. Caller owns returned mesh."""
    if operation not in ('DIFFERENCE', 'UNION', 'INTERSECT'):
        raise ValueError('Unsupported boolean operation')
    result = world_copy(target)
    tool = world_copy(cutter)
    try:
        align_material_slots(result, tool)
        activate(result)
        mod = result.modifiers.new('Exact ' + operation, 'BOOLEAN')
        mod.operation = operation; mod.solver = 'EXACT'; mod.object = tool
        if hasattr(mod, 'material_mode'):
            mod.material_mode = 'INDEX'
        bpy.ops.object.modifier_apply(modifier=mod.name)
        result.name = name
        return result
    except BaseException:
        discard(result)
        raise
    finally:
        discard(tool)


def screw_matrix(center_mm, axis, angle_rad, lift_mm):
    """World-space rigid pose, independent of an imported object's rotation mode."""
    return Matrix(axis_pose(center_mm,axis,angle_rad,lift_mm).tolist())


def intersection_check(body, cap):
    """Full solid intersection catches containment as well as crossing surfaces."""
    require_solid(body); require_solid(cap)
    result = boolean_copy(body, cap, 'INTERSECT', 'Intersection probe')
    try:
        metrics = topology(result)
        return {'status': 'clear' if metrics['faces'] == 0 else 'collision',
                'intersection_faces': metrics['faces'],
                'intersection_volume_mm3': abs(metrics['signed_volume_mm3'])}
    finally:
        discard(result)


def check_screw_path(bodies, caps, center_mm, axis, pitch_mm, angles_deg, *, hand=1, unit_mm=1.0):
    """Snapshot closed objects once, then check every whole-solid pair at each screw pose."""
    if not bodies or not caps or len(set(bodies + caps)) != len(bodies + caps):
        raise ValueError('Distinct nonempty body/cap object lists required')
    if not angles_deg or angles_deg[0] != 0:
        raise ValueError('Pose samples must begin at the closed angle 0')
    angles = [math.radians(finite(x, 'angle_deg')) for x in angles_deg]
    screw_matrix(center_mm, axis, 0, 0)
    for angle in angles:
        if screw_lift(pitch_mm, angle, hand) < 0:
            raise ValueError('Only outward opening poses are supported')
    copies = []
    try:
        for obj in bodies + caps:
            copy = world_copy(obj, unit_mm); copies.append(copy); require_solid(copy)
        fixed, moving = copies[:len(bodies)], copies[len(bodies):]
        rows = []
        for degrees, angle in zip(angles_deg, angles):
            lift = screw_lift(pitch_mm, angle, hand)
            matrix = screw_matrix(center_mm, axis, angle, lift)
            for obj in moving:
                obj.matrix_world = matrix
            bpy.context.view_layer.update()
            pairs = [dict(intersection_check(a, b), body=bodies[i].name, cap=caps[j].name)
                     for i, a in enumerate(fixed) for j, b in enumerate(moving)]
            rows.append({'angle_deg': degrees, 'lift_mm': lift, 'pairs': pairs})
        return {'status': 'sampled_clear' if all(p['status'] == 'clear' for r in rows for p in r['pairs']) else 'failed',
                'poses': rows, 'units': 'mm',
                'scope': 'Whole solids at listed poses only; not continuous swept-volume or self-intersection proof.'}
    finally:
        for obj in copies:
            discard(obj)


def point_location(tree, point_mm, epsilon_mm=1e-5):
    """Three-ray solid parity; boundary/ambiguous points are not silently accepted."""
    point = Vector(point_mm)
    nearest = tree.find_nearest(point)
    if nearest[0] is None:
        raise ValueError('Empty spatial tree')
    if nearest[3] <= epsilon_mm:
        return 'boundary'
    parity = []
    for direction in ((.817, .431, .382), (-.257, .911, .324), (.311, -.537, .784)):
        ray = Vector(direction).normalized(); origin = point.copy(); count = 0
        for _ in range(256):
            hit, _, _, _ = tree.ray_cast(origin, ray)
            if hit is None:
                parity.append(count % 2)
                break
            count += 1; origin = hit + ray * epsilon_mm
        else:
            raise ValueError('Solid parity ray did not terminate')
    return ('inside' if parity[0] else 'outside') if len(set(parity)) == 1 else 'ambiguous'


def probe_points(obj, points_mm, unit_mm=1.0):
    copy = world_copy(obj, unit_mm)
    try:
        require_solid(copy)
        tree = BVHTree.FromObject(copy, bpy.context.evaluated_depsgraph_get())
        return [{'point_mm': list(p), 'location': point_location(tree, p)} for p in points_mm]
    finally:
        discard(copy)


def sample_radial_wall(source, profile, z_values_mm, angles, *, unit_mm=1.0):
    """Radial clearance to an uncut solid in calibrated +Z mm coordinates.

    This is a finite sampling diagnostic, not global shortest wall thickness.
    The caller calibrates the vessel axis to X=Y=0 before calling.
    """
    integer(angles, 'angles', 8)
    if not z_values_mm:
        raise ValueError('At least one height required')
    copy = world_copy(source, unit_mm)
    try:
        require_solid(copy)
        tree = BVHTree.FromObject(copy, bpy.context.evaluated_depsgraph_get())
        minimum = math.inf; at = None; count = 0
        for z in z_values_mm:
            radius = profile_radius(profile, z)
            origin = Vector((0, 0, z))
            if point_location(tree, origin) != 'inside':
                raise ValueError('Section center is not inside the uncut exterior')
            for j in range(angles):
                theta = math.tau*j/angles
                hit, _, _, distance = tree.ray_cast(origin, Vector((math.cos(theta), math.sin(theta), 0)))
                if hit is None:
                    raise ValueError('Section ray missed the exterior')
                count += 1; wall = distance-radius
                if wall < minimum:
                    minimum = wall; at = [z, math.degrees(theta)]
        return {'samples': count, 'minimum_radial_wall_mm': minimum, 'at_z_angle_deg': at,
                'scope': 'Listed heights and evenly spaced angles on the original solid; radial distance only.'}
    finally:
        discard(copy)
