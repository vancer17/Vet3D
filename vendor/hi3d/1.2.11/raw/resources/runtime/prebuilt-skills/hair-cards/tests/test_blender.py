"""Run in a disposable Blender process. All saved fixtures use a temp directory."""

import copy
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import tempfile

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from hair_card_core import build_card_geometry, ribbon_frame, transport_frames
from rebuild_from_scene import read_curve_paths, run_rebuild


def expect_failure(call, error):
    try:
        call()
    except error:
        return
    raise AssertionError(f'Expected {error.__name__}')


def make_curve(scene, name, kind, coords):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    spline = data.splines.new(kind)
    if kind == 'BEZIER':
        spline.bezier_points.add(len(coords) - 1)
        for point, co in zip(spline.bezier_points, coords):
            point.co = co
            point.handle_left_type = point.handle_right_type = 'AUTO'
    else:
        spline.points.add(len(coords) - 1)
        for point, co in zip(spline.points, coords):
            point.co = (*co, 1)
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location.x = 4
    return obj


def coordinates(name):
    return [tuple(v.co) for v in bpy.data.objects[name].data.vertices]


def check_headless_transport():
    path = [Vector((.3 * math.sin(i / 24 * 2.7), .14 * math.sin(i / 24 * 1.3), i / 24))
            for i in range(25)]
    frames = transport_frames(path, (0, -1, 0))
    for j, (side, normal) in enumerate(frames):
        tangent = (path[min(j + 1, 24)] - path[max(j - 1, 0)]).normalized()
        assert abs(side.dot(tangent)) < 1e-6 and abs(normal.dot(tangent)) < 1e-6
        assert abs(side.dot(normal)) < 1e-6
        assert abs(side.length - 1) < 1e-6 and abs(normal.length - 1) < 1e-6
    assert all(a[0].dot(b[0]) > .99 for a, b in zip(frames, frames[1:])), 'Frame jumped'
    planar = [Vector((.3 * math.sin(i / 24 * 2.7), 0, i / 24)) for i in range(25)]
    assert all(abs(side.y) > .9999 for side, _ in transport_frames(planar, (0, 0, 1)))
    expect_failure(lambda: transport_frames([Vector((0, 0, 0)), Vector((0, 0, 1)),
                                            Vector((0, 0, 0))], (0, 1, 0)), ValueError)

    scene = bpy.data.scenes.new('Hair cards without head')
    bpy.context.window.scene = scene
    guide = make_curve(scene, 'SmoothGuide', 'BEZIER', [(0, 0, -2), (.2, .1, -1.5), (0, .4, -1)])
    material = bpy.data.materials.new('IndependentStrands')
    config = dict(placement='guides', material=material.name, output_collection='TransportCards',
                  uv_name='HairUV', atlas_columns=3, seed=123, layers=[dict(
                      name='CrossClump', guides=[guide.name], width=.1, offset=0,
                      segments=24, columns=2, lanes=[0, 2], root_normal=[0, -1, 0],
                      section_angles_degrees=[0, 80])])
    bpy.context.view_layer.update()
    def forbidden_query(point):
        raise AssertionError('Headless geometry queried a surface')
    geometry = build_card_geometry([path], config['layers'][0], 3, 0, forbidden_query, 123, 'guides')
    assert geometry['card_count'] == 2 and set(geometry['card_ids']) == {0, 1}
    assert len(geometry['vertices']) == 150 and len(geometry['faces']) == 96
    side0 = (Vector(geometry['vertices'][2]) - Vector(geometry['vertices'][0])).normalized()
    side1 = (Vector(geometry['vertices'][77]) - Vector(geometry['vertices'][75])).normalized()
    assert abs(side0.dot(side1) - math.cos(math.radians(80))) < 1e-6
    assert geometry == build_card_geometry([path], config['layers'][0], 3, 0, None, 123, 'guides')
    assert not any(obj.type == 'MESH' for obj in scene.objects)
    with tempfile.TemporaryDirectory(prefix='hair-guides-test-') as temp:
        task = Path(temp)
        bpy.ops.wm.save_as_mainfile(filepath=str(task / 'input.blend'))
        result = run_rebuild(bpy, config, task / 'first.blend')
        assert result['layers'][0]['cards'] == 2 and result['layers'][0]['triangles'] == 192
        mesh = scene.objects['CrossClump'].data
        assert all(v.co.z < 0 for v in mesh.vertices), 'Unexpected surface clamping'
        assert all(p.area > 1e-10 for p in mesh.polygons)
        assert set(v.value for v in mesh.attributes['card_id'].data) == {0, 1}
        before = coordinates('CrossClump')
        before_uv = [tuple(uv.uv) for uv in mesh.uv_layers['HairUV'].data]
        run_rebuild(bpy, config, task / 'repeated.blend')
        assert coordinates('CrossClump') == before
        guide.data.splines[0].bezier_points[1].co.x += .1
        run_rebuild(bpy, config, task / 'edited.blend')
        assert coordinates('CrossClump') != before
        assert [tuple(uv.uv) for uv in scene.objects['CrossClump'].data.uv_layers['HairUV'].data] == before_uv
        bpy.ops.wm.open_mainfile(filepath=str(task / 'edited.blend'), load_ui=False, use_scripts=False)
        assert bpy.context.scene.objects['CrossClump'].data.uv_layers['HairUV']
        assert not any(o.name == 'Head' for o in bpy.context.scene.objects)
    print('PASS: headless smooth transport, crossed sections, card IDs and deterministic rebuild')


def main():
    scene = bpy.data.scenes.new('Hair cards isolated verification')
    bpy.context.window.scene = scene
    surface_mesh = bpy.data.meshes.new('Head')
    surface_mesh.from_pydata([(-5, -5, 0), (5, -5, 0), (5, 5, 0), (-5, 5, 0)], [], [(0, 1, 2, 3)])
    head = bpy.data.objects.new('Head', surface_mesh)
    scene.collection.objects.link(head)
    head.location.x = 4
    material = bpy.data.materials.new('HairMaterial')
    poly = make_curve(scene, 'PolyGuide', 'POLY', [(0, 0, .01), (0, .5, .5), (.2, 1, .9)])
    bezier = make_curve(scene, 'BezierGuide', 'BEZIER', [(.5, 0, .1), (.7, .5, .5), (.6, 1, 1)])
    native_data = bpy.data.hair_curves.new('NativeGuide')
    native_data.add_curves([3])
    for point, co in zip(native_data.points, [(1, 0, .1), (1.1, .5, .5), (1.3, 1, 1)]):
        point.position = co
    native = bpy.data.objects.new('NativeGuide', native_data)
    scene.collection.objects.link(native)
    native.location.x = 4
    bpy.context.view_layer.update()
    config = dict(head='Head', material=material.name, output_collection='Cards', uv_name='HairUV',
                  atlas_columns=3, surface_clearance=.005, seed=123, layers=[])
    for name, guide, lane in [('PolyCards', poly, 0), ('BezierCards', bezier, 1), ('NativeCards', native, 2)]:
        config['layers'].append(dict(name=name, guides=[guide.name], width=.1, offset=.01,
                                     segments=8, columns=2, lanes=[lane]))
    tangent, normal = Vector((1, 0, 0)), Vector((1, 0, 0))
    sideways, _ = ribbon_frame(tangent, normal, None)
    assert sideways.length > .99 and abs(sideways.dot(tangent)) < 1e-8
    with tempfile.TemporaryDirectory(prefix='hair-cards-test-') as temp:
        task = Path(temp)
        source = task / 'input.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(source))
        source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
        rng_state = random.getstate()
        result = run_rebuild(bpy, config, task / 'first.blend')
        assert random.getstate() == rng_state
        assert len(result['layers']) == 3 and all(row['cards'] == 1 for row in result['layers'])
        for name in ['PolyCards', 'BezierCards', 'NativeCards']:
            mesh = bpy.data.objects[name].data
            assert all(v.co.x > 3 for v in mesh.vertices), 'World transform was lost'
            assert all(v.co.z >= .0049 for v in mesh.vertices)
            assert all(math.isfinite(c) for v in mesh.vertices for c in v.co)
            assert all(p.area > 1e-10 for p in mesh.polygons)
            assert all(0 <= c <= 1 for uv in mesh.uv_layers['HairUV'].data for c in uv.uv)
            assert mesh.materials[0] == material
        before = {name: coordinates(name) for name in ['PolyCards', 'BezierCards', 'NativeCards']}
        poly.data.splines[0].points[1].co.x += .2
        run_rebuild(bpy, config, task / 'edited.blend')
        assert coordinates('PolyCards') != before['PolyCards']
        assert coordinates('BezierCards') == before['BezierCards']
        assert coordinates('NativeCards') == before['NativeCards']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_digest
        before_bad = coordinates('PolyCards')
        bad = copy.deepcopy(config)
        bad['layers'][0]['guides'] = ['MissingGuide']
        expect_failure(lambda: run_rebuild(bpy, bad, task / 'bad.blend'), KeyError)
        assert not (task / 'bad.blend').exists() and coordinates('PolyCards') == before_bad
        expect_failure(lambda: run_rebuild(bpy, config, task / 'first.blend'), FileExistsError)
        expect_failure(lambda: run_rebuild(bpy, config, task / 'edited.blend', True), ValueError)
        poly.data.splines[0].use_cyclic_u = True
        expect_failure(lambda: read_curve_paths(poly), ValueError)
        poly.data.splines[0].use_cyclic_u = False
        native_data.attributes.new('cyclic', 'BOOLEAN', 'CURVE').data[0].value = True
        expect_failure(lambda: read_curve_paths(native), ValueError)
        expect_failure(lambda: build_card_geometry([[(0, 0, 0)] * 3], config['layers'][0], 3, .005,
                        lambda p: (Vector((p.x, p.y, 0)), Vector((0, 0, 1))), 123), ValueError)
        bpy.ops.wm.open_mainfile(filepath=str(task / 'edited.blend'), load_ui=False, use_scripts=False)
        assert bpy.data.objects['PolyCards'].data.uv_layers['HairUV']
        assert json.loads((task / 'edited.rebuild.json').read_text())['layers'][0]['cards'] == 1
    print('PASS: standalone geometry, three curve types, transforms, UV, edits and failure protection')
    check_headless_transport()


if __name__ == '__main__':
    main()
