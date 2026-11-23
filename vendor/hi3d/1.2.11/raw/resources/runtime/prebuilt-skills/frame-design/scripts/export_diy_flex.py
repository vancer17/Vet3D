"""Export actual preset release shapes separately from manufacturing STL."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from frame_print import export_stl
from frame_runtime import cli_arguments
from frame_diy_runtime import prepare_paths, require_distinct_outputs
from frame_diy_scene import load_flat_parts


def export_pressed(*, source, output):
    paths, inputs = prepare_paths(output=output, derived_inputs={'source':source})
    out = paths['output']
    files = [out/(role+'-pressed-mm.stl') for role in ('locking_ring','stand')]
    require_distinct_outputs(inputs.values(), files)
    parts, _ = load_flat_parts(inputs['source'])
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for role, path in zip(('locking_ring','stand'), files):
        obj = parts[role]
        key = obj.data.shape_keys.key_blocks[1]
        try:
            key.value = 1
            bpy.context.view_layer.update()
            records.append({'role':role, 'file':str(path), **export_stl(path,[obj])})
        finally:
            key.value = 0
            bpy.context.view_layer.update()
    return records


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--output',required=True)
    export_pressed(**vars(parser.parse_args(cli_arguments(argv))))


if __name__ == '__main__':
    main()
