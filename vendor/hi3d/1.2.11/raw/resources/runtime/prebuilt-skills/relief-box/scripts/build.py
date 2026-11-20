"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys, os
from pathlib import Path
import bpy
import json
import numpy as np
from box_core import union_solids
from planar_audit import bounds
from planar_core import MM, cube, height_mesh, loft, loop, material, plate, ring3, ring_relief, tube
from planar_preview import camera, clean, export_glb, save, stage
from planar_print import export_stl_legacy as export_stl
import argparse
from types import SimpleNamespace
from functools import partial
from box_runtime import cli_arguments, validate_paths, load_config
from planar_render import render as _render_base

from cli_schemas import heightfield_stage

def build(*, output, heightfields, config, no_render=False):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    args=SimpleNamespace(output=output, heightfields=heightfields, config=config, no_render=no_render)
    validate_paths(args)
    render=partial(_render_base, enabled=not getattr(args, "no_render", False))
    config = load_config(args.config, required=('variants', 'relief_roles'))
    roles = config['relief_roles']
    if not config.get('variants'):
        raise ValueError('Explicit variants required; choose each physical envelope from stored items')
    for kind,w,h,d,x in config['variants']:
        if kind not in ('rect','circle') or min(w,h) < 70 or d < 30 or (kind=='circle' and w != h):
            raise ValueError('Basic recipe supports rect/circle, >=70mm width/depth and >=30mm height; otherwise adapt tray')
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    D = np.load(args.heightfields)
    clean()
    gold = material('Champagne metal accents', (0.64, 0.35, 0.115), 0.76, 0.31)
    blue = material('Deep lagoon lacquer', (0.018, 0.075, 0.089), 0.35, 0.3)
    velvet = material('Removable felt lining | plum', (0.115, 0.037, 0.063), 0, 0.86)
    dark = material('Tray polymer', (0.03, 0.038, 0.042), 0, 0.45)
    allobj = []
    variants = []
    animations = []
    (OUT / 'print').mkdir(exist_ok=True)
    for idx, (kind, w, h, depth, xx) in enumerate(config['variants']):
        objects = []
        body = tube('Box body / ' + kind, w, h, depth, 3, 3, kind, blue)
        objects.append(body)
        outer = loop(w + 0.8, h + 0.8, kind)
        skirt = loop(w - 6 - 0.8, h - 6 - 0.8, kind)
        skirtin = loop(w - 12 - 0.8, h - 12 - 0.8, kind)
        lipz = depth - 5
        topz = depth + 0.5
        lid = loft('Lift lid with integrated locating skirt / ' + kind, [ring3(outer, topz + 3.2), ring3(outer, topz), ring3(skirt, topz), ring3(skirt, lipz), ring3(skirtin, lipz), ring3(skirtin, topz)], blue, True, True)
        objects.append(lid)
        cw = w * float(config.get('medallion_width_fraction', 0.72))
        ch = min(h * 0.55, cw * D[roles['medallion']].shape[0] / D[roles['medallion']].shape[1])
        crest = height_mesh('Relief lid medallion / ' + kind, D[roles['medallion']], cw, ch, 2.5, 1.1, gold, nx=600, ny=180)
        crest.location.z = (topz + 3.1) * MM
        objects.append(crest)
        toptrim = ring_relief('Relief lid border / ' + kind, w - 5, h - 5, 12, kind, D[roles['border']], gold, z=topz + 3.15, depth=0.8, radial=20)
        objects.append(toptrim)
        trayw = w - 7.0
        trayh = h - 7.0
        tray = tube('Removable tray / ' + kind, trayw, trayh, 20, 1.8, 1.8, kind, dark)
        tray.location.z = 3.5 * MM
        objects.append(tray)
        trayparts = [tray]
        liners = []
        if kind == 'rect':
            divider1 = cube('Tray central divider', (1.8, trayh - 1.2, 17), (0, 0, 13.8), dark, 0.5)
            divider2 = cube('Tray cross divider', (trayw * 0.50, 1.8, 17), (trayw * 0.25, 0, 13.8), dark, 0.5)
            trayparts.extend([divider1, divider2])
            objects += trayparts[1:]
            for px, py, ww, hh in [(-trayw * 0.25, 0, trayw * 0.45, trayh - 7), (trayw * 0.25, -trayh * 0.25, trayw * 0.45, trayh * 0.43), (trayw * 0.25, trayh * 0.25, trayw * 0.45, trayh * 0.43)]:
                o = cube('Replaceable felt insert', (ww, hh, 1), (px, py, 5.8), velvet, 0.8)
                objects.append(o)
                liners.append(o)
            for i in range(3):
                bpy.ops.mesh.primitive_torus_add(major_radius=8.5 * MM, minor_radius=1.1 * MM, major_segments=64, minor_segments=16, location=((trayw * 0.25 + (i - 1) * 21) * MM, -trayh * 0.25 * MM, 8 * MM))
                o = bpy.context.object
                o.name = 'Example ring / visual fit gauge'
                o.data.materials.append(gold)
                objects.append(o)
        else:
            o = plate('Replaceable round felt', trayw - 5, trayh - 5, 1, 5.8, kind, velvet)
            objects.append(o)
            liners.append(o)
            for i in range(2):
                bpy.ops.mesh.primitive_torus_add(major_radius=12 * MM, minor_radius=1.5 * MM, major_segments=64, minor_segments=16, location=((i - 0.5) * 33 * MM, 0, 9 * MM))
                o = bpy.context.object
                o.name = 'Example small jewellery / visual fit gauge'
                o.data.materials.append(gold)
                objects.append(o)
        for sx in [-1, 1]:
            o = cube('Tray lift tab', (5, 14, 3), (sx * (trayw / 2 - 2), 0, 24), gold, 0.6)
            objects.append(o)
            trayparts.append(o)
        # Export one continuous tray; coincident/intersecting submeshes are not a printable union.
        tools = trayparts[1:]
        objects = [o for o in objects if o not in tools]
        union_solids(tray, tools)
        trayparts = [tray]
        for o in objects:
            o['product_part'] = True
            o.location.x += xx * MM
        allobj += objects
        export_glb(OUT / (kind + '-closed.glb'), objects)
        for title, parts in [('body', [body]), ('lid', [lid]), ('medallion', [crest]), ('lid-border', [toptrim]), ('tray', trayparts)]:
            export_stl(OUT / 'print' / f'{kind}-{title}-mm.stl', parts)
        for o in [lid, crest, toptrim]:
            o.location.z += 72 * MM
        export_glb(OUT / (kind + '-open.glb'), objects)
        for o in [lid, crest, toptrim]:
            o.location.z -= 72 * MM
        animations.append({'kind': kind, 'lid': [lid.name, crest.name, toptrim.name], 'tray': [o.name for o in trayparts + liners + [x for x in objects if x.name.startswith('Example ')]], 'body': body.name})
        variants.append({'id': kind, 'outer_mm': [w, h, depth], 'cavity_net_mm': [w - 6, h - 6, depth - 3], 'tray_outer_mm': [trayw, trayh, 20], 'tray_clearance_per_side_mm': 0.5, 'lid_skirt_clearance_per_side_mm': 0.4, 'lid_lift_mm': 72, 'nominal_bottom_mm': 3, 'nominal_wall_mm': 3, 'usable_height_above_insert_floor_mm': depth - 6.3, 'bounds': bounds(objects)})
    export_glb(OUT / 'model.glb', allobj)
    json.dump({'variants': variants, 'animation_groups': animations, 'mesh_cleanup_tolerance_m':1e-9,'physical_test': 'not performed', 'opening': 'unconstrained manual vertical lift; no hinge claim'}, open(OUT / 'measurements.json', 'w'), indent=2)
    cam = stage((-20, 0, 30), 350)
    camera(cam, (-20, 0, 30), (140, -220, 250), 385)
    save(OUT / 'scene.blend')
    render(OUT / 'hero.png', 1450, 1100, 32)
    for group in animations:
        for name in group['lid']:
            bpy.data.objects[name].location.z += 72 * MM
    camera(cam, (-20, 0, 55), (110, -190, 300), 400)
    render(OUT / 'open.png', 1450, 1100, 28)
    for group in animations:
        for name in group['lid']:
            bpy.data.objects[name].hide_render = True
    camera(cam, (-20, 0, 10), (0, 0, 350), 360)
    render(OUT / 'interior.png', 1400, 900, 24)
    for group in animations:
        for name in group['lid']:
            bpy.data.objects[name].hide_render = False
            bpy.data.objects[name].location.z -= 72 * MM
    camera(cam, (-20, 0, 30), (140, -220, 250), 385)
    save(OUT / 'scene.blend')

def main(argv=None):
    return heightfield_stage(build, cli_arguments, argv)

if __name__ == "__main__":
    main()
