import sys, unittest, tempfile, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import bpy
from render_scene import render_scene


class SceneRendering(unittest.TestCase):
    def test_real_profiles_preserve_source_and_report_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root/'source.blend'
            bpy.ops.wm.read_factory_settings(use_empty=False)
            bpy.context.scene.render.fps = 30; bpy.context.scene.render.fps_base = 1.001
            bpy.ops.wm.save_as_mainfile(filepath=str(source))
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            paths = render_scene(source, root/'eevee', [2,4], engine='BLENDER_EEVEE', resolution=(16,16))
            self.assertEqual([p.name for p in paths], ['0002.png','0004.png'])
            self.assertEqual(bpy.context.scene.render.fps, 30)
            self.assertAlmostEqual(bpy.context.scene.render.fps_base, 1.001, places=5)
            with self.assertRaises(FileExistsError):
                render_scene(source, root/'eevee', [2], engine='BLENDER_EEVEE', resolution=(16,16), overwrite=False)
            paths = render_scene(source, root/'cycles', [2,3], engine='CYCLES', resolution=(16,16),
                                 fps=24, samples=1, threads=2, device='CPU', denoise=True,
                                 animation=True, prefix='frame-')
            self.assertEqual([p.name for p in paths], ['frame-0002.png','frame-0003.png'])
            self.assertEqual(bpy.context.scene.render.fps_base, 1)
            for p in paths: self.assertEqual(p.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())
            with self.assertRaises(ValueError):
                render_scene(source, root/'invalid', [2,4], engine='CYCLES', resolution=(16,16), animation=True)
            bpy.context.scene.camera = None
            broken = root/'no-camera.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(broken))
            with self.assertRaises(RuntimeError):
                render_scene(broken, root/'failed', [1], engine='BLENDER_EEVEE', resolution=(16,16))

if __name__ == '__main__': unittest.main(argv=[__file__])
