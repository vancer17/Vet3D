"""fresh review local stage adapter."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import bpy, json
from pathlib import Path
from stage_cli import cli_arguments, StageFinished, _finish_stage
from asset_scene import open_asset
from scene_measure import measure_objects
from checkpoints import digest

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    A = arguments
    cid = A[0]
    root = Path(A[1])
    rows = []
    for file in sorted(root.glob('*/*.glb')):
        loaded = open_asset(file, frame=0)
        metrics = measure_objects(loaded, unit_mm=1000, precision='float32', empty='keep')
        lo, hi = metrics['bounds_mm']
        rows.append({'file': str(file.relative_to(root)), 'sha256': digest(file),
                     'dimensions_mm': [hi[i] - lo[i] for i in range(3)], 'bounds_mm': metrics['bounds_mm'],
                     'objects': [{'name': row['name'], 'triangles': row['triangles']} for row in metrics['objects']],
                     'actions': [a.name for a in bpy.data.actions]})
    (root / 'fresh-import.json').write_text(json.dumps(rows, indent=2))
    print('IMPORTED', len(rows), flush=True)

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
