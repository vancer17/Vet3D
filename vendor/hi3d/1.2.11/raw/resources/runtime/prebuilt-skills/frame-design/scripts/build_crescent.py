"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys, argparse, json, math, os
from pathlib import Path
import bmesh
import bpy
import numpy as np
from frame_core import applymods, boolean, cylinder, hole
from frame_print import export_stl
from mathutils import Vector
from planar_audit import bounds
from planar_core import MM, bevel, clean_solid_mesh, cube, loft, loop, material, plate, repair_boolean_flaps, ring3, sample
from planar_preview import camera, clean, export_glb, save
from preview_scene import area_light
from mathutils import Matrix
from types import SimpleNamespace
from functools import partial
from frame_runtime import cli_arguments, validate_paths, load_config
from planar_render import render as _render_base

def build(*, output, heightfield, config, artwork, preview=False, no_render=False):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    args=SimpleNamespace(output=output, heightfield=heightfield, config=config, artwork=artwork, preview=preview, no_render=no_render)
    validate_paths(args)
    _render=partial(_render_base, enabled=not getattr(args, "no_render", False))
    def render(path, w=1200, h=1000, samples=24):
        if args.preview and Path(path).stem not in ['hero', 'front']:
            return
        return _render(path, w, h, samples)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'print').mkdir(exist_ok=True)
    cfg = load_config(args.config, required=('recipe', 'aperture_mm', 'height_key', 'outer_radius_mm', 'eccentric_x_mm', 'relief_height_mm'))
    W, H = cfg['aperture_mm']
    A, B = (W / 2, H / 2)
    if cfg.get('recipe') != 'eccentric-crescent' or W != H or W < 80:
        raise ValueError('This preset requires an explicit eccentric-crescent recipe and circular aperture >=80mm')
    if float(cfg['outer_radius_mm'])-abs(float(cfg['eccentric_x_mm'])) < W/2+3:
        raise ValueError('Outer contour must retain at least 3mm nominal material around the aperture')
    field = np.load(args.heightfield)[cfg['height_key']]
    field_raw = field.copy()
    valid = field > 0.005
    distance = np.zeros_like(field)
    for _ in range(int(cfg.get('source_boundary_fade_pixels', 18))):
        pad = np.pad(valid, 1)
        valid = pad[1:-1, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:] & pad[:-2, 1:-1] & pad[2:, 1:-1]
        distance += valid
    edge = np.clip(distance / max(1, int(cfg.get('source_boundary_fade_pixels', 18))), 0, 1)
    field = field * edge * edge * (3 - 2 * edge)
    clean()
    s = bpy.context.scene
    bronze = material('Smoked champagne lunar metal', (0.15, 0.115, 0.073), 0.7, 0.44)
    backmat = material('Warm walnut backboard', (0.16, 0.096, 0.055), 0, 0.65)
    steel = material('M3 brushed brass hardware', (0.32, 0.26, 0.16), 0.78, 0.32)
    paper = material('Warm cotton paper', (0.78, 0.75, 0.67), 0, 0.84)
    ink = material('Desaturated olive ink', (0.11, 0.16, 0.115), 0, 0.8)
    lightink = material('Warm sage ink', (0.27, 0.3, 0.21), 0, 0.85)
    printparts = []
    assembly = []
    ornaments = []
    def frame_outer(t):
        R = float(cfg['outer_radius_mm'])
        cx = float(cfg['eccentric_x_mm'])
        rr = cx * np.cos(t) + np.sqrt(R * R - cx * cx * np.sin(t) ** 2)
        return np.column_stack([rr * np.cos(t), rr * np.sin(t)])
    N = 768
    t = np.arange(N) * 2 * np.pi / N
    outer = frame_outer(t)
    inner = loop(W, H, 'ellipse', N)
    seat = loop(W + 4.8, H + 4.8, 'ellipse', N)
    rings = [ring3(outer, 0), ring3(outer, 2.5)]
    for f in np.linspace(0.015, 1, 101):
        xy = outer * (1 - f) + inner * f
        left = 0.5 - 0.5 * np.cos(t)
        env = np.sin(np.pi * f) ** 0.82
        h = sample(field, (xy[:, 0] - cfg['eccentric_x_mm'] + cfg['outer_radius_mm']) / (2 * cfg['outer_radius_mm']), (xy[:, 1] + cfg['outer_radius_mm']) / (2 * cfg['outer_radius_mm']))
        zz = 5.35 + (2.5 + 2.7 * left) * env + cfg['relief_height_mm'] * h * env * np.clip((left - 0.12) / 0.65, 0, 1)
        rings.append(np.column_stack([xy, zz]))
    rings.extend([ring3(inner, 3.4), ring3(seat, 3.4), ring3(seat, 0), rings[0]])
    frame = loft('Eccentric frame with measured relief', rings, bronze)
    ornaments.append(frame)
    def frame_point(deg, f=0.56):
        th = np.radians(deg)
        oo = frame_outer(np.array([th]))[0]
        ii = np.array([A * np.cos(th), B * np.sin(th)])
        return ii * (1 - f) + oo * f
    def curved_tube(name, pts, radii, mat, ncross=18):
        rings = []
        for i, p in enumerate(pts):
            tangent = pts[min(i + 1, len(pts) - 1)] - pts[max(0, i - 1)]
            tangent = tangent / np.linalg.norm(tangent)
            side = np.cross(tangent, [0, 0, 1.0])
            side = side / np.linalg.norm(side)
            up = np.cross(side, tangent)
            q = np.arange(ncross) * 2 * np.pi / ncross
            r = radii[i]
            rings.append(p + np.cos(q)[:, None] * side * r + np.sin(q)[:, None] * up * r * 0.7)
        return loft(name, rings, mat, True, True)
    leaf_records = []
    apcut = plate('Precision visible aperture', W, H, 18, 3.4, 'ellipse', bronze)
    boolean(frame, apcut, 'DIFFERENCE')
    clips = []
    hardware = []
    clip_info = []
    for i, deg in enumerate([75, 145, 215, 285]):
        th = np.radians(deg)
        pivot = (A + 7.3) * np.array([np.cos(th), np.sin(th)])
        iv = np.array([-np.cos(th), -np.sin(th)])
        L = 14.0
        ww = 5.4
        xy = loop(L, ww, 'rect', 64, r=ww / 2 - 0.05)
        xy = np.column_stack([xy[:, 0] + L / 2 - 2.7, xy[:, 1]])
        phi = np.arctan2(iv[1], iv[0])
        rot = np.array([[np.cos(phi), -np.sin(phi)], [np.sin(phi), np.cos(phi)]])
        xy = xy @ rot.T + pivot
        c = loft('Rotating rear keeper %d' % (i + 1), [ring3(xy, -1.65), ring3(xy, -0.1)], steel, True, True)
        hole(c, pivot, 1.7, -3, 1)
        clips.append(c)
        hole(frame, pivot, 2.05, -1, 4.3)
        screw = cylinder('M3 rear keeper screw %d' % (i + 1), 1.48, 5.2, [*pivot, 0.75], steel)
        head = cylinder('M3 screw head %d' % (i + 1), 2.6, 1.5, [*pivot, -2.4], steel)
        boolean(screw, head)
        hardware.append(screw)
        clip_info.append({'pivot_mm': pivot.tolist(), 'angle_deg': float(np.degrees(phi)), 'bore_mm': 3.4, 'frame_blind_insert_bore_mm': 4.1, 'frame_blind_depth_mm': 4.3})
    board = plate('Removable oval walnut backboard', W + 4, H + 4, 2.95, 0, 'ellipse', backmat)
    card = plate('Oval cotton art card', W + 3.9, H + 3.9, 0.4, 2.95, 'ellipse', paper)
    artobjs = [card]
    photo = material('Printed midnight coast photograph', (0.1, 0.17, 0.26), 0, 0.75)
    img = bpy.data.images.load(str(Path(args.artwork).resolve()))
    img.pack()
    tex = photo.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = img
    photo.node_tree.links.new(tex.outputs['Color'], photo.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    card.data.materials.clear()
    card.data.materials.append(photo)
    uv = card.data.uv_layers.new(name='Print UV')
    for poly in card.data.polygons:
        for li in poly.loop_indices:
            co = card.data.vertices[card.data.loops[li].vertex_index].co / MM
            uv.data[li].uv = (0.5 + co.x / (W + 3.9), 0.5 + co.y / (H + 3.9))
    angle = math.radians(82)
    ca, sa = (math.cos(angle), math.sin(angle))
    miny = min((v.co.y / MM for v in frame.data.vertices))
    height = -miny * sa + 0.7
    mountx = A * 0.5 + 0.4
    mounty = -B * math.sqrt(1 - 0.5 ** 2) - 7.0
    stand = None
    mount_info = []
    for x in [-mountx, mountx]:
        pad = cube('Rear easel mounting pad', (9, 8, 3), (x, mounty, -1.5), bronze, 1.2)
        applymods(pad)
        top = np.array([x, mounty, -2.2])
        footz = -57.0
        footy = (-height - ca * footz) / sa
        end = np.array([x * 1.08, footy, footz])
        u3 = np.linspace(0, 1, 65)
        pp = top + (end - top) * u3[:, None]
        pp[:, 2] -= 7 * np.sin(np.pi * u3)
        pp[:, 1] -= 2 * np.sin(np.pi * u3)
        leg = curved_tube('Swept structural easel leg', pp, 3.1 - 0.3 * u3, bronze, 24)
        boolean(pad, leg)
        foot = cube('Rear desk contact foot', (15, 5.5, 9), (end[0], end[1] + 0.2, end[2] + 1.2), bronze, 1.4)
        applymods(foot)
        boolean(pad, foot)
        if stand is None:
            stand = pad
        else:
            boolean(stand, pad)
        boss = cylinder('Integral rear mounting boss', 3.9, 4.9, [x, mounty, 2.45], bronze)
        bevel(boss, 0.55, 3)
        boolean(frame, boss)
        hole(frame, [x, mounty], 2.05, -1, 4.4)
        mount_info.append([float(x), float(mounty)])
    z = -50.0
    y = (-height - ca * -57) / sa + 2
    bar = cube('Easel cross tie', (mountx * 2.2, 5, 6), (0, y, z), bronze, 1.7)
    applymods(bar)
    boolean(stand, bar)
    stand.name = 'One piece detachable rear easel'
    for x, y in mount_info:
        hole(stand, [x, y], 1.7, -5, 1)
        screw = cylinder('M3 easel attachment screw', 1.48, 7, [x, y, -0.5], steel)
        head = cylinder('Easel screw head', 2.8, 1.8, [x, y, -3.9], steel)
        boolean(screw, head)
        hardware.append(screw)
    cut = cube('Table contact halfspace', (700, 700, 300), (0, 0, 0), bronze, 0)
    M = Matrix.Rotation(angle, 4, 'X')
    T = Matrix.Translation((0, 0, height * MM))
    cut.matrix_world = (T @ M).inverted() @ Matrix.Translation((0, 0, -150 * MM))
    boolean(stand, cut, 'DIFFERENCE')
    for x in [cfg['eccentric_x_mm'] - 22, cfg['eccentric_x_mm'] + 14]:
        cy = miny + 2.0
        foot = cube('Integral front resting pad', (8, 7, 6.8), (x, cy, 2.7), bronze, 1.0)
        applymods(foot)
        boolean(frame, foot)
    seat_cutter = loft('Exact rear seat clearance', [ring3(seat, -1), ring3(seat, 3.4)], bronze, True, True)
    boolean(frame, seat_cutter, 'DIFFERENCE')
    for r in clip_info:
        hole(frame, r['pivot_mm'], 2.05, -1, 4.3)
    for x, y in mount_info:
        hole(frame, [x, y], 2.05, -1, 4.4)
    cut = cube('Table contact halfspace', (700, 700, 300), (0, 0, 0), bronze, 0)
    cut.matrix_world = (T @ M).inverted() @ Matrix.Translation((0, 0, -150 * MM))
    boolean(frame, cut, 'DIFFERENCE')
    stand_clear = plate('Rear mounting pad seat clearance', W + 5.2, H + 5.2, 7, -5.5, 'ellipse', bronze)
    boolean(stand, stand_clear, 'DIFFERENCE')
    for pivot in [r['pivot_mm'] for r in clip_info] + mount_info:
        ins = cylinder('M3 nominal threaded sleeve', 2.05, 4, [*pivot, 2], steel)
        hole(ins, pivot, 1.5, -1, 5)
        hardware.append(ins)
    cleanup = []
    for obj in [frame, stand, *clips]:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-09)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-09)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        bm.free()
        clean_solid_mesh(obj)
        n = repair_boolean_flaps(obj)
        cleanup.append({'object': obj.name, 'removed_opposite_duplicate_faces': n, 'merge_tolerance_mm': 1e-06})
    (out / 'source-cleanup.json').write_text(json.dumps(cleanup, indent=2))
    printparts = [frame, board, stand, *clips]
    assembly = [frame, board, *artobjs, stand, *clips, *hardware]
    bpy.context.view_layer.update()
    for o in printparts:
        export_stl(out / 'print' / (o.name.lower().replace(' ', '-') + '.stl'), [o])
    flat_bounds = bounds([frame])
    config_out = {**cfg, 'outer_frame_bounds': flat_bounds, 'rear_seat_mm': [W + 4.8, H + 4.8, 3.4], 'backboard_mm': [W + 4, H + 4, 2.95], 'art_card_mm': [W + 3.9, H + 3.9, 0.4], 'clip_parameters': clip_info, 'easel_mounts_mm': mount_info, 'display_tilt_deg': 82, 'leaves': leaf_records, 'source_heightfield': str(Path(args.heightfield).name)}
    (out / 'measurements.json').write_text(json.dumps(config_out, ensure_ascii=False, indent=2))
    for o in assembly:
        o['assembly_local_location'] = list(o.location)
        o['assembly_local_rotation'] = list(o.rotation_euler)
    for o in [frame, stand, board, *clips]:
        o['printable'] = True
    for o in artobjs:
        o['assembly_role'] = 'artwork'
    board['assembly_role'] = 'backboard'
    stand['assembly_role'] = 'stand'
    frame['assembly_role'] = 'frame'
    for i, o in enumerate(clips):
        o['assembly_role'] = 'keeper'
        o['pivot_mm'] = clip_info[i]['pivot_mm']
    for o in hardware:
        o['assembly_role'] = 'easel_screw' if o.name.startswith('M3 easel attachment screw') else 'hardware'
    export_glb(out / 'flat-model.glb', assembly)
    for o in assembly:
        o.matrix_world = T @ M @ o.matrix_world
    bpy.context.view_layer.update()
    config_out['assembled_bounds'] = bounds(assembly)
    (out / 'measurements.json').write_text(json.dumps(config_out, ensure_ascii=False, indent=2))
    export_glb(out / 'model.glb', assembly)
    coll = bpy.data.collections.new('LUNAR FRAME ASSEMBLY — print parts and hardware')
    s.collection.children.link(coll)
    for o in assembly:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    floor = material('Cool charcoal stone desktop', (0.088, 0.108, 0.125), 0, 0.75)
    cube('Stone table', (12000, 12000, 20), (0, 0, -10), floor, 0)
    n = floor.node_tree.nodes
    l = floor.node_tree.links
    noise = n.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 260
    noise.inputs['Detail'].default_value = 2
    bump = n.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.08
    bump.inputs['Distance'].default_value = 0.0002
    l.new(noise.outputs['Fac'], bump.inputs['Height'])
    l.new(bump.outputs['Normal'], n.get('Principled BSDF').inputs['Normal'])
    s.world.node_tree.nodes['Background'].inputs[0].default_value = (0.65, 0.63, 0.57, 1)
    s.world.node_tree.nodes['Background'].inputs[1].default_value = 0.25
    def light(name, loc, power, size, color):
        return area_light(name, np.array(loc) * MM, (0, 0, 90 * MM), power, size * MM,
                          color, collection=bpy.context.collection, shape='DISK')
    light('Large side window', (-280, -230, 360), 3.5, 270, (1, 0.92, 0.81))
    light('Broad front fill', (190, -280, 220), 2, 220, (0.85, 0.91, 1))
    light('Soft rear rim', (110, 100, 320), 3, 220, (1, 0.95, 0.84))
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.name = 'Product camera'
    cam.data.type = 'ORTHO'
    cam.data.clip_start = 0.001
    s.camera = cam
    camera(cam, (-8, 0, 80), (72, -370, 115), 212)
    render(out / 'hero.png', 1200, 1400, 32)
    camera(cam, (-8, 8, 82), (0, -440, 65), 230)
    render(out / 'front.png', 1000, 1200, 24)
    camera(cam, (-7, 24, 76), (170, 320, 150), 215)
    render(out / 'rear.png', 1100, 1200, 24)
    camera(cam, (-8, 0, 80), (72, -370, 115), 212)
    linen = material('Oatmeal notebook linen', (0.34, 0.28, 0.2), 0, 0.85)
    pages = material('Uncoated pages', (0.63, 0.6, 0.52), 0, 0.9)
    book = cube('Closed notebook cover', (125, 178, 3), (178, 46, 2), linen, 2)
    book.rotation_euler.z = -0.18
    bookpages = cube('Visible notebook pages', (121, 174, 10), (178, 46, 8), pages, 1)
    bookpages.rotation_euler.z = -0.18
    booktop = cube('Top notebook cover', (125, 178, 3), (178, 46, 14), linen, 2)
    booktop.rotation_euler.z = -0.18
    pencil = cylinder('Graphite pencil', 2.8, 148, (169, -7, 20), backmat, (0.18, 1, 0.02), 6)
    cer = material('Stoneware ceramic', (0.36, 0.4, 0.34), 0, 0.68)
    q = np.arange(96) * 2 * np.pi / 96
    cup = []
    for rr, zz in [(23, 0), (25, 3), (29, 49), (28, 55), (25.3, 55), (25.7, 49), (22.3, 5)]:
        cup.append(np.column_stack([rr * np.cos(q) - 164, rr * np.sin(q) + 86, np.full(96, zz)]))
    vessel = loft('Hand thrown ceramic cup', cup, cer, True, True)
    props = [book, bookpages, booktop, pencil, vessel]
    camera(cam, (25, 30, 75), (180, -440, 190), 400)
    render(out / 'desk.png', 1500, 1200, 40)
    for o in props:
        o.hide_render = True
    camera(cam, (-8, 0, 80), (72, -370, 115), 212)
    save(out / 'scene.blend')
    (out / 'build-record.json').write_text(json.dumps({'blender_version': bpy.app.version_string, 'heightfield_used': True, 'native_collection': coll.name, 'printable_parts': len(printparts), 'reduced_still_render_set': args.preview, 'geometry_is_full_resolution': True}, indent=2))
    print('BUILD_COMPLETE', str(out), flush=True)

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--heightfield', required=True)
    p.add_argument('--config', required=True)
    p.add_argument('--artwork', required=True)
    p.add_argument('--preview', action='store_true')
    p.add_argument('--no-render', action='store_true')
    options=p.parse_args(cli_arguments(argv))
    return build(**vars(options))

if __name__ == "__main__":
    main()
