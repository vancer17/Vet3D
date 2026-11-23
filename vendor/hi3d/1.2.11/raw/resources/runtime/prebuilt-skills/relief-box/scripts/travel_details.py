"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys, argparse, json, html
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from planar_audit import bounds
from planar_core import MM, cube
from planar_preview import camera, export_glb
from planar_print import export_stl_legacy as export_stl
from types import SimpleNamespace
from functools import partial
from box_runtime import cli_arguments, validate_paths
from planar_render import render as _render_base

def render_details(*, scene, output):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(scene=scene, output=output)
    validate_paths(a)
    render=partial(_render_base, enabled=not getattr(a, "no_render", False))
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.scene).resolve()))
    s = bpy.context.scene
    cam = s.camera
    parts = list(bpy.data.collections['CORAL TRAVEL ASSEMBLY'].objects)
    soft = [o for o in parts if 'foam' in o.name.lower() or 'microsuede' in o.name.lower()]
    (out / 'soft-part-shaping-references').mkdir(exist_ok=True)
    records = []
    for i, o in enumerate(soft):
        filename = '%02d-soft-shaping-reference.stl' % i
        export_stl(out / 'soft-part-shaping-references' / filename, [o])
        b = bounds([o])
        records.append({'object': o.name, 'file': filename, **b, 'purpose': 'Reference for cutting or shaping purchased soft material, not a rigid FDM part'})
        if 'roll' in o.name:
            continue
        eo = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
        m = eo.to_mesh()
        m.calc_loop_triangles()
        v = np.array([eo.matrix_world @ x.co for x in m.vertices]) / MM
        tri = v[np.array([list(t.vertices) for t in m.loop_triangles])]
        zz = (v[:, 2].min() + v[:, 2].max()) / 2
        lines = []
        for t in tri:
            hits = []
            for u, j in [(0, 1), (1, 2), (2, 0)]:
                if (t[u, 2] < zz) != (t[j, 2] < zz):
                    hits.append(t[u, :2] + (t[j, :2] - t[u, :2]) * (zz - t[u, 2]) / (t[j, 2] - t[u, 2]))
            if len(hits) == 2:
                lines.append(hits)
        lo = v[:, :2].min(0)
        hi = v[:, :2].max(0)
        wh = hi - lo + 10
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%.3fmm" height="%.3fmm" viewBox="0 0 %.3f %.3f">' % (*wh, *wh), '<g stroke="black" stroke-width="0.15" fill="none">']
        for v1, v2 in lines:
            q1 = v1 - lo + 5
            q2 = v2 - lo + 5
            svg.append('<path d="M %.5f %.5f L %.5f %.5f"/>' % (*q1, *q2))
        svg.append('</g></svg>')
        (out / 'soft-part-shaping-references' / ('%02d-midplane-cutting-template.svg' % i)).write_text(''.join(svg))
        eo.to_mesh_clear()
    (out / 'soft-part-shaping-references' / 'dimensions.json').write_text(json.dumps(records, indent=2))
    for o in parts:
        o.hide_render = o.get('assembly_role') != 'lid'
    floor = bpy.data.objects.get('Dressing table')
    floor.hide_render = True
    camera(cam, (0, 0, 28), (120, -190, -200), 215)
    ld = bpy.data.lights.new('Underside inspection softbox', 'AREA')
    ld.energy = 3.0
    ld.shape = 'DISK'
    ld.size = 0.18
    lo = bpy.data.objects.new('Underside inspection softbox', ld)
    s.collection.objects.link(lo)
    lo.location = (0.08, -0.13, -0.16)
    lo.rotation_euler = (Vector((0, 0, 0.028)) - lo.location).to_track_quat('-Z', 'Y').to_euler()
    render(out / 'lid-underside.png', 1400, 1000, 24)
    bpy.data.objects.remove(lo, do_unlink=True)
    for o in parts:
        o.hide_render = False
    floor.hide_render = False
    for o in parts:
        if o.get('assembly_role') == 'lid':
            o.hide_render = True
        if str(o.get('assembly_role')).startswith('screw'):
            o.hide_render = True
        if o.get('assembly_role') == 'spool':
            o.location.z += 0.038
        if o.get('assembly_role') == 'earcard':
            o.location.z += 0.038
    camera(cam, (20, 0, 36), (90, -160, 125), 165)
    render(out / 'retention-detail.png', 1400, 1100, 24)
    for o in parts:
        o.location = o['home_location']
        o.rotation_euler = o['home_rotation']
        o.hide_render = False
    section = []
    for o in parts:
        if o.get('assembly_role') not in ['body', 'lid', 'tray', 'earcard', 'spool']:
            continue
        bpy.context.view_layer.objects.active = o
        for m in list(o.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)
        cut = cube('Actual section cutting halfspace', (500, 500, 500), (0, -250, 100), o.data.materials[0], 0)
        bpy.context.view_layer.objects.active = o
        m = o.modifiers.new('Section at Y zero', 'BOOLEAN')
        m.operation = 'DIFFERENCE'
        m.solver = 'MANIFOLD'
        m.object = cut
        bpy.ops.object.modifier_apply(modifier=m.name)
        bpy.data.objects.remove(cut, do_unlink=True)
        section.append(o)
    for o in parts:
        if o not in section:
            o.hide_render = True
    camera(cam, (0, 15, 24), (75, -240, 80), 230)
    render(out / 'section.png', 1400, 900, 24)
    export_glb(out / 'section.glb', section)
    (out / 'section-model-bounds.json').write_text(json.dumps(bounds(section), indent=2))
    print('DETAILS_COMPLETE', flush=True)

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--scene', required=True)
    p.add_argument('--output', required=True)
    options=p.parse_args(cli_arguments(argv))
    return render_details(**vars(options))

if __name__ == "__main__":
    main()
