"""Use fresh-imported GLB vertices and world transforms to check every rendered pose."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import argparse, json, hashlib
from pathlib import Path
import numpy as np
import manifold3d as M
from stage_cli import cli_arguments, StageFinished, _finish_stage

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    out = a.output
    work = a.work
    info = json.loads((out / 'measurement.json').read_text())
    frames = json.loads((work / 'fresh-animation-transforms.json').read_text())
    solids = {}
    bounds = {}
    deforms = {}
    sourcefaces = {}
    for name in frames[0]['matrices']:
        d = np.load(work / 'fresh-animation-meshes' / f'{name}.npz')
        v, inv = np.unique(d['vertices'], axis=0, return_inverse=True)
        f = inv[d['faces']]
        solid = M.Manifold(M.Mesh(np.ascontiguousarray(v, np.float32), np.ascontiguousarray(f, np.uint32)))
        assert solid.status() == M.Error.NoError, (name, solid.status())
        solids[name] = solid
        sourcefaces[name] = d['faces']
        dp = work / 'fresh-animation-meshes' / f'{name}-deformation.npz'
        if dp.exists():
            deforms[name] = np.load(dp)['vertices']
    rows = []
    worst = 0
    tested = 0
    rolling = []
    for frame in frames:
        moved = {}
        bb = {}
        for name, mat in frame['matrices'].items():
            matrix = np.array(mat)
            matrix[:3, 3] *= 1000
            source = solids[name]
            if name in deforms:
                v, inv = np.unique(deforms[name][frame['frame'] - 1], axis=0, return_inverse=True)
                source = M.Manifold(M.Mesh(np.asarray(v, np.float32), np.asarray(inv[sourcefaces[name]], np.uint32)))
                assert source.status() == M.Error.NoError, (name, frame['frame'], source.status())
            moved[name] = source.transform(matrix[:3])
            bb[name] = np.array(moved[name].bounding_box()).reshape(2, 3)
        names = list(moved)
        cross = []
        for i, name in enumerate(names):
            for other in names[i + 1:]:
                overlap = np.minimum(bb[name][1], bb[other][1]) - np.maximum(bb[name][0], bb[other][0])
                if np.any(overlap < -2e-05):
                    continue
                volume = abs((moved[name] ^ moved[other]).volume())
                tested += 1
                worst = max(worst, volume)
                if volume > 0.0001:
                    cross.append({'a': name, 'b': other, 'volume_mm3': volume})
        rows.append({'frame': frame['frame'], 'penetrations': cross})
        if frame['frame'] >= 113:
            w = []
            for i in range(1, 5):
                matrix = np.array(frame['matrices'][f'wheel-{i}'])
                w.append({'i': i, 'angle_y': float(np.arctan2(matrix[0, 2], matrix[0, 0])), 'x_mm': float(matrix[0, 3] * 1000)})
            rolling.append(w)
    residual = []
    for i in range(4):
        theta = np.unwrap([x[i]['angle_y'] for x in rolling])
        travel = np.array([x[i]['x_mm'] for x in rolling])
        residual.append(float(np.max(np.abs(theta - theta[0] - (travel - travel[0]) / info['config']['wheel_radius_mm']))))
    report = {'source_glb_sha256': hashlib.sha256((out / 'assembly.glb').read_bytes()).hexdigest(), 'method': 'Fresh Blender GLB meshes, actual evaluated morph positions, and all frame world matrices, exact solid intersection after coordinate weld; finite poses only. Near-contact tolerance1e-4mm^3.', 'frames': len(rows), 'tested_broadphase_pairs': tested, 'maximum_intersection_mm3': worst, 'penetrating_frames': sum((bool(x['penetrations']) for x in rows)), 'per_frame': rows, 'rolling_maximum_residual_rad': residual, 'continuous_proof': False, 'friction_strength_snap_fatigue': 'not tested; prescribed deflection is not material/force simulation'}
    (out / 'motion-validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'per_frame'}, indent=2))
    assert report['penetrating_frames'] == 0
    assert max(residual) < 0.0001

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
