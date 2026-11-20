"""Run inside Blender with --out pointing to a NEW external directory."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest
from dataclasses import replace
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE/'scripts'))
from geometry import Thread, threaded_ring, revolved_solid, screw_lift
from blender_ops import (mesh_object, check_screw_path, intersection_check, boolean_copy,
                        topology, require_solid, screw_matrix, sample_radial_wall, probe_points)
from motion import animate_screw
from rendering import render_png, configure_cycles
from run import execute, digest

SPEC = Thread(12, .6, 3, .2, .8, .25, .15)
PAIR = {'thread': vars(SPEC),
        'male': {'low_mm': 0, 'high_mm': 6, 'wall_radius_mm': 9, 'lead_mm': .4},
        'female': {'low_mm': 0, 'high_mm': 7, 'wall_radius_mm': 15},
        'resolution': {'segments': 48, 'rows_per_pitch': 20}}


def pair(spec=SPEC):
    return (mesh_object('Body', *threaded_ring(spec, 0, 6, 9, segments=48, rows_per_pitch=20, lead_mm=.4)),
            mesh_object('Cap', *threaded_ring(spec, 0, 7, 15, female=True, segments=48, rows_per_pitch=20)))


def matrix_close(a, b):
    return max(abs(a[i][j]-b[i][j]) for i in range(4) for j in range(4)) < 3e-5


class BlenderTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_transformed_quaternion_sources_both_hands(self):
        for hand in (1, -1):
            body, cap = pair(replace(SPEC, hand=hand))
            frame = Matrix.Translation((9, -7, 16)) @ Matrix.Rotation(.6, 4, 'Y') @ Matrix.Rotation(.2, 4, 'X')
            for obj in [body, cap]:
                obj.rotation_mode = 'QUATERNION'; obj.matrix_world = frame
            bpy.context.view_layer.update()
            before = cap.matrix_world.copy(); before_vertices = len(cap.data.vertices)
            report = check_screw_path([body], [cap], frame.translation, frame.to_3x3()@Vector((0,0,1)),
                                      3, [hand*x for x in [0, 37, 90, 180, 360, 720, 1080]], hand=hand)
            self.assertEqual(report['status'], 'sampled_clear')
            self.assertTrue(matrix_close(before, cap.matrix_world))
            self.assertEqual(before_vertices, len(cap.data.vertices))
            bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_collision_containment_and_invalid_inputs(self):
        body, cap = pair(); cap.location.z = .75
        self.assertEqual(intersection_check(body, cap)['status'], 'collision')
        bpy.ops.mesh.primitive_cube_add(size=20); outer=bpy.context.object
        bpy.ops.mesh.primitive_cube_add(size=2); inner=bpy.context.object
        result=intersection_check(outer, inner)
        self.assertEqual(result['status'], 'collision')
        self.assertAlmostEqual(result['intersection_volume_mm3'], 8, places=4)
        bpy.ops.mesh.primitive_plane_add(); plane=bpy.context.object
        with self.assertRaises(ValueError): intersection_check(outer, plane)
        empty=mesh_object('Empty', [], [])
        with self.assertRaises(ValueError): intersection_check(outer, empty)

    def test_boolean_material_uv_cavity_and_wall(self):
        red=bpy.data.materials.new('Exterior'); blue=bpy.data.materials.new('Interior')
        bpy.ops.mesh.primitive_cube_add(size=10); exterior=bpy.context.object
        exterior.data.materials.append(red)
        cutter=mesh_object('Cavity', *revolved_solid([[2,-3],[2,8]], 48), blue)
        old_uv=[tuple(x.uv) for x in exterior.data.uv_layers.active.data]
        result=boolean_copy(exterior,cutter,'DIFFERENCE')
        self.assertEqual(topology(result)['nonmanifold_edges'], 0)
        self.assertEqual(topology(result)['components'], 1)
        self.assertEqual(list(exterior.data.materials), [red])
        self.assertEqual(list(cutter.data.materials), [blue])
        self.assertEqual(old_uv,[tuple(x.uv) for x in exterior.data.uv_layers.active.data])
        self.assertTrue(any(result.data.materials[p.material_index]==blue for p in result.data.polygons))
        self.assertEqual([p['location'] for p in probe_points(result,[(0,0,-4),(0,0,0),(0,0,6)])], ['inside','outside','outside'])
        wall=sample_radial_wall(exterior,[[2,-3],[2,3]],[-2,0,2],32)
        self.assertAlmostEqual(wall['minimum_radial_wall_mm'],3,places=4)

    def test_animation_uses_actual_world_pose(self):
        _, cap=pair()
        closed=Matrix.Translation((7,-8,19))@Matrix.Rotation(.3,4,'Y')
        cap.rotation_mode='QUATERNION'; cap.matrix_world=closed
        center=(7,-8,19); axis=Vector((.3,.4,1)).normalized()
        animate_screw([cap],center,axis,3,[(1,0),(11,630)])
        for frame,degree in [(1,0),(6,315),(11,630)]:
            bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
            angle=math.radians(degree)
            expected=screw_matrix(center,axis,angle,screw_lift(3,angle))@closed
            self.assertTrue(matrix_close(cap.matrix_world,expected),(frame,cap.matrix_world,expected))

    def test_cli_pair_roundtrip_and_failure_timing(self):
        spec=OUTPUT/'pair.json';spec.write_text(json.dumps(PAIR))
        destination=OUTPUT/'cli-pair'
        command=[bpy.app.binary_path,'--background','--factory-startup','--python-exit-code','1',
                 '--python',str(PACKAGE/'scripts/run.py'),'--','threads','--spec',str(spec),
                 '--out',str(destination),'--task-id','synthetic']
        result=subprocess.run(command,cwd=OUTPUT,capture_output=True,text=True,timeout=120)
        (OUTPUT/'cli.log').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode,0,result.stdout[-1000:]+result.stderr[-1000:])
        bpy.ops.import_scene.gltf(filepath=str(destination/'threads.glb'))
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
        self.assertEqual(len(meshes),2)
        self.assertAlmostEqual(max(o.dimensions.z for o in meshes),.007,places=6)
        report=json.loads((destination/'report.json').read_text())
        self.assertEqual(report['quality_status'],'not_tested')
        logs=[json.loads(x) for x in (destination/'timings.jsonl').read_text().splitlines()]
        self.assertEqual([r['stage_id'] for r in logs if r['status']=='completed'],['load','threads','deliver'])
        args=SimpleNamespace(command='threads',spec=str(spec),out=str(destination),task_id='synthetic',previous_attempt_id=None)
        with self.assertRaises(ValueError):execute(args)
        invalid=OUTPUT/'invalid.json';invalid.write_text(json.dumps(dict(PAIR,thread=dict(PAIR['thread'],pitch_mm=0))))
        args.spec=str(invalid);args.out=str(OUTPUT/'invalid')
        with self.assertRaises(ValueError):execute(args)
        events=[json.loads(x) for x in (Path(args.out)/'timings.jsonl').read_text().splitlines()]
        self.assertEqual([r['status'] for r in events],['running','failed','skipped','skipped'])

    def test_cli_check_and_render_framing(self):
        body,cap=pair()
        source=OUTPUT/'closed.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source));before=digest(source)
        spec=OUTPUT/'check.json';spec.write_text(json.dumps({'frame':1,'bodies':['Body'],'caps':['Cap'],
            'center_mm':[0,0,0],'axis':[0,0,1],'pitch_mm':3,'angles_deg':[0,90,450,1080],'unit_mm':1}))
        report=execute(SimpleNamespace(command='check',input=str(source),spec=str(spec),out=str(OUTPUT/'check'),task_id='synthetic',previous_attempt_id=None))
        self.assertEqual(report['screw_path']['status'],'sampled_clear');self.assertEqual(digest(source),before)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(size=1);body=bpy.context.object;body.name='Product'
        bpy.ops.mesh.primitive_cube_add(size=.6,location=(0,0,2.5));cap=bpy.context.object;cap.name='Lid'
        bpy.ops.object.camera_add(location=(4,-8,4));camera=bpy.context.object;camera.name='Product camera'
        camera.rotation_euler=(Vector((0,0,1))-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.type='ORTHO';camera.data.ortho_scale=1
        source=OUTPUT/'studio.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source));before=digest(source)
        spec=OUTPUT/'render.json';spec.write_text(json.dumps({'frame':1,'camera':camera.name,'objects':[body.name,cap.name],
            'width':64,'height':80,'samples':1,'device':'CPU','fit':True,'margin':.1}))
        report=execute(SimpleNamespace(command='render',input=str(source),spec=str(spec),out=str(OUTPUT/'render'),task_id='synthetic',previous_attempt_id=None))
        self.assertEqual(report['render']['pixels'],[64,80]);self.assertEqual(digest(source),before)
        self.assertGreaterEqual(min(report['render']['projected_bounds']['min']),.1-1e-5)
        self.assertLessEqual(max(report['render']['projected_bounds']['max']),.9+1e-5)
        self.assertEqual(report['render']['device']['backend'],'CPU')
        with self.assertRaises(ValueError):configure_cycles(bpy.context.scene,'INVALID')
        for invalid_margin in (-.1, .45, float('nan')):
            with self.assertRaises(ValueError):
                render_png(bpy.context.scene, bpy.context.scene.camera, [], OUTPUT/'invalid-margin.png',
                           frame=1, width=64, height=80, samples=1, device='CPU', fit=False, margin=invalid_margin)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    OUTPUT=Path(args.out).expanduser().resolve()
    if OUTPUT.exists() or OUTPUT==PACKAGE or PACKAGE in OUTPUT.parents:
        raise ValueError('Use a NEW directory outside the skill package')
    OUTPUT.mkdir(parents=True)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BlenderTests))
    if not result.wasSuccessful():raise RuntimeError('Blender integration checks failed')
