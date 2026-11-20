"""Run with Blender --background --python; no network or service charges."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mdf_handoff import digest, request_plan
from retopology import import_retopology

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary).resolve()
    config = {'output': str(root), 'remesh_face_goal': 6}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(location=(0.2, -0.4, 0.7))
    obj = bpy.context.object
    obj.scale = (0.3, 0.6, 0.9)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    verts = [v.co[:] for v in obj.data.vertices]
    bounds = [[min(v[i] for v in verts) for i in range(3)], [max(v[i] for v in verts) for i in range(3)]]
    (root / 'working_surface_report.json').write_text(json.dumps({'bounds': bounds}))
    bpy.ops.export_scene.gltf(filepath=str(root / 'working_surface.glb'), export_format='GLB')
    source_obj = root / 'fixture.obj'
    bpy.ops.wm.obj_export(filepath=str(source_obj), forward_axis='NEGATIVE_Z', up_axis='Y')
    plan = request_plan(config)
    output = Path(plan['outputDir'])
    output.mkdir()
    archive = output / 'hi3d-model_obj.zip'
    with zipfile.ZipFile(archive, 'w') as package:
        package.write(source_obj, 'nested/head.obj')
    record = {'status': 'SUCCEEDED', 'httpStatus': 200, 'outputDir': plan['outputDir'],
              'request': {'capability': 'retopology', 'params': plan['params']},
              'response': {'code': 0, 'status': 'SUCCEEDED'},
              'downloads': {'model_obj': {'path': str(archive), 'sha256': digest(archive)}}}
    record['fingerprint'] = hashlib.sha256(json.dumps({'capability': 'retopology', 'params': plan['params'], 'fileHash': digest(plan['file']), 'output': plan['outputDir']}, sort_keys=True).encode()).hexdigest()
    job = Path(plan['jobPath'])
    job.write_text(json.dumps(record))
    import_retopology(config)
    report = json.loads((root / 'retopology_import_report.json').read_text())
    assert report['quads'] == 6 and report['baked'] is False, report
    assert (root / 'source_quads.obj').is_file()
    # A valid archive with triangulated geometry must not be silently paired.
    lines = source_obj.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('f '):
            face = line.split()[1:]
            lines[i] = 'f ' + ' '.join(face[:3])
            break
    with zipfile.ZipFile(archive, 'w') as package:
        package.writestr('head.obj', '\n'.join(lines))
    record['downloads']['model_obj']['sha256'] = digest(archive)
    job.write_text(json.dumps(record))
    try:
        import_retopology(config)
    except ValueError as error:
        assert 'native quads' in str(error), error
    else:
        raise AssertionError('triangulated result accepted')
    print('OBJ ZIP import: native quads, coordinate conversion, triangle rejection PASSED')
