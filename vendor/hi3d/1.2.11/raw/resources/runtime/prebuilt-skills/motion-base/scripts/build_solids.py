"""Character on a parameterized cart; hidden anti-rotation joints and actual axle retention."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import sys, json, math
from pathlib import Path
import numpy as np
from solid_tools import *
from stage_cli import cli_arguments, StageFinished, _finish_stage

def safest(p):
    """Independently callable safest operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    lo = p.min(0)
    hi = p.max(0)
    gx, gy = np.meshgrid(np.arange(lo[0], hi[0] + 0.25, 0.25), np.arange(lo[1], hi[1] + 0.25, 0.25))
    q = np.c_[gx.ravel(), gy.ravel()]
    inside = np.zeros(len(q), bool)
    dist = np.full(len(q), np.inf)
    for a, b in zip(p, np.roll(p, -1, axis=0)):
        v = b - a
        t = np.clip(((q - a) * v).sum(1) / max(np.dot(v, v), 1e-20), 0, 1)
        dist = np.minimum(dist, np.linalg.norm(q - a - t[:, None] * v, axis=1))
        inside ^= ((a[1] > q[:, 1]) != (b[1] > q[:, 1])) & (q[:, 0] < (b[0] - a[0]) * (q[:, 1] - a[1]) / (b[1] - a[1] + 1e-30) + a[0])
    dist[~inside] = -1
    i = dist.argmax()
    return (q[i], dist[i])

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    A = arguments
    srcdir = Path(A[0])
    out = Path(A[1])
    out.mkdir(parents=True, exist_ok=True)
    conf = json.loads(Path(A[2]).read_text()) if len(A) > 2 else {}
    src = Source(srcdir / 'source.npz')
    raw = src.solid
    source_components = sorted(raw.decompose(), key=lambda x: -x.volume())
    removed_components = [{'volume_mm3': x.volume(), 'triangles': x.num_tri(), 'bounds_mm': x.bounding_box()} for x in source_components[1:]]
    assert all((abs(x['volume_mm3']) < 0.1 for x in removed_components)), 'Significant source island needs explicit design review'
    raw = source_components[0]
    sole = float(conf.get('sole_trim_mm', 1.2))
    body = raw.trim_by_plane((0, 0, 1), sole)
    cut_volume = raw.volume() - body.volume()
    core = body.slice(sole + 0.01)
    for z in [sole + 1.4, sole + 2.8, sole + 4.2, sole + 5.7]:
        core = core ^ body.slice(z)
    polys = core.to_polygons()
    positive = []
    for poly in polys:
        p = np.asarray(poly)
        area = 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - p[:, 1] * np.roll(p[:, 0], -1))
        if area > 2:
            positive.append((area, p))
    assert len(positive) >= 2, ('Feet must expose two safely separated pocket regions', [(a, p.min(0), p.max(0)) for a, p in positive])
    positive = sorted(positive, reverse=True, key=lambda x: x[0])[:2]
    centers = []
    keycs = []
    sockets = []
    jointrows = []
    engagement = float(conf.get('engagement_mm', 5))
    gap = float(conf.get('radial_clearance_mm', 0.25))
    bottom_gap = float(conf.get('depth_clearance_mm', 0.3))
    for index, (area, poly) in enumerate(sorted(positive, key=lambda x: x[1][:, 0].mean())):
        c, r = safest(poly)
        a = min(3.0, (r - 1.25) * 0.78)
        b = a * 0.73
        assert a >= 1.8, ('Pocket too thin', a, r)
        pts = [[-a, -b], [a * 0.4, -b], [a, -b * 0.2], [a, b], [-a, b]]
        cs = M.CrossSection([pts])
        socket = cs.offset(gap, circular_segments=16).extrude(engagement + bottom_gap + 0.1).translate((c[0], c[1], sole - 0.1))
        escape = (socket - raw).volume()
        assert escape < 0.1, ('Blind cavity exits foot', escape, c, r)
        sockets.append(socket)
        centers.append(c)
        keycs.append(cs)
        jointrows.append({'foot': index + 1, 'center_xy_mm': c.tolist(), 'section_core_radius_mm': float(r), 'peg_width_mm': a * 2, 'peg_breadth_mm': b * 2, 'engagement_mm': engagement, 'radial_clearance_mm': gap, 'blind_bottom_clearance_mm': bottom_gap, 'cavity_escape_mm3': escape})
    body = body - M.Manifold.batch_boolean(sockets, M.OpType.Add)
    assert len(body.decompose()) == 1
    foot_mid = np.mean(centers, axis=0)
    centers = [c - foot_mid for c in centers]
    for row, c in zip(jointrows, centers):
        row['source_center_xy_mm'] = row['center_xy_mm']
        row['center_xy_mm'] = c.tolist()
    for key, L, W, wb, r, col in conf['boards']:
        d = out / key
        d.mkdir(parents=True, exist_ok=True)
        (d / 'parts').mkdir(exist_ok=True)
        (d / 'print').mkdir(exist_ok=True)
        top = 2 * r + 7.0
        thick = 4.8
        roundness = 13
        cs = M.CrossSection.square((L - 2 * roundness, W - 2 * roundness), True).offset(roundness, circular_segments=80)
        deck = cs.extrude(thick).translate((0, 0, top - thick))
        deck = deck.refine_to_length(4)
        skirt = cs.extrude(3).translate((0, 0, top - thick - 2.5))
        inner = M.CrossSection.square((L - 2 * roundness - 3, W - 2 * roundness - 3), True).offset(roundness, circular_segments=80).extrude(5).translate((0, 0, top - thick - 3))
        skirt = skirt - inner
        deck = deck + skirt
        for z in [top - thick - 1.2, top - thick - 0.1]:
            deck = deck - cube((L - 28, 1, 0.32), (0, -W / 2 + 0.3, z)) - cube((L - 28, 1, 0.32), (0, W / 2 - 0.3, z))
        pegs = []
        for c, cs in zip(centers, keycs):
            peg = cs.extrude(engagement + 1.8, scale_top=(0.94, 0.94)).translate((c[0], c[1], top - 1.8))
            pegs.append(peg)
        deck = deck + M.Manifold.batch_boolean(pegs, M.OpType.Add)
        trucks = []
        wheels = []
        axles = []
        wheelrows = []
        axle_y = W / 2 + 5
        axle_half = axle_y + float(conf.get('axle_overhang_from_wheel_center_mm', 14))
        hardware = []
        retention = []
        for x in [-wb / 2, wb / 2]:
            beam = cube((8, W - 6, 8), (x, 0, r + 1))
            riser = cube((9, 13, top - r - 3), (x, 0, (r + top + 1) / 2))
            journals = [cylinder(4, 3.8, (x, sign * (W / 2 - 1.3), r), 'Y') for sign in [-1, 1]]
            truck = beam + riser + M.Manifold.batch_boolean(journals, M.OpType.Add) - cylinder(1.7, W + 10, (x, 0, r), 'Y')
            trucks.append(truck)
            axles.append(cylinder(1.5, axle_half * 2, (x, 0, r), 'Y'))
            for y in [-axle_y, axle_y]:
                wheel = cylinder(r, 8, (x, y, r), 'Y') - cylinder(1.7, 20, (x, y, r), 'Y')
                for theta in [0, 120, 240]:
                    q = math.radians(theta)
                    wheel -= cylinder(1.4, 20, (x + r * 0.59 * math.cos(q), y, r + r * 0.59 * math.sin(q)), 'Y')
                assert len(wheel.decompose()) == 1
                wheels.append(wheel)
                sign = 1 if y > 0 else -1
                washer_y = y + sign * 4.7
                washer = cylinder(3.5, 0.6, (x, washer_y, r), 'Y') - cylinder(1.6, 2, (x, washer_y, r), 'Y')
                hardware.append(('washer', washer))
                for offset in [6.5, 9.5]:
                    nut_y = y + sign * offset
                    nut = cylinder(5.5 / (2 * math.cos(math.pi / 6)), 3, (x, nut_y, r), 'Y', 6) - cylinder(1.5, 5, (x, nut_y, r), 'Y')
                    hardware.append(('M3-jam-nut', nut))
                projection = axle_half - (abs(y) + 11)
                assert projection >= 2
                retention.append({'wheel_y_mm': y, 'wheel_washer_gap_mm': 0.4, 'wheel_inner_journal_gap_mm': 0.4, 'nominal_total_axial_float_mm': 0.8, 'washer_thickness_mm': 0.6, 'nuts_per_end': 2, 'nut_thickness_mm': 3, 'shaft_past_outer_nut_mm': projection, 'threads': 'purchased M3 rod; thread geometry schematic'})
                wheelrows.append({'center_mm': [x, y, r], 'radius_mm': r, 'width_mm': 8, 'bore_diameter_mm': 3.4})
        assert all((abs((w ^ deck).volume()) < 1e-05 for w in wheels))
        assert all((abs((w ^ t).volume()) < 1e-05 for w in wheels for t in trucks))
        chassis = deck + M.Manifold.batch_boolean(trucks, M.OpType.Add)
        mounted = body.translate((-foot_mid[0], -foot_mid[1], top - sole))
        print('DEBUG', jointrows, [(x.volume(), x.bounding_box()) for x in chassis.decompose()], flush=True)
        assert len(chassis.decompose()) == 1
        check = []
        for dz in [0, 0.5, 2, 5.5, 12, 45]:
            volume = abs((mounted.translate((0, 0, dz)) ^ chassis).volume())
            check.append({'lift_mm': dz, 'overlap_mm3': volume})
            assert volume < 0.001, ('Insertion interference', dz, volume)
        info = src.write(mounted, d / 'parts/character.npz', translation=(-foot_mid[0], -foot_mid[1], top - sole))
        write_solid(chassis, d / 'parts/skateboard.npz')
        stl(mounted, d / 'print/character-with-blind-foot-sockets.stl')
        stl(chassis, d / 'print/skateboard-with-integrated-pegs-and-trucks.stl')
        for i, w in enumerate(wheels):
            write_solid(w, d / 'parts' / f'wheel-{i + 1}.npz')
            stl(w, d / 'print' / f'wheel-{i + 1}.stl')
        for i, a in enumerate(axles):
            write_solid(a, d / 'parts' / f'axle-{i + 1}.npz')
        for i, (name, h) in enumerate(hardware):
            write_solid(h, d / 'parts' / f'hardware-{i + 1}-{name}.npz')
        manifest = {'units': 'mm', 'scheme': key, 'source_triangles': len(src.f), 'removed_source_micro_islands': removed_components, 'support_origin_source_xy_mm': foot_mid.tolist(), 'source_height_mm': float(src.v[:, 2].max() - src.v[:, 2].min()), 'sole_trim_mm': sole, 'sole_trim_volume_mm3': cut_volume, 'global_remesh': False, 'character': info, 'joints': jointrows, 'withdrawal_samples': check, 'continuous_path_proof': False, 'board': {'length_mm': L, 'width_mm': W, 'deck_top_mm': top, 'thickness_mm': thick, 'wheelbase_mm': wb, 'wheel_radius_mm': r, 'wheel_centers': wheelrows, 'shaft_length_mm': axle_half * 2}, 'retention': retention, 'theme': col, 'real_print': 'unverified'}
        (d / 'construction.json').write_text(json.dumps(manifest, indent=2))
        print(key, 'BUILT', info['triangles'], jointrows, flush=True)

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
