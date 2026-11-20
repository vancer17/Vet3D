"""Blender entry: --python-exit-code 1 --python this.py -- CONFIG OUTPUT.blend.

Importing this module performs no scene operations. run_rebuild is callable
independently; timing of the business workflow is recorded by its executor.
"""

import argparse
import json
import math
from pathlib import Path
import sys


def validate_config(config):
    """Validate the conversion contract without reading files or using Blender."""
    if not isinstance(config, dict):
        raise ValueError('Configuration must be a JSON object')
    placement = config.get('placement', 'head_surface')
    if placement not in ('guides', 'head_surface'):
        raise ValueError('placement must be guides or head_surface')
    for key in ('material', 'output_collection', 'uv_name'):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f'{key} must name an existing input or intended output')
    if placement == 'head_surface':
        if not isinstance(config.get('head'), str) or not config['head'].strip():
            raise ValueError('head_surface placement requires a head mesh name')
    elif config.get('head') is not None:
        raise ValueError('guides placement does not use head; omit it or use null')
    for key in ('atlas_columns',):
        if type(config.get(key)) is not int or config[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    if type(config.get('seed')) is not int:
        raise ValueError('seed must be an integer')
    clearance = config.get('surface_clearance', 0 if placement == 'guides' else None)
    if type(clearance) not in (float, int) or not math.isfinite(clearance) or clearance < 0:
        raise ValueError('surface_clearance must be a finite nonnegative world distance')
    if placement == 'guides' and clearance != 0:
        raise ValueError('guides placement has no contact projection; surface_clearance must be zero')
    if not isinstance(config.get('layers'), list) or not config['layers']:
        raise ValueError('layers must be a nonempty list')
    names = set()
    for spec in config['layers']:
        if not isinstance(spec, dict):
            raise ValueError('Each layer must be a JSON object')
        name = spec.get('name')
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError('Layer names must be nonempty and unique')
        names.add(name)
        guides = spec.get('guides')
        if not isinstance(guides, list) or not guides or any(not isinstance(g, str) or not g for g in guides) or len(set(guides)) != len(guides):
            raise ValueError('guides must list unique curve object names')
        for key in ('segments', 'columns', 'stride'):
            value = spec.get(key, 1) if key == 'stride' else spec.get(key)
            if type(value) is not int or value < 1:
                raise ValueError(f'{key} must be a positive integer')
        for key in ('width', 'offset'):
            value = spec.get(key)
            if type(value) not in (float, int) or not math.isfinite(value) or value < 0 or (key == 'width' and value == 0):
                raise ValueError(f'Invalid {key} world distance')
        lanes = spec.get('lanes')
        if not isinstance(lanes, list) or not lanes or any(type(v) is not int or not 0 <= v < config['atlas_columns'] for v in lanes):
            raise ValueError('lanes must contain valid atlas column indices')
        angles = spec.get('section_angles_degrees', [0])
        if (not isinstance(angles, list) or not angles
                or any(type(v) not in (int, float) or not math.isfinite(v) or not -180 <= v <= 180 for v in angles)):
            raise ValueError('section_angles_degrees must list finite angles in [-180, 180]')
        if len({v % 360 for v in angles}) != len(angles):
            raise ValueError('Duplicate section angles create duplicate cards')
        if placement == 'head_surface' and angles != [0]:
            raise ValueError('Crossed sections require guides placement')
        if placement == 'guides':
            normal = spec.get('root_normal')
            if (not isinstance(normal, list) or len(normal) != 3
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in normal)
                    or not 1e-12 < math.hypot(*normal) < float('inf')):
                raise ValueError('root_normal must be a finite nonzero world XYZ direction')
    protected = {config.get('head')} | {name for layer in config['layers'] for name in layer['guides']}
    if names & protected:
        raise ValueError('Output names must not collide with the head or guides')
    return config


def read_curve_paths(obj):
    """Read base guide paths in world space; no modifier evaluation or writes."""
    from mathutils.geometry import interpolate_bezier
    matrix = obj.matrix_world
    if obj.type == 'CURVES':
        cyclic = obj.data.attributes.get('cyclic')
        if cyclic and any(item.value for item in cyclic.data):
            raise ValueError('Hair guides must be open root-to-tip curves')
        return [[tuple(matrix @ p.position) for p in curve.points] for curve in obj.data.curves]
    if obj.type != 'CURVE':
        raise ValueError(f'{obj.name}: expected CURVE or CURVES')
    result = []
    for spline in obj.data.splines:
        if spline.use_cyclic_u:
            raise ValueError('Hair guides must be open root-to-tip curves')
        if spline.type == 'BEZIER':
            points, controls = [], list(spline.bezier_points)
            if len(controls) < 2:
                raise ValueError('Bezier guides need two or more control points')
            for a, b in zip(controls, controls[1:]):
                points.extend(interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, 12)[:-1])
            points.append(controls[-1].co)
        elif spline.type == 'POLY':
            points = [point.co.xyz for point in spline.points]
        else:
            raise ValueError('Sample NURBS guides into POLY curves first')
        result.append([tuple(matrix @ point) for point in points])
    return result


def prepare_scene(bpy, config):
    """Resolve and check all inputs/collisions before allocating any output."""
    scene = bpy.context.scene
    head = scene.objects[config['head']] if config.get('placement', 'head_surface') == 'head_surface' else None
    if head is not None and head.type != 'MESH':
        raise ValueError('head must be a mesh object in the active scene')
    material = bpy.data.materials[config['material']]
    names = {name for spec in config['layers'] for name in spec['guides']}
    guides = {name: read_curve_paths(scene.objects[name]) for name in names}
    if any(not paths for paths in guides.values()):
        raise ValueError('Guide objects must contain curves')
    collection = bpy.data.collections.get(config['output_collection'])
    if collection is not None:
        if collection not in scene.collection.children_recursive:
            raise ValueError('Existing output collection must belong to the active scene')
        if (head is not None and head.name in collection.all_objects) or any(name in collection.all_objects for name in names):
            raise ValueError('Output collection must be separate from head and guides')
        if collection.users > 1:
            raise ValueError('Output collection must not be shared between scenes or parents')
    for spec in config['layers']:
        old = bpy.data.objects.get(spec['name'])
        if old is not None and (collection is None or old.name not in collection.objects or len(old.users_collection) != 1):
            raise ValueError(f'Output name is already used outside its dedicated collection: {spec["name"]}')
    return head, material, guides, collection


def run_rebuild(bpy, config, output, overwrite=False):
    """Build candidate arrays first, replace named output meshes, then save.

    Input file is never saved over. On preflight/geometry failure, scene output
    is untouched. A save/IO failure may leave the in-memory candidate changed;
    reload the unchanged input before retrying. No automatic retries or cache.
    """
    from hair_card_core import build_card_geometry, create_card_object, surface_query
    validate_config(config)
    output = Path(output).expanduser().resolve()
    if not bpy.data.filepath or output == Path(bpy.data.filepath).resolve():
        raise ValueError('Load a saved input and choose a separate output file')
    if output.suffix.lower() != '.blend':
        raise ValueError('Output must end with .blend')
    report_path = output.with_suffix('.rebuild.json')
    if not overwrite and (output.exists() or report_path.exists()):
        raise FileExistsError('Output exists; choose another path or explicitly use --overwrite')
    if not output.parent.is_dir():
        raise ValueError('Output parent directory must already exist outside the skill package')
    package = Path(__file__).resolve().parents[1]
    if output.is_relative_to(package):
        raise ValueError('Write task artifacts outside the skill package')
    head, material, guides, collection = prepare_scene(bpy, config)
    nearest = surface_query(head, bpy.context.evaluated_depsgraph_get()) if head is not None else None
    prepared = []
    for spec in config['layers']:
        paths = [path for name in spec['guides'] for path in guides[name][::spec.get('stride', 1)]]
        geometry = build_card_geometry(paths, spec, config['atlas_columns'], config.get('surface_clearance', 0),
                                       nearest, config['seed'], config.get('placement', 'head_surface'))
        prepared.append((spec, geometry))
    if collection is None:
        collection = bpy.data.collections.new(config['output_collection'])
        bpy.context.scene.collection.children.link(collection)
    pending = []
    try:
        for spec, geometry in prepared:
            old = collection.objects.get(spec['name'])
            obj = create_card_object(bpy, spec['name'], geometry, material, collection, config['uv_name'])
            obj['source_objects'] = spec['guides']
            pending.append((spec, obj, old))
    except BaseException:
        for _, obj, _ in pending:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        raise
    for spec, obj, old in pending:
        if old is not None:
            old_mesh = old.data if old.type == 'MESH' else None
            bpy.data.objects.remove(old, do_unlink=True)
            if old_mesh is not None and old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
        obj.name = spec['name']
    for name in guides:
        bpy.context.scene.objects[name].hide_render = True
    source_path = bpy.data.filepath
    result = {'source_blend': source_path, 'output': str(output), 'blender': bpy.app.version_string,
              'layers': [{'name': obj.name, 'cards': obj['card_count'], 'vertices': len(obj.data.vertices),
                          'triangles': sum(len(p.vertices) - 2 for p in obj.data.polygons)} for _, obj, _ in pending],
              'scope': 'Geometry rebuild and save; visual quality, texture packing and engine validation are separate executor stages.'}
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding='utf-8'))
    import bpy
    result = run_rebuild(bpy, config, args.output, args.overwrite)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
