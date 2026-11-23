"""Export the editable lowpoly and inspect its self-contained glTF contract."""
import json
from pathlib import Path
import sys
from glb_clips import read_glb


def inspect_glb(path, expected_names):
    data, _ = read_glb(Path(path).read_bytes())
    if any('uri' in x for x in data.get('buffers', []) + data.get('images', [])):
        raise ValueError('Delivery must embed its buffers and textures')
    head_index = next(i for i, mesh in enumerate(data['meshes']) if mesh.get('name', '').startswith('Lowpoly_Head'))
    head = data['meshes'][head_index]
    names = head.get('extras', {}).get('targetNames', [])
    if names != expected_names:
        raise ValueError('GLB morph names/order differ from lowpoly data')
    for primitive in head['primitives']:
        if not {'POSITION', 'NORMAL', 'TEXCOORD_0', 'JOINTS_0', 'WEIGHTS_0'}.issubset(primitive['attributes']):
            raise ValueError('GLB head is missing geometry, UV or skin attributes')
        if len(primitive.get('targets', [])) != len(expected_names):
            raise ValueError('GLB morph target count mismatch')
        mat = data['materials'][primitive['material']]
        if 'baseColorTexture' not in mat.get('pbrMetallicRoughness', {}) or 'normalTexture' not in mat:
            raise ValueError('GLB head is missing albedo or normal texture')
    node = next(n for n in data['nodes'] if n.get('mesh') == head_index)
    if 'skin' not in node:
        raise ValueError('GLB head is not attached to its skin')
    return {'morph_names': names, 'head_primitive_count': len(head['primitives']),
            'joints': len(data['skins'][node['skin']]['joints']),
            'mesh_names': [m.get('name') for m in data['meshes']],
            'embedded_images': len(data.get('images', [])), 'passed': True}


def deliver(config):
    import bpy
    import numpy as np
    root = Path(config['output'])
    bpy.ops.wm.open_mainfile(filepath=str(root / 'Lowpoly_Baked.blend'), load_ui=False)
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in scene.objects:
        visible = obj.name.startswith('Lowpoly_')
        if obj.type == 'MESH':
            obj.hide_render = not visible
        obj.hide_set(not visible and obj.type in ['MESH', 'ARMATURE'])
        obj.select_set(visible)
    bpy.context.view_layer.objects.active = bpy.data.objects['Lowpoly_Head']
    scene['workflow'] = 'High GLB to source-derived quad lowpoly, albedo, tangent normal, basic rig and blendshapes.'
    bpy.ops.wm.save_as_mainfile(filepath=str(root / 'Heads_Rigged.blend'), compress=True)
    bpy.ops.export_scene.gltf(filepath=str(root / 'Lowpoly_Rigged.glb'), export_format='GLB',
        use_selection=True, export_skins=True, export_morph=True, export_animations=True,
        export_normals=True, export_texcoords=True, export_tangents=True)
    names = np.load(root / 'lowpoly_data.npz')['expression_names'].tolist()
    report = inspect_glb(root / 'Lowpoly_Rigged.glb', names)
    report['files'] = ['Lowpoly_Rigged.glb', 'Heads_Rigged.blend', 'lowpoly_data.npz',
                       'textures/Lowpoly_BaseColor.png', 'textures/Lowpoly_Normal.png']
    report['albedo_file'] = 'textures/Lowpoly_BaseColor.png'
    report['normal_file'] = 'textures/Lowpoly_Normal.png'
    report['lowpoly'] = json.loads((root / 'lowpoly_report.json').read_text())
    report['hair'] = json.loads((root / 'hair_report.json').read_text())
    (root / 'delivery.json').write_text(json.dumps(report, indent=2))
    print('DELIVERY_READY', report, flush=True)


if __name__ == '__main__':
    deliver(json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text()))
