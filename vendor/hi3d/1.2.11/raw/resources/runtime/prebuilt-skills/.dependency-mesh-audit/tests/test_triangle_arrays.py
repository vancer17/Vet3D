import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from triangle_arrays import edge_incidence, edge_counts, measure_indexed, triangle_double_areas

class Triangles(unittest.TestCase):
    def test_collapsed_edges_are_an_explicit_policy(self):
        triangles=np.array([[0,0,1],[0,1,2]],np.int32);before=triangles.copy()
        edges,counts,collapsed=edge_incidence(triangles,discard_collapsed=False)
        self.assertEqual(collapsed,1);self.assertEqual(len(edges),4)
        self.assertEqual(edge_counts(triangles),dict(unique_edges=3,boundary_edges=2,edges_over_two_faces=1,collapsed_edge_uses=1))
        np.testing.assert_array_equal(triangles,before)
    def test_virtual_weld_and_precision_are_preserved(self):
        v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,0,0],[1,1,0],[0,1,0]],np.float32)
        f=np.arange(6).reshape(-1,3);before=v.copy()
        result=measure_indexed(v,f,exact_weld=True,area_threshold=.5)
        self.assertEqual(result['indexed_topology']['boundary_edges'],6)
        self.assertEqual(result['exact_position_weld_diagnostic']['boundary_edges'],4)
        self.assertEqual(result['degenerate_triangles'],2)
        self.assertEqual(triangle_double_areas(v,f).dtype,np.dtype('float32'))
        np.testing.assert_array_equal(v,before)
    def test_empty_nonfinite_and_invalid_threshold(self):
        empty=measure_indexed(np.empty((0,3)),np.empty((0,3),int),exact_weld=True)
        self.assertIsNone(empty['local_bounds_min']);self.assertIsNone(empty['degenerate_triangles'])
        self.assertEqual(empty['indexed_topology']['unique_edges'],0)
        result=measure_indexed(np.array([[float('nan'),0,0]]),np.array([[0,0,0]]),exact_weld=True)
        self.assertFalse(result['finite_coordinates']);self.assertNotIn('exact_position_weld_diagnostic',result)
        with self.assertRaises(ValueError):measure_indexed(np.empty((0,3)),np.empty((0,3),int),area_threshold=-1)

if __name__=='__main__':unittest.main()
