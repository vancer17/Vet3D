"""Run in Blender against an independently materialized package."""
import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from registered_geometry import native_coordinates, repair_registered_geometry

class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.v = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]], dtype=float)
        self.q = np.array([[0,1,2,3]])
        self.linear = np.array([[2,.3,0],[0,3,.2],[0,0,4.]])
        self.offset = np.array([3.,-2.,7.])

    def test_affine_inverse_and_readonly_inputs(self):
        world = self.v @ self.linear.T + self.offset
        before = world.copy()
        np.testing.assert_allclose(native_coordinates(world,self.linear,self.offset), self.v, atol=1e-14)
        np.testing.assert_array_equal(world,before)
        corrected,native,report=repair_registered_geometry(world,world,self.q,self.linear,self.offset)
        np.testing.assert_array_equal(corrected,world)
        np.testing.assert_allclose(native,self.v,atol=1e-14)
        self.assertEqual(report['new_crossings'],0)
        self.assertEqual(report['maximum_displacement'],0)

    def test_invalid_geometry_transform_and_budget(self):
        for linear in (np.zeros((3,3)), np.eye(2)):
            with self.assertRaises(ValueError): native_coordinates(self.v,linear,self.offset)
        for rest, faces in ((self.v[:-1],self.q),(self.v,np.array([[0,1,2,99]]))):
            with self.assertRaises(ValueError):repair_registered_geometry(rest,self.v,faces,self.linear,self.offset)
        for budget in (-1,float('nan')):
            with self.assertRaises(ValueError):repair_registered_geometry(self.v,self.v,self.q,self.linear,self.offset,budget_fraction=budget)

    def test_zero_trials_preserve_unresolved_crossings(self):
        rest=np.array([[-1,-1,0],[1,-1,0],[0,1,0],[-.5,0,2],[.5,0,2],[0,0,3.]])
        current=rest.copy();current[3:,2]-=2.5
        faces=np.array([[0,1,2],[3,4,5]])
        repaired,_,report=repair_registered_geometry(rest,current,faces,np.eye(3),np.zeros(3),max_trials=0)
        self.assertGreater(report['new_crossings'],0)
        np.testing.assert_array_equal(repaired,current)
        np.testing.assert_array_equal(current[3:,2],[-.5,-.5,.5])

if __name__=='__main__':unittest.main(argv=[__file__])
