import sys, unittest, struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from blender_stl import raw_triangles, evaluated_triangles, stl_bytes

class STL(unittest.TestCase):
    def test_bytes_and_degenerate(self):
        triangles=np.array([[[0,0,0],[1,0,0],[0,1,0]],[[0,0,0]]*3])
        blob=stl_bytes(triangles,header=b'fixture',padding=b'\0')
        self.assertEqual(len(blob),184);self.assertEqual(blob[:80],b'fixture'.ljust(80,b'\0'))
        self.assertEqual(struct.unpack('<I',blob[80:84])[0],2)
        self.assertEqual(struct.unpack('<3f',blob[84:96]),(0,0,1))
        self.assertEqual(struct.unpack('<3f',blob[134:146]),(0,0,0))
        with self.assertRaises(ValueError):stl_bytes(triangles*np.nan,header=b'bad')
    def test_raw_evaluated_and_world(self):
        import bpy
        bpy.ops.mesh.primitive_cube_add(size=2)
        obj=bpy.context.object;obj.location=(3,4,5);obj.scale=(2,3,4)
        mod=obj.modifiers.new('Subdivision fixture','SUBSURF');mod.levels=1
        bpy.context.view_layer.update()
        before=[tuple(v.co) for v in obj.data.vertices]
        local=raw_triangles(obj,world=False,scale=1)
        world=raw_triangles(obj,world=True,scale=1)
        self.assertEqual(len(local),12)
        np.testing.assert_allclose(world.min(axis=(0,1)),[1,1,1])
        np.testing.assert_allclose(world.max(axis=(0,1)),[5,7,9])
        self.assertGreater(len(evaluated_triangles([obj],scale=1)),len(local))
        self.assertEqual(before,[tuple(v.co) for v in obj.data.vertices])
        self.assertEqual(len(raw_triangles(obj,world=True,triangulation='bmesh')),12)

if __name__=='__main__':unittest.main(argv=[__file__])
