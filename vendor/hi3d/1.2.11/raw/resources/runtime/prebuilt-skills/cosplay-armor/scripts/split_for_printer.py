"""Split only the inspected shell into two high-poly keyed FDM parts.
Source UVs are retained by BMesh cuts; print trials still determine tolerances."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, bmesh, numpy as np, sys, json, math, struct, argparse, hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from stage_cli import cli_arguments, StageFinished, _finish_stage

from blender_stl import raw_triangles, stl_bytes

from glb_export import export_glb

def volume(o):
    """Independently callable volume operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    v = abs(bm.calc_volume()) * 1000000000.0
    bm.free()
    return v

def half(name, lower, *, S, source, z):
    """Independently callable half operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    ob = source.copy()
    ob.data = source.data.copy()
    bpy.context.collection.objects.link(ob)
    ob.name = name
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    result = bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces), dist=1e-08, plane_co=(0, 0, z * S), plane_no=(0, 0, 1), clear_outer=lower, clear_inner=not lower)
    edges = [e for e in result['geom_cut'] if isinstance(e, bmesh.types.BMEdge) and e.is_boundary]
    caps = bmesh.ops.holes_fill(bm, edges=edges, sides=0)['faces']
    for f in caps:
        f.smooth = False
    bmesh.ops.triangulate(bm, faces=list(caps))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(ob.data)
    bm.free()
    return ob

def surfaces(zz, tt, *, S, bvh, center):
    """Independently callable surfaces operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    d = Vector((math.cos(tt), math.sin(tt), 0))
    origin = Vector((*center, zz)) * S
    first = bvh.ray_cast(origin, d, 0.3)
    if first[0] is None:
        raise RuntimeError('Missing inner interface ray')
    second = bvh.ray_cast(first[0] + d * 3e-05, d, 0.1)
    if second[0] is None:
        raise RuntimeError('Missing outer interface ray')
    return (first[3] / S, first[3] / S + 0.03 + second[3] / S)

def boolean(ob, tool, mode):
    """Independently callable boolean operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    bpy.context.view_layer.objects.active = ob
    m = ob.modifiers.new(mode + ' precise interface', 'BOOLEAN')
    m.solver = 'MANIFOLD'
    m.operation = mode
    m.object = tool
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(tool, do_unlink=True)

def box(name, loc, dimensions, angle, bevel, *, S):
    """Independently callable box operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=Vector(loc) * S)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = Vector(dimensions) * S
    ob.rotation_euler.z = angle
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    m = ob.modifiers.new('Interface edge chamfer', 'BEVEL')
    m.width = bevel * S
    m.segments = 2
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier=m.name)
    return ob

def stl(o, file):
    triangles = raw_triangles(o, world=True)
    file.write_bytes(stl_bytes(triangles, header=b'High-poly keyed Cosplay shell; mm',
                               padding=b'\0', normal_floor=1e-20))

def glb(name, *, out, preview):
    export_glb(out/name,preview,export_animations=False)

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--scene', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--split-z-mm', type=float, required=True)
    p.add_argument('--side-clearance-mm', type=float, default=0.2)
    p.add_argument('--key-angles-deg', type=float, nargs='+', required=True)
    p.add_argument('--key-width-mm', type=float, default=4.8)
    p.add_argument('--key-thickness-mm', type=float, default=2.0)
    p.add_argument('--minimum-wall-mm', type=float, default=0.6)
    p.add_argument('--render', action='store_true')
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    out = a.output
    out.mkdir(parents=True, exist_ok=True)
    P = out / 'print'
    P.mkdir(exist_ok=True)
    S = 0.001
    z = a.split_z_mm
    bpy.ops.wm.open_mainfile(filepath=str(a.scene))
    source = next((o for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('printable')))
    source.data.calc_loop_triangles()
    sourcehash = hashlib.sha256(a.scene.read_bytes()).hexdigest()
    origvol = volume(source)
    lo = half('Lower shin | integrated alignment tongues', True, S=S, source=source, z=z)
    hi = half('Upper shin | blind receiving pockets', False, S=S, source=source, z=z)
    rawvol = volume(lo) + volume(hi)
    if abs(rawvol - origvol) > max(0.1, origvol * 1e-05):
        raise RuntimeError('Cut did not conserve source volume')
    bvh = BVHTree.FromObject(source, bpy.context.evaluated_depsgraph_get())
    verts = np.array([v.co[:] for v in source.data.vertices]) / S
    rows = verts[abs(verts[:, 2] - z) < 2]
    center = np.array([(rows[:, 0].min() + rows[:, 0].max()) / 2, 0.0])
    center[1] = float(np.quantile(rows[:, 1], 0.998) + 5)
    interfaces = []
    for i, deg in enumerate(a.key_angles_deg, 1):
        t = math.radians(deg)
        width = a.key_width_mm
        root = 2.5
        engagement = 3.5
        bottom = 0.4
        central = surfaces(z, t, S=S, bvh=bvh, center=center)
        halfangle = (width / 2 + a.side_clearance_mm + 0.5) / central[0]
        samples = [surfaces(zz, tt, S=S, bvh=bvh, center=center) for zz in np.linspace(z - root - 0.3, z + engagement + bottom + 0.3, 13) for tt in np.linspace(t - halfangle, t + halfangle, 11)]
        inside = max((v[0] for v in samples))
        outside = min((v[1] for v in samples))
        available = outside - inside
        thick = min(a.key_thickness_mm, available - 2 * a.minimum_wall_mm - 2 * a.side_clearance_mm)
        if thick < 1.6:
            raise RuntimeError(f'Key {i}: insufficient remaining material ({available:.3f} mm)')
        rad = (inside + outside) / 2
        x = center[0] + rad * math.cos(t)
        y = center[1] + rad * math.sin(t)
        tongue = box(f'Key {i}', [x, y, z + (engagement - root) / 2], [thick, width, engagement + root], t, 0.15, S=S)
        boolean(lo, tongue, 'UNION')
        pocket = box(f'Pocket {i}', [x, y, z + (engagement + bottom - 0.2) / 2], [thick + 2 * a.side_clearance_mm, width + 2 * a.side_clearance_mm, engagement + bottom + 0.2], t, 0.15, S=S)
        boolean(hi, pocket, 'DIFFERENCE')
        interfaces.append({'index': i, 'angle_deg': deg, 'center_mm': [x, y, z], 'key_cross_section_mm': [thick, width], 'root_embed_mm': root, 'engagement_mm': engagement, 'side_clearance_mm': a.side_clearance_mm, 'bottom_clearance_mm': bottom, 'sampled_available_wall_mm': available, 'minimum_sampled_radial_margin_mm': (available - thick) / 2 - a.side_clearance_mm, 'purpose': 'Alignment during full-seam adhesive bonding; not a snap joint or sole load-bearing lock.'})
    stl(lo, P / 'lower-shin-keyed-mm.stl')
    stl(hi, P / 'upper-shin-keyed-mm.stl')
    for o in bpy.context.scene.objects:
        if o.type == 'MESH':
            o.hide_render = o not in [lo, hi]
            o.hide_set(o not in [lo, hi])
    source.hide_render = True
    source.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'split-assembly.blend'))
    preview = []
    for src in [lo, hi]:
        dup = src.copy()
        dup.data = src.data.copy()
        bpy.context.collection.objects.link(dup)
        dup.name = src.name + ' | web preview'
        src.hide_render = True
        src.hide_set(True)
        bpy.context.view_layer.objects.active = dup
        m = dup.modifiers.new('Web only', 'DECIMATE')
        m.ratio = min(1, 120000 / len(dup.data.polygons))
        bpy.ops.object.modifier_apply(modifier=m.name)
        dup.hide_set(False)
        preview.append(dup)
    glb('split-assembly.glb', out=out, preview=preview)
    preview[1].location.z += 0.05
    glb('split-exploded.glb', out=out, preview=preview)
    preview[1].location.z -= 0.05
    (out / 'split-design.json').write_text(json.dumps({'source_scene_sha256': sourcehash, 'split_z_mm': z, 'source_volume_mm3': origvol, 'before_keys_sum_mm3': rawvol, 'conservation_difference_mm3': rawvol - origvol, 'source_surface': 'No global remesh or decimation of printable pieces. Source face-corner UV retained by mesh cut.', 'interfaces': interfaces, 'print_orientation': 'Two segments may be oriented separately; inspect actual slicer support.', 'seam_visibility': 'Necessary visible transverse assembly seam at the caller-selected split plane; not claimed invisible.', 'physical_trial': 'not performed', 'joint_use': 'Small alignment tongues only. Bond the full transverse seam with a material-compatible adhesive after fit coupons; not a detachable or certified structural joint.', 'parts': [{'name': o.name, 'height_mm': o.dimensions.z * 1000, 'faces': len(o.data.polygons)} for o in [lo, hi]]}, indent=2))
    if a.render:
        s = bpy.context.scene
        s.cycles.samples = 24
        s.render.resolution_x = 1250
        s.render.resolution_y = 1100
        cam = s.camera
        target = Vector((0, 0, 0.325))
        cam.location = target + Vector((0.35, 1, 0.1))
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        cam.data.ortho_scale = 0.43
        preview[1].location.z += 0.05
        for o in preview:
            o.hide_render = False
        s.render.filepath = str(out / 'split-interface.png')
        bpy.ops.render.render(write_still=True)
    print('SPLIT COMPLETE', json.dumps(interfaces), flush=True)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
