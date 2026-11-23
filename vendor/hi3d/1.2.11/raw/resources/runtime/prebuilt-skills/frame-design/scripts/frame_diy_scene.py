"""Explicit native-scene adapter for this circular bayonet recipe."""
from frame_recipe import validate_recipe
import json
from pathlib import Path
import bpy



def load_flat_parts(source):
    """Open a recipe flat scene, require all roles and reset to manufacturing state.

    Mutates the active Blender scene, not the source file. Rejects display-space
    transforms and missing/duplicate roles instead of silently skipping parts.
    """
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    metadata = json.loads(source.with_name('measurements.json').read_text())
    config = validate_recipe(metadata['configuration'])
    bpy.ops.wm.open_mainfile(filepath=str(source))
    parts = {}
    for role in ('frame', 'backing', 'locking_ring', 'stand'):
        found = [o for o in bpy.data.objects if o.get('assembly_role') == role]
        if len(found) != 1 or found[0].type != 'MESH':
            raise ValueError(f'Exactly one mesh for role {role} required')
        obj = found[0]
        if max(abs(obj.matrix_world[i][j] - (1 if i == j else 0)) for i in range(4) for j in range(4)) > 1e-7:
            raise ValueError('Use flat-assembly.blend, not the transformed display scene')
        if role in ('locking_ring', 'stand'):
            if not obj.data.shape_keys or len(obj.data.shape_keys.key_blocks) != 2:
                raise ValueError(f'{role} requires basis plus one release shape')
            for key in obj.data.shape_keys.key_blocks:
                key.value = 0
        parts[role] = obj
    bpy.context.view_layer.update()
    return parts, config
