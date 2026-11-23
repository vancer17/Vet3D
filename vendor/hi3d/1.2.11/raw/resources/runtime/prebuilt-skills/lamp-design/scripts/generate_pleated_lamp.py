"""Blender CLI: fixed pleated lamp example with adjustable radial wall, not physical certification.
blender -b --factory-startup --python-exit-code 1 --python this.py -- --output out
Geometry authored in metres; individual STL export uses millimetres.
"""
import argparse, sys, math, json, struct, hashlib
from pathlib import Path
import bpy, bmesh
from mathutils import Vector

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from mesh_measure import measure_mesh

from blender_stl import raw_triangles, stl_bytes
from blender_primitives import cylinder_object, curve_tube

from material_nodes import principled_material

def parse():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    p.add_argument('--wall',type=float,default=1.2,help='radial shade thickness mm')
    p.add_argument('--preview',action='store_true');return p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

def active(o):
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o

def material(name,color,metal=0,rough=.45):
    return principled_material(name,color,metallic=metal,roughness=rough)

def cylinder(name,r,h,z,xy=(0,0),n=128):
    return cylinder_object(name,(xy[0]/1000,xy[1]/1000,z/1000),r/1000,h/1000,collection=bpy.context.collection,segments=n)

def box(name,size,xyz):
    bpy.ops.mesh.primitive_cube_add(size=1,location=Vector(xyz)/1000);o=bpy.context.object;o.name=name;o.scale=Vector(size)/1000
    active(o);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return o

def boolean(a,b,op='DIFFERENCE'):
    active(a);m=a.modifiers.new(op,'BOOLEAN');m.operation=op;m.solver='EXACT';m.object=b
    bpy.ops.object.modifier_apply(modifier=m.name);bpy.data.objects.remove(b,do_unlink=True)

def finish(o,mat,bevel=0):
    o.data.materials.clear();o.data.materials.append(mat)
    for f in o.data.polygons:f.material_index=0
    if bevel:
        active(o);m=o.modifiers.new('Edge softness','BEVEL');m.width=bevel/1000;m.segments=3
        bpy.ops.object.modifier_apply(modifier=m.name)
    for f in o.data.polygons:f.use_smooth=True

def metrics(o):
    measured = measure_mesh(o.data, transform=o.matrix_world, unit_mm=1000)
    return {'bounds_mm':[round(x*1000,3) for x in o.dimensions],
            'boundary_edges':measured['boundary_edges'], 'nonmanifold_edges':measured['nonmanifold_edges'],
            'volume_mm3':round(abs(measured['signed_volume']),12)*1e9, 'faces':measured['faces']}

def stl(o,path):
    # Placement belongs to the lamp profile; authored geometry and BMesh diagonals stay unchanged.
    zmin = min((o.matrix_world @ v.co).z for v in o.data.vertices) * 1000
    triangles = raw_triangles(o, world=True, triangulation='bmesh')
    triangles[:,:,2] -= zmin
    Path(path).write_bytes(stl_bytes(triangles, header=b'Pleated lamp | millimetres | example'))

def tube(name,points,r,mat):
    return curve_tube(name,[Vector(p)/1000 for p in points],r/1000,collection=bpy.context.collection,material=mat,bevel_resolution=4,fill_caps=False)

def build_materials():
    white=material('Ivory diffuser - optical approximation',(.82,.77,.65),0,.43)
    # Thin-shell diffuse transmission; no shade emission and no invisible point above the shade.
    nt=white.node_tree;bs=nt.nodes.get('Principled BSDF');output=nt.nodes.get('Material Output')
    trans=nt.nodes.new('ShaderNodeBsdfTranslucent');trans.inputs[0].default_value=(.90,.83,.66,1)
    mix=nt.nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.62
    nt.links.new(bs.outputs[0],mix.inputs[1]);nt.links.new(trans.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],output.inputs['Surface'])
    dark=material('Basalt PETG',(.024,.038,.042),0,.35)
    brass=material('Warm brass finish',(.40,.22,.075),.72,.28)
    cablemat=material('Charcoal cable and switch',(.018,.019,.020),0,.52)
    ledmat=material('LED surface',(.95,.87,.69),0,.35)
    ledmat.node_tree.nodes.get('Principled BSDF').inputs['Emission Color'].default_value=(1,.63,.29,1)
    return white,dark,brass,cablemat,ledmat

def build_shade(wall,white):
    s=bpy.context.scene
    # Shade: closed solid thin wall with 6 mm structural flange and two rising crests.
    N=288;K=120;verts=[];faces=[]
    def ring(rfun,zfun):
        ids=[]
        for j in range(N):
            t=2*math.pi*j/N;r=rfun(t);z=zfun(t);ids.append(len(verts));verts.append((r*math.cos(t)/1000,r*math.sin(t)/1000,z/1000))
        return ids
    rings=[]
    for k in range(K+1):
        u=k/K
        def radius(t,u=u):
            q=max(0,(u-.04)/.96)
            return 58+22*math.sin(math.pi*q)-24*q+2.8*math.sin(math.pi*q)**.6*math.cos(18*(t-.50*q))
        rings.append(ring(radius,lambda t,u=u:16+u*(180+12*math.cos(2*t))))
    # inner surface backwards; explicit ledge at z22 for printable flange.
    for k in range(K,-1,-1):
        u=k/K
        if u*(180-12)<6:continue
        def ir(t,u=u):
            q=max(0,(u-.04)/.96)
            return 58+22*math.sin(math.pi*q)-24*q+2.8*math.sin(math.pi*q)**.6*math.cos(18*(t-.50*q))-wall
        rings.append(ring(ir,lambda t,u=u:16+u*(180+12*math.cos(2*t))))
    rings.extend([ring(lambda t:58-wall,lambda t:22),ring(lambda t:39,lambda t:22),ring(lambda t:39,lambda t:16)])
    for i in range(len(rings)):
        ra=rings[i];rb=rings[(i+1)%len(rings)]
        for j in range(N):faces.append((ra[j],ra[(j+1)%N],rb[(j+1)%N],rb[j]))
    mesh=bpy.data.meshes.new('Twisting fluted shell');mesh.from_pydata(verts,[],faces);mesh.update()
    shade=bpy.data.objects.new('P01_Shade',mesh);s.collection.objects.link(shade)
    return shade

def build_base_and_hardware(shade,white,dark,brass,cablemat,ledmat):
    # Base cup with stepped locating collar, LED tape landing, and screw pillars.
    base=cylinder('P02_Base',63,22,11)
    boolean(base,cylinder('Open base cavity',58.45,28,17)) # floor z3
    boolean(base,cylinder('LED tape landing',22,1,3.5),'UNION')
    fasteners=[]
    for i in range(3):
        t=math.radians(17+120*i);xy=(46*math.cos(t),46*math.sin(t))
        boolean(base,cylinder('Screw pillar',5,13,9.5,xy),'UNION')
        boolean(base,cylinder('M3 through bore',1.7,30,12,xy))
        boolean(base,cylinder('M3 head counterbore',3.1,2.2,1,xy))
        boolean(shade,cylinder('M3 clearance',1.7,10,19,xy))
        # 5.8 mm across flats, open upward; nuts inserted before closing the base.
        boolean(shade,cylinder('M3 hex nut pocket',5.8/math.sqrt(3),3,21,xy,n=6))
        screw=cylinder('Purchased_M3x25_'+str(i+1),1.5,25,14.5,xy,n=32);finish(screw,brass)
        head=cylinder('Purchased_M3_head_'+str(i+1),2.8,2,1,xy,n=32);finish(head,brass)
        nut=cylinder('Purchased_M3_nut_'+str(i+1),5.5/math.sqrt(3),2.4,20.7,xy,n=6)
        boolean(nut,cylinder('nut bore',1.5,5,20.7,xy,n=32));finish(nut,brass)
        fasteners += [screw,head,nut]
    # Open lay-in notch, rather than a falsely tiny hole which needs a USB plug passed through.
    boolean(base,box('Lay-in cable notch',(8,15,18),(0,62,16)))
    # Separate lacing points for optional soft strap; route stays clear of LED pad.
    for x in [-5,5]:boolean(base,box('Cable lacing slot',(2.5,6,6),(x,46,2)))
    for i in range(6):
        t=math.radians(i*60);v=box('Air inlet',(10,3,6),(35*math.cos(t),35*math.sin(t),2));v.rotation_euler.z=t;boolean(base,v)
    # Small lower edge bevel only, retaining nominal interface sizes.
    finish(shade,white);finish(base,dark)
    # Synthetic hardware envelope for this example only; select real hardware separately.
    led=cylinder('Example_LED_59x8_proxy',29.5,8,9)
    finish(led,ledmat,.4)
    for i in range(3):
        t=math.radians(17+120*i);foot=cylinder('Purchased_rubber_foot_'+str(i+1),5,3,-1.5,(52*math.cos(t),52*math.sin(t)),n=48);finish(foot,cablemat,.4)
    cable=tube('Cable_route_proxy',[(0,27,8),(0,45,8),(0,65,8),(10,100,-1),(45,125,-1),(90,124,-1)],1.7,cablemat)
    switch=box('Purchased_inline_switch_envelope',(18,32,9),(97,124,2));finish(switch,cablemat,3)
    button=box('Accessible_switch_button',(8,13,1),(97,124,7));finish(button,dark,1.5)
    tube('Cable_after_switch',[(106,124,1),(136,122,-1),(158,110,-1)],1.7,cablemat)
    return base

def export_parts(shade,base,wall,out):
    s=bpy.context.scene
    parts=[shade,base]
    for o in parts:
        bm=bmesh.new();bm.from_mesh(o.data)
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-8)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-9)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
    bpy.context.view_layer.update()
    report={'revision':'01','units':'mm','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'parts':{o.name:metrics(o) for o in parts},'nominal_radial_wall_mm':wall,
      'locating_radial_clearance_mm':.45,'flange_thickness_mm':6,'fasteners':'3 x M3x25 plus 3 M3 nuts; dimensions require purchased-part check',
      'module_envelope_mm':[59,59,8],'example_voltage_V':5,'example_power_W':3,
      'status':'digital prototype; no slicing, physical fit or thermal test',
      'limits':['Radial wall is not global normal wall thickness','LED/switch/cable are synthetic example envelopes; no procurement compatibility claimed','Shade transparency is an uncalibrated optical approximation']}
    for o in parts:
        assert report['parts'][o.name]['nonmanifold_edges']==0,(o.name,report['parts'][o.name])
        stl(o,out/'print'/f'{o.name}_mm.stl')
    (out/'geometry.json').write_text(json.dumps(report,indent=2))
    bpy.ops.object.select_all(action='DESELECT')
    for o in list(s.objects):
        if o.type in {'MESH','CURVE'}:o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out/'pleated-lamp.glb'),export_format='GLB',use_selection=True,export_apply=True)
    return report

def setup_studio():
    s=bpy.context.scene
    # Authored quiet product studio, same lights/exposure for ON and OFF.
    s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=True;s.cycles.device='CPU'
    s.render.threads_mode='FIXED';s.render.threads=6;s.cycles.max_bounces=8;s.cycles.transmission_bounces=6
    s.render.resolution_x=s.render.resolution_y=960;s.render.resolution_percentage=100
    s.view_settings.view_transform='AgX';s.view_settings.exposure=0
    s.world=bpy.data.worlds.new('Studio ambient');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.04
    floor=box('Studio floor',(3000,3000,10),(0,0,-8));finish(floor,material('Stone backdrop',(.12,.14,.14),0,.8))
    def light(name,kind,xyz,power,size,color):
        d=bpy.data.lights.new(name,kind);d.energy=power;d.color=color
        if kind=='AREA':d.shape='DISK';d.size=size
        else:d.shadow_soft_size=size
        o=bpy.data.objects.new(name,d);s.collection.objects.link(o);o.location=xyz;o.rotation_euler=(Vector((0,0,.1))-o.location).to_track_quat('-Z','Y').to_euler();return o
    light('Studio key','AREA',(.2,-.3,.40),1.2,.3,(.84,.9,1))
    light('Studio rim','AREA',(-.2,.22,.3),1.8,.25,(1,.86,.66))
    emitter=light('Lamp LED','AREA',(0,0,.0131),3.0,.050,(1,.64,.30));emitter.rotation_euler=(math.pi,0,0)
    camd=bpy.data.cameras.new('Product camera');cam=bpy.data.objects.new('Product camera',camd);s.collection.objects.link(cam);s.camera=cam
    cam.location=(.35,-.5,.32);cam.rotation_euler=(Vector((0,0,.098))-cam.location).to_track_quat('-Z','Y').to_euler()
    camd.type='ORTHO';camd.ortho_scale=.325;camd.clip_start=.001
    return emitter

def save_scene(out):
    # Save lamp origin at base floor for dimensional consistency; feet extend below it.
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'pleated-lamp.blend'))
    (out/'light-states.json').write_text(json.dumps({'lights':{'Lamp LED':3.0},'emissions':{'LED surface':3.0},'target_m':[0,0,.098],'orbit_degrees':360},indent=2))

def render_preview(emitter,ledmat,out):
    s=bpy.context.scene
    for state in ['off','on']:
        emitter.data.energy=3.0 if state=='on' else 0
        ledmat.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=3 if state=='on' else 0
        s.render.filepath=str(out/'renders'/f'{state}.png');bpy.ops.render.render(write_still=True)

def main():
    a=parse()
    if not math.isfinite(a.wall) or not .8<=a.wall<=2.4:
        raise ValueError('Example radial wall must be 0.8–2.4 mm; calibrate actual normal thickness')
    out=Path(a.output).resolve()
    if out.exists() and any(out.iterdir()):
        raise FileExistsError('Use a fresh example output directory')
    (out/'print').mkdir(parents=True,exist_ok=True)
    (out/'renders').mkdir()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    white,dark,brass,cablemat,ledmat=build_materials()
    shade=build_shade(a.wall,white)
    base=build_base_and_hardware(shade,white,dark,brass,cablemat,ledmat)
    report=export_parts(shade,base,a.wall,out)
    emitter=setup_studio()
    save_scene(out)
    if a.preview:render_preview(emitter,ledmat,out)
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
