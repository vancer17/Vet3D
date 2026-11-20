"""Local Blender CLI: thread pairs, existing assembly checks and existing scene renders."""
import argparse
import json
from pathlib import Path
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry import Thread, threaded_ring
from timing import stage, skipped
from checkpoints import digest

PACKAGE = Path(__file__).resolve().parents[1]


def read_json(path):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def new_output(path):
    result = Path(path).expanduser().resolve()
    if result.exists() or result == PACKAGE or PACKAGE in result.parents:
        raise ValueError('Output must be a new directory outside the skill package')
    result.mkdir(parents=True)
    return result


def meshes(names):
    import bpy
    if not names or len(names) != len(set(names)):
        raise ValueError('Provide distinct mesh names')
    result = [bpy.data.objects.get(name) for name in names]
    if any(obj is None or obj.type != 'MESH' for obj in result):
        raise ValueError('A requested mesh is missing')
    return result


def execute(args):
    import bpy
    from blender_ops import mesh_object, require_solid, check_screw_path, activate
    from rendering import render_png
    out = new_output(args.out)
    attempt = str(uuid.uuid4()); log = out/'timings.jsonl'; report = {}
    done = []
    stages = ['load', args.command, 'deliver']
    try:
        with stage(log, args.task_id, attempt, 'load', args.previous_attempt_id):
            spec = read_json(args.spec)
            if args.command == 'threads':
                allowed = {'thread', 'male', 'female', 'resolution'}
                if set(spec)-allowed:
                    raise ValueError('Unknown thread-pair fields')
                thread = Thread(**spec['thread'])
                data = [threaded_ring(thread, **spec[key], **spec.get('resolution', {}), female=(key=='female'))
                        for key in ('male', 'female')]
                bpy.ops.wm.read_factory_settings(use_empty=True)
            else:
                source = Path(args.input).expanduser().resolve()
                if source.suffix.lower() != '.blend' or not source.is_file():
                    raise ValueError('An existing BLEND scene is required')
                report['source_sha256'] = digest(source)
                bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
                bpy.context.scene.frame_set(spec['frame'])
        done.append('load')
        with stage(log, args.task_id, attempt, args.command, args.previous_attempt_id):
            if args.command == 'threads':
                objects = [mesh_object(name, *mesh) for name, mesh in zip(('Male thread', 'Female thread'), data)]
                report['topology'] = {obj.name: require_solid(obj) for obj in objects}
                report['quality_status'] = 'not_tested'
            elif args.command == 'check':
                allowed = {'frame', 'bodies', 'caps', 'center_mm', 'axis', 'pitch_mm', 'angles_deg', 'hand', 'unit_mm'}
                if set(spec)-allowed:
                    raise ValueError('Unknown assembly-check fields')
                report['screw_path'] = check_screw_path(meshes(spec['bodies']), meshes(spec['caps']),
                    **{k: v for k, v in spec.items() if k not in ('frame', 'bodies', 'caps')})
                report['quality_status'] = 'failed' if report['screw_path']['status']=='failed' else 'not_tested'
            else:
                camera = bpy.data.objects.get(spec['camera'])
                if camera is None or camera.type != 'CAMERA':
                    raise ValueError('Requested camera is missing')
                report['render'] = render_png(bpy.context.scene, camera, meshes(spec['objects']), out/'render.png',
                    **{k: v for k, v in spec.items() if k not in ('camera', 'objects')})
                report['quality_status'] = 'not_tested'
        done.append(args.command)
        with stage(log, args.task_id, attempt, 'deliver', args.previous_attempt_id):
            if args.command == 'threads':
                # Geometric units actually become metres; unit_settings alone is insufficient.
                for obj in objects:
                    for vertex in obj.data.vertices:
                        vertex.co *= .001
                bpy.context.scene.unit_settings.system = 'METRIC'
                bpy.context.scene.unit_settings.scale_length = 1
                bpy.ops.wm.save_as_mainfile(filepath=str(out/'threads.blend'))
                activate(objects[0]); objects[1].select_set(True)
                bpy.ops.export_scene.gltf(filepath=str(out/'threads.glb'), export_format='GLB', use_selection=True)
            elif digest(source) != report['source_sha256']:
                raise RuntimeError('Input file changed')
            report.update(execution_status='completed', task_id=args.task_id, attempt_id=attempt,
                          timing_file=log.name, parameters=spec)
            write_json(out/'report.json', report)
        done.append('deliver')
        return report
    except BaseException as exc:
        for name in stages[len(done)+1:]:
            skipped(log, args.task_id, attempt, name, 'Earlier stage did not complete', args.previous_attempt_id)
        write_json(out/'report.json', dict(report, execution_status='failed', error_type=type(exc).__name__, attempt_id=attempt))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('threads', 'check', 'render'):
        child = sub.add_parser(name)
        child.add_argument('--spec', required=True); child.add_argument('--out', required=True)
        child.add_argument('--task-id', required=True); child.add_argument('--previous-attempt-id')
        if name != 'threads':
            child.add_argument('--input', required=True)
    if argv is None:
        argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    result = execute(parser.parse_args(argv))
    print(json.dumps({'execution_status': result['execution_status'], 'quality_status': result['quality_status']}))
    if result['quality_status'] == 'failed':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
