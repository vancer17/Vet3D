"""List named nodes, materials and texture URIs from a GLB via glb-clips.read_glb."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from glb_clips import read_glb


def inventory(doc):
    materials = []
    for index, material in enumerate(doc.get('materials') or []):
        if not isinstance(material, dict):
            raise ValueError('material must be an object')
        materials.append({'index': index, 'name': material.get('name') or f'material-{index}'})
    nodes = []
    meshes = doc.get('meshes') or []
    for index, node in enumerate(doc.get('nodes') or []):
        if not isinstance(node, dict):
            raise ValueError('node must be an object')
        mesh_index = node.get('mesh')
        used = []
        if mesh_index is not None:
            if not isinstance(mesh_index, int) or mesh_index < 0 or mesh_index >= len(meshes):
                raise ValueError('node mesh index out of range')
            for primitive in meshes[mesh_index].get('primitives') or []:
                mid = primitive.get('material')
                if isinstance(mid, int) and 0 <= mid < len(materials):
                    used.append(materials[mid]['name'])
        nodes.append({
            'index': index,
            'name': node.get('name') or f'node-{index}',
            'mesh': mesh_index,
            'materials': used,
        })
    images = []
    external = []
    for index, image in enumerate(doc.get('images') or []):
        if not isinstance(image, dict):
            raise ValueError('image must be an object')
        uri = image.get('uri')
        embedded = uri is None or str(uri).startswith('data:')
        item = {'index': index, 'uri': uri, 'embedded': embedded}
        images.append(item)
        if not embedded:
            external.append(uri)
    mesh_nodes = [node for node in nodes if node['mesh'] is not None]
    return {
        'nodes': nodes,
        'materials': materials,
        'images': images,
        'externalTextures': external,
        'selectableParts': len(mesh_nodes) > 1 or len(materials) > 1,
        'meshNodeCount': len(mesh_nodes),
    }


def inspect_file(path):
    data = Path(path).read_bytes()
    doc, _chunks = read_glb(data)
    report = inventory(doc)
    report['bytes'] = len(data)
    report['source'] = Path(path).name
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect GLB parts for product-configurator')
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    report = inspect_file(args.model)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
