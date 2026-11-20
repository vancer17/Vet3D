import sys,unittest,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from primitive_core import rounded_rectangle,extrude_polygon,cylinder_mesh

def volume(vertices,faces):
    total=0
    for f in faces:
        a=vertices[f[0]]
        for j in range(1,len(f)-1):
            b,c=vertices[f[j]],vertices[f[j+1]]
            total+=sum(a[i]*(b[(i+1)%3]*c[(i+2)%3]-b[(i+2)%3]*c[(i+1)%3]) for i in range(3))/6
    return total

class Primitives(unittest.TestCase):
    def test_extrusion_axes(self):
        outline=[(-2,-1),(2,-1),(2,1),(-2,1)]
        for axis in 'XYZ':
            vertices,faces=extrude_polygon(outline,-3,3,axis=axis,center=(10,20,30))
            self.assertAlmostEqual(volume(vertices,faces),48)
        self.assertEqual(outline,[(-2,-1),(2,-1),(2,1),(-2,1)])
    def test_cylinder_winding_and_dimensions(self):
        for axis in 'XYZ':
            vertices,faces=cylinder_mesh((0,0,0),2,6,axis,64)
            self.assertAlmostEqual(volume(vertices,faces)/(math.pi*4*6),1,delta=.002)
            self.assertEqual(len(vertices),128);self.assertEqual(len(faces),66)
    def test_rounded_sampling_and_failures(self):
        self.assertEqual(len(rounded_rectangle(20,10,2)),44)
        for args in [(20,10,5),(0,10,2)]:
            with self.assertRaises(ValueError):rounded_rectangle(*args)
        with self.assertRaises(ValueError):cylinder_mesh((0,0,0),1,2,segments=2)
        with self.assertRaises(ValueError):extrude_polygon([(0,0)]*3,2,1)

if __name__=='__main__':unittest.main()
