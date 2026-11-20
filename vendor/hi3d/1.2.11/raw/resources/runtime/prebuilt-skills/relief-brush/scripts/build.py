"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys, os, argparse, shutil
from pathlib import Path
import bpy
import json
import math
import numpy as np
from brush_audit import bounds
from planar_core import MM, bevel, height_mesh, material, mesh, sample
from planar_preview import camera, clean, export_glb, save, stage
from planar_print import export_stl_legacy as export_stl
from field_ops import warp_surface
from types import SimpleNamespace
from functools import partial
from brush_runtime import cli_arguments, validate_paths, load_config
from brush_preview import render as _render_base

from cli_schemas import heightfield_stage

def build(*, output, heightfields, config, no_render=False):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    args=SimpleNamespace(output=output, heightfields=heightfields, config=config, no_render=no_render)
    validate_paths(args)
    render=partial(_render_base, enabled=not getattr(args, "no_render", False))
    config = load_config(args.config, required=('brush_roles', 'stamp_dimensions_mm'))
    OUT = args.output.resolve()
    D = np.load(args.heightfields)
    keys = [k for k in D.files if k != 'raw']
    roles = config['brush_roles']
    if set(roles) != set(['main', 'tile', 'border']) or any((x not in keys for x in roles.values())):
        raise ValueError('brush_roles must map main/tile/border to actual extracted region names')
    meta = json.load(open(args.heightfields.parent / 'metadata.json'))
    specs = meta.get('region_specs', {})
    if any(k not in config.get('stamp_dimensions_mm', {}) for k in keys):
        raise ValueError('Assign physical stamp_dimensions_mm to every region')
    for k in keys:
        if min(config['stamp_dimensions_mm'][k]) <= 0 or not (args.heightfields.parent / f'{k}.png').is_file():
            raise ValueError('Positive physical dimensions and matching linear PNG required for each region')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'brushes').mkdir(exist_ok=True)
    files = [args.heightfields, args.heightfields.parent / 'metadata.json'] + [args.heightfields.parent / f'{k}.png' for k in keys]
    for f in files:
        if f.resolve() != (OUT / 'brushes' / f.name).resolve():
            shutil.copy2(f, OUT / 'brushes' / f.name)
    clean()
    palette = config.get('palette', {})
    gold = material('Satin bronze relief', palette.get('stamp', [0.38, 0.22, 0.085]), 0.58, 0.38)
    teal = material('Graphite ceramic receiving surface', palette.get('surface', [0.047, 0.082, 0.087]), 0.28, 0.36)
    ivory = material('Chalk composite', palette.get('border', [0.68, 0.65, 0.55]), 0.07, 0.44)
    objects = []
    variants = []
    stamps = []
    coupons = []
    borders = []
    for i, k in enumerate(keys):
        a = D[k]
        w, h, dep = config['stamp_dimensions_mm'][k]
        o = height_mesh(k + ' | closed geometry stamp', a, w, h, dep, 2.4, gold, nx=300, ny=140)
        o.location = ((i - (len(keys) - 1) / 2) * 110 * MM, 72 * MM, 0)
        o.asset_mark()
        objects.append(o)
        stamps.append(o)
        export_stl(OUT / (k + '-stamp-mm.stl'), [o])
        export_glb(OUT / (k + '-stamp.glb'), [o])
        img = bpy.data.images.load(str(args.heightfields.parent / f'{k}.png'))
        img.colorspace_settings.name = 'Non-Color'
        img.pack()
        tex = bpy.data.textures.new(k + ' linear height', type='IMAGE')
        tex.image = img
        tex.extension = 'REPEAT' if specs.get(k, {}).get('mode') == 'tile' or k == roles['tile'] else 'CLIP'
        tex.use_fake_user = True
        b = bpy.data.brushes.new(k + ' | measured relief', mode='SCULPT')
        b.texture = tex
        b.strength = float(config.get('brush_strength', 0.45))
        b.texture_slot.map_mode = 'VIEW_PLANE'
        b.asset_mark()
        b.use_fake_user = True
    for kind, xx in [('plane', -110), ('cylinder', 0), ('double-curvature', 110)]:
        w, h = config.get('coverage_mm', [88, 38])
        depth = float(config.get('relief_depth_mm', 1.6))
        base = float(config.get('base_thickness_mm', 2.4))

        def warp(v):
            radius = float(config.get('cylinder_radius_mm',65) if kind=='cylinder' else config.get('sphere_radius_mm',80))
            return warp_surface(v,kind,radius)
        o = height_mesh(roles['main'] + ' on ' + kind, D[roles['main']], w, h, depth, base, teal, nx=360, ny=144, warp=warp)
        o.location = (xx * MM, -10 * MM, 0)
        objects.append(o)
        coupons.append(o)
        export_glb(OUT / (kind + '.glb'), [o])
        export_stl(OUT / (kind + '-coupon-mm.stl'), [o])
        variants.append({'id': kind, 'region': roles['main'], 'coverage_mm': [w, h], 'max_depth_mm': depth, 'bounds': bounds([o])})
    for i in range(int(config.get('path_count', 9))):
        a = (i - (int(config.get('path_count', 9)) - 1) / 2) * float(config.get('path_angle_step', 0.15))
        x = math.sin(a) * 190
        y = -112 + math.cos(a) * 28
        o = height_mesh('Path ' + roles['border'] + ' %02d' % i, D[roles['border']], 20, 16, 1.6, 1.8, ivory, nx=100, ny=80)
        o.location = (x * MM, y * MM, 0)
        o.rotation_euler[2] = -a
        objects.append(o)
        borders.append(o)
    for i, part in enumerate(borders, 1):
        export_stl(OUT / ('path-segment-%02d-mm.stl' % i), [part])
    export_glb(OUT / 'path-border.glb', borders)
    sleeve = None
    if config.get('grip_sleeve'):
        g = config['grip_sleeve']
        inner = float(g.get('inner_diameter_mm', 12.6)) / 2
        wall = float(g.get('wall_mm', 2))
        height = float(g.get('height_mm', 58))
        depth = float(g.get('relief_mm', 0.7))
        n = 360
        k = 145
        v = []
        a = D[roles['tile']]
        for side in range(2):
            for z in np.linspace(0, height, k):
                t = z / height
                fade = min(1, t / 0.07, (1 - t) / 0.07)
                fade = fade * fade * (3 - 2 * fade)
                for u in np.linspace(0, 1, n, endpoint=False):
                    th = u * math.tau
                    r = inner + wall + depth * float(sample(a, np.array(u), np.array(t))) * fade if side == 0 else inner
                    v.append([r * math.cos(th), r * math.sin(th), z])
        f = []
        off = n * k
        for side in range(2):
            b = side * off
            for j in range(k - 1):
                for i in range(n):
                    q = (i + 1) % n
                    face = (b + j * n + i, b + j * n + q, b + (j + 1) * n + q, b + (j + 1) * n + i)
                    f.append(face if side == 0 else face[::-1])
        for i in range(n):
            q = (i + 1) % n
            f.append((i, off + i, off + q, q))
            f.append(((k - 1) * n + i, (k - 1) * n + q, off + (k - 1) * n + q, off + (k - 1) * n + i))
        sleeve = mesh('Patterned writing grip | real continuous relief', v, f, teal)
        sleeve.location = (168 * MM, -75 * MM, 0)
        sleeve.asset_mark()
        objects.append(sleeve)
        export_glb(OUT / 'grip-sleeve.glb', [sleeve])
        export_stl(OUT / 'grip-sleeve-mm.stl', [sleeve])
        variants.append({'id': 'grip-sleeve', 'region': roles['tile'], 'inner_diameter_mm': inner * 2, 'minimum_wall_mm': wall, 'height_mm': height, 'max_relief_mm': depth, 'physical_fit': 'Measure receiving barrel and test coupon before use'})
    export_glb(OUT / 'model-full.glb', objects)
    preview = []
    for src in objects:
        dup = src.copy()
        dup.data = src.data.copy()
        bpy.context.collection.objects.link(dup)
        bpy.context.view_layer.objects.active = dup
        if len(dup.data.polygons) > 12000:
            q = dup.modifiers.new('Web copy only', 'DECIMATE')
            q.ratio = 0.52
            bpy.ops.object.modifier_apply(modifier=q.name)
        preview.append(dup)
    export_glb(OUT / 'model.glb', preview)
    for dup in preview:
        bpy.data.objects.remove(dup, do_unlink=True)
    json.dump({'source': 'brushes/metadata.json', 'variants': variants, 'brush_roles': roles, 'geometry': 'all relief changes actual vertex positions', 'software': bpy.app.version_string, 'physical_print': 'not performed'}, open(OUT / 'measurements.json', 'w'), indent=2)
    cam = stage((0, 0, 0), 375)
    camera(cam, (15, 4, 0), (105, -190, 355), 400)
    save(OUT / 'brush-library.blend')
    render(OUT / 'hero.png', 1440, 1050, 32)
    camera(cam, (10, 0, 0), (0, 0, 420), 390)
    render(OUT / 'technical.png', 1440, 1050, 24)
    camera(cam, (0, -10, 0), (65, -120, 190), 155)
    render(OUT / 'curved-detail.png', 1280, 960, 32)
    if sleeve:
        for o in objects:
            o.hide_render = o != sleeve
        sleeve.location = (0, 0, 0)
        pen = material('Writing tool graphite', (0.025, 0.028, 0.032), 0.4, 0.28)
        brass = material('Pen brass hardware', (0.46, 0.3, 0.09), 0.75, 0.23)

        def cylinder(name, r, dep, z, mat):
            bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=r * MM, depth=dep * MM, location=(0, 0, z * MM))
            o = bpy.context.object
            o.name = name
            o.data.materials.append(mat)
            bevel(o, 0.35)
            return o
        inner = config['grip_sleeve'].get('inner_diameter_mm', 12.6) / 2
        barrel = cylinder('Reference pen barrel | not a supplied pen', inner - 0.3, 132, 68, pen)
        cap = cylinder('Reference pen cap', inner + 0.3, 27, 121, pen)
        ring = cylinder('Reference pen trim', inner + 0.4, 2, 106.5, brass)
        camera(cam, (0, 0, 61), (145, -200, 110), 178)
        render(OUT / 'context.png', 1120, 1400, 40)
        for o in [barrel, cap, ring]:
            bpy.data.objects.remove(o, do_unlink=True)
        sleeve.location = (168 * MM, -75 * MM, 0)
        for o in objects:
            o.hide_render = False
    camera(cam, (15, 4, 0), (105, -190, 355), 400)
    save(OUT / 'scene.blend')

def main(argv=None):
    return heightfield_stage(build, cli_arguments, argv)

if __name__ == "__main__":
    main()
