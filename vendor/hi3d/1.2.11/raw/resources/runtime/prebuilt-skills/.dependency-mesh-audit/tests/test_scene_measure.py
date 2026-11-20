"""Run with Blender in a materialized mesh-audit package."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import bpy
import numpy as np
from scene_measure import object_bounds, measure_objects


class SceneMeasurements(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(size=2)
        self.obj = bpy.context.object

    def test_world_bounds_local_volume_and_raw_geometry(self):
        obj = self.obj
        parent = bpy.data.objects.new('parent', None)
        bpy.context.scene.collection.objects.link(parent)
        parent.location = (10, 0, 0)
        parent.scale = (-2, 3, 4)
        obj.parent = parent
        obj.location = (1, 0, 0)
        obj.modifiers.new('ignored subdivision', 'SUBSURF').levels = 2
        bpy.context.view_layer.update()
        before = [v.co[:] for v in obj.data.vertices]
        matrix = obj.matrix_world.copy()
        frame = bpy.context.scene.frame_current
        result = measure_objects([parent, obj], unit_mm=1000, topology_objects=[obj])
        np.testing.assert_allclose(result['bounds_mm'], [[6000, -3000, -4000], [10000, 3000, 4000]])
        row = result['objects'][0]
        self.assertEqual((row['vertices'], row['faces'], row['triangles']), (8, 6, 12))
        np.testing.assert_allclose(row['volume_mm3'], 8e9, rtol=1e-12)
        self.assertEqual(row['nonmanifold_edges'], 0)
        self.assertEqual(before, [v.co[:] for v in obj.data.vertices])
        self.assertEqual(matrix, obj.matrix_world)
        self.assertEqual(frame, bpy.context.scene.frame_current)

    def test_empty_mesh_policies(self):
        empty = bpy.data.objects.new('empty', bpy.data.meshes.new('empty'))
        bpy.context.scene.collection.objects.link(empty)
        with self.assertRaises(ValueError):
            measure_objects([self.obj, empty], unit_mm=1)
        self.assertEqual(len(measure_objects([self.obj, empty], unit_mm=1, empty='skip')['objects']), 1)
        kept = measure_objects([self.obj, empty], unit_mm=1, empty='keep')['objects'][1]
        self.assertIsNone(kept['bounds_mm'])
        self.assertEqual(kept['vertices'], 0)
        for policy in ('skip', 'keep'):
            with self.assertRaises(ValueError):
                measure_objects([empty], unit_mm=1, empty=policy)

    def test_precision_and_invalid_parameters(self):
        for precision in ('float32', 'float64'):
            np.testing.assert_array_equal(object_bounds(self.obj, unit_mm=1, precision=precision),
                                          [[-1, -1, -1], [1, 1, 1]])
        for unit in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                object_bounds(self.obj, unit_mm=unit)
        with self.assertRaises(ValueError):
            object_bounds(self.obj, unit_mm=1, precision='float16')
        with self.assertRaises(ValueError):
            measure_objects([self.obj], unit_mm=1, empty='unknown')


if __name__ == '__main__':
    unittest.main(argv=[__file__])
