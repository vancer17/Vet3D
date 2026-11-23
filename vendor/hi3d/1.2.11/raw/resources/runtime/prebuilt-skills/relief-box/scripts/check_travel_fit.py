"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, sys, argparse, json, numpy as np, hashlib
from pathlib import Path
from mathutils.bvhtree import BVHTree
from types import SimpleNamespace
from functools import partial
from box_runtime import cli_arguments, validate_paths

def inspect_fit(*, model, output):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(model=model, output=output)
    validate_paths(a)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(Path(a.model).resolve()))
    meshes = {}
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        o.data.calc_loop_triangles()
        v = np.array([o.matrix_world @ x.co for x in o.data.vertices]) * 1000
        f = np.array([tuple(t.vertices) for t in o.data.loop_triangles])
        meshes[o.name] = (v, f)
    def get(prefix):
        return next((n for n in meshes if n.startswith(prefix)), None)
    def tree(n, d=(0, 0, 0)):
        v, f = meshes[n]
        return BVHTree.FromPolygons((v + np.array(d)).tolist(), f.tolist(), all_triangles=True)
    rows = []
    def check(n, m, delta=(0, 0, 0), context='closed'):
        if not n or not m:
            return
        pairs = tree(n, delta).overlap(tree(m))
        v, f = meshes[n]
        faces = list(dict.fromkeys((i for i, j in pairs)))
        rows.append({'moving': n, 'fixed': m, 'translation_mm': delta, 'context': context, 'triangle_crossing_pairs': len(pairs), 'moving_triangle_centroids_mm': [(v[f[i]].mean(0) + delta).tolist() for i in faces[:10]]})
    body = get('Elliptical travel shell')
    tray = get('One piece removable divided')
    lid = get('Relief domed travel lid')
    card = get('Removable earring card')
    spool = get('Removable necklace winding')
    for x, y in [(tray, body), (card, tray), (spool, tray), (lid, body), (lid, tray), (lid, card), (lid, spool)]:
        check(x, y)
    for n in meshes:
        if 'capture foam' in n or n.startswith('Replaceable underside'):
            for m in [body, tray, card, spool] + [x for x in meshes if x.startswith('Earring ') or x.startswith('Example necklace') or x.startswith('Example ring') or ('elastic' in x.lower())]:
                check(n, m)
    for h in [1, 4, 8, 16, 32, 70]:
        for m in [body, tray, card, spool]:
            check(lid, m, (0, 0, h), 'lid vertical lift')
    for h in [1, 4, 12, 28, 45]:
        check(tray, body, (0, 0, h), 'tray vertical lift')
    for h in [1, 3, 8, 18]:
        check(card, tray, (0, 0, h), 'earring card lift')
        check(spool, tray, (0, 0, h), 'necklace core lift')
    out = {'input_sha256': hashlib.sha256(Path(a.model).read_bytes()).hexdigest(), 'method': 'Fresh imported actual GLB; triangle BVH in millimetres. Exact contact can be reported as crossing and needs local review. Soft roll compression and bought-thread engagement are separate intended relationships.', 'objects': len(meshes), 'checks': rows, 'nonzero_checks': sum((r['triangle_crossing_pairs'] > 0 for r in rows))}
    Path(a.output).write_text(json.dumps(out, indent=2))
    print('FIT_CHECK', len(rows), out['nonzero_checks'])

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True)
    p.add_argument('--output', required=True)
    options=p.parse_args(cli_arguments(argv))
    return inspect_fit(**vars(options))

if __name__ == "__main__":
    main()
