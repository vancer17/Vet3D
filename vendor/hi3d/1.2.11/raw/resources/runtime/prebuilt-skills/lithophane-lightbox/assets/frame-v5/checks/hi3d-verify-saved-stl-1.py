"""Python + numpy: inspect saved binary STLs, not just source meshes."""
from pathlib import Path
import argparse,json,struct
import numpy as np


def inspect(path):
    raw=path.read_bytes();n=struct.unpack_from('<I',raw,80)[0]
    if len(raw)!=84+50*n:raise ValueError('Invalid binary STL length: '+str(path))
    dt=np.dtype([('n','<f4',(3,)),('v','<f4',(3,3)),('a','<u2')])
    tri=np.frombuffer(raw,dtype=dt,offset=84)['v'].astype(float)
    xyz,iv=np.unique(np.round(tri.reshape(-1,3),5),axis=0,return_inverse=True);f=iv.reshape(-1,3)
    edges=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]])
    undirected,idx,counts=np.unique(np.sort(edges,axis=1),axis=0,return_inverse=True,return_counts=True)
    balance=np.bincount(idx,weights=np.where(edges[:,0]<edges[:,1],1,-1))
    areas=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    volume=float(np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])).sum()/6)
    parent=np.arange(len(xyz))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]];x=parent[x]
        return x
    for a,b in undirected:parent[find(a)]=find(b)
    components=len({find(i) for i in range(len(xyz))})
    row=dict(file=path.name,triangles=n,closed_edges=bool(np.all(counts==2)),
        consistent_winding=bool(np.all(balance==0)),zero_area_triangles=int(np.count_nonzero(areas<1e-10)),
        connected_components=components,volume_mm3=volume,extents_mm=np.ptp(xyz,axis=0).tolist())
    row['pass']=row['closed_edges'] and row['consistent_winding'] and row['zero_area_triangles']==0 and components==1 and volume>0
    return row


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dir',type=Path,required=True)
    p.add_argument('--extra',type=Path,nargs='*',default=[]);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();paths=sorted(a.dir.glob('*.stl'))+a.extra
    rows=[inspect(path) for path in paths]
    report={'pass':bool(rows) and all(r['pass'] for r in rows),'units':'mm','vertex_quantization_mm':1e-5,
            'checks':rows,'scope':'saved topology and signed volume; not a general self-intersection proof'}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'pass':report['pass'],'files':len(rows)}))
    if not report['pass']:raise SystemExit(1)
