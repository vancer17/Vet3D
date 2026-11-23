"""Millimetre planar/loft primitives; mutates the explicit Blender scene."""
import bpy, bmesh, numpy as np, math, json, struct, os
from pathlib import Path
from mathutils import Vector
if __package__:
 from .scene_io import create_mesh_object as _create_mesh_object
else:
 from scene_io import create_mesh_object as _create_mesh_object
MM = .001


if __package__:
 from .material_nodes import principled_material as _principled
else:
 from material_nodes import principled_material as _principled

def material(name,color,metal=0,rough=.36):
 return _principled(name,color,metallic=metal,roughness=rough)

def mesh(name,v,f,mat=None):
 return _create_mesh_object(name,(np.asarray(v)*MM).tolist(),f,collection=bpy.context.collection,material=mat,recalculate_normals=True,smooth=True)

def bevel(o,width=.4,segments=3):
 m=o.modifiers.new('Soft manufactured edges','BEVEL');m.width=width*MM;m.segments=segments
 return o

def bore(o,xy,r,z0,z1):
 bpy.ops.mesh.primitive_cylinder_add(vertices=40,radius=r*MM,depth=(z1-z0)*MM,location=(xy[0]*MM,xy[1]*MM,(z0+z1)*.5*MM));c=bpy.context.object;c.name='Temporary bore tool';bpy.context.view_layer.objects.active=o;m=o.modifiers.new('Actual circular bore','BOOLEAN');m.operation='DIFFERENCE';m.object=c;bpy.ops.object.modifier_apply(modifier=m.name);bpy.data.objects.remove(c,do_unlink=True)

def repair_boolean_flaps(o):
 m=o.data;m.calc_loop_triangles();v=np.array([p.co[:] for p in m.vertices]);f=np.array([list(t.vertices) for t in m.loop_triangles]);_,first,inv=np.unique(np.round(v,9),axis=0,return_index=True,return_inverse=True);v=v[first];f=inv[f];keys=np.sort(f,1);_,group,count=np.unique(keys,axis=0,return_inverse=True,return_counts=True);keep=np.ones(len(f),bool);removed=0
 for g in np.flatnonzero(count>1):
  rows=np.flatnonzero(group==g)
  if len(rows)!=2:raise ValueError('Ambiguous duplicated boolean triangles')
  p=v[f[rows]];n=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);cos=np.dot(n[0],n[1])/(np.linalg.norm(n[0])*np.linalg.norm(n[1]))
  if cos>-.999:raise ValueError('Duplicate faces are not an opposite zero-volume flap')
  keep[rows]=False;removed+=2
 if removed:
  f=f[keep];used,remap=np.unique(f,return_inverse=True);new=bpy.data.meshes.new(m.name+' cleaned');new.from_pydata(v[used].tolist(),[],remap.reshape(-1,3).tolist());new.update()
  for mat in m.materials:new.materials.append(mat)
  for p in new.polygons:p.use_smooth=True
  o.data=new;o['removed_opposite_boolean_flap_faces']=removed
 return removed

def cube(name,dim,loc,mat,bev=.4):
 bpy.ops.mesh.primitive_cube_add(size=1,location=np.asarray(loc)*MM);o=bpy.context.object;o.name=name;o.dimensions=np.asarray(dim)*MM;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat)
 if bev:bevel(o,bev)
 return o

def loop(w,h,kind='rect',n=256,r=5):
 if kind!='rect':
  a=np.arange(n)*2*math.pi/n;return np.column_stack([w*.5*np.cos(a),h*.5*np.sin(a)])
 r=min(r,w/2,h/2);pts=[]
 for q in range(4):
  cx=(w/2-r)*(1 if q in [0,3] else -1);cy=(h/2-r)*(1 if q in [0,1] else -1)
  for a in np.linspace(q*math.pi/2,(q+1)*math.pi/2,n//4,endpoint=False):pts.append([cx+r*math.cos(a),cy+r*math.sin(a)])
 pts=np.array(pts);seg=np.linalg.norm(np.roll(pts,-1,axis=0)-pts,axis=1);s=np.r_[0,np.cumsum(seg)];target=np.linspace(0,s[-1],n,endpoint=False);p=np.vstack([pts,pts[0]]);return np.column_stack([np.interp(target,s,p[:,k]) for k in range(2)])

def loft(name,rings,mat,cap_start=False,cap_end=False):
 closed=np.allclose(rings[0],rings[-1]);rings=rings[:-1] if closed else rings
 n=len(rings[0]);v=np.concatenate(rings);f=[]
 for j in range(len(rings) if closed else len(rings)-1):
  nxt=(j+1)%len(rings)
  for i in range(n):k=(i+1)%n;f.append((j*n+i,j*n+k,nxt*n+k,nxt*n+i))
 if cap_start:
  ci=len(v);v=np.vstack([v,np.mean(rings[0],axis=0)])
  for i in range(n):f.append((ci,(i+1)%n,i))
 if cap_end:
  ci=len(v);v=np.vstack([v,np.mean(rings[-1],axis=0)]);off=(len(rings)-1)*n
  for i in range(n):f.append((ci,off+i,off+(i+1)%n))
 o=mesh(name,v,f,mat)
 # Planar cap fans use face normals; smoothing them creates false triangular dents.
 capfaces=n*int(cap_start)+n*int(cap_end)
 if capfaces:
  for poly in list(o.data.polygons)[-capfaces:]:poly.use_smooth=False
 return o

def ring3(xy,z):return np.column_stack([xy,np.full(len(xy),z)])

def tube(name,w,h,depth,wall,base,kind,mat):
 outer=loop(w,h,kind);inner=loop(w-2*wall,h-2*wall,kind,r=3)
 rings=[ring3(outer,0),ring3(outer,depth),ring3(inner,depth),ring3(inner,base)]
 return loft(name,rings,mat,True,True)

def plate(name,w,h,thick,z,kind,mat):
 xy=loop(w,h,kind);return loft(name,[ring3(xy,z),ring3(xy,z+thick)],mat,True,True)

def sample(a,u,v):
 u=np.clip(u,0,1)*(a.shape[1]-1);v=np.clip(v,0,1)*(a.shape[0]-1);i=u.astype(int);j=v.astype(int);x=u-i;y=v-j;i2=np.minimum(i+1,a.shape[1]-1);j2=np.minimum(j+1,a.shape[0]-1)
 return a[j,i]*(1-x)*(1-y)+a[j,i2]*x*(1-y)+a[j2,i]*(1-x)*y+a[j2,i2]*x*y

def height_mesh(name,a,w,h,depth,base,mat,nx=500,ny=160,warp=None):
 xx,yy=np.meshgrid(np.linspace(0,1,nx),np.linspace(0,1,ny));z=base+sample(a,xx,yy)*depth;x=(xx-.5)*w;y=(yy-.5)*h
 v=np.column_stack([x.ravel(),y.ravel(),z.ravel()]);idx=np.arange(nx*ny).reshape(ny,nx);f=[]
 aa=idx[:-1,:-1].ravel();bb=aa+1;dd=aa+nx;cc=dd+1;f.extend(np.column_stack([aa,bb,cc,dd]).tolist());boundary=np.concatenate([idx[0],idx[1:,-1],idx[-1,-2::-1],idx[-2:0:-1,0]])
 bot=v.copy();bot[:,2]=0;off=len(v);v=np.vstack([v,bot]);n=len(boundary)
 f.extend(np.column_stack([dd+off,cc+off,bb+off,aa+off]).tolist())
 for i,k in enumerate(boundary):j=(i+1)%n;f.append((int(k),off+int(k),off+int(boundary[j]),int(boundary[j])))
 if warp:v=warp(v)
 return mesh(name,v,f,mat)

def ring_relief(name,w,h,band,kind,a,mat,depth=1.2,n=768,radial=28,z=7):
 outer=loop(w,h,kind,n,r=8);inner=loop(w-2*band,h-2*band,kind,n,r=4);rings=[]
 for t in np.linspace(0,1,radial):
  xy=outer*(1-t)+inner*t;u=np.arange(n)/n*12;he=sample(a,u%1,np.full(n,t));edge=math.sin(math.pi*t)**2;zz=z+1.2*math.sin(math.pi*t)+depth*he*edge;rings.append(np.column_stack([xy,zz]))
 rings.extend([ring3(inner,z-.8),ring3(outer,z-.8),rings[0]])
 return loft(name,rings,mat)








def clean_solid_mesh(obj, *, tolerance_m=1e-9):
 """Remove coincident/collinear boolean artifacts at explicit metre tolerance.

 Mutates this mesh only; no voxel rebuild or global smoothing. Final float32 STL
 is still checked independently; this operation is not a validation result.
 """
 bm=bmesh.new();bm.from_mesh(obj.data)
 before=(len(bm.verts),len(bm.faces))
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=tolerance_m)
 bmesh.ops.triangulate(bm,faces=list(bm.faces))
 bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=tolerance_m)
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
 bm.to_mesh(obj.data);bm.free();obj.data.update()
 return {'tolerance_m':tolerance_m,'before_vertices_faces':list(before),'after_vertices_faces':[len(obj.data.vertices),len(obj.data.polygons)]}
