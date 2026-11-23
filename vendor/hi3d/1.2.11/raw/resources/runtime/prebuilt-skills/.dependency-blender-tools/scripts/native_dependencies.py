"""native dependencies local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, sys, json, hashlib
from pathlib import Path
from stage_cli import cli_arguments, StageFinished, _finish_stage

from cli_schemas import directory_stage

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    root = Path(arguments)
    rows = []
    for path in sorted(root.glob('*/*.blend')):
        bpy.ops.wm.open_mainfile(filepath=str(path))
        used = []
        for mat in bpy.data.materials:
            if mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        im = node.image
                        used.append({'material': mat.name, 'image': im.name, 'source': im.source, 'packed': bool(im.packed_file), 'size': list(im.size), 'external_required': im.source == 'FILE' and (not bool(im.packed_file))})
        assert not any((x['external_required'] for x in used)), (path, used)
        rows.append({'file': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'used_images': used, 'all_image_dependencies_self_contained': True})
    (root / 'native-image-dependencies.json').write_text(json.dumps(rows, indent=2))
    print('SELF CONTAINED', len(rows))

def main(argv=None):
    return directory_stage(execute, cli_arguments, argv)
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
