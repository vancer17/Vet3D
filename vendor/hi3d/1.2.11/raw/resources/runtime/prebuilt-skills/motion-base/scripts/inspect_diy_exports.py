"""Fresh Blender import, all-frame mechanical transforms, and packed native dependency audit."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys, argparse, json, hashlib
from pathlib import Path
import numpy as np
from mathutils import Vector
from glb_clips import read_glb
from stage_cli import cli_arguments, StageFinished, _finish_stage

from render_engine import set_engine

def sha(p):
    """Independently callable sha operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    return hashlib.sha256(p.read_bytes()).hexdigest()

def inventory():
    """Independently callable inventory operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    rows = []
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        vs = [o.matrix_world @ Vector(x) for x in o.bound_box]
        rows.append({'name': o.name, 'triangles': sum((len(p.vertices) - 2 for p in o.data.polygons)), 'bounds_mm': [[min((v[i] for v in vs)) * 1000 for i in range(3)], [max((v[i] for v in vs)) * 1000 for i in range(3)]], 'materials': [m.name for m in o.data.materials]})
    return rows

def build_parser():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    return p

def execute(a):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    out = a.output.resolve()
    work = a.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    info = json.loads((out / 'measurement.json').read_text())
    ids = [r['id'] for r in info['parts']]
    results = {}
    for filename in ['model.glb', 'assembly.glb']:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.render.fps = info['config']['fps']
        bpy.ops.import_scene.gltf(filepath=str(out / filename))
        sc.frame_set(1)
        bs = (out / filename).read_bytes()
        doc, _ = read_glb(bs)
        rows = inventory()
        assert all((any((r['name'] == x for r in rows)) for x in ids))
        results[filename] = {'sha256': sha(out / filename), 'bytes': len(bs), 'clips': [{'name': x.get('name'), 'channels': len(x['channels'])} for x in doc.get('animations', [])], 'objects': rows}
        if filename == 'assembly.glb':
            assert len(doc.get('animations', [])) == 1
            obs = {i: bpy.data.objects[i] for i in ids}
            meshdir = work / 'fresh-animation-meshes'
            meshdir.mkdir(exist_ok=True)
            for name, o in obs.items():
                me = o.data
                me.calc_loop_triangles()
                vs = np.zeros(len(me.vertices) * 3, np.float32)
                me.vertices.foreach_get('co', vs)
                f = np.array([t.vertices[:] for t in me.loop_triangles], np.uint32)
                np.savez(meshdir / f'{name}.npz', vertices=vs.reshape(-1, 3) * 1000, faces=f)
            poses = []
            deformed_frames = {name: [] for name in obs if name.startswith('pin-')}
            for f in range(1, info['config']['video_frames'] + 1):
                sc.frame_set(f)
                poses.append({'frame': f, 'matrices': {name: np.array(o.matrix_world).tolist() for name, o in obs.items()}})
                dg = bpy.context.evaluated_depsgraph_get()
                for name in deformed_frames:
                    ev = obs[name].evaluated_get(dg)
                    me = ev.to_mesh()
                    v = np.zeros(len(me.vertices) * 3, np.float32)
                    me.vertices.foreach_get('co', v)
                    deformed_frames[name].append(v.reshape(-1, 3) * 1000)
                    ev.to_mesh_clear()
            for name, vs in deformed_frames.items():
                np.savez_compressed(meshdir / f'{name}-deformation.npz', vertices=np.asarray(vs))
            results[filename]['deformation_peak_coordinate_change_mm'] = {name: float(np.max(np.abs(np.asarray(vs) - np.asarray(vs)[0]))) for name, vs in deformed_frames.items()}
            assert all((v > 0.3 for v in results[filename]['deformation_peak_coordinate_change_mm'].values())), 'Actual fresh-import shape motion absent'
            (work / 'fresh-animation-transforms.json').write_text(json.dumps(poses))
            results[filename]['all_frames_exported_for_collision_check'] = len(poses)
            sc.frame_set(128)
            script = Path(__file__).resolve().parent
            sys.path.insert(0, str(script))
            from studio_preview import camera, render, stage
            for o in sc.objects:
                o['asset'] = o.type == 'MESH'
            target, extent = stage()
            set_engine(sc)
            camera((1.25, -2, 0.9), target, extent)
            render(out / 'fresh-import.png', frame=128, res=700)
    native = []
    for name in ['scene.blend', 'assembly.blend']:
        bpy.ops.wm.open_mainfile(filepath=str(out / name))
        images = []
        for im in bpy.data.images:
            if im.users and im.source == 'FILE':
                row = {'name': im.name, 'packed': bool(im.packed_file), 'size': list(im.size)}
                images.append(row)
                assert row['packed'], (name, row)
        native.append({'file': name, 'sha256': sha(out / name), 'images': images, 'meshes': inventory()})
    results['native'] = native
    results['blender_version'] = bpy.app.version_string
    results['physical_testing'] = 'not performed'
    (out / 'fresh-import.json').write_text(json.dumps(results, indent=2))
    print('FRESH IMPORT READY', flush=True)

def main(argv=None):
    try:
        return execute(build_parser().parse_args(cli_arguments(argv)))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
