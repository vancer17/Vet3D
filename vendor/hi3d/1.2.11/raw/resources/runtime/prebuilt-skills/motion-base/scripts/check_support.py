"""check support local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import numpy as np, json, hashlib, sys
from pathlib import Path
from support_core import mass_properties, combine_mass, signed_margins
from stl_to_3mf import decode_stl
from stage_cli import cli_arguments, StageFinished, _finish_stage

from cli_schemas import directory_stage

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    d = Path(arguments)
    info = json.loads((d / 'construction.json').read_text())
    rows = []
    masses = []
    for path in sorted((d / 'print').glob('*.stl')):
        data = path.read_bytes()
        vertices, triangles = decode_stl(data)
        # Equal synthetic density cancels in the combined solid-volume centroid.
        part = mass_properties(vertices, triangles, density_g_cm3=1, unit_mm=1,
                               volume_epsilon_mm3=0)
        if part['signed_volume_mm3'] <= 0:
            raise ValueError('Expected positive-volume, consistently wound final STL')
        rows.append({'file': path.name, 'sha256': hashlib.sha256(data).hexdigest(),
                     'volume_mm3': part['signed_volume_mm3'],
                     'solid_volume_centroid_mm': part['center_mm']})
        masses.append(part)
    c = np.asarray(combine_mass(masses)['center_mm'])
    b = info['board']
    half_x = b['wheelbase_mm'] / 2
    half_y = abs(b['wheel_centers'][0]['center_mm'][1])
    contacts = [[-half_x, -half_y], [half_x, -half_y], [half_x, half_y], [-half_x, half_y]]
    edges = signed_margins(contacts, c[:2])
    # Supplied CCW rectangle edges: bottom, right, top, left.
    margins = [float(min(edges[1], edges[3])), float(min(edges[0], edges[2]))]
    if min(margins) <= 0:
        raise ValueError('Solid-volume centroid must lie strictly inside contact rectangle')
    r = {'method': 'Actual final STL signed-tetrahedron solid volume centroid, all printed parts homogeneous solid. Not the mass centroid of an infilled physical print; metal axles and fasteners excluded. Contact-centre rectangle is conservative vs wheel width.', 'parts': rows, 'combined_solid_volume_centroid_mm': c.tolist(), 'conservative_contact_centres_xy_mm': contacts, 'projection_margin_to_rectangle_mm': margins, 'static_projection_inside': True, 'physical_tipping_load_and_rolling_resistance': 'unverified'}
    (d / 'support-centroid-check.json').write_text(json.dumps(r, indent=2))
    print(c, margins)

def main(argv=None):
    return directory_stage(execute, cli_arguments, argv)
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
