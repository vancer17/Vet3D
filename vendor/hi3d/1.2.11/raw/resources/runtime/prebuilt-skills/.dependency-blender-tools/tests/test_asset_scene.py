"""Exercise explicit asset loading in an isolated Blender process."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import bpy
from asset_scene import open_asset


class AssetScenes(unittest.TestCase):
    def test_full_native_scene_glb_frame_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.mesh.primitive_cube_add(size=2)
            bpy.context.object.name = 'asset cube'
            bpy.context.object.keyframe_insert(data_path='location', frame=1)
            bpy.context.object.location.z = 2
            bpy.context.object.keyframe_insert(data_path='location', frame=9)
            bpy.context.scene['full_scene_marker'] = 'preserved'
            bpy.context.scene.frame_set(7)
            native, glb = root / 'asset.blend', root / 'asset.glb'
            bpy.ops.wm.save_as_mainfile(filepath=str(native))
            bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB')
            hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (native, glb)}
            bpy.context.scene['full_scene_marker'] = 'changed'
            loaded = open_asset(native)
            self.assertEqual(bpy.context.scene['full_scene_marker'], 'preserved')
            self.assertEqual(bpy.context.scene.frame_current, 7)
            self.assertIn('asset cube', [o.name for o in loaded])
            open_asset(glb, frame=0)
            self.assertEqual(bpy.context.scene.frame_current, 0)
            self.assertNotIn('full_scene_marker', bpy.context.scene)
            self.assertTrue(bpy.data.actions)
            for path, digest in hashes.items():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_preflight_failure_preserves_current_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.mesh.primitive_cube_add()
            obj = bpy.context.object
            unsupported = root / 'asset.txt'
            unsupported.write_text('fixture')
            invalid_glb = root / 'asset.glb'
            invalid_glb.write_bytes(b'fixture')
            for path, kwargs, error in ((root / 'missing.blend', {}, FileNotFoundError),
                                        (unsupported, {}, ValueError),
                                        (invalid_glb, {'frame': 1.5}, ValueError)):
                with self.assertRaises(error):
                    open_asset(path, **kwargs)
                self.assertIn(obj, list(bpy.context.scene.objects))


if __name__ == '__main__':
    unittest.main(argv=[__file__])
