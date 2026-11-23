"""Run representative local integration cases in a NEW external directory."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import subprocess
import unittest
import bpy
import numpy as np

PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE/'scripts'))
from run import execute, digest, write_json
from blender_ops import topology, weld_exact, world_mesh

TUNNEL={'mode':'tunnel', 'frame':{'center_mm':[10,30.5,32], 'normal':[1,0,0], 'up':[0,0,1]},
        'major_radius_mm':4, 'tube_radius_mm':1.6,
        'connector':{'major_radius_mm':4, 'wire_radius_mm':.3, 'pitch_mm':.7, 'turns':2.02}}


def source_file(path, open_surface=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if open_surface:
        bpy.ops.mesh.primitive_plane_add(size=.02, location=(.01,.02,.03))
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=.01, location=(.01,.02,.03))
    bpy.context.object.name='Fixture'
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True)


def candidate(args):
    # Each CLI invocation starts a fresh background process; reproduce that isolation.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return execute(args)


def bounds(ob):
    vertices,_=world_mesh(ob)
    return np.ptp(np.asarray(vertices),axis=0)*1000


class BlenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=OUTPUT/'source.glb'; source_file(cls.source)
        cls.original_hash=digest(cls.source)

    def args(self,name,spec,source=None,check=False):
        path=OUTPUT/(name+'.json'); write_json(path,spec)
        return SimpleNamespace(input=str(source or self.source),target='Fixture',spec=str(path),
                               input_unit_mm=1000,out=str(OUTPUT/name),task_id='synthetic',
                               previous_attempt_id=None,check=check)

    def test_tunnel_and_roundtrip(self):
        args=self.args('tunnel',deepcopy(TUNNEL))
        preflight=execute(SimpleNamespace(**dict(vars(args),check=True)))
        self.assertFalse(preflight['writes']); self.assertFalse(Path(args.out).exists())
        report=candidate(args)
        self.assertEqual(report['execution_status'],'completed')
        self.assertEqual(report['quality_status'],'not_tested')
        self.assertEqual(report['checks']['connector']['status'],'sampled_clear')
        self.assertEqual(report['checks']['result_topology']['non_manifold_edges'],0)
        self.assertEqual(report['checks']['result_topology']['components'],1)
        self.assertLess(report['checks']['boolean_effect']['volume_delta_mm3'],0)
        self.assertEqual(digest(self.source),self.original_hash)
        expected=bounds(bpy.data.objects['Keychain body'])
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(Path(args.out)/'assembly.glb'))
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
        self.assertEqual(len(meshes),2)
        body=next(o for o in meshes if o.name.startswith('Keychain body'))
        np.testing.assert_allclose(bounds(body),expected,atol=.002)
        weld_exact(body.data)
        self.assertEqual(topology(body.data)['non_manifold_edges'],0)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.wm.stl_import(filepath=str(Path(args.out)/'body_mm.stl'))
        body=bpy.context.object
        np.testing.assert_allclose(bounds(body)/1000,expected,atol=.002)
        weld_exact(body.data)
        self.assertEqual(topology(body.data)['non_manifold_edges'],0)
        events=[json.loads(line) for line in (Path(args.out)/'timings.jsonl').read_text().splitlines()]
        self.assertEqual(sum(e['status']=='completed' for e in events),4)
        self.assertTrue(all(e['elapsed_seconds']>=0 for e in events if e['status']=='completed'))
        with self.assertRaises(ValueError): candidate(args)

    def test_cli_entry_in_fresh_process(self):
        args=self.args('cli-entry',deepcopy(TUNNEL))
        result=subprocess.run([bpy.app.binary_path,'--background','--factory-startup',
                               '--python-exit-code','1','--python',str(PACKAGE/'scripts/run.py'),'--',
                               '--input',args.input,'--target',args.target,'--spec',args.spec,
                               '--input-unit-mm','1000','--out',args.out],
                              cwd=OUTPUT, capture_output=True,text=True,timeout=60)
        (OUTPUT/'cli-entry.log').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode,0,result.stdout[-1500:]+result.stderr[-1500:])
        report=json.loads((Path(args.out)/'report.json').read_text())
        self.assertEqual(report['execution_status'],'completed')
        self.assertEqual(report['checks']['connector']['status'],'sampled_clear')

    def test_lug_and_disconnected_failure(self):
        spec={'mode':'lug','frame':{'center_mm':[10,20,41.5],'normal':[0,1,0],'up':[0,0,1]},
              'major_radius_mm':3,'tube_radius_mm':1.2}
        report=candidate(self.args('lug',spec))
        self.assertEqual(report['quality_status'],'not_tested')
        self.assertEqual(report['checks']['result_topology']['components'],1)
        self.assertGreater(report['checks']['boolean_effect']['volume_delta_mm3'],0)
        spec=deepcopy(spec); spec['frame']['center_mm'][2]=60
        report=candidate(self.args('disconnected-lug',spec))
        self.assertEqual(report['quality_status'],'fail')
        self.assertGreater(report['checks']['result_topology']['components'],1)

    def test_collision_is_failure(self):
        spec=deepcopy(TUNNEL); spec['connector']['frame']=dict(spec['frame'],center_mm=[10,20,30])
        report=candidate(self.args('embedded-ring',spec))
        self.assertEqual(report['quality_status'],'fail')
        check=report['checks']['connector']
        self.assertGreater(check['inside_body_samples'],0)
        self.assertEqual(check['bvh_surface_pairs'],0)  # A buried ring defeats a surface-only test.

    def test_open_source_logs_failure_and_skips(self):
        source=OUTPUT/'open.glb'; source_file(source,open_surface=True)
        args=self.args('open-source',deepcopy(TUNNEL),source)
        with self.assertRaises(ValueError): candidate(args)
        report=json.loads((Path(args.out)/'report.json').read_text())
        self.assertEqual(report['execution_status'],'failed')
        summary=json.loads((Path(args.out)/'timing_summary.json').read_text())
        self.assertEqual([s['status'] for s in summary['stages']],['failed','skipped','skipped','skipped'])
        self.assertFalse((Path(args.out)/'assembly.blend').exists())
        args=self.args('invalid',dict(TUNNEL,major_radius_mm=-1),check=True)
        with self.assertRaises(ValueError): candidate(args)
        self.assertFalse(Path(args.out).exists())


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--out',required=True)
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    args=parser.parse_args(argv); OUTPUT=Path(args.out).expanduser().resolve()
    if OUTPUT.exists() or OUTPUT==PACKAGE or PACKAGE in OUTPUT.parents:
        raise ValueError('Tests require a NEW directory outside the package')
    OUTPUT.mkdir(parents=True)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BlenderTests))
    if not result.wasSuccessful(): raise RuntimeError('Blender integration tests failed')
