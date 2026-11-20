"""Read-only actual native attachment/arm/shell intersection audit."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys, json, hashlib
from pathlib import Path
from mathutils.bvhtree import BVHTree
from stage_cli import cli_arguments, StageFinished, _finish_stage

def tree(o):
    """Independently callable tree operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    m = o.data
    m.calc_loop_triangles()
    return BVHTree.FromPolygons([o.matrix_world @ v.co for v in m.vertices], [p.vertices for p in m.loop_triangles], all_triangles=True, epsilon=1e-08)

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    A = arguments
    source = Path(A[0])
    target = Path(A[1])
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.view_layer.update()
    arm = next((o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('Hi3D anatomical body')))
    shell = next((o for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('printable')))
    attachments = [o for o in bpy.context.scene.objects if o.type == 'MESH' and any((s in o.name.lower() for s in ['foam pad', 'webbing', 'overlap']))]
    tarm = tree(arm)
    tshell = tree(shell)
    rows = []
    for o in attachments:
        t = tree(o)
        r = {'object': o.name, 'triangles': len(o.data.loop_triangles), 'arm_surface_intersection_pairs': len(t.overlap(tarm)), 'shell_surface_intersection_pairs': len(t.overlap(tshell))}
        rows.append(r)
        print(r, flush=True)
    target.write_text(json.dumps({'source': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'method': 'Actual full-resolution native geometry triangle intersections; surface sampling does not measure pressure, friction, or physical comfort.', 'attachment_count': len(attachments), 'checks': rows}, indent=2))
    if any((r['arm_surface_intersection_pairs'] or r['shell_surface_intersection_pairs'] for r in rows)):
        raise RuntimeError('Attachment intersects the actual arm or shell; inspect full-width geometry before delivery')

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
