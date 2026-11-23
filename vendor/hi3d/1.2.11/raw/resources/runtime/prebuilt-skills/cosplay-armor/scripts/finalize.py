"""finalize local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

from armor_geometry import annular_liner, back_cutter, boolean, check, desired, fit, mat, mesh, save, solid
import bpy, bmesh, numpy as np, math, json, sys, struct, hashlib
from pathlib import Path
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree
import bpy, bmesh, numpy as np, sys, json, math, struct, os
from pathlib import Path
from mathutils import Vector
from runtime_config import config
from stage_cli import cli_arguments, StageFinished, _finish_stage

from cli_schemas import json_config_stage

from blender_stl import raw_triangles, stl_bytes

from preview_scene import position_camera
from glb_export import export_glb

def skin(z, th, offset, *, FIT_SCALE, S, arm_bvh, pf, zf):
    """Independently callable skin operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    zs0, ts = np.broadcast_arrays(np.asarray(z), np.asarray(th))
    result = []
    for zz, tt in zip(zs0.ravel(), ts.ravel()):
        c = fit(float(zz), FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
        direction = Vector((math.cos(float(tt)), math.sin(float(tt)), 0))
        h = arm_bvh.ray_cast(Vector((*c[:2], float(zz))) * S, direction, 0.3)
        if h[0] is None:
            raise RuntimeError('Arm radial sample missing')
        rad = h[3] / S + offset
        result.append([c[0] + rad * direction.x, c[1] + rad * direction.y])
    a = np.array(result).reshape((*zs0.shape, 2))
    return (a[..., 0], a[..., 1])

def grid_solid(name, outer, inner, m, *, S):
    """Independently callable grid_solid operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    outer = np.asarray(outer)
    inner = np.asarray(inner)
    nz, nt, _ = outer.shape
    N = nz * nt
    v = np.concatenate([outer.reshape(-1, 3), inner.reshape(-1, 3)])
    f = []
    for side in range(2):
        q = side * N
        for j in range(nz - 1):
            for i in range(nt - 1):
                face = (q + j * nt + i, q + j * nt + i + 1, q + (j + 1) * nt + i + 1, q + (j + 1) * nt + i)
                f.append(face if side == 0 else face[::-1])
    for i in range(nt - 1):
        f.extend([(i, N + i, N + i + 1, i + 1), ((nz - 1) * nt + i, (nz - 1) * nt + i + 1, N + (nz - 1) * nt + i + 1, N + (nz - 1) * nt + i)])
    for j in range(nz - 1):
        f.extend([(j * nt, (j + 1) * nt, N + (j + 1) * nt, N + j * nt), (j * nt + nt - 1, N + j * nt + nt - 1, N + (j + 1) * nt + nt - 1, (j + 1) * nt + nt - 1)])
    ob = mesh(name, v, f, m, S=S)
    ob['asset'] = True
    ob['printable'] = False
    return ob

def pad(k, z, *, CFG, FIT_SCALE, S, arm_bvh, fit_media, foam, pf, shell_bvh, zf):
    """Independently callable pad operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    angles = np.linspace(math.radians(-127), math.radians(-65), 100)
    rows = np.linspace(z - 12, z + 12, 25)
    outer = []
    inside = []
    thickness = []
    for zz in rows:
        c = fit(zz, FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
        ro = []
        ri = []
        for tt in angles:
            d = Vector((math.cos(tt), math.sin(tt), 0))
            origin = Vector((*c[:2], zz)) * S
            h = shell_bvh.ray_cast(origin, d, 0.3)
            if h[0] is None:
                raise RuntimeError('Pad shell ray missing')
            r_out = h[3] / S - 0.6
            x, y = skin(zz, tt, 1.0, FIT_SCALE=FIT_SCALE, S=S, arm_bvh=arm_bvh, pf=pf, zf=zf)
            r_skin = math.hypot(float(x) - c[0], float(y) - c[1])
            r_in = max(r_skin, r_out - CFG['pad_thickness_mm'])
            if r_out - r_in < 2:
                raise RuntimeError('Insufficient foam space')
            thickness.append(r_out - r_in)
            ro.append([c[0] + r_out * d.x, c[1] + r_out * d.y, zz])
            ri.append([c[0] + r_in * d.x, c[1] + r_in * d.y, zz])
        outer.append(ro)
        inside.append(ri)
    fit_media.append({'part': f'pad {k}', 'radial_thickness_mm': [min(thickness), max(thickness)], 'shell_recess_mm': 0.6, 'minimum_skin_design_offset_mm': 1.0, 'z_grid_mm': 1})
    return grid_solid(f'Removable fitted foam pad {k}', outer, inside, foam, S=S)

def overlap(k, z, *, FIT_SCALE, S, arm_bvh, pf, web, zf):
    """Independently callable overlap operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    angles = np.linspace(math.radians(78), math.radians(108), 60)
    rows = np.linspace(z - 7.5, z + 7.5, 16)
    surfaces = []
    for ex in [2.5, 1.9]:
        surf = []
        for zz in rows:
            x, y = skin(np.full(len(angles), zz), angles, ex, FIT_SCALE=FIT_SCALE, S=S, arm_bvh=arm_bvh, pf=pf, zf=zf)
            surf.append(np.stack([x, y, np.full(len(angles), zz)], axis=1))
        surfaces.append(surf)
    return grid_solid(f'Hook and loop overlap {k}', *surfaces, web, S=S)

def stl(ob, path):
    triangles = raw_triangles(ob, world=False, precision='float32')
    path.write_bytes(stl_bytes(triangles, header=b'Astra; final mesh; millimeters',
                               padding=b'\0', precision='float32', normal_floor=1e-20))

def camera_at(center, direction, scale, roll=0, *, cam):
    position_camera(cam,center,direction,scale,roll)

def render(name, *, CFG, D, sc):
    """Independently callable render operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    if CFG['skip_renders']:
        return
    sc.render.filepath = str(D / name)
    bpy.ops.render.render(write_still=True)

def glb(name, objs, *, D):
    export_glb(D/name,objs,unhide=True,export_animations=False,export_materials='EXPORT')

def execute(configuration):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    CFG = dict(configuration)
    W = Path(CFG['work'])
    OUT = Path(CFG['out'])
    OUT.mkdir(parents=True, exist_ok=True)
    SAVE = W / 'state'
    SAVE.mkdir(parents=True, exist_ok=True)
    FIT_SCALE = float(CFG['transverse_scale'])
    Z0 = float(CFG['forearm_start_mm'])
    Z1 = float(CFG['forearm_end_mm'])
    CLEAR = float(CFG['inner_clearance_mm'])
    ARM_LENGTH = float(CFG['arm_length_mm'])
    S = 0.001
    STRAP_Z = [Z0 + (Z1 - Z0) * 3 / 14, Z0 + (Z1 - Z0) * 11 / 14]
    I = np.load(W / 'armor-inner-profile.npz')
    F = np.load(W / 'arm-fit-profile.npz')
    zs = I['z']
    cs = I['center']
    rin = I['inner']
    zf = F['z']
    pf = F['profile']
    bpy.ops.wm.open_mainfile(filepath=str(SAVE / 'wear-draft.blend'))
    o = bpy.data.objects['Cosplay shell | Hi3D exterior + Astra smooth interior']
    arm = bpy.data.objects['Hi3D anatomical body | digital fixture']
    arm.hide_render = False
    D = OUT / CFG['variant_name']
    D.mkdir(exist_ok=True)
    P = D / 'print'
    P.mkdir(exist_ok=True)
    arm_bvh = BVHTree.FromObject(arm, bpy.context.evaluated_depsgraph_get())
    foam = mat('Removable graphite foam pads', (0.015, 0.02, 0.025), 0, 0.85)
    web = mat('15 mm charcoal woven straps', (0.025, 0.023, 0.022), 0, 0.8)
    shell_bvh = BVHTree.FromObject(o, bpy.context.evaluated_depsgraph_get())
    fit_media = []
    pads = []
    straps = []
    for k, z in enumerate(STRAP_Z, 1):
        pads.append(pad(k, z, CFG=CFG, FIT_SCALE=FIT_SCALE, S=S, arm_bvh=arm_bvh, fit_media=fit_media, foam=foam, pf=pf, shell_bvh=shell_bvh, zf=zf))
        th0 = math.radians(-145)
        th1 = math.radians(-45)
        outer = []
        inside = []
        for zz in np.linspace(z - 7.5, z + 7.5, 16):
            path = []
            for ex in [8, 5, 2]:
                x, y = desired(z, th0, ex, CLEAR=CLEAR, FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
                path.append([float(x), float(y), zz])
            for angle in np.linspace(th0, th1 - 2 * math.pi, 180):
                x, y = skin(zz, angle, CFG['strap_skin_offset_mm'], FIT_SCALE=FIT_SCALE, S=S, arm_bvh=arm_bvh, pf=pf, zf=zf)
                path.append([float(x), float(y), zz])
            for ex in [2, 5, 8]:
                x, y = desired(z, th1, ex, CLEAR=CLEAR, FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
                path.append([float(x), float(y), zz])
            path = np.array(path)
            t = np.gradient(path, axis=0)
            t[:, :2] /= np.linalg.norm(t[:, :2], axis=1)[:, None]
            norm = np.stack([-t[:, 1], t[:, 0], np.zeros(len(t))], axis=1)
            outer.append(path + norm * 0.55)
            inside.append(path - norm * 0.55)
        straps.append(grid_solid(f'15 mm webbing threaded through slots {k}', outer, inside, web, S=S))
        straps.append(overlap(k, z, FIT_SCALE=FIT_SCALE, S=S, arm_bvh=arm_bvh, pf=pf, web=web, zf=zf))
    (D / 'fit-media-design.json').write_text(json.dumps({'method': 'Full-width 1 mm Z grids sampled against actual skin and actual shell; digital offsets, no foam compression or cloth simulation', 'pad_thickness_cap_mm': CFG['pad_thickness_mm'], 'pads': fit_media, 'strap_center_skin_offset_mm': CFG['strap_skin_offset_mm'], 'strap_thickness_mm': 1.1}, indent=2))
    stl(o, P / 'cosplay-shell-mm.stl')
    coupon = o.copy()
    coupon.data = o.data.copy()
    bpy.context.collection.objects.link(coupon)
    coupon.name = 'Shell and strap fit coupon'
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, (STRAP_Z[0] + 1) * S))
    cut = bpy.context.object
    cut.dimensions = Vector((0.4, 0.4, 0.032))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    boolean(coupon, cut, 'INTERSECT')
    stl(coupon, P / 'fit-slot-coupon-mm.stl')
    bpy.data.objects.remove(coupon, do_unlink=True)
    assets = [o, arm, *pads, *straps]
    sc = bpy.context.scene
    sc.render.resolution_x = 1100 if CFG['body_region'] == 'shin' else 1300
    sc.render.resolution_y = 1400 if CFG['body_region'] == 'shin' else 950
    sc.cycles.samples = 32
    cam = sc.camera
    camera_at((-0.012, -0.02, ARM_LENGTH * S * 0.5), (0.28, -1, -0.03) if CFG['body_region'] == 'shin' else (0.28, -1, 0.1), ARM_LENGTH * S * 1.11, 0 if CFG['body_region'] == 'shin' else 55, cam=cam)
    render('hero.png', CFG=CFG, D=D, sc=sc)
    camera_at((-0.015, -0.014, (Z0 + Z1) * S * 0.5), (0.45, 1, 0.35), (Z1 - Z0) * S * 1.52, 0, cam=cam)
    render('rear-worn.png', CFG=CFG, D=D, sc=sc)
    arm.hide_render = True
    camera_at((-0.015, -0.014, (Z0 + Z1) * S * 0.5), (0.45, 1, 0.35), (Z1 - Z0) * S * 1.52, 0, cam=cam)
    render('interior-and-straps.png', CFG=CFG, D=D, sc=sc)
    for ob in pads + straps:
        ob.hide_render = True
    camera_at((-0.015, -0.014, (Z0 + Z1) * S * 0.5), (0.45, 1, 0.35), (Z1 - Z0) * S * 1.52, 0, cam=cam)
    render('smooth-interior.png', CFG=CFG, D=D, sc=sc)
    camera_at((-0.015, -0.014, (Z0 + Z1) * S * 0.5), (0.3, -1, 0.12), (Z1 - Z0) * S * 1.48, -12, cam=cam)
    render('armor-detail.png', CFG=CFG, D=D, sc=sc)
    for ob in pads + straps:
        ob.hide_render = False
    arm.hide_render = False
    camera_at((-0.012, -0.02, ARM_LENGTH * S * 0.5), (0.28, -1, -0.03) if CFG['body_region'] == 'shin' else (0.28, -1, 0.1), ARM_LENGTH * S * 1.11, 0 if CFG['body_region'] == 'shin' else 55, cam=cam)
    bpy.ops.wm.save_as_mainfile(filepath=str(D / 'scene.blend'))
    previews = []
    preview_info = []
    for src in assets:
        dup = src.copy()
        dup.data = src.data.copy()
        bpy.context.collection.objects.link(dup)
        dup.name = src.name + ' | web preview'
        src.hide_render = True
        src.hide_set(True)
        dup.hide_render = False
        dup.hide_set(False)
        target = 210000 if src == o else 170000 if src == arm else None
        if target and len(dup.data.polygons) > target:
            bpy.context.view_layer.objects.active = dup
            q = dup.modifiers.new('Browser preview only', 'DECIMATE')
            q.ratio = target / len(dup.data.polygons)
            q.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=q.name)
        previews.append(dup)
        preview_info.append({'object': src.name, 'source_faces': len(src.data.polygons), 'web_faces': len(dup.data.polygons)})
    glb('wear.glb', previews, D=D)
    glb('armor.glb', [previews[0], *previews[2:]], D=D)
    glb('arm.glb', [previews[1]], D=D)
    for ob in previews:
        ob.hide_render = False
    (D / 'web-preview.json').write_text(json.dumps({'method': 'Preview-only decimation; original Hi3D and final high-poly native/STL supplied separately', 'parts': preview_info, 'body_fixture': 'Independent genuine Hi3D body reference, not a measured person', 'parameters': CFG}, ensure_ascii=False, indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(SAVE / 'preview-scene.blend'))
    print('Final assets saved', flush=True)

def main(argv=None):
    return json_config_stage(execute, cli_arguments, argv)
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
