#!/usr/bin/env python3
"""Validate actual binary STL solids; no geometry edits or implicit scale changes."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import argparse,json,struct
from pathlib import Path
import numpy as np
if __package__:
    from .triangle_arrays import triangle_double_areas, edge_incidence
else:
    from triangle_arrays import triangle_double_areas, edge_incidence
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import manifold3d as M
RECORD=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attribute','<u2')])

def inspect_binary_stl(path,near_area=1e-8):
    path=Path(path)
    with path.open('rb') as f:
        header=f.read(84)
        if len(header)!=84: raise ValueError('Truncated STL header')
        count=struct.unpack('<I',header[80:84])[0]
        if count==0 or path.stat().st_size!=84+50*count:
            raise ValueError('Expected nonempty binary STL with matching record count; convert ASCII STL first')
        records=np.fromfile(f,dtype=RECORD,count=count)
    corners=records['vertices'].reshape(-1,3)
    if not np.isfinite(corners).all(): raise ValueError('Non-finite coordinates')
    verts,inv=np.unique(corners,axis=0,return_inverse=True);faces=inv.reshape(-1,3)
    unique,counts,_=edge_incidence(faces,discard_collapsed=False)
    # Every topological edge must occur once in each direction.
    directed=np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]])
    _,repeated=np.unique(directed,axis=0,return_counts=True)
    bad_winding=int(np.sum(repeated>1))
    v=verts.astype(np.float64)
    areas=triangle_double_areas(v,faces)*.5
    graph=coo_matrix((np.ones(len(unique),np.int8),(unique[:,0],unique[:,1])),shape=(len(v),len(v))).tocsr()
    components=int(connected_components(graph,directed=False,return_labels=False))
    solid=M.Manifold(M.Mesh(np.array(verts,np.float32,order='C'),np.array(faces,np.uint32,order='C')))
    status=solid.status();volume=solid.volume()
    r={'file':str(path.resolve()),'units':'STL units; millimetres only if exported as mm','vertices_welded':len(v),'triangles':count,'boundary_edges':int(np.sum(counts==1)),'nonmanifold_edges':int(np.sum(counts!=2)),'inconsistent_directed_edges':bad_winding,'zero_area_faces':int(np.sum(areas==0)),'near_zero_nonzero_faces':int(np.sum((areas>0)&(areas<near_area))),'near_area_threshold_units2':near_area,'minimum_area_units2':float(areas.min()),'connected_components':components,'bounds':[v.min(axis=0).tolist(),v.max(axis=0).tolist()],'volume_units3':volume,'manifold_status':str(status)}
    r['passed']=bool(r['nonmanifold_edges']==0 and bad_winding==0 and r['zero_area_faces']==0 and components==1 and status==M.Error.NoError and volume>0)
    return r

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('inputs',nargs='+',type=Path);p.add_argument('--json',required=True,type=Path);a=p.parse_args()
    paths=[]
    for x in a.inputs: paths.extend(sorted(x.glob('*.stl')) if x.is_dir() else [x])
    if not paths:p.error('No STL files found')
    results=[]
    for path in paths:
        try:r=inspect_binary_stl(path)
        except Exception as e:r={'file':str(path),'passed':False,'error':str(e)}
        results.append(r);print(path.name,'PASS' if r['passed'] else 'FAIL',flush=True)
    a.json.parent.mkdir(parents=True,exist_ok=True);a.json.write_text(json.dumps(results,ensure_ascii=False,indent=2))
    return 0 if all(r['passed'] for r in results) else 1
if __name__=='__main__':raise SystemExit(main())
