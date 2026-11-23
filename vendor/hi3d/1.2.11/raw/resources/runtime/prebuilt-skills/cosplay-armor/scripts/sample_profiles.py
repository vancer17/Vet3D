"""sample profiles local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, numpy as np, sys, json, math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from runtime_config import config
from stage_cli import cli_arguments, StageFinished, _finish_stage

from cli_schemas import json_config_stage

def execute(configuration):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    CFG = dict(configuration)
    work = Path(CFG['work'])
    Z0 = CFG['forearm_start_mm']
    Z1 = CFG['forearm_end_mm']
    ARM_LENGTH = CFG['arm_length_mm']
    CLEAR = CFG['inner_clearance_mm']
    bpy.ops.wm.open_mainfile(filepath=str(work / 'armor-inspection/source.blend'))
    o = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]
    v = np.load(work / 'armor-inspection/source.npz')['vertices']
    zs = np.linspace(0, 230, 231)
    centers = []
    for z in zs:
        pts = v[abs(v[:, 2] - z) < 3]
        centers.append((np.quantile(pts[:, :2], 0.01, axis=0) + np.quantile(pts[:, :2], 0.99, axis=0)) / 2)
    centers = np.array(centers)
    coef = [np.polyfit(zs[20:201], centers[20:201, i], 3) for i in range(2)]
    centers = np.stack([np.polyval(c, zs) for c in coef], axis=1)
    if CFG.get('armor_center_mode') == 'fixed':
        centers = np.tile([CFG.get('armor_center_x_mm', 0), CFG.get('armor_center_y_mm', 0)], (len(zs), 1))
    bvh = BVHTree.FromObject(o, bpy.context.evaluated_depsgraph_get())
    angles = np.linspace(-math.pi, math.pi, 257)[:-1]
    r = np.full((len(zs), len(angles)), np.nan)
    for j, z in enumerate(zs):
        for k, a in enumerate(angles):
            direction = Vector((math.cos(a), math.sin(a), 0))
            org = Vector((*centers[j], z)) * 0.001
            hit = bvh.ray_cast(org, direction, 0.2)
            if hit[0] is not None:
                r[j, k] = hit[3] * 1000
    for k in range(len(angles)):
        valid = np.isfinite(r[:, k])
        if valid.any():
            r[:, k] = np.interp(zs, zs[valid], r[valid, k])
    for j in range(len(zs)):
        valid = np.isfinite(r[j])
        ks = np.arange(len(angles))
        r[j] = np.interp(ks, np.concatenate([ks[valid] - len(angles), ks[valid], ks[valid] + len(angles)]), np.tile(r[j, valid], 3))
    raw_inner = r.copy()
    if CFG.get('body_region') == 'shin':
        padded = np.pad(r, ((3, 3), (0, 0)), mode='edge')
        stack = []
        for dz in range(7):
            for dt in range(-4, 5):
                stack.append(np.roll(padded[dz:dz + len(r)], dt, axis=1))
        r = np.median(np.stack(stack), axis=0)
        for axis, sigma in [(0, 3.0), (1, 4.0)]:
            radius = int(sigma * 3)
            weights = np.exp(-np.arange(-radius, radius + 1) ** 2 / (2 * sigma * sigma))
            weights /= weights.sum()
            if axis == 0:
                padded = np.pad(r, ((radius, radius), (0, 0)), mode='edge')
                r = sum((w * padded[i:i + len(r)] for i, w in enumerate(weights)))
            else:
                r = sum((w * np.roll(r, i - radius, axis=1) for i, w in enumerate(weights)))
    (work / 'profile-registration.json').write_text(json.dumps({'mode': 'local median and Gaussian registration only' if CFG.get('body_region') == 'shin' else 'first-hit field', 'max_radius_change_mm': float(abs(r - raw_inner).max()), 'mesh_vertices_smoothed': False, 'purpose': 'Avoid discontinuous registration around generated side windows'}, indent=2))
    np.savez(work / 'armor-inner-profile.npz', z=zs, theta=angles, center=centers, inner=r, raw_inner=raw_inner)
    print('inner ranges mm', float(r.min()), float(r.max()), 'center', centers[[0, 20, 110, 200, 230]].tolist())
    a = np.load(work / 'arm-inspection/source.npz')['vertices']
    zarm = np.linspace(Z0 - 15, Z1 + 20, int(round(Z1 - Z0 + 35)) + 1)
    raw = []
    for z in zarm:
        pts = a[abs(a[:, 2] - z) < 2, :2]
        lo = pts.min(0)
        hi = pts.max(0)
        c = (lo + hi) / 2
        ab = (hi - lo) / 2
        f = np.sqrt(np.max(np.sum(((pts - c) / ab) ** 2, axis=1)))
        ab *= f
        raw.append([*c, *ab])
    raw = np.array(raw)
    fits = []
    for i in range(4):
        p = np.polyfit(zarm, raw[:, i], 5)
        fits.append(np.polyval(p, zarm))
    fit = np.stack(fits, axis=1)
    extra = np.max(raw[:, 2:] - fit[:, 2:], axis=0)
    fit[:, 2:] += extra + 0.6
    np.savez(work / 'arm-fit-profile.npz', z=zarm, profile=fit, raw=raw)
    (work / 'fit-profile-summary.json').write_text(json.dumps({'body_region': CFG['body_region'], 'body_length_mm': ARM_LENGTH, 'fit_z_mm': [Z0, Z1], 'allowance_mm': CLEAR, 'ellipse_fit_envelope_extra_mm': extra.tolist(), 'sample_profile': fit[::20].tolist(), 'source': 'Hi3D actual mesh; non-personal digital fixture'}, indent=2))
    print('profile saved', flush=True)

def main(argv=None):
    return json_config_stage(execute, cli_arguments, argv)
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
