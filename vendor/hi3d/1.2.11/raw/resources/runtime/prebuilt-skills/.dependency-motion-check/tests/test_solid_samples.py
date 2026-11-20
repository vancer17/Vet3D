import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import manifold3d as mf
from pose_math import axis_pose
from solid_samples import sample_solids, intersection_volume
from motion_check import check_intersections, check_paths, check_motions


class SolidSamples(unittest.TestCase):
    def test_two_moving_solids_and_containment_all_samples(self):
        outer=mf.Manifold.cube((4,4,4),True);inner=mf.Manifold.cube((1,1,1),True)
        poses=[dict(value=i,poses={'outer':axis_pose((0,0,0),(1,0,0),0,i),
                                  'inner':axis_pose((0,0,0),(1,0,0),0,2*i)}) for i in [0,1,4]]
        report=sample_solids({'outer':outer,'inner':inner},poses,[('outer','inner')],tolerance=.01,absolute_volume=True)
        self.assertEqual(len(report['samples']),3)
        self.assertEqual(report['first_collision']['sample'],0)
        self.assertAlmostEqual(report['max_overlap_mm3'],1)
        self.assertFalse(report['samples'][-1]['collisions'])
        self.assertEqual(report['samples'][-1]['pair_checks'],1)
        np.testing.assert_allclose(outer.bounding_box(),[-2,-2,-2,2,2,2])

    def test_exact_tolerance_and_invalid_matrix_pairs(self):
        solids={'a':mf.Manifold.cube((1,1,1)),'b':mf.Manifold.cube((1,1,1))}
        sample=dict(value=0,poses={k:np.eye(4) for k in solids})
        self.assertIsNone(sample_solids(solids,[sample],[('a','b')],tolerance=1)['first_collision'])
        self.assertIsNotNone(sample_solids(solids,[sample],[('a','b')],tolerance=1,inclusive=True)['first_collision'])
        sample['poses']['a']=np.diag([2,1,1,1])
        with self.assertRaises(ValueError): sample_solids(solids,[sample],[('a','b')],tolerance=.01)
        with self.assertRaises(ValueError): sample_solids(solids,[],[('a','a')],tolerance=.01)
        with self.assertRaises(ValueError): sample_solids(solids,[],[('a','b')],tolerance=.01)

    def test_boolean_failure_nonfinite_and_signed_profile(self):
        class Result:
            def __init__(self,status,volume): self._status,self._volume=status,volume
            def status(self): return self._status
            def volume(self): return self._volume
        class Solid:
            def __init__(self,result): self.result=result
            def status(self): return mf.Error.NoError
            def __xor__(self,other): return self.result
        for result in [Result('failed',0),Result(mf.Error.NoError,float('nan'))]:
            with self.assertRaises(ValueError): intersection_volume(Solid(result),Solid(result))
        solid=Solid(Result(mf.Error.NoError,-2))
        self.assertEqual(intersection_volume(solid,solid),-2)
        self.assertEqual(intersection_volume(solid,solid,absolute_volume=True),2)

    def test_existing_motion_adapters_preserve_report_contract(self):
        solids={'a':mf.Manifold.cube((1,1,1)), 'b':mf.Manifold.cube((1,1,1)).translate((3,0,0))}
        self.assertEqual(check_intersections(solids),(1,0,[]))
        plan=dict(disassembly=[dict(instances=['a'],direction=[-1,0,0],distance_mm=2,max_step_mm=.5)],
                  motions=[dict(id='crossing',instances=['a'],type='translation',direction=[1,0,0],distance_mm=3,samples=4)])
        paths,errors=check_paths(plan,solids)
        self.assertFalse(errors);self.assertEqual(paths[0]['samples'],5)
        motions,errors=check_motions(plan,solids)
        self.assertTrue(errors);self.assertEqual(motions[0]['first_collision']['position'],3)

if __name__ == '__main__': unittest.main()
