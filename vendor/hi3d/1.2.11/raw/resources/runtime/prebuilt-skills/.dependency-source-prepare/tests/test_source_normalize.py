"""Run inside Blender against the materialized source-prepare package."""
import sys
import tempfile
import unittest
import hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import bpy
import numpy as np
from source_normalize import normalize_source


class SourceNormalization(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        parent = bpy.data.objects.new('transformed parent', None)
        bpy.context.collection.objects.link(parent)
        parent.location = (2, 3, 4)
        parent.scale = (2, 1, 1)
        for index, location in enumerate([(0, 0, 0), (1.5, 0, 1)]):
            bpy.ops.mesh.primitive_cube_add(size=1, location=location)
            obj = bpy.context.object
            obj.parent = parent
            obj.data.materials.append(bpy.data.materials.new('material' + str(index)))
        self.source = self.root / 'input.glb'
        bpy.ops.export_scene.gltf(filepath=str(self.source), export_format='GLB', export_animations=False)
        self.original = self.source.read_bytes()

    def test_world_transform_yaw_uv_materials_and_reopen(self):
        obj, first = normalize_source(self.source, self.root / 'zero', 200, yaw_deg=0)
        a = np.load(self.root / 'zero/source.npz')
        vertices = a['vertices'].copy()
        self.assertEqual(set(a['material_index']), {0, 1})
        self.assertEqual(a['uv'].shape, (len(a['faces']), 3, 2))
        self.assertGreater(np.ptp(a['uv']), 0)
        self.assertEqual(first['after']['nonmanifold_edges'], 0)
        self.assertLess(first['after']['vertices'], first['before']['vertices'])
        self.assertIsNone(obj.parent)
        np.testing.assert_allclose(vertices.min(0)[2], 0, atol=1e-5)
        np.testing.assert_allclose(vertices.max(0)[2], 200, atol=1e-4)
        np.testing.assert_allclose((vertices.min(0) + vertices.max(0))[:2], 0, atol=1e-4)
        obj, second = normalize_source(self.source, self.root / 'yaw', 200, yaw_deg=90)
        b = np.load(self.root / 'yaw/source.npz')
        expected = vertices[:, [1, 0, 2]] * [-1, 1, 1]
        np.testing.assert_allclose(b['vertices'], expected, atol=5e-5)
        for key in ['faces', 'uv', 'material_index']:
            np.testing.assert_array_equal(a[key], b[key])
        a.close(); b.close()
        self.assertEqual(second['source_sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(self.source.read_bytes(), self.original)
        bpy.ops.wm.open_mainfile(filepath=str(self.root / 'yaw/source.blend'))
        mesh = bpy.data.objects['Original textured Hi3D surface']
        self.assertAlmostEqual(mesh.dimensions.z, .2, places=5)
        self.assertEqual(len(mesh.data.materials), 2)
        self.assertFalse(any(o.type == 'CAMERA' for o in bpy.context.scene.objects))

    def test_invalid_scalars_and_flat_source(self):
        for height in [0, -1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                normalize_source(self.source, self.root / 'invalid', height)
        with self.assertRaises(ValueError):
            normalize_source(self.source, self.root / 'invalid', 200, yaw_deg=float('nan'))
        with self.assertRaises(ValueError):
            normalize_source(self.source, self.root / 'invalid', 200, weld_tolerance_mm=-1)
        self.assertFalse((self.root / 'invalid').exists())
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_plane_add()
        flat = self.root / 'flat.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(flat))
        with self.assertRaisesRegex(ValueError, 'Z extent'):
            normalize_source(flat, self.root / 'flat-output', 200)


if __name__ == '__main__':
    unittest.main(argv=[__file__])
