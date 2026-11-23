"""Fresh-process checks for actual native and GLB outputs."""

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
from scene_measure import object_bounds, measure_objects
from checkpoints import digest

def bounds(o):
    """Independently callable bounds operation; runtime dependencies are explicit keyword parameters. See references/code-contract.md."""
    return object_bounds(o, unit_mm=1000, precision='float64')

def execute(arguments):
    """Execute this explicit local stage. Files/processes/Blender state change only when called; failures propagate."""
    A = arguments
    d = Path(A[0])
    report = []
    for file in [*sorted(d.glob('*.blend')), *sorted(d.glob('*.glb'))]:
        loaded = open_asset(file)
        metrics = measure_objects(loaded, unit_mm=1000, empty='error',
                                  topology_objects=[o for o in loaded if file.suffix == '.blend' and o.get('printable')])
        objects = [{'object': row['name'], **{k: v for k, v in row.items() if k not in {'name', 'triangles'}}}
                   for row in metrics['objects']]
        assert objects, ('Empty export', file)
        report.append({'file': file.name, 'sha256': digest(file), 'bytes': file.stat().st_size, 'dimensions_mm': metrics['dimensions_mm'], 'objects': objects, 'animations': [a.name for a in bpy.data.actions], 'image_dependencies': [{'name': im.name, 'packed': bool(im.packed_file), 'source': im.source, 'path': im.filepath if not im.packed_file else 'packed'} for im in bpy.data.images if im.type == 'IMAGE' and im.users > 0]})
    (d / 'fresh-import.json').write_text(json.dumps(report, indent=2))
    print('FRESH IMPORTED', len(report), flush=True)

def main(argv=None):
    try:
        return execute(cli_arguments(argv))
    except StageFinished as done:
        return done
if __name__ == '__main__':
    result = main()
    if isinstance(result, StageFinished):
        raise SystemExit(result.code)
