"""check rolling local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys, json, math, hashlib, struct, numpy as np
from pathlib import Path
from stage_cli import cli_arguments, StageFinished, _finish_stage

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    A = arguments
    d = Path(A[0])
    file = d / 'motion.glb'
    data = file.read_bytes()
    n = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + n])
    assert len(doc.get('animations', [])) == 1
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(file))
    sc = bpy.context.scene
    root = bpy.data.objects['Complete cart and character']
    wheels = [bpy.data.objects['Wheel axis ' + str(i)] for i in range(1, 5)]
    r = json.loads((d / 'construction.json').read_text())['board']['wheel_radius_mm']
    rows = []
    for f in range(96):
        sc.frame_set(f)
        bpy.context.view_layer.update()
        angles = [math.atan2(w.matrix_world[0][2], w.matrix_world[0][0]) for w in wheels]
        rows.append({'frame': f, 'root_x_mm': root.matrix_world.translation.x * 1000, 'wheel_angles_rad': angles, 'wheel_centers_mm': [list(w.matrix_world.translation * 1000) for w in wheels]})
    x = np.array([q['root_x_mm'] for q in rows])
    angle = np.unwrap(np.array([q['wheel_angles_rad'] for q in rows]), axis=0)
    error = np.max(np.abs(angle - angle[0] - (x - x[0])[:, None] / r))
    assert error < 0.0001, error
    report = {'sha256': hashlib.sha256(data).hexdigest(), 'animation_clips': len(doc['animations']), 'channels': len(doc['animations'][0]['channels']), 'method': 'Fresh Blender import,96 poses of actualGLB; unwrap wheel world orientation and compare deltaAngle=deltaX/r. Kinematic no-slip assumption, not real traction proof.', 'wheel_radius_mm': r, 'travel_mm': float(x[-1] - x[0]), 'rotation_delta_radians': (angle[-1] - angle[0]).tolist(), 'maximum_kinematic_residual_rad': float(error), 'maximum_sampled_speed_mm_per_s': float(np.max(np.diff(x)) * 24), 'samples': rows}
    (d / 'rolling-check.json').write_text(json.dumps(report, indent=2))
    print('ROLL CHECK', error)

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
