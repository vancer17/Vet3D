"""Keep surface voxels adjacent to exterior air, then pool to Geo2 latent coords."""
import argparse
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import time
import zipfile

import numpy as np
from scipy import ndimage
from checkpoints import digest


def integer_scalar(value):
    a = np.asarray(value)
    if a.ndim != 0 or a.dtype.kind not in 'iu':
        raise ValueError('Expected an integer scalar, without truncation')
    return int(a)


def checked_coords(coords, resolution, *, allow_empty=False):
    a = np.asarray(coords)
    if (a.ndim != 2 or a.shape[1] != 3 or a.dtype.kind not in 'iu'
            or (len(a) == 0 and not allow_empty)):
        raise ValueError('Expected nonempty integer [N,3] coordinates')
    if len(a) and (a.min() < 0 or a.max() >= resolution):
        raise ValueError('Coordinates outside the declared grid; no clipping allowed')
    return np.unique(a.astype(np.int32), axis=0)


def check_grid(grid_size, latent_scale, max_cells):
    if grid_size < 2 or latent_scale < 1 or grid_size % latent_scale:
        raise ValueError('Grid must be >=2 and divisible by positive latent_scale')
    if (grid_size + 2) ** 3 > max_cells:
        raise ValueError('Dense exterior-air grid exceeds max_cells; choose a capable host explicitly')


def exterior_voxels(voxel_coords, grid_size, *, barriers=None, max_cells=150_000_000):
    """Six-connected exterior air; barriers block traversal but never become output."""
    check_grid(grid_size, 1, max_cells)
    coords = checked_coords(voxel_coords, grid_size)
    blocked = np.zeros((grid_size + 2,) * 3, dtype=bool)
    blocked[tuple((coords + 1).T)] = True
    if barriers is not None:
        b = checked_coords(barriers, grid_size, allow_empty=True)
        blocked[tuple((b + 1).T)] = True
    # Padding gives every side a connected exterior seed even when surfaces touch grid edges.
    air = ~blocked
    seed = np.zeros_like(blocked)
    seed[0, :, :] = True
    outside = ndimage.binary_propagation(
        seed, structure=ndimage.generate_binary_structure(3, 1), mask=air)
    keep = np.zeros(len(coords), dtype=bool)
    shifted = coords + 1
    for axis in range(3):
        for delta in (-1, 1):
            neighbor = shifted.copy()
            neighbor[:, axis] += delta
            keep |= outside[tuple(neighbor.T)]
    report = dict(input_voxels=len(coords), exterior_voxels=int(keep.sum()),
                  removed_voxels=int((~keep).sum()),
                  enclosed_empty_cells=int(air.sum() - outside.sum()),
                  air_connectivity=6)
    return coords[keep], coords[~keep], report


def extract(raw_path, output, *, latent_scale, barriers_path=None, max_cells=150_000_000):
    """Read full-resolution surface NPZ; save filtered raw and pooled coords plus proof."""
    started = time.perf_counter()
    raw_path, output = Path(raw_path), Path(output)
    if output.exists():
        raise FileExistsError(output)
    with np.load(raw_path, allow_pickle=False) as data:
        grid = integer_scalar(data['grid_size'])
        source_sha = str(data['source_sha256'])
        frame = str(data['grid_binding_json'])
        coords = data['voxel_coords']
    if len(source_sha) != 64 or any(c not in '0123456789abcdef' for c in source_sha):
        raise ValueError('Expected source SHA-256')
    if not isinstance(json.loads(frame), dict) or not json.loads(frame):
        raise ValueError('Expected nonempty grid binding metadata')
    check_grid(grid, latent_scale, max_cells)
    barriers = None
    if barriers_path is not None:
        with np.load(barriers_path, allow_pickle=False) as data:
            if (integer_scalar(data['grid_size']) != grid or str(data['source_sha256']) != source_sha
                    or str(data['grid_binding_json']) != frame):
                raise ValueError('Barrier source/grid binding mismatch')
            barriers = data['voxel_coords']
    exterior, removed, report = exterior_voxels(coords, grid, barriers=barriers, max_cells=max_cells)
    pooled = checked_coords(exterior // latent_scale, grid // latent_scale)
    output.mkdir(parents=True, exist_ok=False)
    binding = dict(grid_size=grid, source_sha256=source_sha, grid_binding_json=frame)
    np.savez_compressed(output/'surface.npz', voxel_coords=exterior, **binding)
    np.savez_compressed(output/'removed.npz', voxel_coords=removed, **binding)
    np.savez_compressed(output/'geo2_coords.npz', coords=pooled, latent_scale=latent_scale,
                        coord_resolution=grid//latent_scale, **binding)
    report.update(schema=1, source_sha256=source_sha, raw_sha256=digest(raw_path),
                  script_sha256=digest(__file__), grid_size=grid, latent_scale=latent_scale,
                  coord_resolution=grid//latent_scale, latent_voxels=len(pooled),
                  barrier_sha256=digest(barriers_path) if barriers_path is not None else None,
                  grid_binding=json.loads(frame), seconds=time.perf_counter()-started,
                  status='computed_requires_visual_review',
                  geometry_modified=False, watertight_certified=False,
                  artifacts={name: digest(output/name) for name in
                             ['surface.npz', 'removed.npz', 'geo2_coords.npz']})
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def voxelize_mesh(mesh, output, *, grid_size):
    """Use installed hitem_infer's actual Stage2 CUDA voxelizer; no model inference."""
    import inspect
    import torch
    from hitem_infer.methods.geometry_v4_stage2.models.stage2 import coord_fitting
    import pytorch_voxelization
    mesh, output = Path(mesh), Path(output)
    if output.exists():
        raise FileExistsError(output)
    if grid_size < 2 or grid_size > 2048:
        raise ValueError('Expected grid 2..2048 for the checked 11-bit voxelizer')
    before = digest(mesh)
    coords, pad, _ = coord_fitting.glb_to_mesh_voxelizer_coords(
        mesh, grid_size=grid_size, device=torch.device('cuda'), pad=0)
    raw = checked_coords(coords.cpu().numpy(), grid_size)
    if digest(mesh) != before:
        raise ValueError('Source changed during voxelization')
    binding = dict(mode='hitem_stage2_mesh_voxelizer', pad=pad, shift=[0, 0, 0],
                   coordinate_order='xyz', normalization='Stage2 centered uniform fit; voxelizer eps-expanded fit',
                   coord_fitting_sha256=digest(inspect.getfile(coord_fitting)),
                   voxelizer_sha256=digest(inspect.getfile(pytorch_voxelization.MeshVoxelizer)))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as f:
        np.savez_compressed(f, voxel_coords=raw, grid_size=grid_size,
                            source_sha256=before, grid_binding_json=json.dumps(binding, sort_keys=True))
    return dict(voxels=len(raw), grid_size=grid_size, output=str(output))


def attach_coords(prep_zip, coords_npz, source, output, *, grid_size, latent_scale):
    """Copy an already validated prep ZIP verbatim and add the sole root coords NPZ."""
    prep_zip, coords_npz, source, output = map(Path, [prep_zip, coords_npz, source, output])
    if output.exists():
        raise FileExistsError(output)
    check_grid(grid_size, latent_scale, (grid_size+2)**3)
    with np.load(coords_npz, allow_pickle=False) as data:
        if (integer_scalar(data['grid_size']) != grid_size or integer_scalar(data['latent_scale']) != latent_scale
                or integer_scalar(data['coord_resolution']) != grid_size//latent_scale
                or str(data['source_sha256']) != digest(source)):
            raise ValueError('Source or target profile mismatch')
        raw = data['coords']
        valid = checked_coords(raw, grid_size//latent_scale)
        if len(raw) != len(valid):
            raise ValueError('Duplicate latent coords')
    with zipfile.ZipFile(prep_zip) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP members')
        for info in infos:
            path = PurePosixPath(info.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in info.filename
                    or (info.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Unsafe ZIP member')
            if path.suffix.lower() == '.glb':
                raise ValueError('Mesh must be supplied separately; embedded mesh can shadow source')
            if len(path.parts) == 1 and path.suffix.lower() == '.npz':
                with np.load(BytesIO(z.read(info)), allow_pickle=False) as data:
                    if 'coords' in data:
                        raise ValueError('Existing coords NPZ would compete with the new surface coords')
        if 'geo2_coords.npz' in names:
            raise ValueError('Existing output member')
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as stream, zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as out:
            for info in infos:
                out.writestr(info, z.read(info))
            out.write(coords_npz, 'geo2_coords.npz')
    return dict(prep_zip=str(output), sha256=digest(output), source_sha256=digest(source))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    voxel = sub.add_parser('voxelize')
    voxel.add_argument('--mesh', type=Path, required=True)
    voxel.add_argument('--output', type=Path, required=True)
    voxel.add_argument('--grid-size', type=int, required=True)
    filt = sub.add_parser('filter')
    filt.add_argument('--raw', type=Path, required=True)
    filt.add_argument('--output', type=Path, required=True)
    filt.add_argument('--latent-scale', type=int, required=True)
    filt.add_argument('--barriers', type=Path)
    filt.add_argument('--max-cells', type=int, default=150_000_000)
    pack = sub.add_parser('package')
    for name in ['prep-zip', 'coords', 'source', 'output']:
        pack.add_argument('--'+name, type=Path, required=True)
    pack.add_argument('--grid-size', type=int, required=True)
    pack.add_argument('--latent-scale', type=int, required=True)
    a = p.parse_args(argv)
    if a.command == 'voxelize':
        result = voxelize_mesh(a.mesh, a.output, grid_size=a.grid_size)
    elif a.command == 'filter':
        result = extract(a.raw, a.output, latent_scale=a.latent_scale,
                         barriers_path=a.barriers, max_cells=a.max_cells)
    else:
        result = attach_coords(a.prep_zip, a.coords, a.source, a.output,
                               grid_size=a.grid_size, latent_scale=a.latent_scale)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
