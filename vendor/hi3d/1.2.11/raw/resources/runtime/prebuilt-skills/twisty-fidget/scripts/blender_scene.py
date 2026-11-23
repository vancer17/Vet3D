"""Background Blender adapter: synchronized screw animation and fresh-import evidence."""
import argparse
import math
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from motion import offsets, screw_pose, stop_travel_limits
from run import read_json, write_json, digest, resolve_input
from timing import stage
from glb_clips import read_glb


def import_parts(manifest_path, scene):
    import bpy
    from mathutils import Matrix
    manifest = read_json(manifest_path)
    if manifest['schema'] != 'twisty.assembly.v1' or manifest['unit'] != 'mm' or manifest['axis'] != 'Z':
        raise ValueError('expected millimeter Z-axis assembly')
    parts = []
    for i, row in enumerate(manifest['parts']):
        path = resolve_input(manifest_path.parent, row['file'])
        if digest(path) != row['sha256']:
            raise ValueError('part content no longer matches assembly')
        bpy.ops.wm.stl_import(filepath=str(path))
        obj = bpy.context.object
        obj.name = f'Petal_{i+1:03d}'
        obj.data.transform(Matrix.Scale(.001, 4))
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
        obj.data.set_sharp_from_angle(angle=math.radians(45))
        mat = bpy.data.materials.new(f'PetalMaterial_{i%2}')
        mat.diffuse_color = (.12, .42, .47, 1) if i%2 else (.35, .69, .70, 1)
        mat.use_nodes = True
        mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = mat.diffuse_color
        obj.data.materials.append(mat)
        parts.append(obj)
    if len(parts) != manifest['count']:
        raise ValueError('part count mismatch')
    return manifest, parts


def animate(parts, displacements, k, fps):
    import bpy
    keys = [(1, 0), (fps+1, 0), (4*fps+1, 1), (5*fps+1, 1), (8*fps+1, 0)]
    for obj, distance in zip(parts, displacements):
        for frame, progress in keys:
            z, angle = screw_pose(distance, progress, k)
            obj.location.z = z*.001
            obj.rotation_euler.z = math.radians(angle)
            obj.keyframe_insert('location', frame=frame)
            obj.keyframe_insert('rotation_euler', frame=frame)
    bpy.context.scene.frame_end = keys[-1][0]
    return [1, fps+1, round(2.5*fps)+1, 4*fps+1, 5*fps+1, round(6.5*fps)+1, 8*fps+1]


def sample_transforms(scene, parts, frames):
    import bpy
    result = {}
    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        result[frame] = {o.name: (o.matrix_world.translation.copy(), o.matrix_world.to_quaternion().copy()) for o in parts}
    return result


def compare_transforms(scene, parts, expected, k):
    from mathutils import Quaternion
    actual = sample_transforms(scene, parts, list(expected))
    if set(actual[next(iter(actual))]) != set(expected[next(iter(expected))]):
        raise ValueError('export changed required part names')
    errors = []
    for frame, objects in actual.items():
        for name, (p, q) in objects.items():
            ep, eq = expected[frame][name]
            angle_error = math.degrees(2*math.acos(min(1., abs(q.dot(eq)))))
            target = Quaternion((0, 0, 1), math.radians(k*p.z*1000))
            screw_error = math.degrees(2*math.acos(min(1., abs(q.dot(target)))))
            errors.append({'frame': frame, 'part': name, 'position_error_mm': (p-ep).length*1000,
                           'rotation_error_deg': angle_error, 'screw_error_deg': screw_error})
    return errors


def check_glb_layout(path, names):
    """Check the exported file, including accidental objects from other scenes."""
    gltf, _ = read_glb(path.read_bytes())
    mesh_names = [n.get('name') for n in gltf['nodes'] if 'mesh' in n]
    if sorted(mesh_names) != sorted(names) or len(gltf.get('animations', [])) != 1:
        raise ValueError('GLB must contain exactly the required petals and one synchronized clip')


def render_views(scene, parts, out, open_frame):
    import bpy
    from mathutils import Vector
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.world = bpy.data.worlds.new('TwistyWorld')
    scene.world.color = (.055, .062, .07)
    scene.display.shading.background_type = 'WORLD'
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x = scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = 'ORTHO'
    scene.camera = camera
    directions = {'front': (0, -1, .02), 'back': (0, 1, .02), 'left': (-1, 0, .02),
                  'right': (1, 0, .02), 'top': (0, .001, 1), 'hero': (1, -2, .3)}
    for name, frame in [('closed', 1), ('open', open_frame)]:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        corners = [o.matrix_world @ Vector(p) for o in parts for p in o.bound_box]
        low = Vector([min(p[d] for p in corners) for d in range(3)])
        high = Vector([max(p[d] for p in corners) for d in range(3)])
        center = (low+high)/2
        camera.data.ortho_scale = (high-low).length*1.15
        for view, direction in directions.items():
            camera.location = center+Vector(direction).normalized()*max(1, (high-low).length*3)
            camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = str(out/f'{name}_{view}.png')
            bpy.ops.render.render(write_still=True)


def main():
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assembly', type=Path, required=True)
    parser.add_argument('--travel-mm', type=float, required=True)
    parser.add_argument('--mode', choices=['staircase', 'wave'], required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--previous-attempt-id')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if not bpy.app.background:
        raise RuntimeError('run in a separate background Blender process')
    if not math.isfinite(args.travel_mm) or args.travel_mm <= 0:
        raise ValueError('animation requires positive travel; use build for a closed-only model')
    out = args.out.resolve()
    if Path(__file__).resolve().parents[1] in (out, *out.parents) or args.fps < 1:
        raise ValueError('valid fps and output outside skill package required')
    out.mkdir(parents=True, exist_ok=False)
    attempt = uuid.uuid4().hex
    def timed(name):
        return stage(out/'timings.jsonl', args.task_id, attempt, name, args.previous_attempt_id)
    with timed('blender_export'):
        scene = bpy.data.scenes.new('Twisty')
        bpy.context.window.scene = scene
        scene.render.fps = args.fps
        scene.unit_settings.system = 'METRIC'
        scene.unit_settings.length_unit = 'MILLIMETERS'
        manifest, parts = import_parts(args.assembly.resolve(), scene)
        positions = offsets(len(parts), args.travel_mm, args.mode)
        ranges = stop_travel_limits(positions, manifest.get('axial_stops', {}).get('interfaces', []))
        if any(not r['within_limits'] for r in ranges):
            raise ValueError('requested animation crosses an integral stop limit')
        frames = animate(parts, positions, manifest['k_deg_per_mm'], args.fps)
        expected = sample_transforms(scene, parts, frames)
        scene.frame_set(1)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in parts:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.export_scene.gltf(filepath=str(out/'animated.glb'), export_format='GLB',
            use_selection=True, use_active_scene=True, export_animations=True, export_animation_mode='SCENE',
            export_anim_scene_split_object=False, export_frame_range=True, export_yup=True)
        check_glb_layout(out/'animated.glb', list(expected[1]))
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
    with timed('fresh_import'):
        # The source is safely saved; verification uses a separate new scene, not live content.
        scene = bpy.data.scenes.new('Reimport')
        bpy.context.window.scene = scene
        scene.render.fps = args.fps
        bpy.ops.import_scene.gltf(filepath=str(out/'animated.glb'), merge_vertices=True)
        parts = sorted([o for o in scene.objects if o.type == 'MESH'], key=lambda o: o.name)
        # Blender suffixes globally duplicated object names; resolve only the expected import suffix.
        for obj in parts:
            base = obj.name.rsplit('.', 1)[0]
            if base in expected[1]:
                bpy.data.objects[base].name = 'Source_'+base
                obj.name = base
        errors = compare_transforms(scene, parts, expected, manifest['k_deg_per_mm'])
        passed = all(r['position_error_mm'] < .01 and r['rotation_error_deg'] < .1
                     and r['screw_error_deg'] < .1 for r in errors)
        write_json(out/'reimport.json', {'passed': passed, 'checks': errors,
            'glb_sha256': digest(out/'animated.glb'), 'sample_frames': frames,
            'assembly_sha256': digest(args.assembly), 'mode': args.mode, 'travel_mm': args.travel_mm,
            'scope': 'Transform agreement, not collision or mechanical synchronization verification'})
        if not passed:
            raise ValueError('exported transforms do not agree; see reimport.json')
    with timed('render_evidence'):
        render_views(scene, parts, out, 4*args.fps+1)
    print(out)


if __name__ == '__main__':
    main()
