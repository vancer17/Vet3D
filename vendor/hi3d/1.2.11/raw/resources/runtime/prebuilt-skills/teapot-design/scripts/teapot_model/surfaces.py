"""Millimetre-controlled surfaces for the bounded round side-handle teapot; scene coordinates are metres."""
import math, numpy as np, bpy, bmesh
from mathutils import Vector
from .product_core import active, boolean, clean, mesh

def mesh(name,vertices,faces,material):
 data=bpy.data.meshes.new(name);data.from_pydata(vertices,[],faces);data.update();o=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(o);data.materials.append(material)
 for p in data.polygons:p.use_smooth=True
 return o

def pchip(x,y,q):
 x=np.asarray(x,float);y=np.asarray(y,float);q=np.asarray(q,float);h=np.diff(x);d=np.diff(y)/h;m=np.zeros_like(y)
 for i in range(1,len(y)-1):
  if d[i-1]*d[i]>0:
   w1=2*h[i]+h[i-1];w2=h[i]+2*h[i-1];m[i]=(w1+w2)/(w1/d[i-1]+w2/d[i])
 for end,i,j in [(0,0,1),(-1,-1,-2)]:
  v=((2*h[i]+h[j])*d[i]-h[i]*d[j])/(h[i]+h[j])
  if v*d[i]<=0:v=0
  elif d[i]*d[j]<0 and abs(v)>abs(3*d[i]):v=3*d[i]
  m[end]=v
 k=np.clip(np.searchsorted(x,q,side='right')-1,0,len(x)-2);t=(q-x[k])/h[k]
 return (2*t**3-3*t*t+1)*y[k]+(t**3-2*t*t+t)*h[k]*m[k]+(-2*t**3+3*t*t)*y[k+1]+(t**3-t*t)*h[k]*m[k+1]

def surface_of_revolution(name,z,r,material,n=256):
 """Closed solid from a sampled outline, with single-vertex centre caps."""
 verts=[(0,0,float(z[0]))];faces=[]
 for rr,zz in zip(r,z):
  for i in range(n):a=math.tau*i/n;verts.append((rr*math.cos(a),rr*math.sin(a),zz))
 for i in range(n):faces.append((0,1+(i+1)%n,1+i))
 for k in range(len(z)-1):
  for i in range(n):a=1+k*n+i;b=1+k*n+(i+1)%n;faces.append((a,b,b+n,a+n))
 end=len(verts);verts.append((0,0,float(z[-1])))
 for i in range(n):faces.append((1+(len(z)-1)*n+i,1+(len(z)-1)*n+(i+1)%n,end))
 ob=mesh(name,verts,faces,material);clean(ob);return ob

def catmull_arclength(points,count=100):
 p=np.asarray(points,float);out=[]
 for k in range(len(p)-1):
  a,b,c,d=p[max(0,k-1)],p[k],p[k+1],p[min(k+2,len(p)-1)]
  for t in np.linspace(0,1,32,endpoint=False):out.append(.5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
 out=np.vstack([out,p[-1]]);s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(out,axis=0),axis=1))];q=np.linspace(0,s[-1],count)
 return np.stack([np.interp(q,s,out[:,j]) for j in range(3)],-1),q

def swept_ellipse(name,points_mm,diameters_mm,material,count=100,n=64,closed_tip=False):
 """Parallel-transported frame; smoothly varying section. No per-ring axis switch."""
 pp,arc=catmull_arclength(np.asarray(points_mm)/1000,count);p=np.asarray(points_mm,float)/1000
 rawarc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];rawarc*=arc[-1]/rawarc[-1]
 diam=np.asarray(diameters_mm,float)/2000;rr=np.stack([pchip(rawarc,diam[:,j],arc) for j in range(2)],-1)
 tt=np.gradient(pp,axis=0);tt/=np.linalg.norm(tt,axis=1)[:,None];seed=np.array([0,1,0.]) if abs(tt[0,1])<.8 else np.array([1,0,0.]);u=np.cross(tt[0],seed);u/=np.linalg.norm(u);frames=[]
 for t in tt:
  u=u-t*np.dot(u,t);u/=np.linalg.norm(u);v=np.cross(t,u);frames.append((u.copy(),v.copy()))
 vs=[];fs=[]
 for k,(pt,(u,v)) in enumerate(zip(pp,frames)):
  for j in range(n):a=math.tau*j/n;vs.append(pt+rr[k,0]*math.cos(a)*u+rr[k,1]*math.sin(a)*v)
 for k in range(count-1):
  for j in range(n):a=k*n+j;b=k*n+(j+1)%n;fs.append((a,b,b+n,a+n))
 start=len(vs);vs.append(pp[0]);
 for j in range(n):fs.append((start,(j+1)%n,j))
 if closed_tip:
  u,v=frames[-1];t=tt[-1];prev=(count-1)*n;length=min(rr[-1])*1.0
  for an in np.linspace(0,math.pi/2,10)[1:-1]:
   ix=len(vs)
   for j in range(n):a=math.tau*j/n;vs.append(pp[-1]+t*length*math.sin(an)+math.cos(an)*(u*rr[-1,0]*math.cos(a)+v*rr[-1,1]*math.sin(a)))
   for j in range(n):fs.append((prev+j,prev+(j+1)%n,ix+(j+1)%n,ix+j))
   prev=ix
  end=len(vs);vs.append(pp[-1]+t*length)
 else:prev=(count-1)*n;end=len(vs);vs.append(pp[-1])
 for j in range(n):fs.append((prev+j,prev+(j+1)%n,end))
 ob=mesh(name,vs,fs,material);clean(ob);return ob,pp,rr

def smooth_junctions(ob,zones,voxel_mm=.30,iterations=45):
 """Smooth the connected undecorated outer solid locally; precise cavities follow."""
 active(ob);m=ob.modifiers.new('Outer solid uniform junction topology','REMESH');m.mode='VOXEL';m.voxel_size=voxel_mm/1000;m.use_smooth_shade=True;bpy.ops.object.modifier_apply(modifier=m.name)
 xyz=np.empty(len(ob.data.vertices)*3,np.float32);ob.data.vertices.foreach_get('co',xyz);xyz=xyz.reshape(-1,3);weights=np.zeros(len(xyz))
 for center,extent in zones:
  q=np.linalg.norm((xyz-np.asarray(center)/1000)/(np.asarray(extent)/1000),axis=1);t=np.clip(1-q,0,1);weights=np.maximum(weights,t*t*(3-2*t))
 vg=ob.vertex_groups.new(name='Only authored joining zones')
 for quant in range(1,101):
  ids=np.flatnonzero(np.round(weights*100)==quant).tolist()
  if ids:vg.add(ids,quant/100,'REPLACE')
 m=ob.modifiers.new('Local continuous ceramic transitions','SMOOTH');m.factor=1.0;m.iterations=iterations;m.vertex_group=vg.name;bpy.ops.object.modifier_apply(modifier=m.name)
 m=ob.modifiers.new('Outer surface sampling economy','DECIMATE');m.ratio=.55;bpy.ops.object.modifier_apply(modifier=m.name);clean(ob,1e-8)
 return {'voxel_mm':voxel_mm,'smoothing_iterations':iterations,'local_zones_mm':zones,'outer_only_before_relief':True}

def blend_spout_root(ob,profile_z,profile_r,path,sections,blend_mm=7):
 """Bounded smooth-union projection makes an actual fillet at the spout shoulder."""
 xyz=np.empty(len(ob.data.vertices)*3,np.float32);ob.data.vertices.foreach_get('co',xyz);xyz=xyz.reshape(-1,3);sel=np.flatnonzero((xyz[:,0]>.032)&(xyz[:,0]<.070)&(abs(xyz[:,1])<.022)&(xyz[:,2]>.019)&(xyz[:,2]<.060));p=xyz[sel].astype(float);path=np.asarray(path);sections=np.asarray(sections);der=np.gradient(profile_r,profile_z)
 def field(q):
  rho=np.linalg.norm(q[:,:2],axis=1);r=np.interp(q[:,2],profile_z,profile_r);dr=np.interp(q[:,2],profile_z,der);db=(rho-r)/np.sqrt(1+dr*dr)
  # Closest centreline segment, then its oriented elliptical section.
  best=np.full(len(q),np.inf);ds=np.zeros(len(q))
  for i in range(len(path)-1):
   v=path[i+1]-path[i];lv=np.dot(v,v);t=np.clip((q-path[i])@v/lv,0,1);c=path[i]+t[:,None]*v;d=q-c;dist=(d*d).sum(1);use=dist<best
   if not np.any(use):continue
   tang=v/np.sqrt(lv);u=np.cross(tang,[0,1,0]);u/=np.linalg.norm(u);ra=sections[i]+t[:,None]*(sections[i+1]-sections[i]);du=d@u;dy=d[:,1];dt=d@tang;signed=(np.sqrt((du/ra[:,0])**2+(dy/ra[:,1])**2+(dt/ra.min(1))**2)-1)*ra.min(1);ds[use]=signed[use];best[use]=dist[use]
  gate=np.exp(-((q[:,0]-.049)/.017)**4-(q[:,1]/.018)**4-((q[:,2]-.039)/.019)**4);k=np.maximum(blend_mm/1000*gate,1e-7);h=np.clip(.5+.5*(ds-db)/k,0,1);return ds*(1-h)+db*h-k*h*(1-h)
 step=.00005
 for _ in range(5):
  val=field(p);gr=[]
  for j in range(3):v=np.zeros(3);v[j]=step;gr.append((field(p+v)-field(p-v))/(2*step))
  grad=np.stack(gr,-1);dp=val[:,None]*grad/np.maximum((grad*grad).sum(1)[:,None],.1);length=np.linalg.norm(dp,axis=1);dp*=np.minimum(1,.0015/np.maximum(length,1e-12))[:,None];p-=dp
 xyz[sel]=p;ob.data.vertices.foreach_set('co',xyz.ravel());ob.data.update();return {'method':'Bounded smooth-union field projection at the spout shoulder before cavity subtraction','blend_mm':blend_mm,'vertices':len(sel)}
