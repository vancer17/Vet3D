"""Rebuild the lunar frame and four printed mechanical parts. Blender CLI or import.
All input paths explicit. No network calls and no top-level scene mutations.
"""
import argparse, json, math, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from frame_recipe import validate_recipe
from heightfield_io import load_heightfield
import bpy
import numpy as np
from frame_core import applymods, boolean
from frame_print import export_stl
from mathutils import Vector
from planar_audit import bounds
from planar_core import MM, clean_solid_mesh, cube, loft, loop, material, mesh, plate, ring3, sample
from planar_preview import camera, clean, export_glb, save
from planar_render import render
from mathutils import Matrix
from frame_runtime import cli_arguments
from frame_diy_runtime import prepare_paths

def annular_sector(name,r0,r1,a0,a1,z0,z1,mat,n=None):
    n=n or max(8,math.ceil(abs(a1-a0)*4))
    q=np.radians(np.linspace(a0,a1,n));xy=np.vstack([np.c_[r1*np.cos(q),r1*np.sin(q)],np.c_[r0*np.cos(q[::-1]),r0*np.sin(q[::-1])]])
    return prism(name,xy,z0,z1,mat)

def prism(name,xy,z0,z1,mat):
    n=len(xy);v=np.vstack([ring3(xy,z0),ring3(xy,z1)])
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    f += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh(name,v,f,mat)

def annulus(name,ri,ro,z0,z1,mat,n=768):
    a=np.arange(n)*2*np.pi/n;o=np.c_[ro*np.cos(a),ro*np.sin(a)];i=np.c_[ri*np.cos(a),ri*np.sin(a)]
    return loft(name,[ring3(o,z0),ring3(o,z1),ring3(i,z1),ring3(i,z0),ring3(o,z0)],mat)

def moon_frame(cfg,field,mat):
    """Create this fixed contour family from a normalized field; changes scene."""
    W,H=cfg['aperture_mm'];R=cfg['outer_radius_mm'];cx=cfg['eccentric_x_mm'];n=768;t=np.arange(n)*2*np.pi/n
    rr=cx*np.cos(t)+np.sqrt(R*R-cx*cx*np.sin(t)**2);outer=np.c_[rr*np.cos(t),rr*np.sin(t)];inner=loop(W,H,'ellipse',n);seat=loop(W+4.8,H+4.8,'ellipse',n)
    valid=field>.005;distance=np.zeros_like(field);fade=int(cfg.get('source_boundary_fade_pixels',18))
    for _ in range(fade):
        pad=np.pad(valid,1);valid=pad[1:-1,1:-1]&pad[1:-1,:-2]&pad[1:-1,2:]&pad[:-2,1:-1]&pad[2:,1:-1];distance+=valid
    edge=np.clip(distance/max(1,fade),0,1);field=field*edge*edge*(3-2*edge)
    rings=[ring3(outer,cfg['frame_back_mm']),ring3(outer,2.5)]
    for f in np.linspace(.015,1,101):
        xy=outer*(1-f)+inner*f;left=.5-.5*np.cos(t);env=np.sin(np.pi*f)**.82
        h=sample(field,(xy[:,0]-cx+R)/(2*R),(xy[:,1]+R)/(2*R));z=5.35+(2.5+2.7*left)*env+cfg['hi3d_relief_mm']*h*env*np.clip((left-.12)/.65,0,1)
        rings.append(np.c_[xy,z])
    rings.extend([ring3(inner,3.4),ring3(seat,3.4),ring3(seat,cfg['frame_back_mm']),rings[0]])
    f=loft('Main lunar frame',rings,mat)
    boolean(f,plate('Precision visible aperture',W,H,18,3.4,'ellipse',mat),'DIFFERENCE')
    return f

def curved_tube(name,pts,radii,mat,ncross=24):
    rings=[]
    for i,p in enumerate(pts):
        tangent=pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)];tangent/=np.linalg.norm(tangent);side=np.cross(tangent,[0,0,1.]);side/=np.linalg.norm(side);up=np.cross(side,tangent);q=np.arange(ncross)*2*np.pi/ncross;r=radii[i]
        rings.append(p+np.cos(q)[:,None]*side*r+np.sin(q)[:,None]*up*r*.7)
    return loft(name,rings,mat,True,True)

def dovetail(name,x,y0,y1,mat,clearance=0):
    c=clearance
    # Broad head is in +Z. 45-degree transitions; translation along Y.
    xz=np.array([[-3-c,-2.5],[-3-c,-1.2],[-4.5-c,.3],[-4.5-c,2+c],[4.5+c,2+c],[4.5+c,.3],[3+c,-1.2],[3+c,-2.5]])
    v=np.concatenate([np.c_[xz[:,0]+x,np.full(8,y),xz[:,1]] for y in [y0,y1]])
    f=[tuple(range(7,-1,-1)),tuple(range(8,16))]+[(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
    return mesh(name,v,f,mat)

def board_release_shape(obj,delta=1.15):
    obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='Press inward to release')
    for v,k in zip(obj.data.vertices,key.data):
        p=np.array(v.co)/MM;r=np.linalg.norm(p[:2]);a=(math.degrees(math.atan2(p[1],p[0]))+360)%360
        if (r>55.35 and 118<=a<=152) or (r>48.8 and 141.8<=a<=149.2):
            u=np.clip((a-119)/29,0,1);w=u*u*(3-2*u);k.co.x-=delta*w*p[0]/r*MM;k.co.y-=delta*w*p[1]/r*MM
    key.slider_min=0;key.slider_max=1;key.value=0
    return key

def stand_release_shape(obj,delta=1.5):
    obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='Press away from frame to release')
    for v,k in zip(obj.data.vertices,key.data):
        p=np.array(v.co)/MM
        if -21.3<p[0]<17 and -65.0<p[1]<-59.0 and -6.8<p[2]<.1:
            u=np.clip((p[0]+21.3)/35.3,0,1);w=u*u*(3-2*u);k.co.z-=delta*w*MM
    key.slider_min=0;key.slider_max=1;key.value=0
    bpy.context.view_layer.update()
    return key

def build_connectors(frame,cfg,mat,backmat):
    """Mutate the D110 circular frame with this recipe's fixed mating mechanism."""
    c=cfg['fit_clearance_mm'];turn=cfg['bayonet_turn_deg'];tabs=[75.,180.,285.]
    ring=annulus('Bayonet locking back ring',52,57,-1.2,1.5,backmat)
    for angle in tabs:
        boolean(ring,annular_sector('Integral bayonet ear',56.5,60.5,angle-4,angle+4,1.25,2.65,backmat))
        boolean(frame,annular_sector('Swept bayonet female track',57.2,60.5+c,angle-turn-4-.3,angle+4+.3,1.25-c,2.65+c,mat),'DIFFERENCE')
        boolean(frame,annular_sector('Axial tab entrance',57.2,60.5+c,angle-turn-4-.3,angle-turn+4+.3,-2,2.65+c,mat),'DIFFERENCE')
    # Flexible ring tongue: long circumferential slot + free-end radial cut.
    boolean(ring,annular_sector('Curved relief slot',53.7,55.6,119,151,-2,2,mat),'DIFFERENCE')
    boolean(ring,annular_sector('Free end clearance',53.7,58.2,151,153,-2,2,mat),'DIFFERENCE')
    boolean(ring,annular_sector('Positive anti-rotation tooth',56.55,58.,144.0,148.0,-.9,1.3,backmat))
    boolean(frame,annular_sector('Release latch pocket',57.2,58.0+c,143.7,148.3,-1.5,1.3+c,mat),'DIFFERENCE')
    # Broad inward paddle remains in the common print plane. Remove adjacent
    # rigid inner rim first, so this paddle does not short-circuit the flex slot.
    boolean(ring,annular_sector('Paddle access opening',48,55.6,138,152,-2,2,mat),'DIFFERENCE')
    boolean(ring,annular_sector('Inward press paddle',49.0,56.95,142,149,-1.2,1.5,backmat))
    for a in [25,230]:
        boolean(ring,annular_sector('Turn grip',47.5,54.0,a-7,a+7,-1.2,1.5,backmat))
    # Static backing: key prevents friction from driving the photograph in rotation.
    carrier=plate('Stationary keyed photograph backing',111.6,111.6,1.2,1.75,'ellipse',backmat)
    boolean(carrier,annular_sector('Backing anti-rotation key',55.4,58.,-2,2,1.75,2.95,backmat))
    for a in [120,240]:
        boolean(carrier,annular_sector('Static backing centering ear',55.4,57.0,a-4,a+4,1.75,2.95,backmat))
    boolean(frame,annular_sector('Backing key socket',57.2,58.+c,-2.3,2.3,-2.0,3.2,mat),'DIFFERENCE')
    # Two positive, broad load rails. Their entire entry is open below the frame.
    mountx=27.9
    for x in [-mountx,mountx]:
        boolean(frame,dovetail('Full female dovetail with open approach',x,-87,-53.75,mat,c),'DIFFERENCE')
    # Catch pocket has end walls; the catch does not carry the static load.
    boolean(frame,cube('Stand latch receiving pocket',(4.5,5.5,1.5),(12,-62,-.55),mat,0),'DIFFERENCE')
    stand=None;angle=math.radians(82);ca,sa=math.cos(angle),math.sin(angle);height=80*sa+.7
    for x in [-mountx,mountx]:
        pad=cube('Wide rail mounting pad',(13,16,3.6),(x,-61,-3.25),mat,.7);applymods(pad)
        boolean(pad,dovetail('Integral broad dovetail',x,-67,-54,mat))
        top=np.array([x,-59.,-3.2]);footz=-57.;footy=(-height-ca*footz)/sa;end=np.array([x*1.08,footy,footz]);u=np.linspace(0,1,65);pp=top+(end-top)*u[:,None];pp[:,2]-=7*np.sin(np.pi*u);pp[:,1]-=2*np.sin(np.pi*u)
        boolean(pad,curved_tube('Swept structural leg',pp,3.2-.3*u,mat))
        foot=cube('Rear contact foot',(15,5.5,9),(end[0],end[1]+.2,end[2]+1.2),mat,1.4);applymods(foot);boolean(pad,foot)
        if stand is None:stand=pad
        else:boolean(stand,pad)
    for name,dim,loc,bev in [('Low easel cross tie',(61.4,5,6),(0,footy+2,-50),1.7),('Rear mounting bridge',(62,3.6,3.6),(0,-67.8,-3.25),.6),('Long independent release beam',(40,5,1.2),(-4,-62,-3.9),.4),('Positive stop tooth',(4,5,3.3),(12,-62,-1.85),.15),('Stand press pad',(6,5,2.0),(13,-62,-4.9),.5)]:
        o=cube(name,dim,loc,mat,bev);applymods(o);boolean(stand,o)
    stand.name='Twin dovetail easel with release lever'
    # Same functional contact plane/front silhouette as standard version.
    T=Matrix.Translation((0,0,height*MM));M=Matrix.Rotation(angle,4,'X')
    for x in [cfg['eccentric_x_mm']-22,cfg['eccentric_x_mm']+14]:
        o=cube('Integral front rest',(8,7,6.8),(x,-78,2.7),mat,1);applymods(o);boolean(frame,o)
    for ob in [frame,stand]:
        cut=cube('Table contact halfspace',(700,700,300),(0,0,0),mat,0);cut.matrix_world=(T@M).inverted()@Matrix.Translation((0,0,-150*MM));boolean(ob,cut,'DIFFERENCE')
    # Final negative pass after all feet/unions preserves the full entry corridor.
    for x in [-mountx,mountx]:
        boolean(frame,dovetail('Final unfilled rail entry',x,-87,-53.75,mat,c),'DIFFERENCE')
    # Global placement into vertex coordinates is required before shape keys.
    for ob in [frame,ring,carrier,stand]:
        bpy.context.view_layer.objects.active=ob;ob.select_set(True);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ob.select_set(False);clean_solid_mesh(ob)
    # Flat manufactured planes must not inherit relief smoothing.
    for ob in [frame,ring,carrier,stand]:
        for poly in ob.data.polygons:
            zz=[ob.data.vertices[i].co.z for i in poly.vertices]
            if max(zz)-min(zz)<1e-8:poly.use_smooth=False
    board_release_shape(ring);stand_release_shape(stand)
    for role,o in [('frame',frame),('locking_ring',ring),('backing',carrier),('stand',stand)]:o['assembly_role']=role;o['printable']=True
    return [frame,ring,carrier,stand],T@M

def setup_scene(parts,card,display,out,render_stills=True):
    s=bpy.context.scene;assembly=[*parts,card]
    for o in assembly:o.matrix_world=display@o.matrix_world
    coll=bpy.data.collections.new('ECLIPSE ALL PRINTED ASSEMBLY');s.collection.children.link(coll)
    for o in assembly:
        for c in list(o.users_collection):c.objects.unlink(o)
        coll.objects.link(o)
    floor=material('Cool charcoal desktop',(.088,.108,.125),0,.75);cube('Stone table',(12000,12000,20),(0,0,-10),floor,0)
    s.world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.63,.57,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.25
    for name,loc,power,size,col in [('Large side window',(-280,-230,360),3.5,270,(1,.92,.81)),('Front fill',(190,-280,220),2,220,(.85,.91,1)),('Rear rim',(110,100,320),3,220,(1,.95,.84))]:
        bpy.ops.object.light_add(type='AREA',location=np.array(loc)*MM);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size*MM;o.data.color=col;o.rotation_euler=(Vector((0,0,.09))-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();cam=bpy.context.object;cam.name='Product camera';cam.data.type='ORTHO';cam.data.clip_start=.001;s.camera=cam
    camera(cam,(-8,0,80),(72,-370,115),212)
    if render_stills:render(out/'hero.png',1000,1200,24)
    camera(cam,(-7,24,76),(170,320,150),215)
    if render_stills:render(out/'rear.png',1100,1200,24)
    camera(cam,(-7,18,80),(0,370,100),208)
    if render_stills:render(out/'rear-direct.png',1100,1200,24)
    camera(cam,(-8,0,80),(72,-370,115),212);save(out/'scene.blend')

def build(*,output,heightfield,artwork,config,render_stills=True):
    """Validate inputs, build this circular recipe and export four free-state parts."""
    paths, inputs = prepare_paths(output=output, raw_inputs={'heightfield':heightfield, 'artwork':artwork, 'config':config})
    cfg = validate_recipe(json.loads(inputs['config'].read_text()))
    field = load_heightfield(inputs['heightfield'], cfg['height_key'])
    started=time.monotonic();out=paths['output'];out.mkdir(parents=True,exist_ok=True);(out/'print').mkdir(exist_ok=True)
    artwork=inputs['artwork'];clean()
    mat=material('Smoked gold PLA lunar shell',(.15,.115,.073),.48,.48);backmat=material('Graphite PLA mechanics',(.038,.052,.062),0,.48);paper=material('Photograph',(.4,.5,.6),0,.78)
    frame=moon_frame(cfg,field,mat);parts,display=build_connectors(frame,cfg,mat,backmat)
    card=plate('Independent paper photograph',113.9,113.9,.4,2.95,'ellipse',paper);card['assembly_role']='artwork'
    img=bpy.data.images.load(str(Path(artwork).resolve()));img.pack();tex=paper.node_tree.nodes.new('ShaderNodeTexImage');tex.image=img;paper.node_tree.links.new(tex.outputs['Color'],paper.node_tree.nodes.get('Principled BSDF').inputs['Base Color']);uv=card.data.uv_layers.new(name='Print UV')
    for p in card.data.polygons:
        for li in p.loop_indices:
            co=card.data.vertices[card.data.loops[li].vertex_index].co/MM;uv.data[li].uv=(.5+co.x/113.9,.5+co.y/113.9)
    report={'configuration':cfg,'parts':[],'display_transform':list(map(list,display)),'nominal_gaps_mm':{'backing_to_lock_ring_axial':.25,'paper_plus_backing_to_front_stop':.05,'seat_to_backing_main_disc_radial':1.6,'seat_to_backing_centering_ears_radial':.4,'backing_key_to_socket_radial':cfg['fit_clearance_mm'],'bayonet_radial':cfg['fit_clearance_mm'],'bayonet_each_axial':cfg['fit_clearance_mm'],'dovetail_X_each_side_coordinate_offset':cfg['fit_clearance_mm'],'dovetail_Z_head_coordinate_offset':cfg['fit_clearance_mm']},'bayonet':{'tab_centers_deg':[75,180,285],'tab_radius_mm':[56.5,60.5],'tab_half_angle_deg':4,'z_mm':[1.25,2.65],'entrance_offset_deg':-12,'rotation_deg':12,'back_shoulder_z_mm':[cfg['frame_back_mm'],1.25-cfg['fit_clearance_mm']]},'release':{'ring_effective_arc_mm':30.4,'ring_radial_thickness_mm':1.4,'ring_tip_inward_mm':1.15,'stand_effective_length_mm':35.3,'stand_thickness_mm':1.2,'stand_tip_outward_mm':1.5},'physical_status':'not sliced, printed, cycled, load-tested or paper-abrasion-tested'}
    for o in parts:
        if o.data.shape_keys:
            for key in o.data.shape_keys.key_blocks:key.value=0
        bpy.context.view_layer.update()
        path=out/'print'/(o['assembly_role']+'-mm.stl');export_stl(path,[o]);report['parts'].append({'role':o['assembly_role'],'name':o.name,'file':str(path.relative_to(out)),'bounds':bounds([o])})
    save(out/'flat-assembly.blend');export_glb(out/'flat-model.glb',[*parts,card]);setup_scene(parts,card,display,out,render_stills)
    export_glb(out/'model.glb',[*parts,card]);report['assembled_bounds']=bounds([*parts,card]);report['wall_seconds']=time.monotonic()-started
    (out/'measurements.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('BUILD_COMPLETE',out,flush=True)
    return report

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--heightfield',required=True);p.add_argument('--artwork',required=True);p.add_argument('--config',required=True);p.add_argument('--no-render',action='store_true');a=p.parse_args(cli_arguments(argv))
    build(output=a.output,heightfield=a.heightfield,artwork=a.artwork,config=a.config,render_stills=not a.no_render)
if __name__=='__main__':main()
