"""Fresh-import checks. Importing the module does not load or write any asset."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse, json
from types import SimpleNamespace
import bpy
from brush_runtime import cli_arguments, validate_paths
from asset_scene import open_asset
from scene_measure import object_bounds, measure_objects
from checkpoints import digest

def object_bounds_mm(obj):
    """Return world-space min/max in millimetres for a nonempty mesh object."""
    return object_bounds(obj, unit_mm=1000, precision='float64')

def inspect_asset(path):
    """Replace active scene with one .blend/.glb and return actual import metrics."""
    file=Path(path).resolve()
    loaded=open_asset(file)
    metrics=measure_objects(loaded,unit_mm=1000,empty='skip',
                            topology_objects=[o for o in loaded if file.suffix=='.blend' and o.get('printable')])
    objects=[{'object':row['name'],**{k:v for k,v in row.items() if k not in {'name','triangles'}}}
             for row in metrics['objects']]
    if not objects:raise ValueError('Empty export: '+str(file))
    return {'file':file.name,'sha256':digest(file),'bytes':file.stat().st_size,'dimensions_mm':metrics['dimensions_mm'],'objects':objects,'animation_actions':[x.name for x in bpy.data.actions]}

def validate_assets(*, input, output):
    """Inspect one file, or a directory's native scene and GLBs; write a report."""
    a=SimpleNamespace(input=input,output=output);validate_paths(a)
    files=[a.input] if a.input.is_file() else ([a.input/'scene.blend'] if (a.input/'scene.blend').is_file() else [])+sorted(a.input.glob('*.glb'))
    if not files:raise ValueError('No native scene or GLB inputs')
    report=[inspect_asset(p) for p in files];a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2));return report

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    report=validate_assets(**vars(p.parse_args(cli_arguments(argv))));print('FRESH IMPORTED',len(report))
if __name__=='__main__':main()
