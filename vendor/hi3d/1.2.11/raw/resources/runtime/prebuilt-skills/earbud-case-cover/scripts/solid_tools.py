"""Adapted provenance-based Boolean export from high-poly-print-splitting. All geometry units mm."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

from pathlib import Path
import numpy as np,json,sys
import manifold3d as M
from blender_stl import stl_bytes
class Source:
 def __init__(self,path):
  d=np.load(path);self.v=d['vertices'];self.f=d['faces'].astype(np.uint32);self.uv=d['uv'];self.mi=d['material_index'];self.sid=M.Manifold.reserve_ids(1)
  self.solid=M.Manifold(M.Mesh(np.ascontiguousarray(self.v,np.float32),np.ascontiguousarray(self.f),run_index=np.array([0,self.f.size],np.uint32),run_original_id=np.array([self.sid],np.uint32),face_id=np.arange(len(self.f),dtype=np.uint32)))
  assert self.solid.status()==M.Error.NoError,str(self.solid.status())
 def write(self,solid,path,translation=(0,0,0)):
  me=solid.to_mesh();v=np.asarray(me.vert_properties[:,:3]);f=np.asarray(me.tri_verts);ids=np.array(me.face_id,np.int64);sel=np.zeros(len(f),bool)
  for k,rid in enumerate(me.run_original_id):
   if rid==self.sid:sel[me.run_index[k]//3:me.run_index[k+1]//3]=True
  uv=np.zeros((len(f),3,2),np.float32);mats=np.full(len(f),-1,np.int32);idx=np.flatnonzero(sel)
  for start in range(0,len(idx),100000):
   ii=idx[start:start+100000];orig=ids[ii];a=self.v[self.f[orig,0]].astype(float);e1=self.v[self.f[orig,1]]-a;e2=self.v[self.f[orig,2]]-a;p=v[f[ii]].astype(float)-np.asarray(translation)[None,None,:]-a[:,None,:];d00=np.einsum('ij,ij->i',e1,e1);d01=np.einsum('ij,ij->i',e1,e2);d11=np.einsum('ij,ij->i',e2,e2);d20=np.einsum('ikj,ij->ik',p,e1);d21=np.einsum('ikj,ij->ik',p,e2);den=d00*d11-d01*d01;b=(d11[:,None]*d20-d01[:,None]*d21)/den[:,None];c=(d00[:,None]*d21-d01[:,None]*d20)/den[:,None];uv[ii]=(1-b-c)[:,:,None]*self.uv[orig,0,None,:]+b[:,:,None]*self.uv[orig,1,None,:]+c[:,:,None]*self.uv[orig,2,None,:];mats[ii]=self.mi[orig]
  np.savez(path,vertices=v,faces=f,uv=uv,material_index=mats)
  return {'triangles':len(f),'retained_source_surface_triangles':int(sel.sum()),'volume_mm3':solid.volume(),'bounds_mm':solid.bounding_box(),'components':len(solid.decompose())}
def write_solid(solid,path):
 m=solid.to_mesh();np.savez(path,vertices=m.vert_properties[:,:3],faces=m.tri_verts)
def cube(size,center):return M.Manifold.cube(size,True).translate(center)
def cylinder(r,h,center,axis='Z',n=80):
 o=M.Manifold.cylinder(h,r,r,n,True)
 if axis=='X':o=o.rotate((0,90,0))
 if axis=='Y':o=o.rotate((90,0,0))
 return o.translate(center)
def stl(solid,path):
 m=solid.to_mesh();tri=np.asarray(m.vert_properties[:,:3])[m.tri_verts]
 Path(path).write_bytes(stl_bytes(tri,header=b'Hi3D surface and Astra joints; millimeters',padding=b'\0',precision='float32',normal_floor=1e-25))
