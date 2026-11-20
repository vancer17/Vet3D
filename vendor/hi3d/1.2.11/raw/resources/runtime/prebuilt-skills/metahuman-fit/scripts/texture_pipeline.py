"""Offline planning for supported UV and desktop Hi3D texturing tools."""
import argparse
import json
from pathlib import Path


def run(config):
    part = config['part']
    if part not in {'bald', 'hair'}:
        raise ValueError('part must be bald or hair')
    if part == 'hair' and config.get('occluded_hair_completed') is not True:
        raise ValueError('Review the completed hair behind the head first')
    refs = config['color_views']
    if 'front' not in refs or set(refs) - {'front', 'back', 'left', 'right'}:
        raise ValueError('Provide actual named views including front')
    mesh = Path(config['high_glb']).resolve()
    for path in [mesh, *(Path(p).resolve() for p in refs.values())]:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing or empty input artifact')
    size = config.get('texture_size', 4096)
    if type(size) is not int or size < 1:
        raise ValueError('texture_size must be a positive integer')
    output = Path(config['output']).resolve()
    needs_uv = not config.get('has_uv', False)
    uv = {'tool': 'mdf_api', 'arguments': {
        'action': 'invoke', 'capability': 'unwrap-uv', 'file': str(mesh),
        'params': {'texture_size': size, 'need_repair': False},
        'jobPath': str(output / '.hi3d/uv.json'), 'outputDir': str(output / 'uv'), 'dryRun': True}}
    texture = {'tool': 'hi3d_api', 'arguments': {
        'action': 'generate_3d', 'kind': 'model', 'mesh': None if needs_uv else str(mesh),
        'images': [str(Path(refs['front']).resolve())], 'settings': {'request_type': 2},
        'jobPath': str(output / '.hi3d/texture.json'), 'outputDir': str(output / 'texture'), 'dryRun': True}}
    return {'status': 'plan_only', 'uv': uv if needs_uv else None, 'texture': texture,
            'meshFrom': 'uv.files.uv_mesh_glb' if needs_uv else None,
            'reviewViews': refs, 'geometry_preservation_verified': False,
            'instructions': 'Read the named skills. Dry-run then invoke each formal call; waiting_choice is the host global popup. If UV is needed, dry-run then invoke it, and fill texture.mesh from the actual returned file. Dry-run then invoke texturing. This is not four-view projection; verify geometry, scale, UV and material before downstream use.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    print(json.dumps(run(json.loads(parser.parse_args().config.read_text(encoding='utf-8'))), indent=2))
