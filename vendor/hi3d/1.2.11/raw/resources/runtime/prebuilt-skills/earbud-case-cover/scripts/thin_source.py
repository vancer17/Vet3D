"""Opt-in exterior contraction around the existing nominal rounded-box cavity.

Millimetres throughout. This changes source vertices, not the cavity or final
shell checks. The unchanged build_solids stage must still cut and validate the
actual parts. Importing this module performs no file or process operations.
"""
from collections.abc import Mapping
from pathlib import Path
import argparse
import json
import shutil

import numpy as np

from path_safety import validate_write_roots
from stage_cli import cli_arguments


def _scalar(value, name):
    """Return one finite real number, rejecting booleans and array inputs."""
    if isinstance(value, (bool, np.bool_)) or not np.isscalar(value):
        raise ValueError(f'{name} must be one finite real number')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f'{name} must be one finite real number') from error
    if not np.isfinite(result):
        raise ValueError(f'{name} must be finite')
    return result


def _vector(value, name):
    """Return an independent finite three-vector."""
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (3,) or not np.isfinite(result).all():
        raise ValueError(f'{name} must contain three finite numbers')
    return result.copy()


def _controls(fraction, preserve):
    fraction = _scalar(fraction, 'fraction')
    preserve = _scalar(preserve, 'preserve')
    if not 0 <= fraction < 0.6 or not 1.5 <= preserve <= 3:
        raise ValueError('fraction must be in [0, 0.6); preserve must be in [1.5, 3] mm')
    return fraction, preserve


def thinning_parameters(configuration):
    """Return explicit contraction inputs, or None when thinning is disabled.

The opt-in flag must be boolean. Missing/false preserves the existing workflow;
no numeric thinning values are inferred or enabled from their presence alone.
With true, both thinning controls and all nominal cavity fields are required.
"""
    if not isinstance(configuration, Mapping):
        raise ValueError('configuration must be a mapping')
    enabled = configuration.get('thin_enabled', False)
    if not isinstance(enabled, bool):
        raise ValueError('thin_enabled must be true or false')
    if not enabled:
        return None
    names = ('thin_excess_fraction', 'thin_preserve_offset_mm', 'device_mm',
             'clearance_mm', 'device_y_mm', 'device_bottom_mm',
             'device_corner_radius_mm')
    missing = [name for name in names if name not in configuration]
    if missing:
        raise ValueError('Enabled thinning requires explicit fields: ' + ', '.join(missing))
    fraction, preserve = _controls(configuration['thin_excess_fraction'],
                                    configuration['thin_preserve_offset_mm'])
    device = _vector(configuration['device_mm'], 'device_mm')
    clearance = _scalar(configuration['clearance_mm'], 'clearance_mm')
    radius = _scalar(configuration['device_corner_radius_mm'], 'device_corner_radius_mm')
    if np.any(device <= 0) or clearance < 0 or radius <= 0 or radius > device.min() / 2:
        raise ValueError('Device dimensions/radius must define a positive rounded box; clearance must be nonnegative')
    center = [0, _scalar(configuration['device_y_mm'], 'device_y_mm'),
              _scalar(configuration['device_bottom_mm'], 'device_bottom_mm') + device[2] / 2]
    dimensions = device + 2 * clearance
    if not np.isfinite(dimensions).all() or not np.isfinite(center).all():
        raise ValueError('Cavity arithmetic exceeded finite millimetre coordinates')
    return dict(center=center, dimensions=dimensions, radius=radius + clearance,
                fraction=fraction, preserve=preserve)


def contract_excess(vertices, *, center, dimensions, radius, fraction, preserve):
    """Return new Nx3 vertices and old/new vertex distances to the nominal cavity.

Preserve the closest rounded-box core point and ray direction. Above the
explicit protected offset, reduce excess by fraction with a fixed 0.6 mm C1
onset. Source vertices and topology are never modified in place. Distances are
source vertex samples, not a final shell minimum-thickness certificate.
"""
    fraction, preserve = _controls(fraction, preserve)
    v = np.asarray(vertices, dtype=np.float64)
    if v.ndim != 2 or v.shape[1] != 3 or len(v) == 0 or not np.isfinite(v).all():
        raise ValueError('vertices must be finite nonempty Nx3 millimetre coordinates')
    center = _vector(center, 'center')
    dimensions = _vector(dimensions, 'dimensions')
    radius = _scalar(radius, 'radius')
    half_core = dimensions / 2 - radius
    if radius <= 0 or np.any(dimensions <= 0) or np.any(half_core < 0):
        raise ValueError('dimensions and radius must define a positive rounded box')
    with np.errstate(over='ignore', invalid='ignore'):
        local = v - center
        core = np.clip(local, -half_core, half_core)
        ray = local - core
        distance = np.linalg.norm(ray, axis=1)
    if not np.isfinite(distance).all() or np.any(distance <= radius):
        raise ValueError('Source vertices must have finite distances outside the nominal cavity')
    old = distance - radius
    excess = np.maximum(old - preserve, 0)
    transition = 0.6
    # Piecewise evaluation avoids squaring large values outside the onset band.
    smoothed = excess - transition / 2
    onset = excess < transition
    smoothed[onset] = excess[onset] ** 2 / (2 * transition)
    new = old - fraction * smoothed
    moved = center + core + ray * ((radius + new) / distance)[:, None]
    # Exactly preserve the protected vertices, including a zero-fraction replay.
    moved[excess == 0] = v[excess == 0]
    if fraction == 0:
        moved = v.copy()
    if not np.isfinite(moved).all():
        raise ValueError('Contraction exceeded finite millimetre coordinates')
    return moved, old, new


def thin_prepared_source(source, output, configuration):
    """Write a distinct source NPZ/material library and sampled transform report.

Requires thin_enabled=true plus explicit controls. Reject root overlap, linked
output files, missing source files and malformed geometry before writing.
Existing ordinary files in a separate derived output directory may be replaced.
The copied source.blend remains the original material library, not thinned mesh.
"""
    parameters = thinning_parameters(configuration)
    if parameters is None:
        raise ValueError('Thinning is disabled; explicitly set thin_enabled=true to run this stage')
    source = Path(source).resolve()
    output = validate_write_roots({'output': output},
        package_root=Path(__file__).resolve().parents[1], protected_inputs=[source])['output']
    inputs = [source / name for name in ('source.npz', 'source.blend')]
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists() and not output.is_dir():
        raise ValueError('output must be a directory')
    for name in ('source.npz', 'source.blend', 'thinning-transform.json'):
        destination = output / name
        if destination.is_symlink() or (destination.exists() and not destination.is_file()):
            raise ValueError(f'Output must be a regular unlinked file: {destination}')
        if destination.exists() and (destination.stat().st_nlink > 1
                or any(destination.samefile(path) for path in inputs)):
            raise ValueError(f'Output aliases an existing file: {destination}')
    with np.load(inputs[0], allow_pickle=False) as archive:
        data = {name: archive[name].copy() for name in archive.files}
    for name in ('vertices', 'faces', 'uv', 'material_index'):
        if name not in data:
            raise ValueError(f'source.npz is missing {name}')
    moved, old, new = contract_excess(data['vertices'], **parameters)
    faces, uv, material = data['faces'], data['uv'], data['material_index']
    if (faces.ndim != 2 or faces.shape[1] != 3 or len(faces) == 0
            or not np.issubdtype(faces.dtype, np.integer)
            or faces.min() < 0 or faces.max() >= len(moved)):
        raise ValueError('faces must be nonempty Mx3 integer indices into vertices')
    if uv.shape != (len(faces), 3, 2) or not np.isfinite(uv).all():
        raise ValueError('uv must contain finite Mx3x2 corner coordinates')
    if (material.shape != (len(faces),) or not np.issubdtype(material.dtype, np.integer)
            or np.any(material < 0)):
        raise ValueError('material_index must contain M nonnegative integers')
    record = {
        'method': 'Closest-core radial contraction around fixed nominal rounded-box cavity',
        'fraction': parameters['fraction'],
        'protected_offset_mm': parameters['preserve'], 'transition_mm': 0.6,
        'before_bounds_mm': [data['vertices'].min(0).tolist(), data['vertices'].max(0).tolist()],
        'after_bounds_mm': [moved.min(0).tolist(), moved.max(0).tolist()],
        'before_vertex_cavity_distance_mm': np.percentile(old, [0, 5, 50, 95, 100]).tolist(),
        'after_vertex_cavity_distance_mm': np.percentile(new, [0, 5, 50, 95, 100]).tolist(),
        'distance_note': 'Uncut source vertex samples; not final shell thickness or a physical strength test',
        'faces_and_corner_uv_unchanged': True,
        'global_remesh': False, 'source_decimation': False,
        'next_stage': 'Cut the same cavity, seams and openings, then validate actual solids and motion',
    }
    data['vertices'] = moved
    output.mkdir(parents=True, exist_ok=True)
    np.savez(output / 'source.npz', **data)
    shutil.copy2(inputs[1], output / 'source.blend')
    (output / 'thinning-transform.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args(cli_arguments(argv))
    validate_write_roots({'output': args.output},
        package_root=Path(__file__).resolve().parents[1], protected_inputs=[args.source, args.config])
    configuration = json.loads(args.config.read_text())
    result = thin_prepared_source(args.source, args.output, configuration)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    main()
