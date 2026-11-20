# Portable derivative; original SHA-256 is recorded in evidence-map.json.
import os
from pathlib import Path
import sys, json, copy
from pathlib import Path
sys.dont_write_bytecode = True
import bpy, numpy as np
skill = Path(str(Path(os.environ['HI3D_RESOURCES_ROOT']) / 'runtime/prebuilt-skills/rig-retarget'))
sys.path.insert(0, str(skill / 'scripts'))
from rigging.rig_adapter import skeleton
from rigging.retarget_math import retarget_samples
fixture = Path(str(Path(__file__).resolve().parents[1] / 'hi3d-retarget-audit-722b3e5c5b2a434ebd672a9dcb8a3090'))
bpy.ops.wm.open_mainfile(filepath=str(fixture / 'source.blend'), use_scripts=False)
target = skeleton(bpy.data.objects['Target'])
with np.load(fixture / 'cache.npz', allow_pickle=False) as archive:
    data = {k: archive[k] for k in archive.files}
spec = json.loads((fixture / 'mapping.json').read_text())

def calculate(value):
    return retarget_samples(data, target, value)
false = copy.deepcopy(spec)
false['root']['in_place'] = False
true = copy.deepcopy(spec)
true['root']['in_place'] = True
text_false = copy.deepcopy(spec)
text_false['root']['in_place'] = 'false'
_, a, _ = calculate(false)
_, b, _ = calculate(true)
_, c, _ = calculate(text_false)
results = {'string_false_behaves_like_true': bool(np.array_equal(b, c)), 'string_false_differs_from_boolean_false': bool(not np.array_equal(a, c)), 'max_root_location_difference': float(np.max(np.abs(a - c)))}
partial = copy.deepcopy(spec)
partial['mapping'] = {spec['root']['target']: {'source': spec['root']['source']}}
partial['limbs'] = []
q, loc, detail = calculate(partial)
results['partial_mapping_accepted'] = {'mapped': len(partial['mapping']), 'output_bones': q.shape[1], 'frames': q.shape[0]}
endpoint = copy.deepcopy(spec)
name = next((n for n, row in endpoint['mapping'].items() if 'source_end' in row and 'target_end' in row))
endpoint['mapping'][name].pop('target_end')
q, loc, detail = calculate(endpoint)
results['single_endpoint_accepted'] = {'target_bone': name, 'frames': q.shape[0]}
extra = copy.deepcopy(spec)
extra['unrecognized_config_key'] = 'sample'
calculate(extra)
results['unknown_top_level_config_key_accepted'] = True
wrong = copy.deepcopy(spec)
wrong['calibrated'] = 1
try:
    calculate(wrong)
except ValueError as error:
    results['non_boolean_calibrated_rejected'] = str(error)
else:
    raise AssertionError('numeric calibrated accepted')
out = Path(__file__).with_name('results.json')
out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf8')
print(json.dumps(results, ensure_ascii=False))
print('PROBE_RESULTS=' + str(out))
