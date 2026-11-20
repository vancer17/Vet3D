"""Parametric lithophane lightbox — Blender 4.3+/5.x, millimetres.

Open this file in Blender's Text Editor and Run Script to enable the
N-panel > Litho Frame. The shipped .blend also embeds this source.
CLI: blender -b --python hi3d-frame-builder-1.py -- --out OUTPUT [--config JSON]
No third-party Python dependencies. Hardware and photos are not printable.
"""
import bpy
import bmesh
import math
import json
import struct
import sys
import csv
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion
from mathutils.geometry import delaunay_2d_cdt
from bpy.props import FloatProperty, StringProperty, EnumProperty, PointerProperty

bl_info = {"name": "Lithophane Frame Builder", "author": "Codex", "version": (5, 1, 0),
           "blender": (4, 3, 0), "location": "3D View > N > Litho Frame", "category": "Add Mesh"}

DEFAULT = dict(width=150.0, height=100.0, border=10.0, overlap=3.5,
               panel_min=1.5, panel_max=3.0, preview_thickness=2.25,
               slot_clearance=0.3, panel_xy_clearance=0.4, light_gap=25.0,
               led_width=8.0, led_thickness=2.0, led_channel_width=9.0,
               led_recess=1.0, back_thickness=3.2, joint_clearance=0.2,
               stand_angle=35.0, insert_bore=4.0, insert_length=5.7,
               hinge_ear_width=12.0, hinge_ear_thickness=5.0, hinge_slot=6.6,
               hinge_fuse_overlap=0.8, hinge_root_rib=1.6)

PARTS = []
VISUALS = []
MATS = {}
WORK = None


def derived(p):
    w, h, b = p['width'], p['height'], p['border']
    if min(w, h) < 100 or not 10 <= b <= 26 or min(w, h)-2*b < 45:
        raise ValueError('Use width/height >=100, border 10..26 and window >=45 mm.')
    if not (1.5 <= p['panel_min'] <= p['preview_thickness'] <= p['panel_max'] <= 3):
        raise ValueError('Thickness must satisfy 1.5 <= min <= preview <= max <= 3 mm.')
    if not 25 <= p['light_gap'] <= 60:
        raise ValueError('Light gap must be 25..60 mm.')
    if p['led_channel_width'] < p['led_width'] + 0.3:
        raise ValueError('LED channel must be at least LED width +0.3 mm.')
    vw, vh = w-2*b, h-2*b
    pw, ph = vw+2*p['overlap'], vh+2*p['overlap']
    seat = 3.0
    slot_end = seat+p['panel_max']+p['slot_clearance']
    emitter = seat+p['panel_max']+p['light_gap']
    led_floor = emitter+p['led_thickness']
    back_front = led_floor-p['led_recess']
    depth = back_front+p['back_thickness']
    if back_front < 30:
        raise ValueError('Light gap too small for the nut bridges; use gap >=25 mm here.')
    short=min(w,h);long=max(w,h)
    led_row=short*.26-16+9.5
    slim=b<18
    led_length=math.floor((long-2*b-8)/10)*10
    return dict(window_w=vw, window_h=vh, photo_w=pw, photo_h=ph, seat=seat,
                slot_end=slot_end, slot_width=p['panel_max']+p['slot_clearance'],
                rear_flange=slot_end+3.0, back_front=back_front, depth=depth,
                led_floor=led_floor, emitter=emitter,
                led_length=led_length, led_center_length=max(10,led_length-20),led_row_y=led_row,
                led_vertical=h>w, hinge_x=min(short*.26,short/2-33), hinge_y=-h/2+short-20,
                hinge_z=depth+11, alternate_pivot_x=-w/2+short-22,
                stand_length=short-20, clamp_y=min(18.0, ph/2-10),
                hinge_ear_radius=p['hinge_ear_width']/2,
                pressure_d=2.0 if slim else 3.0,
                pressure_screw_length=10.0 if slim else 12.0,
                pressure_head_d=3.8 if slim else 5.5,
                pressure_head_h=2.0 if slim else 3.0,
                pressure_tool_af=1.5 if slim else 2.5,
                pressure_x=w/2-(3.5 if slim else 10.5),
                pressure_bridge_x=w/2-(4.7 if slim else 11.0),
                pressure_bridge_width=9.0 if slim else 13.0,
                pressure_nut_af=4.3 if slim else 5.8,
                pressure_nut_t=1.9 if slim else 2.6,
                pressure_bar_inner=vw/2+.3, pressure_bar_outer=w/2-(1.8 if slim else 7.0))


def pressure_access_spec(p,d):
    """Rear axial head/key access, with an inward neck to avoid a thin membrane.

    The screw tip seats 1.5 mm behind the pressure bar's front face.  The
    counterbore starts below the earliest under-head plane but above the
    complete nut bridge (Z15.6), preserving its axial bearing shoulder.
    """
    return dict(diameter=d['pressure_head_d']+.6,
                start_z=d['seat']+p['panel_min']+1.5+d['pressure_screw_length']-.3,
                end_z=d['depth']+2.0,
                neck_width=3.0 if d['pressure_d']==2 else 4.0,
                chamber_inner_x=p['width']/2-6.0-.2)


def link_object(obj):
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    WORK.objects.link(obj)
    return obj


def box(name, dims, center):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    o = link_object(bpy.context.object)
    o.name = name
    o.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return o


def prism(name, points, z0, z1):
    n = len(points)
    verts = [(x,y,z0) for x,y in points] + [(x,y,z1) for x,y in points]
    faces = [tuple(reversed(range(n))), tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    o = bpy.data.objects.new(name, mesh)
    WORK.objects.link(o)
    clean(o)
    return o


def prism_yz(name, points, x0, x1):
    """Extrude an explicit YZ profile along X, with no cylinder union seams."""
    n=len(points)
    verts=[(x0,y,z) for y,z in points]+[(x1,y,z) for y,z in points]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);WORK.objects.link(o);clean(o)
    return o


def cyl(name, diameter, length, center, axis='Z', vertices=48, phase=0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=diameter/2,
                                       depth=length, location=center,
                                       rotation=(0,0,math.radians(phase)))
    o = link_object(bpy.context.object)
    o.name = name
    if axis == 'X':
        o.rotation_euler = (0, math.pi/2, 0)
    elif axis == 'Y':
        o.rotation_euler = (math.pi/2, 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return o


def boolean(a, cutter, operation='DIFFERENCE'):
    bpy.context.view_layer.objects.active = a
    mod = a.modifiers.new('Exact_'+operation, 'BOOLEAN')
    mod.operation = operation
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return a


def clean(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.00001)
    bmesh.ops.dissolve_degenerate(bm, dist=0.00001, edges=list(bm.edges))
    zero=[f for f in bm.faces if f.calc_area()<1e-9]
    if zero:bmesh.ops.delete(bm,geom=zero,context='FACES_ONLY')
    wires=[e for e in bm.edges if not e.link_faces]
    if wires:bmesh.ops.delete(bm,geom=wires,context='EDGES')
    loose=[v for v in bm.verts if not v.link_edges]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()


def material(name, color, metallic=0, roughness=.4):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*color,1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color,1)
    bs.inputs['Metallic'].default_value = metallic
    bs.inputs['Roughness'].default_value = roughness
    return m


def materials():
    MATS.clear()
    MATS['wood'] = material('Walnut preview — use any printable filament', (.20,.075,.026),0,.5)
    MATS['wood'].node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value=.2
    n = MATS['wood'].node_tree.nodes
    l = MATS['wood'].node_tree.links
    tex=n.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=3
    coord=n.new('ShaderNodeTexCoord'); mapping=n.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'
    mapping.inputs[1].default_value=(2,65,3)
    ramp=n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position=.22; ramp.color_ramp.elements[0].color=(.055,.016,.006,1)
    ramp.color_ramp.elements[1].position=.8; ramp.color_ramp.elements[1].color=(.30,.13,.045,1)
    l.new(coord.outputs['Generated'],mapping.inputs[0]);l.new(mapping.outputs['Vector'],tex.inputs['Vector'])
    l.new(tex.outputs['Fac'],ramp.inputs['Fac']);l.new(ramp.outputs['Color'],n.get('Principled BSDF').inputs['Base Color'])
    MATS['back']=material('Matte ivory reflector',(.78,.8,.78),0,.48)
    MATS['key']=material('Orange removable keys',(.94,.25,.045),0,.36)
    MATS['clamp']=material('Cyan floating pressure bars',(.025,.46,.55),0,.35)
    MATS['stand']=material('Graphite stand',(.055,.075,.09),.1,.34)
    MATS['photo']=material('PHOTO PLACEHOLDER — not printable',(.81,.69,.48),0,.58)
    MATS['led']=material('LED PLACEHOLDER — not printable',(.95,.72,.22),0,.38)
    bs=MATS['led'].node_tree.nodes.get('Principled BSDF')
    bs.inputs['Emission Color'].default_value=(1,.68,.3,1);bs.inputs['Emission Strength'].default_value=.5
    MATS['hardware']=material('Hardware position guide — not printable',(.35,.39,.42),.65,.28)


def finish(o, name, kind, description, explode=(0,0,0)):
    o.name=name
    clean(o)
    o.data.materials.clear();o.data.materials.append(MATS[kind])
    for poly in o.data.polygons:poly.material_index=0
    o['printable']=True;o['function']=description;o['explode']=list(explode)
    # Render-only micro bevel; exported STL uses the exact engineering mesh.
    bevel=o.modifiers.new('Preview edge highlights (not in STL)', 'BEVEL')
    bevel.width=.14;bevel.segments=2
    bevel.limit_method='ANGLE'
    PARTS.append(o)
    return o


def nut_z(o, x, y, z, direction=(0,1), af=5.8, thick=2.6, reach=8):
    # Hex plus lateral insertion tunnel; axial faces remain closed.
    along_x=abs(direction[0])>.5
    # Blender's zero-phase hex has vertices on +/-Y. Rotate for an X tunnel
    # so its parallel flats, rather than its corners, face the tunnel walls.
    boolean(o,cyl('metal nut trap', af*2/math.sqrt(3),thick,(x,y,z+thick/2),
                  vertices=6,phase=30 if along_x else 0))
    dx,dy=direction
    dims=(reach+.2,af,thick) if along_x else (af,reach+.2,thick)
    boolean(o,box('nut loading tunnel',dims,(x+dx*reach/2,y+dy*reach/2,z+thick/2)))


def stand_mount_points(p,d):
    points=[]
    for direction in ['primary','alternate']:
        for sx in [-1,1]:
            for dx in [-16,16]:
                if direction=='primary':x=sx*d['hinge_x']+dx;y=d['hinge_y']
                else:x=d['alternate_pivot_x'];y=sx*d['hinge_x']+dx
                points.append((x,y))
    return points


def canonical_xy(p,x,y):
    return (y,x) if p['height']>p['width'] else (x,y)


def owner_for_inward(nx,ny):
    if nx<-.5:return 'RIGHT'
    if nx>.5:return 'LEFT'
    if ny<-.5:return 'TOP'
    return 'BOTTOM'


def back_screw_specs(p):
    a,b=max(p['width'],p['height']),min(p['width'],p['height'])
    raw=[(a/2-8.5,-14,-1,0),(-a/2+8.5,-14,1,0),
         (-8,b/2-8.5,0,-1),(-8,-b/2+8.5,0,1)]
    result=[]
    for x,y,nx,ny in raw:
        x,y=canonical_xy(p,x,y);nx,ny=canonical_xy(p,nx,ny)
        result.append((x,y,nx,ny,owner_for_inward(nx,ny)))
    return result


def build_rails(p,d):
    w,h,b=p['width'],p['height'],p['border'];D=d['depth']; bf=d['back_front']
    vw,vh=d['window_w'],d['window_h'];pw,ph=d['photo_w'],d['photo_h']
    shapes={
        '01_RAIL_BOTTOM':[(-w/2,-h/2),(w/2,-h/2),(vw/2,-vh/2),(-vw/2,-vh/2)],
        '02_RAIL_RIGHT':[(vw/2,-vh/2),(w/2,-h/2),(w/2,h/2),(vw/2,vh/2)],
        '03_RAIL_TOP':[(-vw/2,vh/2),(vw/2,vh/2),(w/2,h/2),(-w/2,h/2)],
        '04_RAIL_LEFT':[(-w/2,-h/2),(-vw/2,-vh/2),(-vw/2,vh/2),(-w/2,h/2)]}
    # Deep bow-tie sockets are covered by the installed back plate.
    corners=[]
    for sx,sy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
        cx,cy=sx*(w/2-9),sy*(h/2-9)
        u=Vector((sx,-sy));u.normalize();v=Vector((sx,sy));v.normalize()
        local=[(-4.8,-3.6),(0,-2.0),(4.8,-3.6),(4.8,3.6),(0,2.0),(-4.8,3.6)]
        def pts(scale=1, cx=cx,cy=cy,u=u,v=v,local=local):
            return [(cx+scale*(a*u.x+bb*v.x),cy+scale*(a*u.y+bb*v.y)) for a,bb in local]
        corners.append((sx,sy,cx,cy,pts))
    screw_specs=back_screw_specs(p)
    screw_points=[(x,y) for x,y,nx,ny,owner in screw_specs]
    for name,points in shapes.items():
        o=prism(name,points,0,D)
        boolean(o,box('photo insertion rebate',(pw+p['panel_xy_clearance'],ph+p['panel_xy_clearance'],d['slot_width']),
                      (0,0,d['seat']+d['slot_width']/2)))
        # Back shoulder closes the U channel; moving clamp windows open it locally.
        boolean(o,box('clear rear window',(vw,vh,D+2),(0,0,d['slot_end']+(D+2)/2)))
        boolean(o,box('light chamber',(w-12,h-12,D+2),(0,0,d['rear_flange']+(D+2)/2)))
        if 'LEFT' in name or 'RIGHT' in name:
            sx=1 if 'RIGHT' in name else -1
            xi=d['pressure_bar_inner'];xo=d['pressure_bar_outer']
            pocket_h=ph-12+.4
            boolean(o,box('floating bar clearance',(xo-xi+.6,pocket_h,5.6),
                          (sx*(xi+xo)/2,0,d['seat']+2.8)))
            for yy in [-d['clamp_y'],d['clamp_y']]:
                bridge=box('clamp nut bridge',(d['pressure_bridge_width'],12,6.8),(sx*d['pressure_bridge_x'],yy,12.2))
                boolean(o,bridge,'UNION')
                xx=sx*d['pressure_x']
                boolean(o,cyl('pressure screw clearance',d['pressure_d']+.4,12,(xx,yy,12)))
                # Load from the open light chamber. Along-rail tunnels would
                # terminate inside the continuous side wall rather than open.
                nut_z(o,xx,yy,11,(-sx,0),af=d['pressure_nut_af'],thick=d['pressure_nut_t'],reach=7)
        # Add corner webs, clipped to each rail's mitre envelope.
        for sx,sy,cx,cy,pts in corners:
            web=box('corner structural web',(14.4,14.4,D-d['rear_flange']+.2),
                    (cx,cy,(d['rear_flange']-.2+D)/2))
            boolean(web,prism('mitre halfspace',points,-1,D+1),'INTERSECT')
            if len(web.data.polygons):
                boolean(o,web,'UNION')
            else:
                bpy.data.objects.remove(web,do_unlink=True)
        # Back-plate screw bosses are at mid-edges, away from the corner keys.
        for xx,yy,nx,ny,owner in screw_specs:
            own=owner in name
            if own:
                boolean(o,box('back screw boss',(12,12,bf-23),(xx,yy,(23+bf)/2)),'UNION')
                boolean(o,cyl('back screw clearance',3.4,bf-20,(xx,yy,(22+bf)/2)))
                nut_z(o,xx,yy,bf-4.8,(nx,ny),reach=8)
        # Apply again after web unions: rear plate pocket and insertion-key sockets.
        boolean(o,box('back plate seat',(w-6,h-6,D-bf+2),(0,0,(bf+D+2)/2)))
        for x,y in stand_mount_points(p,d):
            boolean(o,cyl('insert boss clearance',9.4,4.4,(x,y,bf-2.0)))
        for sx,sy,cx,cy,pts in corners:
            scale=1+p['joint_clearance']/3.6
            boolean(o,prism('bow-tie socket',pts(scale),19,D+2))
        # Two shallow decorative grooves following the mitred front face.
        for inset in [b*.15,b*.31,b*.895]:
            outer=box('profile groove',(w-2*inset,h-2*inset,.7),(0,0,.25))
            groove_width=max(.45,.6*b/20)
            boolean(outer,box('profile core',(w-2*inset-2*groove_width,h-2*inset-2*groove_width,2),(0,0,.25)))
            boolean(o,outer)
        # Viewed from the front (-Z), -X is the viewer's right side.
        if 'LEFT' in name:
            boolean(o,box('12x8 switch opening',(16,12,8),
                          (-w/2+2,h*-0.5+23,(d['rear_flange']+bf)/2)))
            boolean(o,box('portrait USB cable notch',(10,7,7),(-w/2+2,20,D-2.5)))
        if 'BOTTOM' in name:
            boolean(o,box('USB cable open notch',(7,10,7),
                          (20,-h/2+2,D-2.5)))
        # Last cuts: corner webs and rear fixing bosses must not re-close the
        # pressure-screw path. Remove the back tray before accessing these M2s.
        if 'LEFT' in name or 'RIGHT' in name:
            sx=1 if 'RIGHT' in name else -1
            access=pressure_access_spec(p,d)
            z0,z1=access['start_z'],access['end_z']
            for yy in [-d['clamp_y'],d['clamp_y']]:
                xx=sx*d['pressure_x']
                boolean(o,cyl('V5.1 screw head and hex-key rear access',
                              access['diameter'],z1-z0,(xx,yy,(z0+z1)/2),vertices=64))
                # Slim frames would otherwise leave a 0.3 mm wall between the
                # round bore and light chamber. A narrower neck opens it up
                # while preserving the adjacent M3 fixing/nut shoulder.
                inner=access['chamber_inner_x'];outer=d['pressure_x']+.1
                if inner<outer:
                    boolean(o,box('V5.1 inward access neck',
                                  (outer-inner,access['neck_width'],z1-z0),
                                  (sx*(inner+outer)/2,yy,(z0+z1)/2)))
        ev={'01_RAIL_BOTTOM':(0,-15,0),'02_RAIL_RIGHT':(15,0,0),
            '03_RAIL_TOP':(0,25,0),'04_RAIL_LEFT':(-15,0,0)}[name]
        finish(o,name,'wood','45-degree mitred rail; top rail removes after extracting upper keys',ev)
    for i,(sx,sy,cx,cy,pts) in enumerate(corners,5):
        o=prism('key',pts(),19.2,bf-.2)
        finish(o,f'{i:02d}_KEY_{"L" if sx<0 else "R"}{"B" if sy<0 else "T"}',
               'key','Bow-tie joint spline, axially retained by back plate',(sx*15,sy*15,25))
    return screw_points


def build_clamps(p,d):
    w=p['width'];xi=d['pressure_bar_inner'];xo=d['pressure_bar_outer']
    length=d['photo_h']-12
    front=d['seat']+p['preview_thickness']
    for i,sx in enumerate([-1,1],9):
        o=box('floating pressure bar',(xo-xi,length,2), (sx*(xi+xo)/2,0,front+1))
        for y in [-d['clamp_y'],d['clamp_y']]:
            boolean(o,cyl('pressure screw cup',d['pressure_d']+.8,.6,(sx*d['pressure_x'],y,front+1.8)))
        finish(o,f'{i:02d}_PRESSURE_BAR_{"L" if sx<0 else "R"}','clamp',
               'Floating bar: retract before sliding panel; tighten pressure screws gently',(sx*8,0,-10))


def build_back(p,d,screw_points):
    w,h=p['width'],p['height'];bf,D=d['back_front'],d['depth']
    o=box('back',(w-6.4,h-6.4,p['back_thickness']),(0,0,(bf+D)/2))
    for x,y in screw_points:
        boolean(o,cyl('M3 back attachment',3.4,8,(x,y,D)))
        boolean(o,cyl('M3 head counterbore',6.4,1.85,(x,y,D-.9)))
    # Three straight strips, not bent round corners; end-to-end jumper wires.
    for y in [-d['led_row_y'],0,d['led_row_y']]:
        length=d['led_center_length'] if y==0 else d['led_length']
        dims=(p['led_channel_width'],length+4,p['led_recess']+.1) if d['led_vertical'] else (length+4,p['led_channel_width'],p['led_recess']+.1)
        center=(y,0,bf+(p['led_recess']-.1)/2) if d['led_vertical'] else (0,y,bf+(p['led_recess']-.1)/2)
        boolean(o,box('LED mounting channel',dims,center))
    # Stay clear of the opposing M3 head recesses; otherwise the two cuts
    # leave a sub-layer membrane at their overlap.
    route_x=d['led_length']/2-3.0
    dims=(d['led_row_y']*2+p['led_channel_width'],3,1.1) if d['led_vertical'] else (3,d['led_row_y']*2+p['led_channel_width'],1.1)
    center=(0,route_x,bf+.45) if d['led_vertical'] else (route_x,0,bf+.45)
    boolean(o,box('jumper wire route',dims,center))
    start=d['led_center_length']/2-.5;end=route_x+1.5
    dims=(3,end-start,1.1) if d['led_vertical'] else (end-start,3,1.1)
    center=(0,(start+end)/2,bf+.45) if d['led_vertical'] else ((start+end)/2,0,bf+.45)
    boolean(o,box('centre strip lead route',dims,center))
    boolean(o,cyl('5 mm cable service hole',5,10,(w/2-16,-h/2+14,D)))
    # Both display orientations get fixed clevises fused to the tray itself.
    # Only the movable U stand changes axes. No mounting screw or heat insert.
    master=create_hinge_master(p)
    placements=[]
    for sx in [-1,1]:
        primary=Matrix.Translation(Vector((sx*d['hinge_x'],d['hinge_y'],D)))@Matrix.Rotation(math.pi if sx>0 else 0,4,'Z')
        alternate=Matrix.Translation(Vector((d['alternate_pivot_x'],-sx*d['hinge_x'],D)))@Matrix.Rotation(math.pi/2,4,'Z')
        placements.extend([primary,alternate])
    mount_metadata=[]
    for placement in placements:
        hinge_copy=master.copy();hinge_copy.data=master.data.copy();WORK.objects.link(hinge_copy)
        hinge_copy.matrix_world=placement
        boolean(o,hinge_copy,'UNION')
        mount_metadata.append({'placement':[[float(v) for v in row] for row in placement]})
    bpy.data.objects.remove(master,do_unlink=True)
    o['integral_hinges']=4
    o['hinge_fuse_overlap_mm']=p['hinge_fuse_overlap']
    o['integral_mounts_json']=json.dumps(mount_metadata)
    # Cable enters through the bottom corresponding to either display orientation.
    boolean(o,box('primary cable edge opening',(7,10,10),(20,-h/2+2,D)))
    boolean(o,box('alternate cable edge opening',(10,7,10),(-w/2+2,20,D)))
    finish(o,'11_BACK_LED_TRAY','back','One solid tray with four integral R6 clevises, two display orientations',(0,0,65))


def create_hinge_master(p):
    # One canonical master reused at all four placements before solid union.
    r=p['hinge_ear_width']/2;t=p['hinge_ear_thickness'];gap=p['hinge_slot']
    pivot=11.0;outer=gap+2*t
    u=box('rectangular U blank',(outer,2*r,pivot+r-3.8),(0,0,(3.8+pivot+r)/2))
    boolean(u,box('rectangular U slot',(gap,2*r+2,20),(0,0,14)))
    # Exact tangent semicircle: two end fillets R=width/2 join at the centre.
    profile=[(-r,3.8),(r,3.8),(r,pivot)]
    profile += [(r*math.cos(math.pi*i/64),pivot+r*math.sin(math.pi*i/64)) for i in range(1,65)]
    boolean(u,prism_yz('R equals half-width end mask',profile,-outer/2-1,outer/2+1),'INTERSECT')
    overlap=p['hinge_fuse_overlap']
    o=box('hinge base master',(40,16,4+overlap),(0,0,(4-overlap)/2));boolean(o,u,'UNION')
    # Four triangular ribs reinforce the ear roots without obstructing the
    # axle or the outer-face nut loading path. Rib tips terminate inside
    # the 12 mm ear width, avoiding thin exposed fins along their tapered tips.
    for sx in [-1,1]:
        for sy in [-1,1]:
            triangle=[(sx*8.1,-.4),(sx*16,-.4),(sx*8.1,8.5)]
            rib=prism('integral root rib',triangle,sy*5.15-p['hinge_root_rib']/2,sy*5.15+p['hinge_root_rib']/2)
            # prism XY represents local XZ; its extrusion is local Y.
            rib.data.transform(Matrix(((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1))))
            clean(rib);boolean(o,rib,'UNION')
    boolean(o,cyl('M4 axle clearance',4.4,outer+4,(0,0,pivot),'X'))
    boolean(o,cyl('M4 captive hex',7.3*2/math.sqrt(3),3.25,
                  (outer/2-1.6,0,pivot),'X',6))
    # Bake construction translations into the local master before instancing.
    o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
    clean(o)
    o.data.name='INTEGRAL_HINGE_MASTER_MESH'
    return o


def build_stand(p,d):
    x,py,pz,L=d['hinge_x'],d['hinge_y'],d['hinge_z'],d['stand_length']
    o=box('U stand crossbar',(2*x+6,7,8),(0,py-L+3.5,pz))
    for sx in [-1,1]:
        boolean(o,box('stand arm',(6,L-3,8),(sx*x,py-(L-3)/2,pz)),'UNION')
        boolean(o,cyl('stand pivot hub',12,6,(sx*x,py,pz),'X'),'UNION')
        boolean(o,cyl('stand axle hole',4.4,10,(sx*x,py,pz),'X'))
    pivot=Vector((0,py,pz))
    mat=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(-p['stand_angle']),4,'X')@Matrix.Translation(-pivot)
    o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
    o.data.transform(mat)
    o['stand_pivot']=list(pivot);o['stand_angle']=p['stand_angle']
    finish(o,'14_U_STAND','stand','Two-arm adjustable support; loosen/tighten both M4 hinge screws',(0,-12,105))


def add_visual(o,mat):
    o.data.materials.append(MATS[mat]);o['printable']=False
    VISUALS.append(o)
    return o


def visuals(p,d):
    add_visual(box('PHOTO_PLACEHOLDER_NOT_FOR_PRINT',
                   (d['photo_w'],d['photo_h'],p['preview_thickness']),
                   (0,0,d['seat']+p['preview_thickness']/2)),'photo')
    for i,y in enumerate([-d['led_row_y'],0,d['led_row_y']],1):
        length=d['led_center_length'] if y==0 else d['led_length']
        dims=(p['led_width'],length,p['led_thickness']) if d['led_vertical'] else (length,p['led_width'],p['led_thickness'])
        center=(y,0,d['led_floor']-p['led_thickness']/2) if d['led_vertical'] else (0,y,d['led_floor']-p['led_thickness']/2)
        add_visual(box(f'LED_{i}_NOT_FOR_PRINT',dims,center),'led')


def mesh_report(o):
    bm=bmesh.new();bm.from_mesh(o.data)
    nonmanifold=sum(not e.is_manifold for e in bm.edges)
    volume=bm.calc_volume(signed=True)
    pending=set(bm.verts);components=0
    while pending:
        components+=1;stack=[pending.pop()]
        while stack:
            v=stack.pop()
            for e in v.link_edges:
                n=e.other_vert(v)
                if n in pending:pending.remove(n);stack.append(n)
    bm.free()
    vv=[o.matrix_world@v.co for v in o.data.vertices]
    lo=[min(v[k] for v in vv) for k in range(3)];hi=[max(v[k] for v in vv) for k in range(3)]
    return dict(name=o.name,vertices=len(vv),faces=len(o.data.polygons),
                nonmanifold_edges=nonmanifold,components=components,volume_mm3=round(volume,4),
                bounds_mm=[[round(x,5) for x in lo],[round(x,5) for x in hi]],
                size_mm=[round(hi[k]-lo[k],5) for k in range(3)])


def write_stl(o,path,matrix=None):
    m=matrix if matrix is not None else o.matrix_world
    def cross64(points):
        u=[float(points[1][k])-float(points[0][k]) for k in range(3)]
        v=[float(points[2][k])-float(points[0][k]) for k in range(3)]
        return (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    # Keep valid native facets. For an ngon whose tessellation has a collinear
    # triangle, use a constrained triangulation that retains every boundary
    # vertex/edge. Deleting those vertices can create nonmanifold T junctions.
    mesh=o.data;mesh.calc_loop_triangles()
    native=[tuple(m@mesh.vertices[i].co for i in tri.vertices) for tri in mesh.loop_triangles]
    bad_faces={mesh.loop_triangles[i].polygon_index for i,v in enumerate(native)
               if math.sqrt(sum(x*x for x in cross64(v)))/2<1e-10}
    triangles=[v for i,v in enumerate(native) if mesh.loop_triangles[i].polygon_index not in bad_faces]
    normal_matrix=m.to_3x3().inverted().transposed()
    for index in sorted(bad_faces):
        poly=mesh.polygons[index]
        points=[m@mesh.vertices[i].co for i in poly.vertices]
        normal=(normal_matrix@poly.normal).normalized()
        drop=max(range(3),key=lambda k:abs(normal[k]));axes=[k for k in range(3) if k!=drop]
        origin=points[0]
        projected=[Vector((v[axes[0]]-origin[axes[0]],v[axes[1]]-origin[axes[1]])) for v in points]
        area=sum(projected[i].x*projected[(i+1)%len(points)].y-projected[(i+1)%len(points)].x*projected[i].y for i in range(len(points)))
        if area<0:points.reverse();projected.reverse()
        count=len(points)
        coords,edges,faces,orig,_,_=delaunay_2d_cdt(projected,
            [(i,(i+1)%count) for i in range(count)],[list(range(count))],1,1e-7)
        if any(not ids for ids in orig):
            raise RuntimeError('Unexpected new intersection in STL face: '+o.name)
        mapped=[points[ids[0]] for ids in orig]
        for face in faces:
            if len(face)!=3:raise RuntimeError('Nontriangular constrained STL output')
            vs=tuple(mapped[i] for i in face);cross=cross64(vs)
            if sum(cross[k]*normal[k] for k in range(3))<0:vs=(vs[0],vs[2],vs[1])
            triangles.append(vs)
    if any(math.sqrt(sum(x*x for x in cross64(v)))/2<1e-10 for v in triangles):
        raise RuntimeError('Degenerate STL triangle remains: '+o.name)
    with open(path,'wb') as f:
        f.write(b'Blender parametric frame | mm | one printable part'.ljust(80,b' '))
        f.write(struct.pack('<I',len(triangles)))
        for vs in triangles:
            cross=cross64(vs);length=math.sqrt(sum(x*x for x in cross))
            normal=tuple(x/length for x in cross)
            f.write(struct.pack('<12fH',*normal,*vs[0],*vs[1],*vs[2],0))


def flat_matrix(o,d):
    # Export local print coordinates; render bevel is intentionally excluded.
    mat=o.matrix_world.copy()
    if o.name=='14_U_STAND':
        pivot=Vector(o['stand_pivot'])
        mat=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(o['stand_angle']),4,'X')@Matrix.Translation(-pivot)@mat
        # Stand prints on its broad XY face after undoing the pose.
    # Integral back tray now prints with its planar LED face towards the bed,
    # and all four hinge groups growing upward. Recesses still need a slicer
    # support/bridge decision; do not put the hinge tips on the build plate.
    vs=[mat@v.co for v in o.data.vertices]
    lo=Vector(tuple(min(v[i] for v in vs) for i in range(3)))
    return Matrix.Translation(-lo)@mat


def setup_scene(scene):
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001
    scene.unit_settings.length_unit='MILLIMETERS'
    scene.render.engine='CYCLES';scene.cycles.samples=40
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1500;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
    world=bpy.data.worlds.new(scene.name+'_World');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.59,.63,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.6
    scene.world=world
    scene.view_settings.view_transform='AgX'


def camera_for(scene,position,target,ortho):
    data=bpy.data.cameras.new('Camera_'+scene.name);data.type='ORTHO';data.ortho_scale=ortho
    o=bpy.data.objects.new(data.name,data);scene.collection.objects.link(o)
    o.location=position
    back=(o.location-Vector(target)).normalized()
    up_hint=Vector((0,1,0))
    if abs(back.dot(up_hint))>.99:up_hint=Vector((0,0,1))
    right=up_hint.cross(back).normalized();up=back.cross(right).normalized()
    o.rotation_euler=Matrix(((right.x,up.x,back.x),(right.y,up.y,back.y),(right.z,up.z,back.z))).to_euler()
    scene.camera=o
    return o


def fit_camera(scene,items,margin=1.18):
    previous=bpy.context.window.scene if bpy.context.window else None
    if previous:bpy.context.window.scene=scene
    bpy.context.view_layer.update()
    cam=scene.camera;rotation=cam.rotation_euler.to_matrix()
    right=rotation.col[0];up=rotation.col[1]
    vv=[o.matrix_world@v.co for o in items for v in o.data.vertices]
    xx=[v.dot(right) for v in vv];yy=[v.dot(up) for v in vv]
    cx=(min(xx)+max(xx))/2;cy=(min(yy)+max(yy))/2
    cam.location+=right*(cx-cam.location.dot(right))+up*(cy-cam.location.dot(up))
    aspect=scene.render.resolution_x/scene.render.resolution_y
    cam.data.ortho_scale=max(max(xx)-min(xx),(max(yy)-min(yy))*aspect)*margin
    if previous:bpy.context.window.scene=previous


def alternate_stand_matrix(d):
    old=Vector((0,d['hinge_y'],d['hinge_z']))
    new=Vector((d['alternate_pivot_x'],0,d['hinge_z']))
    return Matrix.Translation(new)@Matrix.Rotation(-math.pi/2,4,'Z')@Matrix.Translation(-old)


def lights_for(scene,target,scale):
    for i,(offset,power,size) in enumerate([((-1,1,-1.5),1200,1.3),((1.4,0,-.5),800,1),((0,.7,1.5),1600,1.1)]):
        ld=bpy.data.lights.new(f'{scene.name}_Softbox_{i}','AREA')
        # millimetre coordinates / physical inverse-square lighting
        ld.energy=power*1000;ld.shape='DISK';ld.size=scale*size
        o=bpy.data.objects.new(ld.name,ld);scene.collection.objects.link(o)
        o.location=Vector(target)+Vector(offset)*scale
        o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()


def make_review_scene(name,items,p,d,mode):
    scene=bpy.data.scenes.new(name);setup_scene(scene)
    for original in items:
        o=original.copy();o.data=original.data;scene.collection.objects.link(o)
        if mode=='explode':
            o.location+=Vector(original.get('explode',(0,0,0)))
            if not original.get('printable',False):
                if original.name.startswith('PHOTO'):o.location.z-=22
                elif original.name.startswith('LED'):o.location.z+=65
        if mode=='layout':
            o.matrix_world=flat_matrix(original,d)
        if mode=='alternate':
            if 'HINGE_' in original.name or original.name=='14_U_STAND':
                o.matrix_world=alternate_stand_matrix(d)@original.matrix_world
            # Rotate whole physical frame, so its alternate bottom is at -Y.
            o.matrix_world=Matrix.Rotation(math.pi/2,4,'Z')@o.matrix_world
    maxdim=max(p['width'],p['height'])
    if mode=='explode':
        camera_for(scene,(maxdim*1.25,maxdim*1.0,maxdim*1.6),(0,0,45),maxdim*1.9)
        lights_for(scene,(0,0,40),maxdim*1.5)
    elif mode in ['rear','alternate']:
        camera_for(scene,(maxdim*.9,maxdim*.7,maxdim*1.6),(0,0,d['depth']+18),maxdim*1.6)
        lights_for(scene,(0,0,25),maxdim*1.5)
    elif mode=='led':
        camera_for(scene,(maxdim*.35,maxdim*.25,-maxdim*1.7),(0,0,d['back_front']),maxdim*1.5)
        lights_for(scene,(0,0,25),maxdim*1.5)
    elif mode=='layout':
        x=y=0;row_h=0;maxw=maxdim*2.4
        for o in [ob for ob in scene.objects if ob.type=='MESH']:
            vv=[o.matrix_world@v.co for v in o.data.vertices]
            sx=max(v.x for v in vv)-min(v.x for v in vv);sy=max(v.y for v in vv)-min(v.y for v in vv)
            if x+sx>maxw:x=0;y+=row_h+12;row_h=0
            o.location+=Vector((x,y,0));x+=sx+12;row_h=max(row_h,sy)
        totalh=y+row_h
        camera_for(scene,(maxw/2,totalh/2,600),(maxw/2,totalh/2,0),max(maxw,totalh*1.4)*1.05)
        lights_for(scene,(maxw/2,totalh/2,0),maxw*1.5)
    fit_camera(scene,[ob for ob in scene.objects if ob.type=='MESH'])
    return scene


def embed_source(out):
    src=Path(__file__) if '__file__' in globals() else None
    if src and src.exists():
        t=bpy.data.texts.get('hi3d-frame-builder-1.py') or bpy.data.texts.new('hi3d-frame-builder-1.py')
        t.clear();t.write(src.read_text(encoding='utf-8'))
    t=bpy.data.texts.get('00_READ_ME') or bpy.data.texts.new('00_READ_ME')
    t.clear();t.write('参数化相框 / Parametric lithophane frame\n\n'
        '1. 在 Scripting 工作区打开 hi3d-frame-builder-1.py，按 Run Script。\n'
        '2. 回到 3D View，按 N，在 Litho Frame 面板修改参数。\n'
        '3. Rebuild 更新模型；Export 导出 STL、尺寸表和 blend。\n'
        '4. 场景切换：01_ASSEMBLY / 02_EXPLODED / 03_REAR / 04_PRINT_LAYOUT / 05_LED_TRAY / 06_ALTERNATE。\n'
        '照片和 LED 仅占位，不在 STL 内；所有尺寸为 mm。\n'
        'V5：背板用四颗金属 M3×8 和四颗 M3 螺母固定；已取消两片转扣及对应柱、缺口。\n'
        'V5.1：压条螺丝头和内六角长腿从背面直达；先拆下 LED 背板再调整压条。\n'
        '普通修改参数后必须点 Rebuild；仅改变面板数值不会自动重建。\n'
        f'Output folder: {out}\n')


def generate(p, output=None, reviews=True):
    global WORK
    d=derived(p)
    PARTS.clear();VISUALS.clear()
    # Only remove this tool's generated scenes/collections.
    keep=bpy.context.scene
    if bpy.context.window:
        bpy.context.window.scene=keep
    for scene in list(bpy.data.scenes):
        if scene!=keep and scene.get('litho_generated'):bpy.data.scenes.remove(scene)
    for o in list(bpy.data.objects):
        if o.get('litho_generated'):bpy.data.objects.remove(o,do_unlink=True)
    keep.name='01_ASSEMBLY';keep['litho_generated']=True
    # On the first command-line run remove Blender's untouched startup objects.
    if not bpy.data.collections.get('LITHO_GENERATED'):
        for o in list(keep.objects):
            if o.name in {'Cube','Camera','Light'}:bpy.data.objects.remove(o,do_unlink=True)
    WORK=bpy.data.collections.get('LITHO_GENERATED') or bpy.data.collections.new('LITHO_GENERATED')
    if WORK.name not in keep.collection.children:keep.collection.children.link(WORK)
    materials()
    screw_points=build_rails(p,d)
    build_clamps(p,d);build_back(p,d,screw_points);build_stand(p,d)
    visuals(p,d)
    for o in list(keep.objects):o['litho_generated']=True
    setup_scene(keep)
    maxdim=max(p['width'],p['height'])
    camera_for(keep,(maxdim*.45,maxdim*.28,-maxdim*1.8),(0,0,15),maxdim*1.52)
    lights_for(keep,(0,0,15),maxdim*1.5)
    fit_camera(keep,PARTS+VISUALS)
    for o in keep.objects:o['litho_generated']=True
    if reviews:
        for name,items,mode in [('02_EXPLODED',PARTS+VISUALS,'explode'),
                                 ('03_REAR',PARTS,'rear'),('04_PRINT_LAYOUT',PARTS,'layout'),
                                 ('05_LED_TRAY',[o for o in PARTS if o.name=='11_BACK_LED_TRAY']+[o for o in VISUALS if o.name.startswith('LED')],'led'),
                                 ('06_ALTERNATE',PARTS,'alternate')]:
            sc=make_review_scene(name,items,p,d,mode);sc['litho_generated']=True
            for o in sc.objects:o['litho_generated']=True
    keep['parameters_json']=json.dumps(p)
    keep['dimensions_json']=json.dumps(d)
    reports=[mesh_report(o) for o in PARTS]
    failures=[r['name'] for r in reports if r['nonmanifold_edges'] or r['components']!=1 or r['volume_mm3']<=0]
    if failures:raise RuntimeError('Invalid printable meshes: '+json.dumps([r for r in reports if r['name'] in failures]))
    if output:
        export_all(output,p,d,reports)
    return d,reports


def export_all(output,p,d,reports=None):
    out=Path(output).expanduser().resolve()
    for folder in ['STL','checks','configs','previews']: (out/folder).mkdir(parents=True,exist_ok=True)
    export_groups={}
    for o in PARTS:
        stem=o.get('export_stem',o.name)
        if not stem.startswith('hi3d-'):stem='hi3d-'+stem
        export_groups.setdefault(stem,[]).append(o)
    for stem,occurrences in export_groups.items():
        o=occurrences[0]
        write_stl(o,out/'STL'/f'{stem}.stl',flat_matrix(o,d))
    with open(out/'hi3d-打印清单.csv','w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['STL文件','打印数量','装配实例'])
        for stem,occurrences in export_groups.items():
            writer.writerow([stem+'.stl',len(occurrences),' / '.join(o.name for o in occurrences)])
    (out/'configs'/'hi3d-current.json').write_text(json.dumps(p,indent=2),encoding='utf-8')
    if reports is None:reports=[mesh_report(o) for o in PARTS]
    (out/'checks'/'hi3d-blender-mesh-checks.json').write_text(json.dumps(dict(parameters=p,dimensions=d,parts=reports),indent=2),encoding='utf-8')
    rows=[]
    presets=list(dict.fromkeys([(p['width'],p['height']),(150,100),(100,150),(180,130),(200,150),(250,200)]))
    for w,h in presets:
        q={**p,'width':w,'height':h};v=derived(q)
        rows.append([w,h,p['border'],v['photo_w'],v['photo_h'],v['window_w'],v['window_h'],
                     p['panel_min'],p['panel_max'],v['slot_width'],round(v['depth'],2),v['led_length'],v['led_center_length']])
    with open(out/'hi3d-尺寸对照表.csv','w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['外框宽mm','外框高mm','边框宽mm','浮雕板成品宽mm','浮雕板成品高mm',
                    '可视宽mm','可视高mm','最小板厚mm','最大板厚mm','导槽宽mm','框体深mm','外侧两段LED长度mm','中间LED长度mm']);writer.writerows(rows)
    embed_source(out)
    # Save viewport focused on assembly. Parameters are also stored on the scene.
    scene=bpy.data.scenes['01_ASSEMBLY']
    if bpy.context.window:bpy.context.window.scene=scene
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=max(p['width'],p['height'])*1.9
            area.spaces.active.region_3d.view_location=Vector((0,0,18))
            area.spaces.active.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion()
            area.spaces.active.clip_end=10000
            area.spaces.active.shading.type='MATERIAL'
    blend_name=f"hi3d-相框_{p['width']:g}x{p['height']:g}_参数化.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out/blend_name))
    # Export a correctly scaled GLB for quick viewing (glTF uses metres).
    bpy.ops.object.select_all(action='DESELECT')
    temporary=[];temporary_data={}
    for original in PARTS+VISUALS:
        key=original.data.as_pointer()
        if key not in temporary_data:temporary_data[key]=original.data.copy()
        o=bpy.data.objects.new('GLB_'+original.name,temporary_data[key]);scene.collection.objects.link(o)
        o.matrix_world=Matrix.Scale(.001,4)@original.matrix_world
        o['sparc3dPhysicalUnits']={'version':1,'unit':'meter'}
        o.select_set(True);temporary.append(o)
    # Temporary nodes already convert mm coordinates to metres. Avoid a second
    # scene-unit conversion in glTF exporters that apply scale_length.
    original_unit_scale=scene.unit_settings.scale_length
    scene.unit_settings.scale_length=1.0
    try:
        bpy.ops.export_scene.gltf(filepath=str(out/'hi3d-assembly.glb'),export_format='GLB',use_selection=True,
            use_active_scene=True,export_cameras=False,export_lights=False,
            export_yup=True,export_extras=True)
    finally:
        scene.unit_settings.scale_length=original_unit_scale
        for o in temporary:bpy.data.objects.remove(o,do_unlink=True)
    print('FRAME_EXPORT_OK',json.dumps(d),flush=True)


class LITHO_Properties(bpy.types.PropertyGroup):
    width: FloatProperty(name='外框宽 / Width',default=150,min=100,max=500)
    height: FloatProperty(name='外框高 / Height',default=100,min=100,max=500)
    border: FloatProperty(name='正面边宽 / Border',default=10,min=10,max=26)
    preview_thickness: FloatProperty(name='板厚预览 / Preview',default=2.25,min=1.5,max=3)
    light_gap: FloatProperty(name='灯距 / Gap',default=25,min=25,max=60)
    led_width: FloatProperty(name='LED 宽 / Width',default=8,min=5,max=10)
    stand_angle: FloatProperty(name='支架展开角 / Open',default=35,min=25,max=55)
    output: StringProperty(name='输出目录 / Folder',subtype='DIR_PATH')
    preset: EnumProperty(name='预设 / Preset',items=[('150x100','150 × 100',''),('100x150','100 × 150',''),
                ('180x130','180 × 130',''),('200x150','200 × 150',''),('250x200','250 × 200','')])


def ui_parameters(context):
    props=context.scene.litho_frame
    p={**DEFAULT}
    raw=context.scene.get('parameters_json')
    if raw:p.update(json.loads(raw))
    for key in ['width','height','border','preview_thickness','light_gap','led_width','stand_angle']:
        p[key]=getattr(props,key)
    p['led_channel_width']=p['led_width']+1
    return p


class LITHO_OT_Preset(bpy.types.Operator):
    bl_idname='litho.preset';bl_label='Use preset / 使用预设'
    def execute(self,context):
        props=context.scene.litho_frame
        props.width,props.height=map(float,props.preset.split('x'))
        return {'FINISHED'}


class LITHO_OT_Rebuild(bpy.types.Operator):
    bl_idname='litho.rebuild';bl_label='Rebuild / 重建模型';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        try:generate(ui_parameters(context),reviews=True)
        except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
        return {'FINISHED'}


class LITHO_OT_Export(bpy.types.Operator):
    bl_idname='litho.export';bl_label='Export / 重建并导出'
    def execute(self,context):
        out=context.scene.litho_frame.output or str(Path(bpy.data.filepath).parent)
        try:generate(ui_parameters(context),output=out,reviews=True)
        except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
        return {'FINISHED'}


class LITHO_PT_Panel(bpy.types.Panel):
    bl_label='Lithophane Lightbox / 浮雕灯箱';bl_idname='LITHO_PT_panel'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Litho Frame'
    def draw(self,context):
        layout=self.layout;props=context.scene.litho_frame
        layout.prop(props,'preset');layout.operator('litho.preset')
        for k in ['width','height','border','preview_thickness','light_gap','led_width','stand_angle']:layout.prop(props,k)
        try:
            p=ui_parameters(context);d=derived(p)
            layout.label(text=f"浮雕板 {d['photo_w']:.1f} × {d['photo_h']:.1f} mm")
            layout.label(text=f"可视 {d['window_w']:.1f} × {d['window_h']:.1f} mm")
            layout.label(text=f"兼容 1.5–3 mm | 导槽 {d['slot_width']:.1f}")
        except Exception as e:layout.label(text=str(e),icon='ERROR')
        layout.operator('litho.rebuild');layout.prop(props,'output');layout.operator('litho.export')


CLASSES=[LITHO_Properties,LITHO_OT_Preset,LITHO_OT_Rebuild,LITHO_OT_Export,LITHO_PT_Panel]


def register():
    if hasattr(bpy.types.Scene,'litho_frame'):del bpy.types.Scene.litho_frame
    for cls in reversed(CLASSES):
        old=getattr(bpy.types,cls.__name__,None)
        if old:
            try:bpy.utils.unregister_class(old)
            except RuntimeError:pass
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.Scene.litho_frame=PointerProperty(type=LITHO_Properties)
    for scene in bpy.data.scenes:
        raw=scene.get('parameters_json')
        if raw:
            p=json.loads(raw)
            for k in ['width','height','border','preview_thickness','light_gap','led_width','stand_angle']:
                setattr(scene.litho_frame,k,p[k])
        if bpy.data.filepath:scene.litho_frame.output=str(Path(bpy.data.filepath).parent)


def unregister():
    if hasattr(bpy.types.Scene,'litho_frame'):del bpy.types.Scene.litho_frame
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)


if __name__=='__main__':
    register()
    if bpy.app.background and '--' in sys.argv:
        import argparse
        parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--config')
        parser.add_argument('--render',action='store_true');parser.add_argument('--no-reviews',action='store_true')
        args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
        p={**DEFAULT}
        if args.config:p.update(json.loads(Path(args.config).read_text(encoding='utf-8')))
        d,reports=generate(p,args.out,not args.no_reviews)
        # Persist editable UI values after geometry generation.
        for k in ['width','height','border','preview_thickness','light_gap','led_width','stand_angle']:
            setattr(bpy.data.scenes['01_ASSEMBLY'].litho_frame,k,p[k])
        bpy.data.scenes['01_ASSEMBLY'].litho_frame.output=str(Path(args.out).resolve())
        blend_name=f"hi3d-相框_{p['width']:g}x{p['height']:g}_参数化.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.out).resolve()/blend_name))
        if args.render:
            for name,filename in [('01_ASSEMBLY','hi3d-front.png'),('02_EXPLODED','hi3d-exploded.png'),
                                  ('03_REAR','hi3d-rear.png'),('04_PRINT_LAYOUT','hi3d-parts.png'),('05_LED_TRAY','hi3d-led-tray.png'),('06_ALTERNATE','hi3d-portrait.png')]:
                sc=bpy.data.scenes.get(name)
                if sc:
                    sc.render.filepath=str(Path(args.out).resolve()/'previews'/filename)
                    bpy.ops.render.render(write_still=True,scene=sc.name)
