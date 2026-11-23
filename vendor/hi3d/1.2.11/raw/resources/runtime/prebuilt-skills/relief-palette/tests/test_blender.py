"""Offline integration: create outputs only in an explicitly supplied new directory."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE/'scripts'))
sys.path.insert(0, str(PACKAGE/'tests'))
import bpy
import numpy as np
from assembly import MANIFEST, validate_scene
from make_fixture import create
from pipeline import run
from relief import fit_vertices


def main(directory):
    directory = Path(directory).resolve()
    if directory == PACKAGE or PACKAGE in directory.parents:
        raise ValueError('Tests must run outside this package')
    directory.mkdir(parents=True, exist_ok=False)
    config = create(directory/'fixture', PACKAGE)
    original = bpy.context.scene
    original_names = set(original.objects.keys())
    sentinel = bpy.data.objects.new('Existing user object', None)
    original.collection.objects.link(sentinel)
    sentinel.location = (3, 4, 5)
    bpy.context.view_layer.update()
    matrix = sentinel.matrix_world.copy()
    result = run(config, directory/'attempt')
    assert bpy.context.scene == original
    assert sentinel.matrix_world == matrix
    assert set(original.objects.keys()) == original_names | {sentinel.name}
    assert result['checks']['passed'], result['checks']
    assert result['checks']['pan_count'] == 3
    events = [json.loads(s) for s in (directory/'attempt/timings.jsonl').read_text().splitlines()]
    assert {e['task_id'] for e in events} == {'offline-three-pan'}
    for name in ('01_render.png', '02_render.png'):
        data = (directory/'attempt'/name).read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II', data[16:24]) == (480, 400)
    try:
        run(config, directory/'attempt')
        raise AssertionError('Existing outputs overwritten')
    except FileExistsError:
        pass

    # A different source axis order and negative depth retain XY ratio and target height.
    source = [[0, 0, 0], [4, 0, 2], [0, 3, 0], [4, 3, 2]]
    values, report = fit_vertices(source, [20, 10], [4, 5, 6], 1.2, [0, 2, 1], -1)
    assert np.allclose(np.ptp(values, axis=0)*1000, [20, 10, 1.2])
    assert abs(values[:, 2].min()*1000-6) < 1e-9
    try:
        fit_vertices(source, [20, 10], [0, float('nan'), 0], 1, [0, 1, 2], 1)
        raise AssertionError('Nonfinite target silently accepted')
    except ValueError:
        pass
    try:
        fit_vertices([[0,0,0],[1,0,0],[0,1,0]], [20,20], [0,0,0], 1, [0,1,2], 1)
        raise AssertionError('Degenerate relief silently accepted')
    except ValueError:
        pass

    bpy.ops.wm.open_mainfile(filepath=str(directory/'attempt/palette.blend'))
    scene = bpy.context.scene
    assert len(bpy.data.scenes) == 1
    assert 'Existing user object' not in bpy.data.objects
    assert validate_scene(scene)['passed']
    info = json.loads(scene[MANIFEST])
    ctrl = scene.objects[info['control']]
    assert scene.frame_current == 20
    assert scene.camera.data.ortho_scale > .1
    # A broken rotation driver must fail even if the angle property still animates.
    curve = ctrl.animation_data.drivers[0]
    curve.mute = True
    broken = validate_scene(scene)
    assert broken['motion_errors'] and not broken['passed']
    curve.mute = False
    assert validate_scene(scene)['passed']
    # Deliberately lower the registered mirror into powder; report must identify collision.
    mirror = scene.objects[info['mirror']]
    before = [v.co.z for v in mirror.data.vertices]
    for vertex in mirror.data.vertices:
        vertex.co.z -= .0025
    mirror.data.update()
    collided = validate_scene(scene)
    assert not collided['passed']
    assert collided['closed_vertical_clearance_mm'] < 0
    assert any(hit['moving'] == mirror.name for hit in collided['surface_intersections'])
    for vertex, z in zip(mirror.data.vertices, before):
        vertex.co.z = z
    mirror.data.update()
    assert validate_scene(scene)['passed']
    # Preflight failure retains measured failure and explicit downstream skips.
    bad = json.loads(config.read_text())
    bad['pans'][0]['relief'] = 'missing.stl'
    bad_path = directory/'fixture/bad.json'
    bad_path.write_text(json.dumps(bad))
    try:
        run(bad_path, directory/'failed-attempt', result['timing']['attempt_id'])
        raise AssertionError('Missing asset did not fail')
    except ValueError:
        pass
    failed = json.loads((directory/'failed-attempt/timing_summary.json').read_text())
    assert failed['previous_attempt_id'] == result['timing']['attempt_id']
    assert failed['stages'][0]['status'] == 'failed'
    assert all(r['status'] == 'skipped' for r in failed['stages'][1:])
    (directory/'integration-result.json').write_text(json.dumps({
        'passed': True, 'blender': bpy.app.version_string,
        'checks': ['three_pan_build_and_render', 'caller_scene_preserved', 'reopen_and_motion',
                   'broken_driver_detected', 'mirror_collision_detected', 'source_axes_and_depth',
                   'existing_output_refused', 'failure_timing_and_retry_link']}, indent=2))
    print('Offline Blender integration passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = sys.argv[sys.argv.index('--')+1:]
    main(parser.parse_args(args).output)
