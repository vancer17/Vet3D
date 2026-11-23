"""Blender CLI: --background --factory-startup --python render_kit.py -- kit.json.
Authors a reproducible scene from delivered STL bytes. Optional --render performs
the bounded render directly; otherwise render the authored scene with Blender tools.
"""
import argparse,json,math,sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector

def matrix_mm(v):
    m=Matrix(v);m.translation*=.001;return m

def camera(name,objs,positions,direction,resolution):
    pts=[]
    for ob,mat in zip(objs,positions):
        pts.extend(mat@Vector(v) for v in ob.bound_box)
    lo=Vector([min(v[a] for v in pts) for a in range(3)]);hi=Vector([max(v[a] for v in pts) for a in range(3)])
    center=(lo+hi)/2;direction=Vector(direction).normalized()
    bpy.ops.object.camera_add(location=center+direction*max((hi-lo).length*2,.5))
    cam=bpy.context.object;cam.name=name;cam.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO';r=cam.rotation_euler.to_matrix();inv=r.transposed()
    local=[inv@(v-center) for v in pts];width=max(v.x for v in local)-min(v.x for v in local);height=max(v.y for v in local)-min(v.y for v in local)
    cam.data.ortho_scale=max(width,height*resolution[0]/resolution[1])*1.15
    cam.data.clip_start=.001;cam.data.clip_end=100
    return cam,lo.z

def configure_scene():
    """Reset the current Blender scene and configure an isolated CPU render session."""
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=24;sc.cycles.use_denoising=True
    sc.render.resolution_x=1000;sc.render.resolution_y=800;sc.render.resolution_percentage=100
    sc.view_settings.view_transform='AgX';sc.render.image_settings.file_format='PNG';sc.render.film_transparent=False
    world=bpy.data.worlds.new('Warm gray studio');sc.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(.32,.35,.39,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.4
    return sc


def load_geometry(d,out):
    """Import delivered mm STL as metre meshes with display materials; mutates Blender."""
    geos={}
    for part in d['parts']:
        bpy.ops.wm.stl_import(filepath=str(out/part['file']));ob=bpy.context.object
        ob.data.transform(Matrix.Scale(.001,4));geos[part['id']]=ob.data
        c=part['color'].lstrip('#');color=[((int(c[i:i+2],16)/255+.055)/1.055)**2.4 for i in [0,2,4]]
        mat=bpy.data.materials.new(part['id']);mat.diffuse_color=(*color,1);mat.use_nodes=True
        bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(*color,1);bsdf.inputs['Roughness'].default_value=.4
        ob.data.materials.append(mat);bpy.data.objects.remove(ob,do_unlink=True)
    return geos


def instance_poses(d,sc,geos):
    """Instantiate parts and keyframe assembly/explosion/plates/first motion endpoint."""
    objects=[];poses={1:[],2:[],3:[]}
    stride=Vector(((d['bed_mm'][0]+20)*.001,(d['bed_mm'][1]+20)*.001,0))
    pb={q['instance']:q for q in d['plates']};maxplate=max(q['plate'] for q in d['plates']);cols=min(3,maxplate)
    for inst in d['instances']:
        ob=bpy.data.objects.new(inst['id'],geos[inst['part']]);sc.collection.objects.link(ob);objects.append(ob)
        m=matrix_mm(inst['matrix']);poses[1].append(m);e=m.copy();e.translation+=Vector(inst['explode'])*.001;poses[2].append(e)
        pl=pb[inst['id']];pm=matrix_mm(pl['matrix']);idx=pl['plate']-1;pm.translation+=Vector([(idx%cols)*stride.x,(idx//cols)*stride.y,0]);poses[3].append(pm)
        for frame,mat in [(1,m),(2,e),(3,pm)]:
            ob.matrix_world=mat
            ob.keyframe_insert('location',frame=frame);ob.keyframe_insert('rotation_euler',frame=frame);ob.keyframe_insert('scale',frame=frame)
    # Optional fourth view exposes motion at a meaningful endpoint, based on the same plan.
    if d.get('motions'):
        mo=d['motions'][0];openposes=[]
        if mo['type']=='rotation':
            pivot=Vector(mo['pivot'])*.001;rr=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(mo['end_deg']),4,mo['axis'].upper())@Matrix.Translation(-pivot)
        else:rr=Matrix.Translation(Vector(mo['direction']).normalized()*mo['distance_mm']*.001)
        for ob,inst,m in zip(objects,d['instances'],poses[1]):
            pose=rr@m if inst['id'] in mo['instances'] else m;openposes.append(pose);ob.matrix_world=pose
            ob.keyframe_insert('location',frame=4);ob.keyframe_insert('rotation_euler',frame=4);ob.keyframe_insert('scale',frame=4)
        poses[4]=openposes
    return objects,poses


def add_cameras(objects,poses):
    """Author fitted orthographic cameras from actual mesh bounds."""
    cams={};lowest={}
    names={f:name for f,name in {1:'assembly',2:'exploded',3:'plates',4:'operation'}.items() if f in poses}
    for f,ps in poses.items():
        cams[f],lowest[f]=camera(names[f],objects,ps,(0,-.001,1) if f==3 else (2.5,-3.5,2.5),(1000,800))
    return cams,lowest,names


def add_studio(d,poses,lowest):
    """Author backdrop, task-sized beds and studio lights; mutates Blender scene."""
    bpy.ops.mesh.primitive_plane_add(size=5,location=(0,0,-.001));floor=bpy.context.object;floor.name='studio-ground'
    fm=bpy.data.materials.new('warm backdrop');fm.diffuse_color=(.18,.20,.22,1);floor.data.materials.append(fm)
    for f,z in lowest.items():floor.location.z=z-.001;floor.keyframe_insert('location',frame=f)
    maxplate=max(p['plate'] for p in d['plates']);cols=min(3,maxplate)
    bw,bd=[v*.001 for v in d['bed_mm'][:2]]
    for pi in range(maxplate):
        bpy.ops.mesh.primitive_plane_add(size=1,location=((pi%cols)*(bw+.02)+bw/2,(pi//cols)*(bd+.02)+bd/2,-.0003))
        bed=bpy.context.object;bed.scale=(bw,bd,1);bed.name='build-plate-'+str(pi+1)
        bm=bpy.data.materials.get('build-plate-material') or bpy.data.materials.new('build-plate-material');bm.diffuse_color=(.08,.09,.10,1);bed.data.materials.append(bm)
        for f in poses:
            bed.hide_render=f!=3;bed.keyframe_insert('hide_render',frame=f)
    for name,pos,energy,size in [('key',(.25,-.35,.55),8,.4),('fill',(-.3,-.1,.3),3,.35),('rim',(.2,.4,.45),6,.3)]:
        bpy.ops.object.light_add(type='AREA',location=pos);light=bpy.context.object;light.name=name;light.data.energy=energy;light.data.shape='DISK';light.data.size=size;light.rotation_euler=(Vector((.08,.06,.07))-light.location).to_track_quat('-Z','Y').to_euler()


def render_views(sc,cams,names,out):
    """Render PNG frames and write render-manifest.json, replacing matching outputs."""
    for f,cam in cams.items():
        sc.frame_set(f);sc.camera=cam;sc.render.filepath=str(out/(names[f]+'.png'));bpy.ops.render.render(write_still=True)
    (out/'render-manifest.json').write_text(json.dumps({'blender':bpy.app.version_string,'engine':'CYCLES','device':'CPU','samples':24,'denoised':True,'color_management':'AgX','resolution':[1000,800],'frames':names,'source':'delivered parts/*.stl'},indent=2))


def author(plan_path,render=False):
    """Read plan/STLs, replace current scene, save scene.blend and optional PNGs.

    Invoke only in an isolated Blender --background --factory-startup process.
    A missing STL or Blender/render exception propagates; partial outputs may remain.
    """
    path=Path(plan_path).resolve();out=path.parent;d=json.loads(path.read_text())
    sc=configure_scene();geos=load_geometry(d,out)
    objects,poses=instance_poses(d,sc,geos)
    cams,lowest,names=add_cameras(objects,poses);add_studio(d,poses,lowest)
    sc.frame_end=max(poses);sc.frame_set(1);sc.camera=cams[1]
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    if render:render_views(sc,cams,names,out)
    return out/'scene.blend'


def main():
    p=argparse.ArgumentParser();p.add_argument('plan');p.add_argument('--render',action='store_true')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);author(a.plan,a.render)


if __name__=='__main__':main()
