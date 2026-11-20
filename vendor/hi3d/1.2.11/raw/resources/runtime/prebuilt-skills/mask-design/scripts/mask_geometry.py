"""Blender helpers: prepared face patch -> liner; strap coupon; sampled mesh audit.
Usage: blender -b --factory-startup --disable-autoexec --python-exit-code 1
       --python mask_geometry.py -- <command> [options]
All CLI lengths and generated mesh coordinates are millimetres.
"""
import argparse
import hashlib
import json
import math
import random
import struct
import sys
from bisect import bisect_left
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree


import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from mesh_measure import measure_mesh

def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def mesh_mm(obj):
    """Evaluated copy in physical world millimetres; does not modify the source."""
    deps = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(deps)
    me = bpy.data.meshes.new_from_object(evaluated, depsgraph=deps)
    factor = bpy.context.scene.unit_settings.scale_length * 1000
    for v in me.vertices:
        v.co = (obj.matrix_world @ v.co) * factor
    me.update()
    return me


def topology(me):
    measured = measure_mesh(me, area_epsilon=1e-9)
    result = {key: measured[key] for key in ('vertices','faces','boundary_edges','nonmanifold_edges',
              'inconsistent_winding_edges','degenerate_faces','components','bounds_mm')}
    valid = measured['nonmanifold_edges'] == 0 and measured['degenerate_faces'] == 0
    result.update(signed_volume_mm3=measured['signed_volume_mm3'] if valid else None,
                  closed_oriented_topology=bool(measured['faces']) and valid and measured['inconsistent_winding_edges']==0 and measured['signed_volume_mm3']>0,
                  self_intersection='not_tested')
    return result


def tree(me):
    # Use the same triangulation as sampling/export. Independently triangulating
    # nonplanar bevel n-gons can otherwise create false self-hits/thin walls.
    me.calc_loop_triangles()
    return BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(t.vertices) for t in me.loop_triangles], all_triangles=True, epsilon=1e-7)


def samples(me, count, seed=23):
    me.calc_loop_triangles()
    tris = [t for t in me.loop_triangles if t.area > 1e-10]
    if not tris:
        raise ValueError("Cannot sample empty/zero-area mesh")
    cumulative, total = [], 0.0
    for t in tris:
        total += t.area
        cumulative.append(total)
    rng = random.Random(seed)
    for _ in range(count):
        t = tris[min(bisect_left(cumulative, rng.random()*total), len(tris)-1)]
        a, b, c = [me.vertices[i].co for i in t.vertices]
        u, v = math.sqrt(rng.random()), rng.random()
        yield (1-u)*a + u*(1-v)*b + u*v*c, (b-a).cross(c-a).normalized()


def stats(values):
    if not values:
        return {"count": 0, "min": None, "p05": None, "median": None, "p95": None, "max": None}
    v = sorted(values)
    return {"count": len(v), "min": v[0], "p05": v[int(.05*(len(v)-1))],
            "median": v[len(v)//2], "p95": v[int(.95*(len(v)-1))], "max": v[-1]}


def audit(shell, head=None, inner=None, count=3000, minimum_wall=2.4):
    """Evaluate scene meshes, analyze, then free copies even when checks fail."""
    if (head is None) != (inner is None):
        raise ValueError("Supply both head and inner to measure clearance")
    if not 100 <= count <= 100000 or not math.isfinite(minimum_wall) or minimum_wall <= 0:
        raise ValueError("Samples must be 100..100000 and minimum wall finite/positive")
    copies = []
    try:
        for obj in (shell, head, inner):
            copies.append(mesh_mm(obj) if obj is not None else None)
        return audit_meshes(copies[0], shell.name, copies[1], copies[2], count, minimum_wall)
    finally:
        for me in copies:
            if me is not None:
                bpy.data.meshes.remove(me)


def audit_meshes(me, shell_name, hm=None, im=None, count=3000, minimum_wall=2.4):
    """Analyze prepared world-mm meshes without creating scene objects or files."""
    top = topology(me)
    report = {"blender": bpy.app.version_string, "shell": shell_name, "topology": top,
              "status": "sampled_review_only", "global_collision": "not_tested",
              "strap_root_strength": "not_tested", "slicing": "not_tested", "personal_wear_test": "not_tested"}
    bvh = tree(me)
    if top["closed_oriented_topology"]:
        thickness = []
        for p, n in samples(me, count):
            hit = bvh.ray_cast(p - n*.001, -n, 1000)
            if hit[0] is not None:
                thickness.append(hit[3]+.001)
        report["ray_thickness_mm"] = stats(thickness)
        report["ray_thickness_misses"] = count-len(thickness)
        report["samples_below_project_wall_target"] = sum(t < minimum_wall for t in thickness)
        report["project_wall_target_mm"] = minimum_wall
    else:
        report["status"] = "topology_repair_required"
        report["ray_thickness_mm"] = "invalid_topology"
    if hm is not None:
        ht = topology(hm)
        report["head_topology"] = ht
        hb = tree(hm)
        distances, signed, near_zero = [], [], 0
        for p, _ in samples(im, count):
            q, n, _, distance = hb.find_nearest(p)
            if q is None:
                continue
            distances.append(distance)
            # Nearest-normal sign is a screening heuristic, not a global inside test.
            signed.append((p-q).dot(n))
            near_zero += distance < .05
        report["inner_to_head_unsigned_distance_mm"] = stats(distances)
        report["near_contact_samples_under_0_05_mm"] = near_zero
        report["nearest_normal_negative_flags"] = sum(v < -.05 for v in signed) if ht["closed_oriented_topology"] else "invalid_head_topology"
        report["clearance_sampling"] = {"method": "area-weighted inner surface samples to nearest head triangles", "count": count, "seed": 23,
                                           "normal_sign_limit": "Local nearest-normal sign only. Unsigned distances cannot prove nonpenetration; no global collision claim."}
    report["limits"] = "Topology and sampled distances only; no complete self-intersection, global collision, pressure, strength, slicing or comfort validation. Ray thickness can hit another shell and overestimate local wall."
    return report


def make_object(name, vertices, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(vertices, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def active(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def apply(ob, modifier):
    active(ob)
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def mm_scene():
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = .001


def stl_mm(ob, path):
    me = mesh_mm(ob)
    try:
        me.calc_loop_triangles()
        with open(path, "xb") as out:
            out.write(b"mask-design: coordinates in mm".ljust(80, b" "))
            out.write(struct.pack("<I", len(me.loop_triangles)))
            for t in me.loop_triangles:
                a, b, c = [me.vertices[i].co for i in t.vertices]
                n = (b-a).cross(c-a).normalized()
                out.write(struct.pack("<12fH", *n, *a, *b, *c, 0))
    finally:
        bpy.data.meshes.remove(me)


def glb_metres(ob, path):
    """glTF exporter uses raw coordinates; normalize explicitly to metres."""
    require_new_paths([path])
    me = mesh_mm(ob)
    for v in me.vertices:
        v.co /= 1000
    exported = bpy.data.objects.new(ob.name + "_export_metres", me)
    bpy.context.collection.objects.link(exported)
    original_unit = bpy.context.scene.unit_settings.scale_length
    try:
        bpy.context.scene.unit_settings.scale_length = 1
        active(exported)
        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True)
    finally:
        bpy.context.scene.unit_settings.scale_length = original_unit
        bpy.data.objects.remove(exported, do_unlink=True)
        bpy.data.meshes.remove(me)
        active(ob)


def liner(patch, gap, wall, relief_group=None, relief_mm=0):
    """Create inner/shell objects from an open outward patch; mutates the scene."""
    if not all(math.isfinite(v) for v in (gap, wall, relief_mm)) or gap <= 0 or wall <= 0 or relief_mm < 0:
        raise ValueError("Gap/wall must be positive and relief nonnegative, all finite")
    if bpy.data.objects.get("Mask_Shell") or bpy.data.objects.get("Mask_Inner"):
        raise ValueError("Use a prepared revision without existing Mask_Shell/Mask_Inner")
    if patch.modifiers and relief_group:
        raise ValueError("Apply patch modifiers before using a relief vertex group so vertex indices are stable")
    me = mesh_mm(patch)
    try:
        t = topology(me)
        if t["components"] != 1 or t["degenerate_faces"] or t["inconsistent_winding_edges"] or t["nonmanifold_edges"] != t["boundary_edges"] or not t["boundary_edges"]:
            raise ValueError("Patch must be one consistent open 2-manifold surface with only intentional boundaries")
        group = patch.vertex_groups.get(relief_group) if relief_group else None
        if relief_group and group is None:
            raise ValueError("Relief vertex group not found")
        coords = []
        for v in me.vertices:
            w = 0
            if group:
                try:
                    w = group.weight(v.index)
                except RuntimeError:
                    pass
            coords.append(v.co + v.normal*(gap+relief_mm*w))
        faces = [tuple(p.vertices) for p in me.polygons]
        # Remains in the original scene unit convention; do not change the head scale.
        factor = bpy.context.scene.unit_settings.scale_length*1000
        inside = make_object("Mask_Inner", [v/factor for v in coords], faces)
        shell = make_object("Mask_Shell", [v/factor for v in coords], faces)
        solid = shell.modifiers.new("Outward structural wall", "SOLIDIFY")
        solid.thickness = wall/factor
        solid.offset = 1
        solid.use_even_offset = True
        solid.use_quality_normals = True
        apply(shell, solid)
        inside.hide_render = True
        inside.hide_set(True)
        return shell, inside

    finally:
        bpy.data.meshes.remove(me)


def extruded_mesh(polygon, depth):
    """Pure planar polygon extrusion; return vertices/faces."""
    count = len(polygon)
    verts = [(x, y, z) for z in (-depth/2, depth/2) for x, y in polygon]
    faces = [tuple(reversed(range(count))), tuple(range(count, count*2))]
    faces += [(i, (i+1)%count, (i+1)%count+count, i+count) for i in range(count)]
    return verts, faces


def extruded(name, polygon, depth):
    """Create an object from the pure extrusion result."""
    return make_object(name, *extruded_mesh(polygon, depth))


def build_coupon(hole, slot_length, slot_height):
    """Create a dimensioned sample in an empty Blender scene; no file writes."""
    if not (2 <= hole <= 8 and 10 <= slot_length <= 30 and 2 <= slot_height <= 6):
        raise ValueError("Coupon supports hole 2..8, slot length 10..30, slot height 2..6 mm")
    if bpy.context.scene.objects:
        raise ValueError("Coupon requires an empty scene; preserve existing work")
    mm_scene()
    plate = extruded("Strap_Coupon_80x30x4_mm", [(-40,-15),(40,-15),(40,15),(-40,15)], 4)
    r = slot_height/2
    half_centres = (slot_length-slot_height)/2
    capsule = []
    for cx, start in ((half_centres, -90), (-half_centres, 90)):
        for i in range(49):
            a = math.radians(start+180*i/48)
            capsule.append((-18+cx+r*math.cos(a), r*math.sin(a)))
    cutters = [extruded("slot_cutter", capsule, 12),
               extruded("hole_cutter", [(22+hole/2*math.cos(i*math.tau/96), hole/2*math.sin(i*math.tau/96)) for i in range(96)], 12)]
    for cutter in cutters:
        mod = plate.modifiers.new("Through passage", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = cutter
        apply(plate, mod)
        bpy.data.objects.remove(cutter, do_unlink=True)
    bevel = plate.modifiers.new("Smooth cord entry", "BEVEL")
    bevel.width = .6
    bevel.segments = 4
    apply(plate, bevel)
    plate.location.z = 2
    bpy.context.view_layer.update()
    return plate


def audit_coupon(plate, hole, slot_length, slot_height):
    """Measure topology and passages on the actual plate; no file writes."""
    report = audit(plate, count=2000, minimum_wall=2.4)
    probe_mesh = mesh_mm(plate)
    try:
        bvh = tree(probe_mesh)
        probe = lambda x,y: bvh.ray_cast(Vector((x,y,-1)), Vector((0,0,1)), 10)[0] is None
        report["coupon"] = {"hole_nominal_mm": hole, "slot_nominal_mm": [slot_length, slot_height], "plate_nominal_mm": [80,30,4],
                             "centre_passages_open": [probe(22,0), probe(-18,0)],
                             "purpose": "Passage, printer tolerance and cord-edge finish sample only, not a real mask anchor root or strength proof."}
        hole_radii = []
        for i in range(96):
            angle = math.tau*i/96
            direction = Vector((math.cos(angle),math.sin(angle),0))
            hit = bvh.ray_cast(Vector((22,0,2)),direction,20)
            if hit[0] is not None:
                hole_radii.append(hit[3])
        axial = []
        for direction in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0)):
            hit = bvh.ray_cast(Vector((-18,0,2)),Vector(direction),30)
            axial.append(hit[3] if hit[0] is not None else None)
        report["coupon"]["midplane_hole_min_sampled_diameter_mm"] = 2*min(hole_radii) if len(hole_radii)==96 else None
        report["coupon"]["midplane_slot_axial_span_mm"] = [axial[0]+axial[1],axial[2]+axial[3]] if all(v is not None for v in axial) else None
        report["coupon"]["sampled_hole_ring_material_present"] = all(not probe(22+(hole/2+2)*math.cos(i*math.tau/48),(hole/2+2)*math.sin(i*math.tau/48)) for i in range(48))
    finally:
        bpy.data.meshes.remove(probe_mesh)
    if not report["topology"]["closed_oriented_topology"] or not all(report["coupon"]["centre_passages_open"]) or not report["coupon"]["sampled_hole_ring_material_present"] or len(hole_radii)!=96 or any(v is None for v in axial):
        raise ValueError("Coupon geometry failed; inspect the generated geometry")
    return report


def coupon(out, hole, slot_length, slot_height):
    """Build/check/export sample; refuse overwrite, retain partial output on failure."""
    out=Path(out).resolve()
    require_new_paths([out/name for name in ("strap_coupon_mm.stl", "strap_coupon.glb", "strap_coupon.blend", "coupon_audit.json")])
    plate=build_coupon(hole, slot_length, slot_height)
    report=audit_coupon(plate, hole, slot_length, slot_height)
    out.mkdir(parents=True, exist_ok=True)
    stl_mm(plate, out/"strap_coupon_mm.stl")
    glb_metres(plate, out/"strap_coupon.glb")
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"strap_coupon.blend"))
    write_json(out/"coupon_audit.json", report)
    return report


def require_new_paths(paths):
    """Read-only preflight; refuse existing artifacts rather than overwrite."""
    if any(Path(path).exists() for path in paths):
        raise FileExistsError("Output exists; reuse it or choose new revision paths")


def run_liner(source, output, patch_name, gap, wall, group=None, relief=0):
    """Open a prepared scene and save a new shell revision and sampled report."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output:
        raise ValueError("Use a new output file to preserve the input")
    require_new_paths([output, output.with_suffix(".audit.json")])
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False)
    shell, inner = liner(bpy.data.objects[patch_name], gap, wall, group, relief)
    report = audit(shell)
    report["construction"] = {"gap_mm":gap, "wall_mm":wall, "relief_group":group, "relief_mm":relief,
        "limits":"Prepared-patch offset only; no automatic smoothing, collision repair, rounding, straps or ornament integration."}
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    write_json(output.with_suffix(".audit.json"), report)
    return report


def run_audit(source, output, shell_name, head_name=None, inner_name=None, count=3000, minimum_wall=2.4):
    """Open a scene, audit named objects and write a new report; no scene saving."""
    source, output = Path(source).resolve(), Path(output).resolve()
    require_new_paths([output])
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False)
    report = audit(bpy.data.objects[shell_name], bpy.data.objects[head_name] if head_name else None,
                   bpy.data.objects[inner_name] if inner_name else None, count, minimum_wall)
    report["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    write_json(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("coupon")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--hole-mm", type=float, default=4.6)
    p.add_argument("--slot-length-mm", type=float, default=22)
    p.add_argument("--slot-height-mm", type=float, default=3.2)
    p = sub.add_parser("liner")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--patch", default="FacePatch")
    p.add_argument("--gap-mm", required=True, type=float)
    p.add_argument("--wall-mm", type=float, default=2.8)
    p.add_argument("--relief-group")
    p.add_argument("--relief-mm", type=float, default=0)
    p.add_argument("--out", required=True, type=Path)
    p = sub.add_parser("audit")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--shell", default="Mask_Shell")
    p.add_argument("--head")
    p.add_argument("--inner")
    p.add_argument("--samples", type=int, default=3000)
    p.add_argument("--min-wall-mm", type=float, default=2.4)
    p.add_argument("--out", required=True, type=Path)
    a = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if a.command == "coupon":
        # This CLI process is explicitly a disposable empty startup scene.
        bpy.ops.wm.read_factory_settings(use_empty=True)
        report = coupon(a.out, a.hole_mm, a.slot_length_mm, a.slot_height_mm)
    elif a.command == "liner":
        report = run_liner(a.input, a.out, a.patch, a.gap_mm, a.wall_mm, a.relief_group, a.relief_mm)
    else:
        report = run_audit(a.input, a.out, a.shell, a.head, a.inner, a.samples, a.min_wall_mm)
    print(json.dumps({"status": report["status"], "command": a.command}))


if __name__ == "__main__":
    main()
