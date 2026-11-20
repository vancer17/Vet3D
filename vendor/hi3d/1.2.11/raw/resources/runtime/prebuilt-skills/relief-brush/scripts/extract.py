"""Explicit GLB ray sampling, pure repair pipeline, and linear height asset output."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse, hashlib, json
import bpy
import numpy as np
from mathutils import Vector
from height_sampling import sample_mesh
from types import SimpleNamespace
from brush_runtime import cli_arguments, validate_paths
from field_ops import prepare_regions

def sample_scene(*, resolution, axes, front_sign, ray_margin=.1):
    """Sample current scene world-space meshes. Does not import or delete objects."""
    n,m=map(int,resolution); wa,ha,da=axes
    if set(axes)!={0,1,2} or front_sign not in (-1,1) or min(n,m)<8 or ray_margin<=0:
        raise ValueError('Invalid sampling axes, sign, resolution or margin')
    verts=[]; faces=[]
    deps=bpy.context.evaluated_depsgraph_get()
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH': continue
        eo=obj.evaluated_get(deps); mesh=eo.to_mesh(); off=len(verts)
        verts.extend([eo.matrix_world @ v.co for v in mesh.vertices]); faces.extend([[i+off for i in p.vertices] for p in mesh.polygons]); eo.to_mesh_clear()
    if not verts or not faces: raise ValueError('Source scene has no mesh surface')
    raw, valid, bounds = sample_mesh(verts, faces, resolution=(n,m), axes=axes,
                                      front_sign=front_sign, ray_margin=ray_margin)
    return raw,{'source_vertices':len(verts),'source_polygons':len(faces),'source_bounds':{'min':bounds[0].tolist(),'max':bounds[1].tolist()}}

def write_height_assets(*, output, processed, metadata):
    """Write explicit arrays/reports and Raw linear 16-bit PNG in current Blender."""
    out=Path(output);validate_paths(SimpleNamespace(output=out));out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'heightfields.npz',**processed['fields']);np.savez_compressed(out/'heightfields-before.npz',**processed['before'])
    for name,mask in processed['masks'].items():np.save(out/f'{name}-repair-mask.npy',mask)
    s=bpy.context.scene;s.view_settings.view_transform='Raw';s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='BW'
    for name,a in processed['fields'].items():
        img=bpy.data.images.new(name,width=a.shape[1],height=a.shape[0],alpha=True,float_buffer=True);img.colorspace_settings.name='Non-Color'
        rgba=np.ones((*a.shape,4),np.float32);rgba[:,:,:3]=a[:,:,None];img.pixels.foreach_set(rgba.ravel())
        s.render.image_settings.color_depth='16';img.save_render(str(out/f'{name}.png'),scene=s)
        s.render.image_settings.color_depth='8';img.save_render(str(out/f'{name}-preview.png'),scene=s);bpy.data.images.remove(img)
    (out/'pit-repair.json').write_text(json.dumps(processed['repair'],indent=2))
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2))
    return {'heightfields':str(out/'heightfields.npz'),'metadata':str(out/'metadata.json')}

def extract(*, source, output, config):
    """Import GLB (replaces scene), sample/process and write assets. No online call."""
    a=SimpleNamespace(source=source,output=output,config=config);validate_paths(a)
    if a.source.suffix.lower() not in ('.glb', '.gltf'):
        raise ValueError('extract accepts GLB/glTF directly; convert STL with explicit units using prepare_stl.py first')
    c=json.loads(a.config.read_text())
    for key in ('resolution','axes','front_sign','regions'):
        if key not in c:raise ValueError(f'Missing explicit extraction config: {key}')
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(a.source))
    raw,measure=sample_scene(resolution=c['resolution'],axes=c['axes'],front_sign=c['front_sign'],ray_margin=float(c.get('ray_margin',.1)))
    p=prepare_regions(raw,c)
    meta={**measure,'source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'blender':bpy.app.version_string,'sample_grid':c['resolution'],'axes':c['axes'],'front_sign':c['front_sign'],'baseline_source_units':p['baseline'],'valid_ray_fraction':p['valid_ray_fraction'],'regions_normalized':c['regions'],'region_specs':p['region_specs'],'repair':p['repair'],'config':c,'output':'16-bit linear grayscale PNG; black zero / white chosen physical displacement; source rays use source units','array_row_origin':'minimum sampling height axis; Blender PNG top row corresponds to the last array row','undercuts':'not retained by first-hit projection'}
    result=write_height_assets(output=a.output,processed=p,metadata=meta);np.save(a.output/'source_depth.npy',raw)
    return result

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--config',required=True)
    print(json.dumps(extract(**vars(p.parse_args(cli_arguments(argv)))),indent=2))
if __name__=='__main__':main()
