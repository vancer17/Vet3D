"""Conservative multi-axis printable envelope; no fixed sculpture or service coordinates."""
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .product_core import active, mesh

def visibility_hull(source,work,pitch,max_cells=20000000):
 """Create a local-coordinate three-axis silhouette intersection; writes occupancy to explicit work."""
 if not 0 < pitch <= .01:raise ValueError('pitch must be in metres, (0,.01]')
 W=Path(work);W.mkdir(exist_ok=True,parents=True)
 bm=bmesh.new();bm.from_mesh(source.data);tree=BVHTree.FromBMesh(bm);v=np.array([q.co for q in source.data.vertices]);lo=v.min(0)-.0015;hi=v.max(0)+.0015;axes=[np.arange(lo[i],hi[i],pitch) for i in range(3)];shape=tuple(map(len,axes));
 if np.prod(shape)>max_cells: bm.free();raise ValueError('Visibility hull grid exceeds max_cells')
 mask=np.ones(shape,bool)
 for ax in range(3):
  other=[i for i in range(3) if i!=ax];A=np.full((len(axes[other[0]]),len(axes[other[1]])),np.nan);B=A.copy()
  for j,a in enumerate(axes[other[0]]):
   for k,b in enumerate(axes[other[1]]):
    p=np.zeros(3);p[ax]=lo[ax]-.001;p[other[0]]=a;p[other[1]]=b;dire=np.zeros(3);dire[ax]=1;front=tree.ray_cast(Vector(p),Vector(dire),1)[0];p[ax]=hi[ax]+.001;back=tree.ray_cast(Vector(p),Vector(-dire),1)[0]
    if front is not None and back is not None:A[j,k]=front[ax];B[j,k]=back[ax]
  shape=[1,1,1];shape[ax]=len(axes[ax]);grid=axes[ax].reshape(shape);A=np.expand_dims(A,ax);B=np.expand_dims(B,ax);mask &= (grid>A)&(grid<B);print('AXIS',ax,'filled',mask.sum(),flush=True)
 # Six-neighbor close/open removes features near the two-cell scale.
 def morph(a,op):
  out=a.copy()
  for ax in range(3):
   for sh in [-1,1]:out=(out|np.roll(a,sh,ax)) if op=='dilate' else (out&np.roll(a,sh,ax))
  for ax in range(3):
   sl=[slice(None)]*3;sl[ax]=0;out[tuple(sl)]=False;sl[ax]=-1;out[tuple(sl)]=False
  return out
 bm.free();mask=morph(morph(mask,'dilate'),'erode');mask=morph(morph(mask,'erode'),'dilate');np.savez_compressed(W/'visual-hull-occupancy.npz',mask=mask,origin=lo,pitch=pitch)
 verts=[];faces=[]
 for ax in range(3):
  for side in [-1,1]:
   exposed=mask & ~np.roll(mask,-side,ax);ids=np.argwhere(exposed);other=[i for i in range(3) if i!=ax];base=ids.copy();base[:,ax]+=1 if side==1 else 0
   corners=[]
   for a,b in [(0,0),(1,0),(1,1),(0,1)]:
    q=base.copy();q[:,other[0]]+=a;q[:,other[1]]+=b;corners.append(q)
   q=np.stack(corners,1);verts.append(q.reshape(-1,3));start=sum(len(x) for x in verts[:-1]);faces.append(np.arange(start,start+len(q)*4).reshape(-1,4))
 v=np.concatenate(verts);f=np.concatenate(faces);v,inv=np.unique(v,axis=0,return_inverse=True);f=inv[f];o=mesh('FDM visual hull | all-three-axis constrained',lo+v*pitch,f,source.data.materials[0]);o.matrix_world=source.matrix_world.copy();b=bmesh.new();b.from_mesh(o.data);bmesh.ops.recalc_face_normals(b,faces=list(b.faces));b.to_mesh(o.data);b.free();active(o);q=o.modifiers.new('Closed hull smoothing remesh','REMESH');q.mode='VOXEL';q.voxel_size=pitch*.75;q.use_smooth_shade=True;bpy.ops.object.modifier_apply(modifier=q.name);q=o.modifiers.new('Voxel grid relaxation','SMOOTH');q.factor=.35;q.iterations=3;bpy.ops.object.modifier_apply(modifier=q.name)
 return o, {"pitch_mm":pitch*1000,"grid_shape":list(mask.shape),"limitation":"Three-axis visual hull removes concavities/thin detail. Recut precision interfaces afterwards and recheck topology and exterior."}
