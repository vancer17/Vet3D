"""Measure source fidelity and independently reimport the delivered GLB morphs."""
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_io import coordinates
from low_rig import shape_coords
from run import digest


def stats(values):
    values = np.asarray(values)
    return {'samples': len(values), 'rms': float(np.sqrt(np.mean(values ** 2))),
            'p95': float(np.percentile(values, 95)), 'max': float(values.max())}


def glb_roundtrip(path, low_data):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    head = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('Lowpoly_Head'))
    matrix = np.asarray(head.matrix_world)
    keys = head.data.shape_keys.key_blocks
    names = low_data['expression_names'].tolist()
    if [k.name for k in keys if k.name != 'Basis'] != names:
        raise ValueError('Reimported GLB morph names/order mismatch')
    def world(key):
        return shape_coords(key) @ matrix[:3, :3].T + matrix[:3, 3]
    imported = world(keys['Basis'])
    source = low_data['vertices']
    tree = KDTree(len(source))
    for i, p in enumerate(source):
        tree.insert(p, i)
    tree.balance()
    mapping = np.array([tree.find(p)[1] for p in imported])
    errors = {'neutral': float(np.max(np.linalg.norm(imported - source[mapping], axis=1)))}
    for name, delta in zip(names, low_data['expression_deltas']):
        expected = (source + delta)[mapping]
        errors[name] = float(np.max(np.linalg.norm(world(keys[name]) - expected, axis=1)))
    tolerance = float(np.ptp(source, axis=0).max()) * 2e-5
    report = {'max_errors': errors, 'tolerance': tolerance, 'passed': max(errors.values()) < tolerance,
              'scope': 'GLB reimport, UV-seam duplicates matched by neutral positions; neutral and all morph endpoints in source world coordinates'}
    if not report['passed']:
        raise ValueError('GLB morph roundtrip failed: ' + str(errors))
    return report


def run(config):
    root = Path(config['output'])
    bpy.ops.wm.open_mainfile(filepath=str(root / 'Heads_Rigged.blend'), load_ui=False)
    bpy.context.scene.frame_set(1)
    low = bpy.data.objects['Lowpoly_Head']; low.hide_set(False)
    low.data.shape_keys.animation_data_clear()
    for key in low.data.shape_keys.key_blocks:
        key.value = 0
    high = bpy.data.objects['Source_High']; high.hide_set(False)
    high_bvh = BVHTree.FromObject(high, bpy.context.evaluated_depsgraph_get())
    low_bvh = BVHTree.FromObject(low, bpy.context.evaluated_depsgraph_get())
    low_data = dict(np.load(root / 'lowpoly_data.npz'))
    rng = np.random.default_rng(config.get('seed', 0))
    v = low_data['vertices']; sample = v[rng.choice(len(v), min(len(v), 8000), replace=False)]
    low_to_high = [high_bvh.find_nearest(Vector(p))[3] for p in sample]
    samples = np.load(root / 'surface_samples.npz')['points']
    samples = samples[rng.choice(len(samples), min(len(samples), 8000), replace=False)]
    face = json.loads(Path(config['face_config']).read_text())
    exclude = np.zeros(len(samples), bool)
    for patch in face['patches']:
        cx, cz = patch['center']; rx, rz = patch['outer_radii']
        exclude |= (((samples[:, 0] - cx) / rx) ** 2 + ((samples[:, 2] - cz) / rz) ** 2 < 1) & (samples[:, 1] < face['front_depth'])
    high_to_low = [low_bvh.find_nearest(Vector(p))[3] for p in samples[~exclude]]
    report = {'source_sha256': digest(config['source']), 'fidelity': {
        'low_to_original_high': stats(low_to_high), 'original_high_to_low': stats(high_to_low),
        'high_to_low_scope': 'excludes explicitly rebuilt eye/mouth patches; sampled nearest-triangle distances in model units'},
        'glb_roundtrip': glb_roundtrip(root / 'Lowpoly_Rigged.glb', low_data)}
    (root / 'metrics.json').write_text(json.dumps(report, indent=2))
    print('METRICS_READY', report, flush=True)


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text()))
