import sys, unittest, tempfile, struct, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import bpy
from web_derivative import export_derivative, clear_mesh_cache


class DerivativeTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8)
        self.obj = bpy.context.object
        self.obj['asset'] = False
        self.obj.hide_set(True)
        mat = bpy.data.materials.new('fixture'); mat.use_nodes = True
        self.node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        self.image = bpy.data.images.new('wide', width=64, height=2)
        self.node.image = self.image; self.obj.data.materials.append(mat)
        self.cache = {}

    def tearDown(self):
        clear_mesh_cache(self.cache)

    def export(self, path, **kwargs):
        return export_derivative(path, [self.obj], derivatives=[self.obj],
                    collection=bpy.context.collection, polygon_budget=32,
                    texture_limit=8, mesh_cache=self.cache, **kwargs)

    def test_failed_export_restores_scene_and_resources(self):
        def counts():
            return tuple(len(c) for c in [bpy.data.objects,bpy.data.meshes,bpy.data.images])
        before = counts(); verts = [v.co[:] for v in self.obj.data.vertices]
        selected = self.obj.select_get()
        def fail(**kwargs):
            self.assertEqual(tuple(self.node.image.size), (8,1))
            self.assertIsNot(self.node.image, self.image)
            raise RuntimeError('export fixture')
        with self.assertRaisesRegex(RuntimeError, 'fixture'):
            self.export('/unused.glb', exporter=fail)
        self.assertEqual(before, counts()); self.assertFalse(self.cache)
        self.assertIs(self.node.image, self.image)
        self.assertEqual(tuple(self.image.size), (64,2))
        self.assertTrue(self.obj.hide_get()); self.assertFalse(self.obj['asset'])
        self.assertEqual(self.obj.select_get(), selected)
        self.assertEqual(verts, [v.co[:] for v in self.obj.data.vertices])

    def test_real_exports_and_content_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'preview.glb'
            report = self.export(path, export_animations=False)
            self.assertLess(report[0]['preview_polygons'], report[0]['source_polygons'])
            self.assertTrue(self.export(path, export_animations=False)[0]['cache_hit'])
            self.obj.data.vertices[0].co.x += .5
            self.assertFalse(self.export(path, export_animations=False)[0]['cache_hit'])
            self.obj.location.x = 0; self.obj.keyframe_insert('location',frame=1)
            self.obj.location.x = 1; self.obj.keyframe_insert('location',frame=2)
            bpy.context.scene.frame_start = 1; bpy.context.scene.frame_end = 2
            self.export(path, export_animations=True, export_force_sampling=True)
            data = path.read_bytes(); length = struct.unpack_from('<I',data,12)[0]
            self.assertTrue(json.loads(data[20:20+length]).get('animations'))
            self.assertIs(self.node.image, self.image)
            self.assertFalse(self.obj['asset'])

if __name__ == '__main__':
    unittest.main(argv=[__file__])
