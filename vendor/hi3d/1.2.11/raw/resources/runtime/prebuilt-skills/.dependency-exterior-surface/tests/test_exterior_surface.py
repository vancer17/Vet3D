import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from exterior_surface import exterior_voxels, extract, attach_coords, digest


def box_shell(lo, hi):
    coords = np.indices((hi-lo+1,)*3).reshape(3, -1).T + lo
    return coords[np.any((coords == lo) | (coords == hi), axis=1)]


class ExteriorTests(unittest.TestCase):
    def test_enclosed_parts_removed_exposed_parts_retained(self):
        outer = box_shell(3, 12)
        inner = box_shell(6, 9)
        exposed = np.array([[14, 8, 8]])
        kept, removed, report = exterior_voxels(np.vstack([outer, inner, exposed]), 16)
        self.assertEqual(set(map(tuple, kept)), set(map(tuple, np.vstack([outer, exposed]))))
        self.assertEqual(set(map(tuple, removed)), set(map(tuple, inner)))
        self.assertGreater(report['enclosed_empty_cells'], 0)

    def test_open_mouth_keeps_connected_inner_surfaces(self):
        outer = box_shell(3, 12)
        outer = outer[~np.all(outer == [3, 7, 7], axis=1)]
        tooth = np.array([[7, 7, 7]])
        kept, removed, _ = exterior_voxels(np.vstack([outer, tooth]), 16)
        self.assertIn((7, 7, 7), set(map(tuple, kept)))
        self.assertEqual(len(removed), 0)

    def test_virtual_cap_does_not_create_output_surface(self):
        outer = box_shell(3, 12)
        outer = outer[~np.all(outer == [3, 7, 7], axis=1)]
        kept, removed, _ = exterior_voxels(np.vstack([outer, [[7, 7, 7]]]), 16,
                                         barriers=np.array([[3, 7, 7]]))
        self.assertNotIn((3, 7, 7), set(map(tuple, kept)))
        self.assertEqual(removed.tolist(), [[7, 7, 7]])

    def test_grid_boundary_is_exterior(self):
        coords = box_shell(0, 7)
        kept, removed, _ = exterior_voxels(coords, 8)
        self.assertEqual(len(kept), len(coords))
        self.assertEqual(len(removed), 0)

    def test_invalid_and_budget_rejected(self):
        for coords in [np.array([[0.5, 1, 2]]), np.array([[-1, 1, 2]]), np.array([[8, 1, 2]])]:
            with self.assertRaises(ValueError):
                exterior_voxels(coords, 8)
        with self.assertRaisesRegex(ValueError, 'max_cells'):
            exterior_voxels(np.array([[0, 0, 0]]), 1024)

    def make_inputs(self, root):
        source = root/'assembled.glb'
        source.write_bytes(b'synthetic source binding; not a GLB decoding test')
        raw = root/'raw.npz'
        binding = dict(grid_size=16, source_sha256=digest(source),
                       grid_binding_json=json.dumps({'test_grid': 'xyz'}))
        np.savez(raw, voxel_coords=np.vstack([box_shell(3,12), box_shell(6,9)]), **binding)
        return source, raw, binding

    def test_pool_after_exterior_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, raw, _ = self.make_inputs(root)
            report = extract(raw, root/'out', latent_scale=2)
            with np.load(root/'out/geo2_coords.npz') as data:
                self.assertEqual(set(map(tuple, data['coords'])), set(map(tuple, box_shell(3,12)//2)))
                self.assertEqual(int(data['coord_resolution']), 8)
            self.assertEqual(report['status'], 'computed_requires_visual_review')
            with self.assertRaises(FileExistsError):
                extract(raw, root/'out', latent_scale=2)

    def test_barrier_binding_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, raw, binding = self.make_inputs(root)
            binding['source_sha256'] = '0'*64
            np.savez(root/'barrier.npz', voxel_coords=np.array([[3,7,7]]), **binding)
            with self.assertRaisesRegex(ValueError, 'binding mismatch'):
                extract(raw, root/'out', latent_scale=2, barriers_path=root/'barrier.npz')
            self.assertFalse((root/'out').exists())

    def test_package_preserves_members_and_blocks_stale_coords(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, raw, _ = self.make_inputs(root)
            extract(raw, root/'out', latent_scale=2)
            prep = root/'prep.zip'
            with zipfile.ZipFile(prep, 'w') as z:
                z.writestr('View0_CCM.exr', b'opaque fixture bytes')
                z.writestr('camera_info.txt', b'exact camera fixture')
            coords = root/'out/geo2_coords.npz'
            attach_coords(prep, coords, source, root/'ready.zip', grid_size=16, latent_scale=2)
            with zipfile.ZipFile(root/'ready.zip') as z:
                self.assertEqual(z.read('View0_CCM.exr'), b'opaque fixture bytes')
                self.assertEqual(z.read('geo2_coords.npz'), coords.read_bytes())
            with self.assertRaisesRegex(ValueError, 'Existing coords'):
                attach_coords(root/'ready.zip', coords, source, root/'bad.zip', grid_size=16, latent_scale=2)
            source.write_bytes(b'different source')
            with self.assertRaisesRegex(ValueError, 'profile mismatch'):
                attach_coords(prep, coords, source, root/'bad2.zip', grid_size=16, latent_scale=2)


if __name__ == '__main__':
    unittest.main()
