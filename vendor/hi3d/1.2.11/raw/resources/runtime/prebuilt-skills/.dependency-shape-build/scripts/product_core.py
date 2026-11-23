import bpy, math, numpy as np, bmesh, json
from pathlib import Path
from mathutils import Vector
if __package__:
 from .blender_primitives import curve_tube as _curve_tube, cylinder_object as _cylinder_object
else:
 from blender_primitives import curve_tube as _curve_tube, cylinder_object as _cylinder_object

if __package__:
 from .material_nodes import principled_material as _principled
else:
 from material_nodes import principled_material as _principled

def active(o):
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o

def mat(name,c,metal=0,rough=.32,trans=0):
 return _principled(name,c,metallic=metal,roughness=rough,inputs={'Transmission Weight':trans,'IOR':1.46})

def mesh(name,v,f,m):
 v=np.array(v,dtype=np.float32);f=np.array(f,dtype=np.int32)
 me=bpy.data.meshes.new(name);me.vertices.add(len(v));me.vertices.foreach_set('co',v.ravel());me.loops.add(f.size);me.loops.foreach_set('vertex_index',f.ravel());me.polygons.add(len(f));me.polygons.foreach_set('loop_start',np.arange(len(f),dtype=np.int32)*f.shape[1]);me.polygons.foreach_set('loop_total',np.full(len(f),f.shape[1],dtype=np.int32));me.update();o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);me.materials.append(m);me.polygons.foreach_set('use_smooth',np.ones(len(f),dtype=bool));return o

def cyl(name,loc,r,h,m):
 o=_cylinder_object(name,loc,r,h,collection=bpy.context.collection,segments=96);o.data.materials.append(m);return o

def cube(name,loc,size,m,bevel=.001):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.scale=size;active(o);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m)
 if bevel:
  q=o.modifiers.new('Soft manufacturing edges','BEVEL');q.width=bevel;q.segments=3;bpy.ops.object.modifier_apply(modifier=q.name)
 return o

def lathe(name,profile,m,center=(0,0),n=128):
 v=[];f=[]
 for r,z in profile:
  for i in range(n):a=math.tau*i/n;v.append((center[0]+r*math.cos(a),center[1]+r*math.sin(a),z))
 for k in range(len(profile)-1):
  for i in range(n):j=(i+1)%n;f.append((k*n+i,k*n+j,(k+1)*n+j,(k+1)*n+i))
 o=mesh(name,v,f,m);bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-8);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();return o

def tube(name,pts,rad,m):
 return _curve_tube(name,pts,rad,collection=bpy.context.collection,material=m)

def boolean(o,c,op='DIFFERENCE'):
 active(o);q=o.modifiers.new('Functional '+op,'BOOLEAN');q.solver='EXACT';q.operation=op;q.object=c;bpy.ops.object.modifier_apply(modifier=q.name);bpy.data.objects.remove(c,do_unlink=True)






def bisect_half(o,axis=1,side=1):
 bm=bmesh.new();bm.from_mesh(o.data);normal=[0,0,0];normal[axis]=side
 ret=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.000001,plane_co=(0,0,0),plane_no=normal,clear_outer=True,clear_inner=False)
 ed=[g for g in ret['geom_cut'] if isinstance(g,bmesh.types.BMEdge)];bmesh.ops.holes_fill(bm,edges=ed,sides=0);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()

def copy_obj(o,name):
 c=o.copy();c.data=o.data.copy();bpy.context.collection.objects.link(c);c.name=name;return c

def clean(o,tol=1e-8):
 active(o);bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=tol);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=tol);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();o.data.update();return o


def pipe(name,pts,rads,m,res=12,n=64):
 data=np.asarray(pts,float);rr=[float(value) for value in rads]
 if data.ndim!=2 or data.shape[1]!=3 or len(data)<2 or len(rr)!=len(data) or not np.isfinite(data).all() or min(rr)<=0 or np.any(np.linalg.norm(np.diff(data,axis=0),axis=1)<1e-10) or res<1 or n<3:raise ValueError('Pipe requires distinct finite xyz points, matched positive radii and positive resolution')
 raw=[Vector(p) for p in data];pp=[];radi=[]
 for k in range(len(raw)-1):
  p0=raw[max(k-1,0)];p1=raw[k];p2=raw[k+1];p3=raw[min(k+2,len(raw)-1)]
  for j in range(res):
   t=j/res;pp.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t));radi.append(rr[k]*(1-t)+rr[k+1]*t)
 pp.append(raw[-1]);radi.append(rr[-1]);v=[];f=[]
 for k,p in enumerate(pp):
  tangent=(pp[min(k+1,len(pp)-1)]-pp[max(0,k-1)]).normalized();seed=Vector((0,1,0)) if abs(tangent.y)<.8 else Vector((1,0,0));u=tangent.cross(seed).normalized();w=tangent.cross(u).normalized()
  for j in range(n):a=math.tau*j/n;v.append(p+radi[k]*(math.cos(a)*u+math.sin(a)*w))
 for k in range(len(pp)-1):
  for j in range(n):a=k*n+j;b=k*n+(j+1)%n;f.append((a,b,b+n,a+n))
 f.extend([tuple(range(n-1,-1,-1)),tuple((len(pp)-1)*n+j for j in range(n))]);me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o);me.materials.append(m)
 for p in me.polygons:p.use_smooth=True
 clean(o);return o,pp,radi

def hollow_pipe(name,pts,rout,rin,m):
 o,pp,rr=pipe(name,pts,[rout]*len(pts),m);v=Vector(pts[1])-Vector(pts[0]);v.normalize();w=Vector(pts[-1])-Vector(pts[-2]);w.normalize();inner=[Vector(pts[0])-v*.003]+[Vector(p) for p in pts[1:-1]]+[Vector(pts[-1])+w*.003];c,_,_=pipe('Inner lumen',inner,[rin]*len(inner),m);boolean(o,c);return o


def make_stem(origin,tip,matl,r=.0012):
 o=tube('DISPLAY flower stem',[origin,(origin[0]+.01,origin[1],(origin[2]+tip[2])/2),tip],r,matl);return o


def remove_numerical_islands(o,limit_mm=2):
 bm=bmesh.new();bm.from_mesh(o.data);seen=set();removed=[]
 for v in list(bm.verts):
  if v in seen:continue
  todo=[v];seen.add(v);part=[]
  while todo:
   w=todo.pop();part.append(w)
   for e in w.link_edges:
    q=e.other_vert(w)
    if q not in seen:seen.add(q);todo.append(q)
  if len(part)<=32:
   xyz=np.array([v.co[:] for v in part]);extent=(xyz.max(0)-xyz.min(0))*1000;print('SMALL_COMPONENT',len(part),extent,flush=True)
   if max(extent)<limit_mm:removed.append({'vertices':len(part),'dimensions_mm':extent.tolist()});bmesh.ops.delete(bm,geom=part,context='VERTS')
 bm.to_mesh(o.data);bm.free();return removed
