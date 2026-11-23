import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support_core import mass_properties, combine_mass, support_polygon, assess_support

class SupportTests(unittest.TestCase):
    def test_tetrahedron_mass(self):
        v=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]], dtype=float)
        f=np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
        p=mass_properties(v,f,density_g_cm3=6,unit_mm=10)
        self.assertAlmostEqual(p['volume_mm3'],1000/6)
        self.assertAlmostEqual(p['mass_g'],1)
        np.testing.assert_allclose(p['center_mm'],[2.5]*3)
        q=mass_properties(v+1e6,f[:,::-1],density_g_cm3=12,unit_mm=10)
        self.assertLess(q['signed_volume_mm3'],0)
        self.assertAlmostEqual(q['mass_g'],2)
        np.testing.assert_allclose(q['center_mm'],[10000002.5]*3)
        combined=combine_mass([p,dict(mass_g=1,center_mm=[7.5]*3)])
        np.testing.assert_allclose(combined['center_mm'],[5]*3)
        np.testing.assert_array_equal(v,[[0,0,0],[1,0,0],[0,1,0],[0,0,1]])
        for density in (0,-1,float('nan')):
            with self.assertRaises(ValueError):mass_properties(v,f,density_g_cm3=density)
        with self.assertRaises(ValueError):mass_properties(v*0,f,density_g_cm3=1)

    def test_support_and_gravity(self):
        contacts=np.array([[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]])
        for x,margin in [(0,1),(1,0),(2,-1)]:
            r=assess_support([dict(mass_g=1,center_mm=[x,0,5])],contacts)
            self.assertAlmostEqual(r['minimum_support_margin_mm'],margin)
            self.assertEqual(r['center_inside_support_polygon'],x==0)
        r=assess_support([dict(mass_g=1,center_mm=[5,0,0])],contacts[:,[2,0,1]],gravity=(-1,0,0))
        self.assertAlmostEqual(r['minimum_support_margin_mm'],1)
        with self.assertRaises(ValueError):support_polygon([[0,0],[1,0],[2,0]])
        with self.assertRaises(ValueError):assess_support([dict(mass_g=1,center_mm=[0,0,0])],contacts,gravity=(0,0,0))
        with self.assertRaises(ValueError):combine_mass([])

if __name__ == '__main__':unittest.main()
