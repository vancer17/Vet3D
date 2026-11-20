"""Read a display assembly with explicit density/contact roles in isolated Blender."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from scene_io import import_objects
from mesh_snapshot import mesh_snapshot
from support_core import mass_properties, assess_support


def check(source, config, output):
    source, config, output = [Path(p).expanduser().resolve() for p in (source, config, output)]
    if output in (source, config) or output.is_relative_to(Path(__file__).resolve().parent.parent):
        raise ValueError("Report must be separate and outside the package")
    if output.exists():
        raise FileExistsError(output)
    data = json.loads(config.read_text())
    unit = float(data['unit_mm']); ground = float(data['ground_z_mm']); tolerance = float(data['contact_tolerance_mm'])
    if not np.isfinite([unit, ground, tolerance]).all() or unit <= 0 or tolerance < 0:
        raise ValueError("Invalid unit, ground or contact tolerance")
    if source.suffix.lower() not in ('.glb', '.blend'):
        raise ValueError("Expected GLB or BLEND")
    roles = data['parts']; contact_names = data['contact_objects']
    names = [part['object'] for part in roles]
    if not names or len(set(names)) != len(names) or not contact_names or len(set(contact_names)) != len(contact_names):
        raise ValueError("Nonempty unique mass and contact roles required")
    if not set(contact_names) <= set(names):
        raise ValueError("Contacts must belong to the mass assembly")
    objects = {obj.name: obj for obj in import_objects(source, reset=True)}
    snapshots = {}
    for name in names:
        if name not in objects or objects[name].type != 'MESH':
            raise ValueError('Missing mesh role: ' + name)
        snapshots[name] = mesh_snapshot(objects[name], evaluated=True, space='world', scale=unit)
    properties = [dict(object=part['object'], density_g_cm3=part['density_g_cm3'],
                       **mass_properties(snapshots[part['object']]['vertices'], snapshots[part['object']]['triangles'],
                                         density_g_cm3=part['density_g_cm3'])) for part in roles]
    contacts = []
    for name in contact_names:
        vertices = snapshots[name]['vertices']
        if vertices[:, 2].min() < ground - tolerance:
            raise ValueError('Contact mesh penetrates the stated ground: ' + name)
        contacts.extend(vertices[np.abs(vertices[:, 2]-ground) <= tolerance].tolist())
    result = assess_support(properties, contacts, gravity=(0, 0, -1))
    result.update(parts=properties, contact_count=len(contacts), assumptions=data,
                  method='Evaluated world meshes; solid-equivalent density, horizontal ground, vertical gravity. Static geometry only; infill, friction, fixing and push loads not tested.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('source', 'config', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    result = check(**vars(args)); print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['center_inside_support_polygon'] else 1)
