"""Trusted task-builder composition; local geometry only, no service client."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import bpy
import geometry
from assembly import hinge_control, store_roles, validate_scene
from relief import import_relief
from spec import read_spec
from timing import Recorder, write_json


def import_builder(path):
    spec = importlib.util.spec_from_file_location('palette_task_builder', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, 'build', None)):
        raise ValueError('The reviewed task module must expose build(ctx)')
    return module.build


def configure_render(scene, config):
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = config['samples']
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.render.resolution_x, scene.render.resolution_y = config['resolution']
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = config['exposure']


def render_shot(scene, shot, path, resolution):
    old_camera, old_frame, old_path = scene.camera, scene.frame_current, scene.render.filepath
    camera = shot['camera']
    old_matrix, old_scale = camera.matrix_world.copy(), camera.data.ortho_scale
    try:
        scene.frame_set(shot['frame'])
        scene.camera = shot['camera']
        geometry.fit_camera(scene.camera, shot['objects'], resolution, shot.get('margin', 1.15))
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True, scene=scene.name)
    finally:
        camera.matrix_world, camera.data.ortho_scale = old_matrix, old_scale
        scene.camera, scene.render.filepath = old_camera, old_path
        scene.frame_set(old_frame)


def run(config_path, output, previous_attempt_id=None):
    """Create a new candidate scene and output directory; restore the caller's scene.

    The explicit builder is trusted code authored/reviewed by the executor. The
    runner cannot sandbox it. Existing user scenes are neither cleared nor saved
    into the candidate: libraries.write writes only this scene and dependencies.
    """
    output = Path(output).resolve()
    package = Path(__file__).resolve().parent.parent
    if output == package or package in output.parents:
        raise ValueError('Outputs must be outside the skill package')
    output.mkdir(parents=True, exist_ok=False)
    # Keep even failed preflight events under a stable task identity.
    task_id = Path(config_path).stem
    try:
        declared = json.loads(Path(config_path).read_text(encoding='utf-8'))
        if isinstance(declared, dict) and isinstance(declared.get('task_id'), str) and declared['task_id']:
            task_id = declared['task_id']
    except (OSError, ValueError):
        pass
    recorder = Recorder(output, task_id, previous_attempt_id)
    stages = ['preflight', 'scene', 'shell_and_accessories', 'powder_reliefs', 'hinge', 'checks', 'save', 'render']
    old_scene = bpy.context.window.scene
    status = 'failed'
    report = {'execution_status': 'failed', 'checks': None, 'artifacts': []}
    try:
        with recorder.stage('preflight'):
            config = read_spec(config_path)
            write_json(output/'resolved_config.json', config)
            build = import_builder(config['builder'])
        with recorder.stage('scene'):
            scene = bpy.data.scenes.new('Relief palette '+config['task_id'])
            bpy.context.window.scene = scene
            scene.unit_settings.system = 'METRIC'
            scene.unit_settings.length_unit = 'MILLIMETERS'
            collection = bpy.data.collections.new('Palette assembly')
            scene.collection.children.link(collection)
            configure_render(scene, config)
        with recorder.stage('shell_and_accessories'):
            built = build(SimpleNamespace(scene=scene, collection=collection, config=config, geometry=geometry))
        cakes, reliefs, adaptations = [], [], []
        with recorder.stage('powder_reliefs'):
            for pan in config['pans']:
                mat = geometry.powder_material('Powder '+pan['id'], pan['color'], **config.get('powder_finish', {}))
                cakes.append(geometry.plate(collection, 'Cake '+pan['id'], pan['center_mm'], pan['size_mm'],
                                            pan['corner_mm'], mat, min(.1, pan['size_mm'][2]/10)))
                obj, measured = import_relief(collection, pan, mat)
                reliefs.append(obj)
                measured.update(pan_id=pan['id'], variant_id=pan['variant_id'],
                                source_sha256=hashlib.sha256(Path(pan['relief']).read_bytes()).hexdigest())
                adaptations.append(measured)
        with recorder.stage('hinge'):
            ctrl = hinge_control(collection, built['moving'], config['hinge'], config['keyframes'])
            store_roles(scene, config, built, ctrl, cakes, reliefs)
            scene.frame_start, scene.frame_end = config['keyframes'][0][0], config['keyframes'][-1][0]
            scene.frame_set(max(config['keyframes'], key=lambda k:k[1])[0])
            for shot in built['shots'].values():
                if shot['camera'].name not in scene.objects or shot['camera'].type != 'CAMERA':
                    raise ValueError('Shot camera must belong to task scene')
            if config['shots']:
                if not all(s in built['shots'] for s in config['shots']):
                    raise ValueError('Requested shot is not implemented by builder')
                scene.camera = built['shots'][config['shots'][0]]['camera']
                first = built['shots'][config['shots'][0]]
                geometry.fit_camera(scene.camera, first['objects'], config['resolution'], first.get('margin', 1.15))
        with recorder.stage('checks'):
            report['checks'] = validate_scene(scene)
            report['relief_adaptations'] = adaptations
        with recorder.stage('save'):
            path = output/'palette.blend'
            bpy.data.libraries.write(str(path), {scene}, fake_user=True)
            report['artifacts'].append(str(path))
        if config['shots']:
            with recorder.stage('render'):
                for index, name in enumerate(config['shots'], 1):
                    path = output/f'{index:02}_render.png'
                    render_shot(scene, built['shots'][name], path, config['resolution'])
                    report['artifacts'].append(str(path))
        else:
            recorder.skip('render', 'No images requested in this stage')
        report['execution_status'] = 'completed'
        status = 'completed' if report['checks']['passed'] else 'checks_failed'
    except BaseException as error:
        report['error_type'] = type(error).__name__
        status = 'interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'failed'
        raise
    finally:
        bpy.context.window.scene = old_scene
        seen = {r['stage'] for r in recorder.records}
        for stage in stages:
            if stage not in seen:
                recorder.skip(stage, 'Earlier stage prevented execution')
        report['timing'] = recorder.finish(status)
        write_json(output/'report.json', report)
    return report
