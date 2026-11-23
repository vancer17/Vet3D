"""Build the separately printable 10-part shoulder-snap cart. Units mm; no API calls."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import argparse, json, hashlib, struct, shutil
from pathlib import Path
import numpy as np
from solid_tools import M, cube, stl, write_solid
from diy_snap_geometry import pin, wheel, socket, compressed_mesh, release_tool
from stage_cli import cli_arguments, StageFinished, _finish_stage

def sha(p):
    """Independently callable sha operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def good(s):
    """Independently callable good operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    assert s.status() == M.Error.NoError and s.volume() > 0 and (len(s.decompose()) == 1), (s.status(), s.volume(), len(s.decompose()))

def readstl(p):
    """Independently callable readstl operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    b = Path(p).read_bytes()
    dt = np.dtype([('n', '<f4', (3,)), ('v', '<f4', (3, 3)), ('a', '<u2')])
    n = struct.unpack_from('<I', b, 80)[0]
    assert len(b) == 84 + 50 * n
    t = np.frombuffer(b, dtype=dt, offset=84, count=n)['v']
    v, inv = np.unique(t.reshape(-1, 3), axis=0, return_inverse=True)
    s = M.Manifold(M.Mesh(v, np.asarray(inv.reshape(-1, 3), np.uint32)))
    good(s)
    return s

def place(s, x, side):
    """Independently callable place operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    return (s.mirror((0, 1, 0)) if side < 0 else s).translate((x, 0, 0))

def writeprint(s, path, rot=(0, 0, 0)):
    """Independently callable writeprint operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    good(s)
    ss = s.rotate(rot)
    b = ss.bounding_box()
    v = (-(b[0] + b[3]) / 2, -(b[1] + b[4]) / 2, -b[2])
    ss = ss.translate(v)
    stl(ss, path)
    return (list(rot), list(v))

def savepart(name, s, kind, center=None, rot=(0, 0, 0), deformed=None, *, elastic, out, rows, solids):
    """Independently callable savepart operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    good(s)
    file = f'print/{name}.stl'
    rr, tt = writeprint(s, out / file, rot)
    write_solid(s, out / 'parts' / f'{name}.npz')
    solids[name] = s
    row = {'id': name, 'kind': kind, 'file': file, 'assembly_npz': f'parts/{name}.npz', 'assembly_bounds_mm': s.bounding_box(), 'volume_mm3': s.volume(), 'axis_center_mm': center, 'print_rotation_deg': rr, 'print_translation_mm': tt, 'sha256': sha(out / file)}
    if deformed is not None:
        write_solid(deformed, out / 'parts' / f'{name}-compressed.npz')
        row['compressed_npz'] = f'parts/{name}-compressed.npz'
        elastic[name] = deformed
    rows.append(row)

def pair(label, x, y, tol=1e-06, *, checks):
    """Independently callable pair operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    q = x ^ y
    assert q.status() == M.Error.NoError
    vol = abs(q.volume())
    checks.append({'pair': label, 'intersection_mm3': vol})
    assert vol < tol, (label, vol)

def maxshift(s, obstacles, vec, limit=2):
    """Independently callable maxshift operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    lo, hi = (0.0, limit)
    for _ in range(29):
        mid = (lo + hi) / 2
        hit = False
        for b in obstacles:
            q = s.translate(np.asarray(vec) * mid) ^ b
            assert q.status() == M.Error.NoError
            if abs(q.volume()) > 1e-07:
                hit = True
                break
        if hit:
            hi = mid
        else:
            lo = mid
    return lo

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--source-case', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for d in ['parts', 'print', 'coupons', 'source', 'interface']:
        (out / d).mkdir(exist_ok=True)
    c = json.loads(a.config.read_text())
    old = json.loads((a.source_case / 'construction.json').read_text())
    assert old['board']['length_mm'] == 100 and old['board']['width_mm'] == 62 and (abs(old['board']['deck_top_mm'] - 29) < 1e-05), 'Current adapter preserves this original deck layout; do not silently substitute another source.'
    assert c['wheel_radius_mm'] == 11 and c['wheelbase_mm'] == 68 and (c['track_mm'] == 72), 'Original foot deck requires independent review before changing the wheel layout.'
    charfile = a.source_case / 'print/character-with-blind-foot-sockets.stl'
    deckfile = a.source_case / 'print/skateboard-with-integrated-pegs-and-trucks.stl'
    shutil.copy2(charfile, out / 'print/character-with-blind-foot-sockets.stl')
    deck = readstl(deckfile).trim_by_plane((0, 0, 1), 21.65)
    localpin, localwheel, localseat = (pin(c), wheel(c), socket(c))
    for s in [localpin, localwheel, localseat]:
        good(s)
    rows = []
    solids = {}
    elastic = {}
    wheelcenters = []
    L = c['beam_root_y_mm'] - c['barb_back_y_mm']
    t = c['tail_halfwidth_mm'] - c['slot_root_radius_mm']
    delta = c['tail_halfwidth_mm'] + c['barb_projection_mm'] - c['socket_tail_width_mm'] / 2
    visual_delta = delta + c['animation_safety_clearance_mm']
    cp, _, _ = compressed_mesh(localpin, c, visual_delta)
    good(cp)
    i = 0
    for x in [-c['wheelbase_mm'] / 2, c['wheelbase_mm'] / 2]:
        deck += cube((12, 62, 6.7), (x, 0, 21.85))
        for side in [-1, 1]:
            i += 1
            deck += place(localseat, x, side)
            center = [x, side * c['track_mm'] / 2, c['wheel_radius_mm']]
            wheelcenters.append(center)
            savepart(f'wheel-{i}', place(localwheel, x, side), 'rounded rotating wheel', center, (90 * side, 0, 0), elastic=elastic, out=out, rows=rows, solids=solids)
            savepart(f'pin-{i}', place(localpin, x, side), 'fixed shoulder spindle with releaseable snap tail', [x, side * 27, c['wheel_radius_mm']], deformed=place(cp, x, side), elastic=elastic, out=out, rows=rows, solids=solids)
    savepart('chassis', deck, 'original foot deck and four integral supported D journals', elastic=elastic, out=out, rows=rows, solids=solids)
    couponrows = []
    for j, off in enumerate(c['coupon_fit_offsets_mm'], 1):
        for label, s, rot in [('seat', socket(c, off), (0, 0, 0)), ('wheel', wheel(c, off), (90, 0, 0))]:
            name = f'{label}-fit-{j}'
            file = f'coupons/{name}.stl'
            rr, tt = writeprint(s, out / file, rot)
            couponrows.append({'id': name, 'file': file, 'offset_per_side_mm': off, 'seat_radius_gap_mm': c['seat_radial_clearance_mm'] + off, 'tail_width_gap_per_side_mm': c['socket_tail_width_mm'] / 2 + off - c['tail_halfwidth_mm'], 'wheel_radial_gap_mm': c['wheel_radial_clearance_mm'] + off, 'print_rotation_deg': rr, 'print_translation_mm': tt, 'sha256': sha(out / file), 'purpose': 'Real local seat and wheel, use with the same complete test shoulder pin; offset labels are CAD gaps, not tested fit.'})
    for name, s in [('complete-test-pin', localpin), ('rigid-release-fork', release_tool(c))]:
        file = f'coupons/{name}.stl'
        rr, tt = writeprint(s, out / file)
        couponrows.append({'id': name, 'file': file, 'print_rotation_deg': rr, 'print_translation_mm': tt, 'sha256': sha(out / file)})
    for name, s in [('pin', localpin), ('wheel', localwheel), ('seat', localseat), ('pin-compressed', cp), ('release-fork', release_tool(c).translate((0, 0, c['wheel_radius_mm'] - c['shoulder_radius_mm'] + c['print_flat_mm'])))]:
        write_solid(s, out / 'interface' / f'{name}.npz')
        stl(s, out / 'interface' / f'{name}-assembly-mm.stl')
    checks = []
    for i in range(1, 5):
        pair(f'wheel-{i}/chassis', solids[f'wheel-{i}'], deck, checks=checks)
        pair(f'pin-{i}/chassis', solids[f'pin-{i}'], deck, checks=checks)
        pair(f'wheel-{i}/pin-{i}', solids[f'wheel-{i}'], solids[f'pin-{i}'], checks=checks)
    for shift in np.linspace(34, 0, 69):
        pair(f'compressed insertion at {shift:.2f}mm', cp.translate((0, float(shift), 0)), localseat, checks=checks)
        pair(f'pin through held wheel at {shift:.2f}mm', cp.translate((0, float(shift), 0)), localwheel, checks=checks)
    for amount in np.linspace(0, visual_delta, 17):
        pp, _, _ = compressed_mesh(localpin, c, float(amount))
        pair(f'in-place release deformation {amount:.3f}mm', pp, localseat, checks=checks)
    inward = maxshift(localpin, [localseat], (0, -1, 0))
    outward = maxshift(localpin, [localseat], (0, 1, 0))
    assert inward < 0.01 and 0.29 < outward < 0.31
    limits = []
    for shift in [-inward, 0, outward]:
        pp = localpin.translate((0, shift, 0))
        wi = maxshift(localwheel, [localseat, pp], (0, -1, 0))
        wo = maxshift(localwheel, [localseat, pp], (0, 1, 0))
        assert wi + wo > 0.9
        limits.append({'pin_shift_outward_mm': shift, 'wheel_inward_mm': wi, 'wheel_outward_mm': wo, 'total_wheel_axial_float_mm': wi + wo})
        for angle in range(0, 360, 5):
            ww = localwheel.translate((0, -c['track_mm'] / 2, -c['wheel_radius_mm'])).rotate((0, angle, 0)).translate((0, c['track_mm'] / 2, c['wheel_radius_mm']))
            pair(f'rotation {angle} at pin shift {shift:.4f}', ww, localseat + pp, checks=checks)
    info = {'version': 'r6-shoulder-snap-cart', 'units': 'mm', 'config': c, 'parts': rows, 'coupons': couponrows, 'wheel_centers_mm': wheelcenters, 'source_joints': old['joints'], 'character_preserved_byte_identical': sha(charfile) == sha(out / 'print/character-with-blind-foot-sockets.stl'), 'character_stl_sha256': sha(charfile), 'shoulder': {'diameter_mm': 2 * c['shoulder_radius_mm'], 'supported_seat_length_mm': c['seat_outer_y_mm'] - c['shoulder_stop_y_mm'], 'unbroken_length_mm': c['head_stop_y_mm'] - c['shoulder_stop_y_mm'], 'wheel_sliding_interval_y_mm': [32, 38], 'load_path': 'wheel -> unbroken shoulder -> D journal 27..31.4mm -> integral seat/riser -> original foot deck; flexible tails provide only axial retention'}, 'snap': {'L_effective_mm': L, 'arm_thickness_mm': t, 'arm_depth_mm': c['tail_height_mm'], 'root_radius_mm': c['slot_root_radius_mm'], 'nominal_tip_deflection_per_arm_mm': delta, 'illustrated_deflection_per_arm_mm': visual_delta, 'strain_estimate_nominal': 1.5 * t * delta / L ** 2, 'strain_estimate_illustrated': 1.5 * t * visual_delta / L ** 2, 'strain_estimate_delta_plus_0p1mm': 1.5 * t * (delta + 0.1) / L ** 2, 'estimate_scope': 'Equal-section small-deflection cantilever epsilon=3*t*delta/(2*L^2). Real root concentration, anisotropy, fatigue/creep unmodelled; not a PLA allowable limit.', 'rest_preload_mm': 0, 'animation': 'Precompress exposed twin tails, insert along Y, release after shoulders reach seat. Deformation is an illustrated assumption, not force/material simulation.'}, 'retention': {'external_fasteners_count': 0, 'adhesive_count': 0, 'part_count_including_character': 10, 'pin_inward_stop_mm': inward, 'pin_outward_stop_mm': outward, 'wheel_extreme_positions': limits, 'measurement_scope': 'Nominal coaxial finite-position geometric checks; eccentric and tilted combinations are not continuously proved.', 'mechanism': 'Integral recessed head and separate shoulder-to-seat step; inward stop at shoulder, outward stop at two relaxed rear-facing teeth. No detached cap. D journal limits rotation with clearance; not zero angular play.'}, 'generated_solid_checks': checks, 'physical_testing': 'Not printed. Fit, insertion force, removal, cycles, wheel friction, load and wear unverified.', 'continuous_motion_proof': False, 'source_native_sha256': sha(a.source_case / 'scene.blend')}
    (out / 'measurement.json').write_text(json.dumps(info, ensure_ascii=False, indent=2))
    shutil.copy2(a.config, out / 'config.json')
    (out / 'source/provenance.json').write_text(json.dumps({'source_character_sha256': sha(charfile), 'source_chassis_sha256': sha(deckfile), 'source_native_sha256': sha(a.source_case / 'scene.blend'), 'new_hi3d_calls': 0, 'character_mesh': 'Caller-supplied character; exact retained high-poly STL with foot interfaces. Offline code cannot authenticate upstream source.', 'new_geometry': 'Original Astra shoulder snap wheel mechanism; principles documented in references/diy-printing.md; no third-party CAD copied'}, indent=2))
    print('DIY SOLIDS READY', out)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
