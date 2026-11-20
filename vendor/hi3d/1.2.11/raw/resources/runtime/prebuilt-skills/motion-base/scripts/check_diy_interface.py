"""check diy interface local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import sys, json, argparse, struct, hashlib
from pathlib import Path
import numpy as np
from diy_snap_geometry import *
from solid_tools import *
from stage_cli import cli_arguments, StageFinished, _finish_stage

def load(name, *, out):
    """Independently callable load operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    path = out / 'interface' / f'{name}-assembly-mm.stl'
    bb = path.read_bytes()
    dt = np.dtype([('n', '<f4', (3,)), ('v', '<f4', (3, 3)), ('a', '<u2')])
    n = struct.unpack_from('<I', bb, 80)[0]
    v, inv = np.unique(np.frombuffer(bb, dtype=dt, offset=84, count=n)['v'].reshape(-1, 3), axis=0, return_inverse=True)
    s = M.Manifold(M.Mesh(np.asarray(v, np.float32), np.asarray(inv.reshape(-1, 3), np.uint32)))
    assert s.status() == M.Error.NoError and s.volume() > 0
    return s

def check(label, pp, qq, *, b, release, w):
    """Independently callable check operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    for name, left, right in [('pin/tool', pp, qq), ('pin/seat', pp, b), ('pin/wheel', pp, w), ('tool/seat', qq, b)]:
        r = left ^ right
        assert r.status() == M.Error.NoError
        vv = abs(r.volume())
        release.append({'phase': label, 'pair': name, 'intersection_mm3': vv})
        assert vv < 1e-05, (label, name, vv)

def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    return parser

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    out = a.output.resolve()
    c = json.loads((out / 'config.json').read_text())
    p = load('pin', out=out)
    b = load('seat', out=out)
    w = load('wheel', out=out)
    tool = load('release-fork', out=out)
    rows = []
    for sh in np.linspace(-14, 0, 57):
        q = tool.translate((0, float(sh), 0))
        assert (q ^ b).status() == M.Error.NoError
        assert abs((q ^ b).volume()) < 1e-07
        lo, hi = (0.0, 0.6)
        for _ in range(26):
            mid = (lo + hi) / 2
            pp, _, _ = compressed_mesh(p, c, mid)
            x = pp ^ q
            assert x.status() == M.Error.NoError
            if abs(x.volume()) > 1e-07:
                lo = mid
            else:
                hi = mid
        pp, _, _ = compressed_mesh(p, c, hi)
        rows.append({'tool_shift_y_mm': float(sh), 'required_deflection_per_arm_mm': hi, 'pin_tool_intersection_mm3': abs((pp ^ q).volume()), 'pin_seat_intersection_mm3': abs((pp ^ b).volume()), 'tool_seat_intersection_mm3': abs((q ^ b).volume())})
    release = []
    delta = max((x['required_deflection_per_arm_mm'] for x in rows)) + 1e-05
    cp, _, _ = compressed_mesh(p, c, delta)
    for y in np.linspace(0, 2, 17):
        check('withdraw pin while fork holds the tail', cp.translate((0, float(y), 0)), tool, b=b, release=release, w=w)
    for y in np.linspace(0, -14, 29):
        check('withdraw fork after teeth enter the straight guide', cp.translate((0, 2, 0)), tool.translate((0, float(y), 0)), b=b, release=release, w=w)
    for y in np.linspace(2, 34, 65):
        pp = cp.translate((0, float(y), 0))
        check('withdraw pin with illustrated wall-constrained compression', pp, tool.translate((0, -14, 0)), b=b, release=release, w=w)
    for d in np.linspace(delta, 0, 13):
        pp, _, _ = compressed_mesh(p, c, float(d))
        check('release free tail outside assembly', pp.translate((0, 34, 0)), tool.translate((0, -14, 0)), b=b, release=release, w=w)
    report = {'scope': 'Actual exported millimetre STL and prescribed symmetric cantilever compression. Rigid release fork has no spring or external hardware. Force, friction, user reach and fatigue not measured.', 'insertion_path': rows, 'release_path': release, 'max_required_deflection_per_arm_mm': max((x['required_deflection_per_arm_mm'] for x in rows)), 'maximum_intersection_mm3': max([x['intersection_mm3'] for x in release] + [x['pin_tool_intersection_mm3'] for x in rows]), 'inputs': {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (out / 'interface').glob('*-assembly-mm.stl')}, 'continuous_proof': False}
    (out / 'interface-validation.json').write_text(json.dumps(report, indent=2))
    print('INTERFACE ACTUAL STL PATH READY', len(rows), len(release))

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
