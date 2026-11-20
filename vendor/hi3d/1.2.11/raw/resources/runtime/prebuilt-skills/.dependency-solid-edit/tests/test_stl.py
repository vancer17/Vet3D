"""STL adapter retains millimetres, float32 profile and source solids."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import numpy as np
import manifold3d as M
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from solid_tools import stl


class StlTests(unittest.TestCase):
    def test_actual_solid_coordinates_and_header_roundtrip(self):
        solid = M.Manifold.cube((2, 3, 4), True).rotate((15, 20, 30)).translate((1, -2, 3))
        mesh = solid.to_mesh()
        expected = np.asarray(mesh.vert_properties[:, :3])[mesh.tri_verts].astype(np.float32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'part.stl'; stl(solid, path); data = path.read_bytes()
        self.assertEqual(data[:80], b'Hi3D surface and Astra joints; millimeters'.ljust(80, b'\0'))
        count = struct.unpack_from('<I', data, 80)[0]
        self.assertEqual(count, len(expected)); self.assertEqual(len(data), 84+50*count)
        records = [struct.unpack_from('<12fH', data, 84+i*50) for i in range(count)]
        np.testing.assert_array_equal(np.array([r[3:12] for r in records]).reshape(-1, 3, 3), expected)
        np.testing.assert_allclose(np.linalg.norm([r[:3] for r in records], axis=1), 1, atol=2e-7)
        self.assertTrue(all(r[-1] == 0 for r in records))
        after = solid.to_mesh()
        np.testing.assert_array_equal(after.vert_properties, mesh.vert_properties)
        np.testing.assert_array_equal(after.tri_verts, mesh.tri_verts)


if __name__ == '__main__': unittest.main()
