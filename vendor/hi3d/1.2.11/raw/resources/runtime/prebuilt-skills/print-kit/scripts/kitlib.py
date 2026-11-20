"""Millimetre solid construction and STL-first assembly export. Python 3.11+.

Dependencies: numpy, manifold3d, trimesh. No Blender dependency.
All transforms use column vectors, right handed Z up, degrees for rotation().
"""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import trimesh
import manifold3d as md


from motion_check import is_rigid, rotation, transform, translation

def box(size, at=(0, 0, 0)):
    return md.Manifold.cube(size).translate(at)


def cyl(r, h, at=(0, 0, 0), segments=96):
    return md.Manifold.cylinder(h, r, circular_segments=segments).translate(at)


def union(items):
    items = list(items)
    if not items:
        return md.Manifold()
    return md.Manifold.batch_boolean(items, md.OpType.Add)


def polygon(points, thickness):
    return md.Manifold.extrude(md.CrossSection([points]), thickness)


def rounded_box(w, d, h, r=3, at=(0, 0, 0)):
    pts=[]
    for x,y,a in [(w-r,d-r,0),(r,d-r,90),(r,r,180),(w-r,r,270)]:
        for angle in np.linspace(a,a+90,17):
            pts.append((x+r*math.cos(math.radians(angle)),y+r*math.sin(math.radians(angle))))
    return polygon(pts,h).translate(at)


def tray(w,d,h,t=2.4,r=3):
    return rounded_box(w,d,h,r)-rounded_box(w-2*t,d-2*t,h,r=max(.5,r-t),at=(t,t,t))








def mesh(s):
    m=s.to_mesh()
    return trimesh.Trimesh(np.asarray(m.vert_properties)[:,:3],np.asarray(m.tri_verts),process=True)


def solid(m):
    return md.Manifold(md.Mesh(np.asarray(m.vertices,dtype=np.float32),np.asarray(m.faces,dtype=np.uint32)))


def write_json(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()




def valid_mesh(m):
    """Check one nondegenerate closed positive mesh; no filesystem side effects."""
    return bool(m.is_watertight and m.is_winding_consistent and m.volume>0
                and len(m.split(only_watertight=False))==1 and (m.area_faces>1e-10).all())


def export_solid(s,path):
    """Write one STL, reread float32 bytes, return mesh or raise ValueError.

    The parent must exist. Invalid output is retained for diagnosis, not delivery.
    """
    if len(s.decompose())!=1 or s.volume()<=0:
        raise ValueError('expected one positive connected solid')
    mesh(s).export(path)
    exported=trimesh.load_mesh(path,process=True)
    if not valid_mesh(exported):
        raise ValueError('invalid STL; check tangent booleans / float32 precision: '+str(path))
    return exported


def assembly_geometry(plan,parts):
    """Return a metre-unit GLB scene and mm meshes from delivered parts; no writes."""
    scene=trimesh.Scene();assembled=[]
    colors={p['id']:p['color'] for p in plan['parts']}
    for inst in plan['instances']:
        m=parts[inst['part']].copy();m.apply_transform(inst['matrix']);assembled.append(m.copy())
        c=colors[inst['part']].lstrip('#')
        m.visual.face_colors=[int(c[k:k+2],16) for k in (0,2,4)]+[255]
        m.apply_scale(.001);scene.add_geometry(m,node_name=inst['id'],geom_name=inst['id'])
    return scene,assembled


def pack_plates(plan,parts):
    """Return deterministic axis-aligned shelf packing; raise on bed overflow.

    Uses every instance, no rotations or mesh nesting. Margin and spacing are
    explicit plan values; does not include slicer-generated supports/brims.
    """
    bed=plan['bed_mm'];margin=plan['bed_margin_mm'];gap=plan['part_spacing_mm']
    plates=[];x=y=margin;row=0;plate=0
    for inst in sorted(plan['instances'],key=lambda i:-parts[i['part']].extents[1]):
        w,d,h=parts[inst['part']].extents
        if w>bed[0]-2*margin or d>bed[1]-2*margin or h>bed[2]:
            raise ValueError('bed overflow '+inst['id'])
        if x+w>bed[0]-margin:x=margin;y+=row+gap;row=0
        if y+d>bed[1]-margin:plate+=1;x=y=margin;row=0
        plates.append({'instance':inst['id'],'plate':plate+1,'matrix':translation([x,y,0]).tolist()})
        x+=w+gap;row=max(row,d)
    return plates


class Kit:
    def __init__(self,id,title,parameters=None,bed=None,*,profile=None,bed_margin=5,spacing=6):
        """Create an in-memory plan; bed is required in mm, profile is task supplied."""
        if bed is None or len(bed)!=3 or not np.isfinite(bed).all() or min(bed)<=0:
            raise ValueError("supply positive finite bed=(width, depth, height) in mm")
        if not np.isfinite([bed_margin, spacing]).all() or min(bed_margin,spacing)<0 or min(bed[:2])<=2*bed_margin:
            raise ValueError("invalid bed margin or part spacing")
        self.data={'schema_version':1,'id':id,'title':title,'units':'mm','up_axis':'Z',
          'matrix_convention':'row arrays, column vectors; print STL to assembly',
          'bed_mm':list(bed),'bed_margin_mm':bed_margin,'part_spacing_mm':spacing,
          'profile':dict(profile or {}),
          'parameters':parameters or {},'parts':[],'instances':[],'joints':[],
          'disassembly':[],'motions':[],'features':[],'hardware':[],
          'notes':[],'assembly_steps':[],'evidence':{'physical_test':'not_run','slicer':'not_run'}}
        self.solids={}

    def add(self,id,s,color='#b6ac94',instances=None,print_rotation=None,
            note='',support='not_assessed',explode=(0,0,0)):
        if id in self.solids:raise ValueError('duplicate part '+id)
        r=np.eye(4) if print_rotation is None else np.asarray(print_rotation)
        if not is_rigid(r):raise ValueError('print transform must be rigid')
        m=mesh(transform(s,r)); p=translation(-m.bounds[0])@r
        instances=[np.eye(4)] if instances is None else list(instances)
        if not instances or not all(is_rigid(v) for v in instances):
            raise ValueError('supply nonempty rigid instance transforms')
        self.solids[id]=transform(s,p)
        self.data['parts'].append({'id':id,'file':'parts/'+id+'.stl','qty':len(instances),
           'color':color,'print_notes':note,'support':support})
        for i,im in enumerate(instances):
            self.data['instances'].append({'id':id if len(instances)==1 else f'{id}-{i+1}',
              'part':id,'matrix':(np.asarray(im)@np.linalg.inv(p)).round(10).tolist(),
              'explode':list(explode)})
        return id

    def joint(self,id,a,b,kind,clearance,retention,**kw):
        self.data['joints'].append(dict(id=id,a=a,b=b,kind=kind,
          clearance_per_side_mm=clearance,retention=retention,**kw))

    def path(self,ids,vector,distance,step=2):
        self.data['disassembly'].append({'instances':ids,'direction':vector,
           'distance_mm':distance,'max_step_mm':step})

    def probe(self,id,instance,center,axis,expected,span=30):
        self.data['features'].append(dict(id=id,instance=instance,center=center,axis=axis,
          expected_mm=expected,span_mm=span,tolerance_mm=.025))

    def export(self,out):
        """Write STL/GLB/JSON to an output directory; raise on invalid geometry/packing.

        Existing matching outputs are replaced. A failed export may leave partial
        files; only a returned kit.json path marks export completion, not validation.
        """
        if not self.data['parts']:
            raise ValueError('cannot export an empty kit')
        out=Path(out);(out/'parts').mkdir(parents=True,exist_ok=True)
        by={}
        for part in self.data['parts']:
            exported=export_solid(self.solids[part['id']],out/part['file'])
            part.update(sha256=sha(out/part['file']),size_mm=exported.extents.tolist(),
                        volume_mm3=float(exported.volume))
            by[part['id']]=exported
        scene,assembled=assembly_geometry(self.data,by)
        scene.export(out/'assembly.glb')
        trimesh.util.concatenate(assembled).export(out/'assembly-view-only.stl')
        self.data['assembled_size_mm']=np.ptp(np.vstack([m.bounds for m in assembled]),axis=0).tolist()
        self.data['plates']=pack_plates(self.data,by)
        write_json(out/'kit.json',self.data)
        return out/'kit.json'
