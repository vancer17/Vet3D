"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sys, argparse, json, math
from pathlib import Path
import bmesh
import bpy
import numpy as np
from box_core import apply, boolean, cyl, hole
from mathutils import Vector
from planar_audit import bounds
from planar_core import MM, bevel, cube, loft, loop, material, plate, repair_boolean_flaps, ring3, sample
from planar_preview import camera, clean, export_glb, save
from preview_scene import area_light
from planar_print import export_stl_legacy as export_stl
from types import SimpleNamespace
from functools import partial
from box_runtime import cli_arguments, validate_paths, load_config
from planar_render import render as _render_base

from cli_schemas import preview_stage

def build(*, output, heightfield, config, preview=False, no_render=False):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(output=output, heightfield=heightfield, config=config, preview=preview, no_render=no_render)
    validate_paths(a)
    render=partial(_render_base, enabled=not getattr(a, "no_render", False))
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'print').mkdir(exist_ok=True)
    cfg = load_config(a.config, required=('recipe', 'outer_mm', 'body_height_mm', 'height_key', 'relief_height_mm'))
    if cfg.get('recipe') != 'three-zone-travel':
        raise ValueError('Select the three-zone-travel preset explicitly or adapt the layout')
    if cfg.get('outer_mm') != [172, 104] or cfg.get('body_height_mm') != 34:
        raise ValueError('The three-zone layout currently supports 172x104x34mm; rebuild item positions before another envelope')
    field = np.load(a.heightfield)[cfg['height_key']]
    clean()
    s = bpy.context.scene
    red = material('Oxblood lacquer over printed shell', (0.13, 0.012, 0.025), 0.1, 0.32)
    ivory = material('Warm ivory relief', (0.44, 0.35, 0.25), 0.05, 0.42)
    lining = material('Replaceable cream microsuede', (0.57, 0.49, 0.39), 0, 0.92)
    gold = material('Satin brass bought hardware', (0.36, 0.235, 0.092), 0.75, 0.36)
    traymat = material('Warm taupe fitted tray', (0.23, 0.14, 0.11), 0, 0.55)
    jewel = material('Example blue-grey stones', (0.025, 0.12, 0.2), 0.24, 0.18)
    strapmat = material('Wine elastic keeper', (0.105, 0.009, 0.025), 0, 0.87)
    parts = []
    allobjs = []
    groups = {}
    def path(name, pts, r, mat, n=12):
        pp = np.asarray(pts)
        rings = []
        for i, v in enumerate(pp):
            tang = pp[(i + 1) % len(pp)] - pp[(i - 1) % len(pp)]
            tang /= np.linalg.norm(tang)
            ref = np.array([0.0, 0.0, 1.0])
            ss = np.cross(tang, ref)
            if np.linalg.norm(ss) < 0.05:
                ss = np.cross(tang, [0, 1, 0])
            ss /= np.linalg.norm(ss)
            up = np.cross(tang, ss)
            q = np.arange(n) * 2 * np.pi / n
            rings.append(v + np.cos(q)[:, None] * ss * r + np.sin(q)[:, None] * up * r)
        rings.append(rings[0])
        return loft(name, rings, mat)
    def role(o, group, printed=False):
        o['assembly_role'] = group
        groups.setdefault(group, []).append(o)
        allobjs.append(o)
        if printed:
            parts.append(o)
        return o
    N = 512
    aa = cfg['outer_mm'][0] / 2
    bb = cfg['outer_mm'][1] / 2
    ia = aa - 13
    ib = bb - 6
    top = cfg['body_height_mm']
    q = np.arange(N) * 2 * np.pi / N
    def ell(a, b, z, n=N):
        return ring3(loop(a * 2, b * 2, 'ellipse', n), z)
    body = loft('Elliptical travel shell with protected screw lands', [ell(aa - 4, bb - 4, 0), ell(aa - 1, bb - 1, 2), ell(aa, bb, 6), ell(aa, bb, top - 0.8), ell(aa - 0.3, bb - 0.3, top), ell(ia, ib, top), ell(ia, ib, 3)], red, True, True)
    role(body, 'body', True)
    nr = 164
    nv = 768
    qq = np.arange(nv) * 2 * np.pi / nv
    rr = np.linspace(0.003, 1, nr)
    rings = []
    for r in rr:
        x = aa * r * np.cos(qq)
        y = bb * r * np.sin(qq)
        h = sample(field, (x / aa + 1) * 0.5, (y / bb + 1) * 0.5)
        fade = np.clip((1 - r) / 0.085, 0, 1)
        fade = fade * fade * (3 - 2 * fade)
        z = top + 3.7 + 2.1 * (1 - r * r) + cfg['relief_height_mm'] * h * fade
        rings.append(np.column_stack([x, y, z]))
    rings.append(ell(aa, bb, top + 0.4, nv))
    lid = loft('Relief domed travel lid', rings, ivory, True, True)
    skirt = loft('Lid locating skirt', [ell(ia - 0.4, ib - 0.4, top - 5), ell(ia - 0.4, ib - 0.4, top + 0.7), ell(ia - 3.2, ib - 3.2, top + 0.7), ell(ia - 3.2, ib - 3.2, top - 5), ell(ia - 0.4, ib - 0.4, top - 5)], ivory)
    boolean(lid, skirt)
    sx = aa - 7
    for x in [-sx, sx]:
        seat = cyl('Level thumb screw bearing seat', 5, 3.6, (x, 0, top + 4.2), ivory)
        bevel(seat, 0.45, 3)
        boolean(lid, seat)
        hole(body, x, 0, 2.05, top - 8, top + 1)
        hole(lid, x, 0, 1.7, top - 10, top + 20)
    role(lid, 'lid', True)
    for i, x in enumerate([-sx, sx]):
        ins = cyl('M3 threaded insert %d' % i, 2.05, 6, (x, 0, top - 3), gold)
        hole(ins, x, 0, 1.5, top - 8, top + 1)
        role(ins, 'body')
        sh = cyl('M3 removable thumb screw %d' % i, 1.48, 11, (x, 0, top + 0.5), gold)
        head = cyl('Rounded brass thumb head', 4.5, 3, (x, 0, top + 7.5), gold)
        bevel(head, 0.65, 3)
        boolean(sh, head)
        role(sh, 'screw' + str(i))
    ta = ia - 2
    tb = ib - 2
    z0 = 3.45
    zt = 22.5
    tr = loft('One piece removable divided travel tray', [ell(ta, tb, z0), ell(ta, tb, zt), ell(ta - 2, tb - 2, zt), ell(ta - 2, tb - 2, z0 + 2)], traymat, True, True)
    for x in [-25, 25]:
        half = tb * math.sqrt(1 - (x / ta) ** 2)
        wall = cube('Tray partition', (2.2, half * 2, zt - z0 - 1), (x, 0, (zt + z0 + 1) / 2), traymat, 0.7)
        boolean(tr, wall)
    cut = cyl('Finger scoop', 10, 12, (0, -tb, zt), red, (0, 1, 0))
    boolean(tr, cut, 'DIFFERENCE')
    for y in [-27, 27]:
        ledge = cube('Earring card rail', (49, 5, 6.8), (0, y, z0 + 5.4), traymat, 0.5)
        boolean(tr, ledge)
    role(tr, 'tray', True)
    floorpad = plate('Removable microsuede floor liner', (ta - 2.3) * 2, (tb - 2.3) * 2, 0.9, z0 + 2, 'ellipse', lining)
    for x in [-25, 25]:
        boolean(floorpad, cube('Liner partition gap', (3.3, 120, 10), (x, 0, z0 + 2), red, 0), 'DIFFERENCE')
    role(floorpad, 'tray')
    for i, y in enumerate([-17, 0, 17]):
        roll = cyl('Replaceable ring foam roll %d' % i, 6.6, 32, (-46, y, 12.5), lining, (1, 0, 0), 64)
        bevel(roll, 2.2, 4)
        role(roll, 'tray')
    for i, y in enumerate([-8.5, 8.5]):
        pts = [[-46 + 9 * math.cos(t), y, 16.8 + 9 * math.sin(t)] for t in np.linspace(0, 2 * np.pi, 120, endpoint=False)]
        ring = path('Example ring retained between soft rolls %d' % i, pts, 1.1, gold)
        role(ring, 'tray')
    ear = cube('Removable earring card with real post holes', (44, 57, 1.8), (0, 0, 13.35), ivory, 2)
    apply(ear)
    for x in [-11, 11]:
        for y in [-13, 13]:
            hole(ear, x, y, 0.8, 10, 17)
    role(ear, 'earcard', True)
    for i, (x, y) in enumerate([(-11, -13), (11, -13), (-11, 13), (11, 13)]):
        post = cyl('Earring post %d' % i, 0.45, 7, (x, y, 13.8), gold)
        stone = cyl('Earring stone %d' % i, 3.1, 2, (x, y, 17.8), jewel)
        role(post, 'earcard')
        role(stone, 'earcard')
        back = cyl('Earring back %d' % i, 1.5, 1.2, (x, y, 11), gold)
        role(back, 'earcard')
    spool = plate('Removable necklace winding core', 28, 52, 1.5, 7, 'ellipse', ivory)
    spool.location.x = 44 * MM
    core = plate('Necklace core', 22, 46, 6, 8.2, 'ellipse', ivory)
    core.location.x = 44 * MM
    boolean(spool, core)
    lip = plate('Necklace upper flange', 28, 52, 1.5, 14, 'ellipse', ivory)
    lip.location.x = 44 * MM
    boolean(spool, lip)
    role(spool, 'spool', True)
    for j in range(3):
        t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
        pts = np.column_stack([44 + 11.8 * np.cos(t), 23.8 * np.sin(t), np.full(len(t), 9.2 + j * 1.45)])
        chain = path('Example necklace coil %d' % j, pts, 0.48, gold, 8)
        role(chain, 'spool')
    pendant = cyl('Example necklace pendant', 4.4, 1.8, (44, -17, 17), jewel)
    role(pendant, 'spool')
    def band(name, x, y, w, h, zlo, zhi, group, around='Y'):
        outer = cube(name, (w, h, zhi - zlo), (x, y, (zhi + zlo) / 2), strapmat, 1)
        inner = cube('Elastic hollow', (w + 2 if around == 'Y' else w - 1.4, h - 1.4 if around == 'Y' else h + 2, zhi - zlo - 1.4), (x, y, (zhi + zlo) / 2), strapmat, 0.5)
        boolean(outer, inner, 'DIFFERENCE')
        role(outer, group)
        return outer
    band('Necklace core elastic keeper', 44, 0, 7, 55, 6.8, 19, 'spool')
    for y in [-22, 22]:
        band('Earring card elastic end retainer', 0, y, 46, 5, 11.9, 15.5, 'earcard', 'X')
    foam = plate('Replaceable underside pressure foam', (ia - 4) * 2, (ib - 4) * 2, 3.2, top - 3.0, 'ellipse', lining)
    role(foam, 'lid')
    for name, loc, dim in [('Ring roll capture foam', (-46, 0, 30.7), (32, 56, 7)), ('Pierced earring capture foam', (0, 0, 24.9), (43, 58, 18.6)), ('Necklace core capture foam', (44, 0, 26.7), (25, 44, 15))]:
        pad = cube(name, dim, loc, lining, 1.5)
        apply(pad)
        envelope = plate('Actual foam fit envelope', (ia - 4.2) * 2, (ib - 4.2) * 2, 35, 3, 'ellipse', lining)
        boolean(pad, envelope, 'INTERSECT')
        if name.startswith('Pierced'):
            for x in [-11, 11]:
                for y in [-13, 13]:
                    hole(pad, x, y, 4, 14, 37)
        role(pad, 'lid')
    records = []
    for o in parts:
        apply(o)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-09)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-09)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.to_mesh(o.data)
        bm.free()
        n = repair_boolean_flaps(o)
        records.append({'name': o.name, 'opposite_duplicate_flaps_removed': n})
        export_stl(out / 'print' / (o['assembly_role'] + '.stl'), [o])
    for o in allobjs:
        o['home_location'] = list(o.location)
        o['home_rotation'] = list(o.rotation_euler)
    measure = {'outer_design_mm': cfg['outer_mm'], 'body_height_mm': top, 'body_cavity_mm': [ia * 2, ib * 2, top - 3], 'tray_outline_mm': [ta * 2, tb * 2], 'body_tray_nominal_radial_clearance_mm': 2, 'lid_skirt_nominal_radial_clearance_mm': 0.4, 'lid_vertical_seam_mm': 0.4, 'earring_card_mm': [44, 57, 1.8], 'earring_post_hole_mm': 1.6, 'ring_example_outer_mm': 20.2, 'necklace_core_mm': [28, 52, 8.5], 'retention': 'Purchased M3 thumb screws, fitted foam rolls, pierced earring card with elastic end bands, necklace core with elastic wrap. No impact or inversion test has been performed.', 'assembled_bounds': bounds(allobjs), 'cleanup': records}
    (out / 'measurements.json').write_text(json.dumps(measure, indent=2))
    export_glb(out / 'model.glb', allobjs)
    coll = bpy.data.collections.new('CORAL TRAVEL ASSEMBLY')
    s.collection.children.link(coll)
    for o in allobjs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    floor = material('Warm limestone dressing table', (0.18, 0.12, 0.095), 0, 0.75)
    cube('Dressing table', (5000, 5000, 20), (0, 0, -10), floor, 0)
    s.world.node_tree.nodes['Background'].inputs[0].default_value = (0.47, 0.44, 0.4, 1)
    s.world.node_tree.nodes['Background'].inputs[1].default_value = 0.16
    def light(name, loc, energy, size, color):
        return area_light(name, np.array(loc) * MM, (0, 0, 0.025), energy, size * MM,
                          color, collection=bpy.context.collection, shape='SQUARE')
    light('Large cream window', (-180, -150, 300), 2.2, 220, (1, 0.88, 0.76))
    light('Soft neutral fill', (200, -100, 180), 0.9, 180, (0.84, 0.91, 1))
    light('Long rim light', (30, 230, 230), 2.4, 170, (1, 0.84, 0.65))
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.type = 'ORTHO'
    cam.data.clip_start = 0.001
    s.camera = cam
    camera(cam, (0, 0, 22), (160, -235, 235), 240)
    render(out / 'hero.png', 1400, 1050, 32)
    camera(cam, (0, 0, 25), (0, -30, 300), 222)
    render(out / 'top.png', 1200, 1000, 24)
    lid_rest_delta = -float(bounds(groups['lid'])['min_mm'][2])
    def move(group, delta):
        for o in groups.get(group, []):
            o.location = Vector(o['home_location']) + Vector(np.array(delta) * MM)
            o.rotation_euler = o['home_rotation']
    def park_screws():
        for i, x in enumerate([-109, 109]):
            for o in groups['screw' + str(i)]:
                o.location = Vector((x, -65, 4.5)) * MM
                o.rotation_euler = (0, math.pi / 2, 0)
    move('lid', (0, 132, lid_rest_delta))
    park_screws()
    camera(cam, (0, 57, 18), (130, -170, 300), 285)
    render(out / 'interior.png', 1400, 1300, 32)
    move('tray', (0, 0, 45))
    move('earcard', (0, 0, 61))
    move('spool', (0, 0, 61))
    camera(cam, (0, 40, 45), (160, -230, 210), 285)
    render(out / 'assembly.png', 1400, 1200, 28)
    export_glb(out / 'exploded.glb', allobjs)
    for group in groups:
        move(group, (0, 0, 0))
    camera(cam, (0, 0, 18), (170, 215, 100), 235)
    render(out / 'rear.png', 1200, 900, 24)
    cloth = material('Ivory linen travel cloth', (0.53, 0.45, 0.36), 0, 0.94)
    bookmat = material('Deep berry travel envelope', (0.085, 0.019, 0.036), 0, 0.63)
    book = cube('Travel document envelope', (103, 145, 9), (168, 36, 5), bookmat, 5)
    book.rotation_euler.z = -0.17
    for i in range(3):
        cube('Folded soft cloth', (125, 92, 3), (-156, 52, 1.5 + 3 * i), cloth, 2)
    move('lid', (0, 132, lid_rest_delta))
    park_screws()
    camera(cam, (5, 47, 12), (180, -250, 270), 440)
    render(out / 'desk.png', 1600, 1200, 36)
    for o in list(s.objects):
        if o not in allobjs and o.type == 'MESH' and (o.name != 'Dressing table'):
            o.hide_render = True
    for group in groups:
        move(group, (0, 0, 0))
    camera(cam, (0, 0, 22), (160, -235, 235), 240)
    bpy.ops.file.pack_all()
    save(out / 'scene.blend')
    print('TRAVEL_BUILD_COMPLETE', flush=True)

def main(argv=None):
    return preview_stage(build, cli_arguments, argv)

if __name__ == "__main__":
    main()
