"""Run with background Blender in a materialized package."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import bpy, bmesh
from mathutils import Matrix
from mesh_measure import measure_mesh

class Measurements(unittest.TestCase):
    def setUp(self):
        self.mesh = bpy.data.meshes.new('measure fixture')
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2); bm.to_mesh(self.mesh); bm.free()
    def tearDown(self):
        bpy.data.meshes.remove(self.mesh)
    def test_closed_reverse_and_transform(self):
        before = [tuple(v.co) for v in self.mesh.vertices]
        measured = measure_mesh(self.mesh, unit_mm=1000, transform=Matrix.Diagonal((2,3,4,1)))
        self.assertEqual(measured['components'],1)
        self.assertEqual(measured['nonmanifold_edges'],0)
        self.assertAlmostEqual(measured['signed_volume_mm3'],192e9)
        self.assertEqual(measured['bounds_mm'],[[-2000,2000],[-3000,3000],[-4000,4000]])
        self.assertEqual(before,[tuple(v.co) for v in self.mesh.vertices])
        bm=bmesh.new();bm.from_mesh(self.mesh);bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.to_mesh(self.mesh);bm.free()
        self.assertAlmostEqual(measure_mesh(self.mesh)['signed_volume'],-8)
    def test_empty_isolated_and_weld(self):
        self.mesh.clear_geometry()
        self.assertIsNone(measure_mesh(self.mesh)['bounds'])
        self.assertEqual(measure_mesh(self.mesh)['signed_volume'],0)
        self.mesh.from_pydata([(0,0,0),(0.00001,0,0),(1,0,0)],[],[])
        self.assertEqual(measure_mesh(self.mesh)['components'],3)
        self.assertEqual(measure_mesh(self.mesh,weld=.0001)['components'],2)
        self.assertEqual(len(self.mesh.vertices),3)
    def test_threshold_and_invalid_policy(self):
        self.mesh.clear_geometry(); self.mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
        self.assertEqual(measure_mesh(self.mesh,area_epsilon=.5)['degenerate_faces'],0)
        self.assertEqual(measure_mesh(self.mesh,area_epsilon=.5,area_inclusive=True)['degenerate_faces'],1)
        for options in ({'unit_mm':0},{'weld':-1},{'area_epsilon':float('nan')}):
            with self.assertRaises(ValueError): measure_mesh(self.mesh,**options)

if __name__=='__main__': unittest.main(argv=[__file__])
