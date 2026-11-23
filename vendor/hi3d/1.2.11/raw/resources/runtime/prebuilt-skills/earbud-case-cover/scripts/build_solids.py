"""Split charging-case cover: preserve source sculpture and a distinct parameterized device fixture."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import sys, json, numpy as np
from pathlib import Path
from solid_tools import *
from stage_cli import cli_arguments, StageFinished, _finish_stage

def rounded(dim, loc, r):
    """Independently callable rounded operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    return M.Manifold.cube(np.array(dim) - 2 * r, True).minkowski_sum(M.Manifold.sphere(r, 48)).translate(loc)

def parse_lid_rear_clearance(value):
    """Return explicit rounded cutter parameters, or None when disabled.

    The dimensions/location are finite millimetre XYZ triples. Require a
    positive radius and positive rounded-box core. This validates the cutter,
    not its suitability for a particular lid; solid and motion checks follow.
    """
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError('lid_rear_clearance_mm must be [dimensions_xyz, location_xyz, radius]')
    dims, location, radius = value
    dims = np.asarray(dims, dtype=float)
    location = np.asarray(location, dtype=float)
    if (dims.shape != (3,) or location.shape != (3,) or not np.isfinite(dims).all()
            or not np.isfinite(location).all() or isinstance(radius, (bool, np.bool_))
            or not np.isscalar(radius)):
        raise ValueError('Lid rear cutter requires finite XYZ triples and a scalar radius')
    radius = float(radius)
    if not np.isfinite(radius) or radius <= 0 or np.any(dims <= 2 * radius):
        raise ValueError('Lid rear cutter must have a positive radius and positive rounded-box core')
    return dims, location, radius

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    A = arguments
    srcdir = Path(A[0])
    out = Path(A[1])
    conf = json.loads(Path(A[2]).read_text()) if len(A) > 2 else {}
    lid_rear_clearance = parse_lid_rear_clearance(conf.get('lid_rear_clearance_mm'))
    out.mkdir(parents=True, exist_ok=True)
    src = Source(srcdir / 'source.npz')
    s = src.solid
    W, D, H = conf['device_mm']
    clear = float(conf.get('clearance_mm', 0.6))
    bottom = float(conf.get('device_bottom_mm', 3))
    split = float(conf.get('device_lid_split_mm', 34.2)) + bottom
    gap = float(conf.get('seam_gap_mm', 0.6))
    rad = float(conf.get('device_corner_radius_mm', 9))
    opening = float(conf.get('opening_degrees', 115))
    if not np.isfinite(opening) or not 0 <= opening <= 360:
        raise ValueError('opening_degrees must be finite and between 0 and 360')
    cy = float(conf.get('device_y_mm', 0))
    center = (0, cy, bottom + H / 2)
    cavity = rounded((W + 2 * clear, D + 2 * clear, H + 2 * clear), center, rad + clear)
    inside = (cavity - s).volume()
    print('CAVITY ESCAPE', inside, flush=True)
    assert abs(inside) < 0.01, 'Source exterior does not contain precision cavity; resize/position with real views before continuing'
    wall_offset = 1.5
    wall_envelope = rounded((W + 2 * (clear + wall_offset), D + 2 * (clear + wall_offset), H + 2 * (clear + wall_offset)), center, rad + clear + wall_offset)
    wall_escape = abs((wall_envelope - s).volume())
    print('WALL ENVELOPE ESCAPE', wall_escape, flush=True)
    assert wall_escape < 0.01, '1.5mm pre-opening wall envelope exits sculpture'
    upper = s.trim_by_plane((0, 0, 1), split + gap / 2) - cavity
    lower = s.trim_by_plane((0, 0, -1), -split + gap / 2) - cavity
    back = rounded((41, 22, 11), (0, cy + D / 2 + 9, split - 1.5), 2)
    lower -= back
    upper -= back
    if lid_rear_clearance is not None:
        dims, location, radius = lid_rear_clearance
        upper -= rounded(dims, location, radius)
    port = cube((14, 9, 18), (0, cy, 1))
    lower -= port
    if conf.get('rear_relief_mm'):
        dims, loc, r = conf['rear_relief_mm']
        lower -= rounded(dims, loc, r)
    led_z = bottom + float(conf['led_center_z_from_bottom_mm'])
    lower -= cylinder(1.6, 30, (0, cy - D / 2 - 8, led_z), 'Y')
    device = rounded((W, D, H), center, rad)
    device_upper = device.trim_by_plane((0, 0, 1), split)
    device_lower = device.trim_by_plane((0, 0, -1), -split)
    device_lower -= rounded((W - 6, D - 5, 40), (0, cy, split + 8), 4)
    device_lower -= cube((10, 3.4, 10), (0, cy, bottom + 3))
    plug_housing = rounded((12, 7, 15), (0, cy, bottom - 8.5), 1.5)
    plug_tip = rounded((8.2, 2.3, 6), (0, cy, bottom + 1.5), 0.7)
    manifest = {'profile': conf['profile'], 'nominal_device_mm': [W, D, H], 'clearance_per_side_mm': clear, 'device_bottom_z_mm': bottom, 'device_center_y_mm': cy, 'lid_split_z_mm': split, 'seam_gap_mm': gap, 'inner_curvature': f'Provisional{rad + clear}mm cavity corner radius; requires measured device-specific calibration', 'cavity_escape_mm3': inside, 'wall_envelope_escape_mm3': wall_escape, 'minimum_inner_offset_checked_mm': 1.5, 'global_remesh': False, 'source_triangles': len(src.f), 'parts': {}, 'real_fit': 'unverified; no device scan or physical installation', 'status_light': 'Observation hole at caller-configured LED height. Verify the matching device operating area; LED opening alone does not prove pairing/reset access.', 'hinge_axis_mm': [0, cy + D / 2 - 1, split], 'opening_degrees': opening, 'wireless_charging': 'unverified; preserve user wireless-charge requirements and test separately', 'retention': 'Removable low-residue liner tape candidate at smooth sidewalls; thickness calibrated during real trial. Animation is not holding-force evidence.'}
    (d := (out / conf['key'])).mkdir(exist_ok=True)
    (d / 'parts').mkdir(exist_ok=True)
    (d / 'print').mkdir(exist_ok=True)
    for name, solid in [('cover-lower', lower), ('cover-lid', upper)]:
        assert len(solid.decompose()) == 1, (name, [x.volume() for x in solid.decompose()])
        manifest['parts'][name] = src.write(solid, d / 'parts' / (name + '.npz'))
        stl(solid, d / 'print' / (name + '.stl'))
    for name, solid in [('device-lower', device_lower), ('device-lid', device_upper), ('plug-housing', plug_housing), ('plug-tip', plug_tip)]:
        write_solid(solid, d / 'parts' / (name + '.npz'))
    manifest['assembly_overlap_mm3'] = {'lower_device': abs((lower ^ device_lower).volume()), 'lid_device': abs((upper ^ device_upper).volume()), 'lower_lid': abs((lower ^ upper).volume())}
    checks = []
    for deg in [0, 15, 30, 45, 60, 75, 90, 105, opening]:
        pivot = np.array(manifest['hinge_axis_mm'])
        moving = upper.translate(-pivot).rotate((-deg, 0, 0)).translate(pivot)
        checks.append({'angle_deg': deg, 'upper_lower_overlap_mm3': abs((moving ^ lower).volume()), 'overlap_bounds_mm': (moving ^ lower).bounding_box() if abs((moving ^ lower).volume()) > 0.001 else None})
    manifest['hinge_samples'] = checks
    assert all((x['upper_lower_overlap_mm3'] < 0.001 for x in checks)), checks
    # The moving shell must also clear the fixed lower device, not only its shell.
    manifest['lid_rear_clearance_mm'] = (None if lid_rear_clearance is None else
        [lid_rear_clearance[0].tolist(), lid_rear_clearance[1].tolist(), lid_rear_clearance[2]])
    cross_checks = []
    for deg in np.linspace(0, opening, 116):
        moving = upper.translate(-pivot).rotate((-float(deg), 0, 0)).translate(pivot)
        cross_checks.append({'angle_deg': float(deg),
            'upper_fixed_lower_device_mm3': abs((moving ^ device_lower).volume())})
    manifest['lid_fixed_device_samples'] = cross_checks
    assert all(x['upper_fixed_lower_device_mm3'] < 0.001 for x in cross_checks), cross_checks
    (d / 'construction.json').write_text(json.dumps(manifest, indent=2))
    print('COVER BUILT', manifest, flush=True)

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
