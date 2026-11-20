# Portable derivative; original SHA-256 is recorded in evidence-map.json.
import os
from pathlib import Path
from pathlib import Path
from types import SimpleNamespace
import sys, json, hashlib
import bpy, numpy as np
from mathutils import Quaternion
sys.dont_write_bytecode = True
skill = Path(str(Path(os.environ['HI3D_RESOURCES_ROOT']) / 'runtime/prebuilt-skills/rig-retarget'))
sys.path.insert(0, str(skill / 'scripts'))
from rigging.rig_adapter import execute, cache_rig
from rigging.test_retarget import make_rig
root = Path(__file__).parent
result = {}

def cache_cli(input_path, name, start, end, fps, source_fps=None):
    report = root / (name + '.json')
    output = root / (name + '.npz')
    args = SimpleNamespace(operation='cache', input=str(input_path), rig='Source', report=str(report), output=str(output), start=start, end=end, fps=fps, source_fps=source_fps)
    before = hashlib.sha256(input_path.read_bytes()).hexdigest()
    execute(args)
    with np.load(output, allow_pickle=False) as archive:
        data = {k: archive[k] for k in archive.files}
    assert hashlib.sha256(input_path.read_bytes()).hexdigest() == before
    return (data, json.loads(report.read_text()))
bpy.ops.wm.read_factory_settings(use_empty=True)
rig = make_rig('Source')
bpy.context.scene.render.fps = 24
bpy.context.scene.render.fps_base = 1.001
for f, a in [(0, 0), (2, 0.6)]:
    rig.pose.bones['fore'].rotation_quaternion = Quaternion((0, 0, 1), a)
    rig.pose.bones['fore'].keyframe_insert('rotation_quaternion', frame=f)
bpy.context.scene.frame_set(1, subframe=0.25)
before = (bpy.context.scene.frame_current, bpy.context.scene.frame_subframe)
direct = cache_rig(rig, [0.0, 0.5, 1.5])
after = (bpy.context.scene.frame_current, bpy.context.scene.frame_subframe)
assert np.allclose(before, after)
result['subframe_restored'] = {'before': before, 'after': after}
input_path = root / 'time-source.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(input_path))
data, report = cache_cli(input_path, 'time-cache', 0, 2, 30)
assert np.allclose(data['sample_frames'], [0, 0.7992, 1.5984], atol=1e-06)
result['fractional_fps'] = {'source_fps': float(data['source_fps']), 'sample_frames': data['sample_frames'].tolist(), 'frames': report['frames'], 'last_is_requested_end': bool(data['sample_frames'][-1] == 2)}
data, report = cache_cli(input_path, 'override-cache', 0, 2, 30, 60)
assert np.allclose(data['sample_frames'], [0, 2])
result['source_fps_override'] = {'source_fps': float(data['source_fps']), 'sample_frames': data['sample_frames'].tolist()}
bpy.ops.wm.open_mainfile(filepath=str(input_path), use_scripts=False)
rig = bpy.data.objects['Source']
frames = [0, 1, 2]
active = cache_rig(rig, frames)
action = rig.animation_data.action
track = rig.animation_data.nla_tracks.new()
strip = track.strips.new('SourceNLA', 0, action)
rig.animation_data.action = None
nla = cache_rig(rig, frames)
assert np.allclose(active['poses'], nla['poses'], atol=1e-06)
assert not np.allclose(nla['poses'][0], nla['poses'][-1])
result['nla_only'] = {'active_action_is_none': rig.animation_data.action is None, 'tracks': len(rig.animation_data.nla_tracks), 'matches_active_action': True, 'actual_motion': True}
bpy.ops.wm.read_factory_settings(use_empty=True)
make_rig('Source')
static_path = root / 'static-source.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(static_path))
data, report = cache_cli(static_path, 'static-cache', 0, 2, 30, 30)
assert np.array_equal(data['poses'][0], data['poses'][1]) and np.array_equal(data['poses'][1], data['poses'][2])
result['static_cache_accepted'] = {'schema': str(data['schema']), 'frames': report['frames'], 'all_poses_identical': True, 'report_fields': sorted(report)}
(root / 'probe-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps(result, ensure_ascii=False))
