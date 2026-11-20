"""Assembly operations on explicit objects, with persisted roles for independent review."""
import json
import math
import bpy
from mathutils import Vector
from scene_samples import sample_frames, world_mesh
from surface_pairs import bounds_overlap as overlaps, surface_tree
from geometry import MM, parent_keep_world

MANIFEST = 'relief_palette_manifest'


def hinge_control(collection, objects, hinge, keys):
    ctrl = bpy.data.objects.new('Palette lid control', None)
    collection.objects.link(ctrl)
    ctrl.location = Vector(hinge['pivot_mm'])*MM
    for obj in objects:
        parent_keep_world(obj, ctrl)
    ctrl['open_angle'] = 0.0
    ctrl.id_properties_ui('open_angle').update(min=0, max=hinge['max_angle'])
    curve = ctrl.driver_add('rotation_euler', 'XYZ'.index(hinge['axis']))
    curve.driver.expression = f"angle * {hinge['sign']} * pi / 180"
    variable = curve.driver.variables.new()
    variable.name = 'angle'
    variable.targets[0].id = ctrl
    variable.targets[0].data_path = '["open_angle"]'
    for frame, angle in keys:
        ctrl['open_angle'] = float(angle)
        ctrl.keyframe_insert(data_path='["open_angle"]', frame=frame)
    return ctrl


def tree(data):
    return surface_tree(data[0],data[1])


def validate_scene(scene):
    """Sample evaluated triangle intersections, endpoints and vertical closed clearance.

    This is a surface test, not continuous collision detection or a containment
    proof. Specific intended-contact object pairs remain listed in the report.
    """
    if bpy.context.scene != scene:
        raise ValueError('Activate the task scene before evaluating its dependency graph')
    info = json.loads(scene[MANIFEST])
    registry = {o.name: o for o in scene.objects}
    for key in ('moving', 'stationary', 'contents', 'reliefs', 'cakes'):
        if any(name not in registry for name in info[key]):
            raise ValueError('Missing registered object in '+key)
    original_frame = (scene.frame_current,scene.frame_subframe)
    collisions, poses, changed, motion_errors = [], [], set(), []
    ctrl = registry[info['control']]
    if any(registry[n].parent != ctrl for n in info['moving']):
        motion_errors.append('Moving geometry lost its controller binding')
    ignored = {frozenset(contact['objects']) for contact in info['contacts']}
    try:
        scene.frame_set(info['keyframes'][0][0])
        bpy.context.view_layer.update()
        static_data = {name: world_mesh(registry[name]) for name in info['stationary']}
        matrices = {name: registry[name].matrix_world.copy() for name in info['stationary']}
        static_trees = {}
        mirror = registry.get(info['mirror'])
        clearance = None
        if mirror and info['contents']:
            top = max(world_mesh(registry[n])[2][1][2] for n in info['contents'])
            clearance = (world_mesh(mirror)[2][0][2]-top)/MM
        frames = sorted(set(info['check_frames'] + [k[0] for k in info['keyframes']]))
        def inspect_pose(frame):
            angle = float(ctrl['open_angle'])
            evaluated = ctrl.evaluated_get(bpy.context.evaluated_depsgraph_get())
            axis = 'XYZ'.index(info['hinge']['axis'])
            expected = [0.0, 0.0, 0.0]
            expected[axis] = math.radians(angle)*info['hinge']['sign']
            actual = tuple(evaluated.rotation_euler)
            poses.append({'frame': frame, 'angle': angle, 'rotation_radians': actual})
            key_angle = dict(info['keyframes']).get(frame)
            if (not -1e-4 <= angle <= info['hinge']['max_angle']+1e-4
                    or (key_angle is not None and abs(angle-key_angle)>1e-4)
                    or any(abs(a-b)>1e-5 for a,b in zip(actual,expected))):
                motion_errors.append(f'Controller motion differs from declared hinge at frame {frame}')
            for name in info['stationary']:
                if any(abs(a-b)>1e-9 for ra, rb in zip(registry[name].matrix_world, matrices[name]) for a,b in zip(ra,rb)):
                    changed.add(name)
            for name in info['moving']:
                a = world_mesh(registry[name])
                a_tree = None
                for other, b in static_data.items():
                    if frozenset((name, other)) in ignored or not overlaps(a[2], b[2]):
                        continue
                    a_tree = a_tree or tree(a)
                    if other not in static_trees:
                        static_trees[other] = tree(b)
                    hits = a_tree.overlap(static_trees[other])
                    if hits:
                        collisions.append({'frame': frame, 'moving': name, 'stationary': other, 'triangle_pairs': len(hits)})
        sample_frames(scene,frames,inspect_pose)
        colors = []
        matching = True
        for cake_name, relief_name in zip(info['cakes'], info['reliefs']):
            cake, relief = registry[cake_name], registry[relief_name]
            matching = matching and len(cake.data.materials)==1 and len(relief.data.materials)==1 and cake.data.materials[0]==relief.data.materials[0]
            colors.append(tuple(cake.data.materials[0].diffuse_color))
        material_ok = matching and len(set(colors))==len(colors)
        passed = not collisions and not changed and not motion_errors and material_ok and (clearance is None or clearance>0)
        return dict(passed=passed, application=bpy.app.version_string, file=bpy.data.filepath,
                    surface_intersections=collisions, intended_contacts=info['contacts'], poses=poses,
                    stationary_transform_changes=sorted(changed), motion_errors=motion_errors,
                    closed_vertical_clearance_mm=clearance,
                    pan_count=len(info['cakes']), unique_same_material_pairs=material_ok,
                    boundary='Sampled surfaces and vertical clearance only; no full containment, continuous-motion or physical-manufacturing proof.')
    finally:
        scene.frame_set(original_frame[0],subframe=original_frame[1])


def store_roles(scene, config, built, ctrl, cakes, reliefs):
    required = {'stationary', 'moving', 'contents', 'studio', 'shots'}
    if not required <= set(built):
        raise ValueError('Builder must return all required role lists and shots')
    for key in ('stationary', 'moving', 'contents', 'studio'):
        if not isinstance(built[key], list) or any(o.name not in scene.objects for o in built[key]):
            raise ValueError('Builder returned objects outside the task scene')
    if not built['moving']:
        raise ValueError('Register the actual moving lid geometry')
    ids = [o.name for o in built['stationary'] + built['moving'] + built['studio']]
    if len(ids) != len(set(ids)):
        raise ValueError('Collision and studio roles must be disjoint')
    geometry = [o.name for o in scene.objects if o.type in {'MESH', 'CURVE', 'FONT'}]
    all_roles = set(ids) | {o.name for o in cakes+reliefs}
    if set(geometry) != all_roles:
        raise ValueError('Every visible/collision geometry must have an explicit role')
    contacts = []
    for c in built.get('contacts', []):
        pair = c['objects']
        if len(pair)!=2 or pair[0]==pair[1] or not c.get('reason'):
            raise ValueError('Intended contacts need two distinct objects and a reason')
        if not any(o in built['moving'] for o in pair) or not any(o in built['stationary'] for o in pair):
            raise ValueError('Contacts must identify a moving/stationary pair')
        contacts.append({'objects': [o.name for o in pair], 'reason': c['reason']})
    if any(o not in built['stationary'] for o in built['contents']):
        raise ValueError('Contents must be stationary during the lid test')
    mirror = built.get('mirror')
    if mirror is not None and mirror not in built['moving']:
        raise ValueError('Mirror must belong to the moving lid')
    info = dict(moving=[o.name for o in built['moving']],
                stationary=[o.name for o in built['stationary']+cakes+reliefs],
                contents=[o.name for o in built['contents']+cakes+reliefs],
                studio=[o.name for o in built['studio']], control=ctrl.name,
                mirror=mirror.name if mirror else None, contacts=contacts,
                cakes=[o.name for o in cakes], reliefs=[o.name for o in reliefs],
                keyframes=config['keyframes'], check_frames=config['check_frames'], hinge=config['hinge'])
    scene[MANIFEST] = json.dumps(info)
    return info
