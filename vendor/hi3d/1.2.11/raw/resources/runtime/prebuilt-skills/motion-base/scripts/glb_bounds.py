"""Read actual GLB positions and node transforms; report default scene extents."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

from pathlib import Path
import argparse, json
from glb_clips import read_glb
import numpy as np


def inspect(path):
    doc,chunks=read_glb(path.read_bytes())
    binaries=[payload for kind,payload in chunks if kind==b'BIN\x00']
    if len(binaries)!=1:raise ValueError('Position inspection requires one embedded GLB buffer')
    binary=binaries[0];cache={}
    def positions(index):
        if index not in cache:
            a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
            if a.get('componentType')!=5126 or a.get('type')!='VEC3' or 'sparse' in a:
                raise ValueError('Positions require non-sparse float VEC3')
            if v.get('buffer')!=0 or 'uri' in doc['buffers'][0]:
                raise ValueError('Positions must use the embedded GLB buffer')
            count=a.get('count');start=v.get('byteOffset',0);local=a.get('byteOffset',0)
            length=v.get('byteLength');stride=v.get('byteStride',12);declared=doc['buffers'][0].get('byteLength')
            if (any(type(n) is not int for n in [count,start,local,length,stride,declared])
                    or count<1 or min(start,local,length,declared)<0 or stride<12 or stride%4
                    or (start+local)%4 or local+(count-1)*stride+12>length
                    or start+length>min(len(binary),declared)):
                raise ValueError('Invalid position accessor byte range')
            points=np.ndarray((count,3),dtype='<f4',buffer=binary,offset=start+local,strides=(stride,4))
            if not np.isfinite(points).all():raise ValueError('Positions must be finite')
            cache[index]=points
        return cache[index]
    lo=np.array([np.inf]*3);hi=-lo;vertices=0
    def visit(index,parent):
        nonlocal lo,hi,vertices
        node=doc['nodes'][index]
        if 'matrix' in node:m=np.array(node['matrix']).reshape(4,4,order='F')
        else:
            x,y,z,w=node.get('rotation',[0,0,0,1]);s=np.array(node.get('scale',[1,1,1]))
            r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                        [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                        [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
            m=np.eye(4);m[:3,:3]=r*s;m[:3,3]=node.get('translation',[0,0,0])
        world=parent@m
        if 'mesh' in node:
            for part in doc['meshes'][node['mesh']]['primitives']:
                xyz=positions(part['attributes']['POSITION'])@world[:3,:3].T+world[:3,3]
                lo=np.minimum(lo,xyz.min(axis=0));hi=np.maximum(hi,xyz.max(axis=0));vertices+=len(xyz)
        for child in node.get('children',[]):visit(child,world)
    scene=doc['scenes'][doc.get('scene',0)]
    for node in scene['nodes']:visit(node,np.eye(4))
    return {'scene_dimensions_xyz_m':(hi-lo).tolist(),'width_depth_height_mm':((hi-lo)[[0,2,1]]*1000).tolist(),
            'mesh_vertex_instances':vertices,'animations':[a.get('name',str(i)) for i,a in enumerate(doc.get('animations',[]))],
            'external_resources':[v['uri'] for k in ['buffers','images'] for v in doc.get(k,[]) if v.get('uri') and not v['uri'].startswith('data:')]}

if __name__=='__main__':
 import sys,hashlib
 root=Path(sys.argv[1]);rows=[]
 for p in sorted(root.glob('*/*.glb')):
  r=inspect(p);r['file']=str(p.relative_to(root));r['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();r['bytes']=p.stat().st_size;assert not r['external_resources'];assert r['bytes']<25*1024*1024;rows.append(r)
 (root/'glb-bounds-check.json').write_text(json.dumps(rows,indent=2));print('GLB files',len(rows))
