"""build armor local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

from armor_geometry import annular_liner, back_cutter, boolean, check, desired, fit, mat, mesh, save, solid
import bpy, bmesh, numpy as np, sys, json, math, struct, os
from pathlib import Path
from mathutils import Vector
from runtime_config import config
from stage_cli import cli_arguments, StageFinished, _finish_stage

from cli_schemas import json_config_stage

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
    bpy.ops.wm.open_mainfile(filepath=str(W / 'armor-inspection/source.blend'))
    o = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
    o.name = 'Hi3D art shell — preserved art surface'
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1
    v = np.empty(len(o.data.vertices) * 3, dtype=np.float64)
    o.data.vertices.foreach_get('co', v)
    v = v.reshape(-1, 3) / S
    zold = v[:, 2].copy()
    cx = np.interp(zold, zs, cs[:, 0])
    cy = np.interp(zold, zs, cs[:, 1])
    th = np.arctan2(v[:, 1] - cy, v[:, 0] - cx)
    rr = np.hypot(v[:, 0] - cx, v[:, 1] - cy)
    zi = np.clip(zold, 0, 229.999)
    j = zi.astype(int)
    fz = zi - j
    t = (th + math.pi) / (2 * math.pi) * 256
    a = np.floor(t).astype(int) % 256
    ft = t - np.floor(t)
    b = (a + 1) % 256
    ri = rin[j, a] * (1 - fz) * (1 - ft) + rin[j, b] * (1 - fz) * ft + rin[j + 1, a] * fz * (1 - ft) + rin[j + 1, b] * fz * ft
    newz = Z0 + zold / 230 * (Z1 - Z0)
    f = fit(newz, FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
    ai = f[:, 2] + CLEAR
    bi = f[:, 3] + CLEAR
    target = 1 / np.sqrt((np.cos(th) / ai) ** 2 + (np.sin(th) / bi) ** 2)
    dr = rr - ri
    newr = target + 1.8 + 1.3 * dr
    if CFG.get('body_region') == 'shin':
        newr = target + 5.0 + 6.0 * np.tanh(dr / 6.0)
    vnew = np.stack([f[:, 0] + newr * np.cos(th), f[:, 1] + newr * np.sin(th), newz], axis=1)
    o.data.vertices.foreach_set('co', (vnew * S).ravel())
    o.data.update()
    print('raw radial delta quantiles', np.quantile(dr, [0, 0.01, 0.5, 0.99, 1]).tolist(), flush=True)
    n = 160
    angles = np.linspace(-math.pi, math.pi, n, endpoint=False)
    low = []
    high = []
    for t0 in angles:
        diff = np.abs(np.angle(np.exp(1j * (th - t0))))
        sel = newz[diff < math.pi / n * 1.8]
        low.append(float(sel.min() + 2) if len(sel) else np.nan)
        high.append(float(sel.max() - 2) if len(sel) else np.nan)
    low = np.array(low)
    high = np.array(high)
    for arr in [low, high]:
        idx = np.arange(n)
        ok = np.isfinite(arr)
        arr[:] = np.interp(idx, np.r_[idx[ok] - n, idx[ok], idx[ok] + n], np.tile(arr[ok], 3))
    for _ in range(3):
        low = (np.roll(low, 1) + 2 * low + np.roll(low, -1)) / 4
        high = (np.roll(high, 1) + 2 * high + np.roll(high, -1)) / 4
    inner = mat('Astra regular interior | soft graphite', (0.043, 0.055, 0.068), 0.15, 0.53)
    liner = annular_liner(low, high, n=n, CLEAR=CLEAR, FIT_SCALE=FIT_SCALE, S=S, inner=inner, pf=pf, zf=zf)
    boolean(o, liner, 'UNION')
    boolean(o, solid('Smooth calibrated inner cavity', Z0 - 50, Z1 + 60, 0, inner, CLEAR=CLEAR, FIT_SCALE=FIT_SCALE, S=S, pf=pf, zf=zf), 'DIFFERENCE')
    boolean(o, back_cutter(FIT_SCALE=FIT_SCALE, S=S, Z0=Z0, Z1=Z1, pf=pf, zf=zf), 'DIFFERENCE')
    o.name = 'Cosplay shell | Hi3D exterior + Astra smooth interior'
    o['asset'] = True
    o['printable'] = True
    for name in ['sharp_edge', 'sharp_face', 'custom_normal']:
        a = o.data.attributes.get(name)
        if a:
            o.data.attributes.remove(a)
    if o.data.has_custom_normals:
        o.data.normals_split_custom_set([(0, 0, 0)] * len(o.data.loops))
    for p in o.data.polygons:
        p.use_smooth = True
    slot_rows = []
    for zslot in STRAP_Z:
        for deg in [-145, -45]:
            t0 = math.radians(deg)
            x, y = desired(zslot, t0, 5, CLEAR=CLEAR, FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(float(x) * S, float(y) * S, zslot * S))
            cut = bpy.context.object
            cut.name = '18 x 3.6 mm rounded strap slot'
            cut.dimensions = Vector((30, 3.6, 18)) * S
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            cut.rotation_euler.z = t0
            bpy.context.view_layer.objects.active = cut
            q = cut.modifiers.new('Rounded slot corners', 'BEVEL')
            q.width = 0.8 * S
            q.segments = 4
            bpy.ops.object.modifier_apply(modifier=q.name)
            boolean(o, cut, 'DIFFERENCE')
            slot_rows.append({'z_mm': zslot, 'angle_deg': deg, 'width_mm': 3.6, 'height_mm': 18})
    for slot_i, m in enumerate(o.data.materials):
        if m is None:
            o.data.materials[slot_i] = inner
    if inner.name not in [m.name for m in o.data.materials]:
        o.data.materials.append(inner)
    mi = [m.name for m in o.data.materials].index(inner.name)
    cent = np.empty(len(o.data.polygons) * 3)
    norm = np.empty_like(cent)
    o.data.polygons.foreach_get('center', cent)
    o.data.polygons.foreach_get('normal', norm)
    cent = cent.reshape(-1, 3) / S
    norm = norm.reshape(-1, 3)
    fp = fit(cent[:, 2], FIT_SCALE=FIT_SCALE, pf=pf, zf=zf)
    rad = cent[:, :2] - fp[:, :2]
    dot = (rad * norm[:, :2]).sum(1)
    idx = np.empty(len(o.data.polygons), np.int32)
    o.data.polygons.foreach_get('material_index', idx)
    idx[dot < -0.3 * np.linalg.norm(rad, axis=1)] = mi
    o.data.polygons.foreach_set('material_index', idx)
    pre = set(bpy.context.scene.objects)
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    parts = [o] + [x for x in bpy.context.scene.objects if x not in pre and x.type == 'MESH']
    main = max(parts, key=lambda x: len(x.data.polygons))
    removed = []
    for part in parts:
        if part == main:
            continue
        if len(part.data.polygons) > len(main.data.polygons) * 0.03:
            raise RuntimeError('Unexpected substantial detached component; inspect before removal')
        removed.append({'faces': len(part.data.polygons), 'dimensions_mm': [v * 1000 for v in part.dimensions]})
        bpy.data.objects.remove(part, do_unlink=True)
    o = main
    o.name = 'Cosplay shell | Hi3D exterior + Astra smooth interior'
    o['asset'] = True
    o['printable'] = True
    report = {'removed_disconnected_remnants': removed, 'fit_transverse_scale': FIT_SCALE, 'strap_slots': slot_rows, 'geometry': check(o), 'arm_length_mm': ARM_LENGTH, 'armor_z_mm': [Z0, Z1], 'nominal_inner_allowance_mm': CLEAR, 'nominal_structural_liner_mm': 3.5, 'rear_cut_offset_mm': -5, 'outer_operation': 'continuous radius/center fit of full-resolution Hi3D mesh, regular inner liner union, smooth cavity subtraction and rear opening', 'global_remesh': False, 'source_decimation': False, 'registration_mode': CFG.get('armor_center_mode', 'fitted'), 'source_residual_mapping': '5 + 6*tanh(dr/6) mm over target envelope' if CFG.get('body_region') == 'shin' else '1.8 + 1.3*dr mm over target envelope', 'physical_test': 'not performed', 'changes': 'rear inferred panel trimmed for donning; sculpted front plates and UV preserved', 'source_radial_delta_quantiles_mm': np.quantile(dr, [0, 0.01, 0.5, 0.99, 1]).tolist()}
    (OUT / 'geometry-build.json').write_text(json.dumps(report, indent=2))
    save('armor-built.blend', SAVE=SAVE)
    print('geometry complete', report['geometry'], flush=True)
    with bpy.data.libraries.load(str(W / 'arm-inspection/source.blend'), link=False) as (a, b):
        b.objects = [n for n in a.objects if n == 'Original textured Hi3D surface']
    arm = b.objects[0]
    bpy.context.collection.objects.link(arm)
    arm.name = 'Hi3D anatomical body | digital fixture'
    arm['asset'] = True
    arm['printable'] = False
    arm.scale.x = FIT_SCALE
    arm.scale.y = FIT_SCALE
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    arm.data.materials.clear()
    arm.data.materials.append(mat('Warm gray plaster anatomy', (0.3, 0.28, 0.26), 0, 0.62))
    for name in ['sharp_edge', 'sharp_face', 'custom_normal']:
        a = arm.data.attributes.get(name)
        if a:
            arm.data.attributes.remove(a)
    if arm.data.has_custom_normals:
        arm.data.normals_split_custom_set([(0, 0, 0)] * len(arm.data.loops))
    for p in arm.data.polygons:
        p.use_smooth = True
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.render.threads_mode = 'FIXED'
    sc.render.threads = 2
    sc.render.resolution_x = 1100
    sc.render.resolution_y = 1300
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'AgX'
    sc.world = bpy.data.worlds.new('Quiet studio')
    sc.world.use_nodes = True
    sc.world.node_tree.nodes['Background'].inputs[0].default_value = (0.1, 0.12, 0.15, 1)
    sc.world.node_tree.nodes['Background'].inputs[1].default_value = 0.35
    center = Vector((-0.012, -0.02, ARM_LENGTH * S * 0.5))
    for name, loc, power, size, col in [('Large soft key', (-0.5, -0.8, 0.9), 110, 0.6, (1, 0.92, 0.82)), ('Cool fill', (0.5, -0.1, 0.5), 65, 0.5, (0.75, 0.85, 1)), ('Rim', (0.1, 0.5, 0.65), 125, 0.5, (1, 0.95, 0.9))]:
        d = bpy.data.lights.new(name, 'AREA')
        d.energy = power * 0.25
        d.shape = 'DISK'
        d.size = size
        d.color = col
        l = bpy.data.objects.new(name, d)
        bpy.context.collection.objects.link(l)
        l.location = loc
        l.rotation_euler = (center - l.location).to_track_quat('-Z', 'Y').to_euler()
    d = bpy.data.cameras.new('Hero camera')
    d.type = 'ORTHO'
    d.ortho_scale = ARM_LENGTH * S * 1.16
    cam = bpy.data.objects.new('Hero camera', d)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    cam.location = center + Vector((0.48, -1, 0.22))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = str(OUT / 'hero-draft.png')
    None if CFG['skip_renders'] else bpy.ops.render.render(write_still=True)
    arm.hide_render = True
    center = Vector((-0.016, -0.014, (Z0 + Z1) * S * 0.5))
    cam.location = center + Vector((0.5, 1, 0.6))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = (Z1 - Z0) * S * 1.43
    sc.render.filepath = str(OUT / 'interior-draft.png')
    None if CFG['skip_renders'] else bpy.ops.render.render(write_still=True)
    arm.hide_render = False
    save('wear-draft.blend', SAVE=SAVE)

def main(argv=None):
    return json_config_stage(execute, cli_arguments, argv)
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
