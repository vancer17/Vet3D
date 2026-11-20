"""Run inside Blender after opening the generated .blend. No mutation is saved."""
import bpy, bmesh, json, math, importlib.util
from pathlib import Path
from mathutils import Matrix, Vector

ROOT=Path(bpy.data.filepath).parent
scene=bpy.data.scenes['01_ASSEMBLY']
bpy.context.window.scene=scene
p=json.loads(scene['parameters_json']);d=json.loads(scene['dimensions_json'])
parts=[o for o in scene.objects if o.type=='MESH' and o.get('printable')]
photo=next(o for o in scene.objects if o.name.startswith('PHOTO_PLACEHOLDER'))
leds=[o for o in scene.objects if o.name.startswith('LED_')]
work=bpy.data.collections.new('TEMP_VALIDATION');scene.collection.children.link(work)

def volume(o):
    bm=bmesh.new();bm.from_mesh(o.data);v=abs(bm.calc_volume(signed=True));bm.free();return v

def intersection(a,b):
    # Engineering meshes only, excluding the render bevels.
    bpy.context.view_layer.update()
    aa=bpy.data.objects.new('temp_intersection',a.data.copy());work.objects.link(aa)
    aa.data.transform(a.matrix_world);aa.matrix_world=Matrix.Identity(4)
    bb=bpy.data.objects.new('temp_cutter',b.data.copy());work.objects.link(bb)
    bb.data.transform(b.matrix_world);bb.matrix_world=Matrix.Identity(4)
    bpy.context.view_layer.objects.active=aa
    mod=aa.modifiers.new('intersection','BOOLEAN');mod.solver='EXACT';mod.operation='INTERSECT';mod.object=bb
    bpy.ops.object.modifier_apply(modifier=mod.name)
    result=volume(aa)
    bpy.data.objects.remove(aa,do_unlink=True);bpy.data.objects.remove(bb,do_unlink=True)
    return result

def bounds(o):
    bpy.context.view_layer.update()
    vv=[o.matrix_world@v.co for v in o.data.vertices]
    return [min(v[k] for v in vv) for k in range(3)],[max(v[k] for v in vv) for k in range(3)]

def may_overlap(a,b):
    lo,hi=bounds(a);ll,hh=bounds(b)
    return all(min(hi[k],hh[k])-max(lo[k],ll[k])>.0001 for k in range(3))

result={'units':'mm','pair_intersection_tolerance_mm3':0.02,'parts':len(parts),
        'interferences':[],'pair_tests':0,'panel_tests':[],'led_tests':[],'stand_tests':[],
        'clamp_endpoint_tests':[],'alternate_stand_tests':[], 'revision_checks':{}}
for i,a in enumerate(parts):
    for b in parts[i+1:]:
        if may_overlap(a,b):
            v=intersection(a,b);result['pair_tests']+=1
            if v>.02:result['interferences'].append([a.name,b.name,round(v,5)])
for led in leds:
    for part in parts:
        if may_overlap(led,part):
            v=intersection(led,part)
            result['led_tests'].append([led.name,part.name,round(v,5)])
            if v>.02:result['interferences'].append([led.name,part.name,round(v,5)])

# Verify both thickness endpoints and insertion path with top rail and clamps removed.
rails=[o for o in parts if 'RAIL_' in o.name]
original=photo.matrix_world.copy();original_mesh=photo.data
bars=[o for o in parts if 'PRESSURE_BAR' in o.name]
bar_locations=[o.location.copy() for o in bars]
for t in [1.5,3.0]:
    photo.data=original_mesh.copy()
    for v in photo.data.vertices:v.co.z*=t/p['preview_thickness']
    photo.data.update()
    photo.location.z=d['seat']+t/2
    photo.location.y=0
    for bar,loc in zip(bars,bar_locations):bar.location.z=loc.z+t-p['preview_thickness']
    endpoint=[]
    for a in [photo]+bars:
        for b in parts:
            if a==b or (a in bars and b in bars):continue
            if may_overlap(a,b):
                v=intersection(a,b)
                if v>.02:endpoint.append([a.name,b.name,round(v,5)])
    result['clamp_endpoint_tests'].append({'thickness':t,'collisions':endpoint})
    for dy in [0, d['photo_h']*.25, d['photo_h']*.5, d['photo_h'], d['photo_h']+15]:
        photo.location.y=dy
        collisions=[]
        for rail in rails:
            if 'TOP' in rail.name:continue
            if may_overlap(photo,rail):
                v=intersection(photo,rail)
                if v>.02:collisions.append([rail.name,v])
        result['panel_tests'].append({'thickness':t,'slide_offset_y':dy,'collisions':collisions})
    photo.data=original_mesh;photo.matrix_world=original
for bar,loc in zip(bars,bar_locations):bar.location=loc

# The U stand must clear the brackets and back plate across its operating range.
stand=next(o for o in parts if o.name=='14_U_STAND')
orig=stand.data.copy();pivot=Vector(stand['stand_pivot'])
others=[o for o in parts if o!=stand]
for angle in [0,25,35,45,55]:
    stand.data=orig.copy()
    mat=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(p['stand_angle']-angle),4,'X')@Matrix.Translation(-pivot)
    stand.data.transform(mat)
    collisions=[]
    for other in others:
        if may_overlap(stand,other):
            v=intersection(stand,other)
            if v>.02:collisions.append([other.name,round(v,5)])
    result['stand_tests'].append({'open_angle_deg':angle,'collisions':collisions})
    if angle:
        # Solve contact of the actual lower crossbar surface with the table.
        vv=[stand.matrix_world@v.co for v in stand.data.vertices]
        def height(alpha):
            return min((v.y+p['height']/2)*math.cos(alpha)+(d['depth']-v.z)*math.sin(alpha) for v in vv)
        low,high=0,math.radians(70)
        for _ in range(60):
            mid=(low+high)/2
            if height(mid)>0:low=mid
            else:high=mid
        result['stand_tests'][-1]['frame_lean_from_vertical_deg']=round(math.degrees((low+high)/2),2)
stand.data=orig
# Alternate stand axes are integral to the same back tray; only the stand moves.
original_stand_matrix=stand.matrix_world.copy()
alt=Matrix.Translation(Vector((d['alternate_pivot_x'],0,d['hinge_z'])))@Matrix.Rotation(-math.pi/2,4,'Z')@Matrix.Translation(-pivot)
stand.matrix_world=alt@original_stand_matrix
for angle in [0,25,35,45,55]:
    stand.data=orig.copy()
    mat=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(p['stand_angle']-angle),4,'X')@Matrix.Translation(-pivot)
    stand.data.transform(mat)
    collisions=[]
    for other in parts:
        if other==stand:continue
        if may_overlap(stand,other):
            v=intersection(stand,other)
            if v>.02:collisions.append([stand.name,other.name,round(v,5)])
    result['alternate_stand_tests'].append({'open_angle_deg':angle,'collisions':collisions})
stand.matrix_world=original_stand_matrix;stand.data=orig
tray=next(o for o in parts if o.name=='11_BACK_LED_TRAY')
bm=bmesh.new();bm.from_mesh(tray.data)
integral_manifold=all(e.is_manifold for e in bm.edges)
pending=set(bm.verts);count=0
while pending:
    count+=1;stack=[pending.pop()]
    while stack:
        vert=stack.pop()
        for edge in vert.link_edges:
            nxt=edge.other_vert(vert)
            if nxt in pending:pending.remove(nxt);stack.append(nxt)
bm.free()
integral_pass=integral_manifold and count==1 and tray.get('integral_hinges')==4
result['revision_checks']['integral_back_tray']={'components':count,'manifold':integral_manifold,
    'fixed_hinge_groups':tray.get('integral_hinges'),'nominal_fusion_overlap_mm':tray.get('hinge_fuse_overlap_mm'),
    'separate_fixed_hinge_objects':len([o for o in parts if 'HINGE_' in o.name]),'pass':integral_pass}

# Clearance envelopes are test geometry only, not printable hardware models.
fastener_checks=[]
for i,entry in enumerate(json.loads(tray['integral_mounts_json'])):
    placement=Matrix(entry['placement'])
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=4,depth=4)
    head=bpy.context.object
    head.matrix_world=placement@Matrix.Translation(Vector((-p['hinge_slot']/2-p['hinge_ear_thickness']-2,0,11)))@Matrix.Rotation(math.pi/2,4,'Y')
    head_volume=intersection(head,tray)
    bpy.data.objects.remove(head,do_unlink=True)
    bpy.ops.mesh.primitive_cylinder_add(vertices=6,radius=7/math.sqrt(3),depth=3.2)
    nut=bpy.context.object
    nut.matrix_world=placement@Matrix.Translation(Vector(((p['hinge_slot']+2*p['hinge_ear_thickness'])/2-1.6,0,11)))@Matrix.Rotation(math.pi/2,4,'Y')
    nut_volume=intersection(nut,tray)
    bpy.data.objects.remove(nut,do_unlink=True)
    fastener_checks.append({'mount':i,'head_D8_L4_overlap_mm3':round(head_volume,6),'nut_AF7_T3_2_overlap_mm3':round(nut_volume,6)})
fastener_pass=all(x['head_D8_L4_overlap_mm3']<=.02 and x['nut_AF7_T3_2_overlap_mm3']<=.02 for x in fastener_checks)
result['revision_checks']['M4_fastener_clearance']={'checks':fastener_checks,'pass':fastener_pass}

# Verify the real four M3 fixing paths, captured nuts and head retention.
builder_source=ROOT/'src'/'hi3d-frame-builder-1.py'
if not builder_source.exists():builder_source=ROOT/'hi3d-frame-builder-1.py'
spec=importlib.util.spec_from_file_location('v5_check_builder',builder_source)
fb=importlib.util.module_from_spec(spec);spec.loader.exec_module(fb)
fb.WORK=work
fixings=[]
tray_original=tray.matrix_world.copy()
for x,y,nx,ny,owner in fb.back_screw_specs(p):
    rail=next(o for o in rails if owner in o.name)
    under_head=d['depth']-1.825
    shaft=fb.cyl('M3x8 shaft envelope',3.0,8,(x,y,under_head-4))
    head=fb.cyl('M3 head D5.5 H3 envelope',5.5,3,(x,y,under_head+1.5))
    nut=fb.cyl('M3 nut AF5.5 T2.4 envelope',5.5*2/math.sqrt(3),2.4,
               (x,y,d['back_front']-3.5),vertices=6,phase=30 if nx else 0)
    shaft_overlap=sum(intersection(shaft,o) for o in [rail,tray])
    head_overlap=sum(intersection(head,o) for o in [rail,tray])
    nut_overlap=intersection(nut,rail)
    nut_original=nut.matrix_world.copy()
    insertion=[]
    for delta in [8,6,4,2,0]:
        nut.matrix_world=Matrix.Translation(Vector((nx*delta,ny*delta,0)))@nut_original
        insertion.append({'inward_offset_mm':delta,'overlap_mm3':round(intersection(nut,rail),6)})
    nut.matrix_world=Matrix.Translation(Vector((0,0,.5)))@nut_original
    captured_overlap=intersection(nut,rail)
    nut.matrix_world=nut_original
    tray.matrix_world=Matrix.Translation(Vector((0,0,.5)))@tray_original
    head_stop_overlap=intersection(head,tray)
    tray.matrix_world=tray_original
    lo,hi=bounds(nut)
    engagement=max(0,min(under_head,hi[2])-max(under_head-8,lo[2]))
    passed=shaft_overlap<=.02 and head_overlap<=.02 and nut_overlap<=.02 and all(t['overlap_mm3']<=.02 for t in insertion) and captured_overlap>.02 and head_stop_overlap>.02 and engagement>=2.39
    fixings.append({'xy_mm':[x,y],'owner':rail.name,'shaft_overlap_mm3':round(shaft_overlap,6),
        'head_overlap_mm3':round(head_overlap,6),'nut_overlap_mm3':round(nut_overlap,6),
        'nut_loading_path':insertion,'nut_axial_lift_0_5_contact_mm3':round(captured_overlap,6),
        'tray_lift_0_5_head_contact_mm3':round(head_stop_overlap,6),
        'nominal_nut_engagement_mm':round(engagement,4),'pass':passed})
    for ob in [shaft,head,nut]:bpy.data.objects.remove(ob,do_unlink=True)
fixing_pass=len(fixings)==4 and all(t['pass'] for t in fixings)
result['revision_checks']['four_M3_back_fixings']={'checks':fixings,'pass':fixing_pass,
    'scope':'geometric envelopes and capture; not a physical load or thread test'}

# The shared hex-slot orientation also applies to the photo pressure nuts.
pressure_nuts=[]
for sx in [-1,1]:
    rail=next(o for o in rails if ('RIGHT' if sx>0 else 'LEFT') in o.name)
    for yy in [-d['clamp_y'],d['clamp_y']]:
        af=4.0 if d['pressure_d']==2 else 5.5
        thick=1.6 if d['pressure_d']==2 else 2.4
        nut=fb.cyl('pressure nut loading envelope',af*2/math.sqrt(3),thick,
            (sx*d['pressure_x'],yy,11+d['pressure_nut_t']/2),vertices=6,phase=30)
        orig_nut=nut.matrix_world.copy();path=[]
        for offset in [7,5,3,1,0]:
            nut.matrix_world=Matrix.Translation(Vector((-sx*offset,0,0)))@orig_nut
            path.append(round(intersection(nut,rail),6))
        pressure_nuts.append({'xy_mm':[sx*d['pressure_x'],yy],'path_overlap_mm3':path,
            'pass':all(v<=.02 for v in path)})
        bpy.data.objects.remove(nut,do_unlink=True)
pressure_nut_pass=all(t['pass'] for t in pressure_nuts)
result['revision_checks']['pressure_nut_loading']={'checks':pressure_nuts,'pass':pressure_nut_pass}

# Both former latch positions must be filled on the tray and free of rail posts.
former=[]
for sx in [-1,1]:
    x,y=fb.canonical_xy(p,sx*(max(p['width'],p['height'])/2-8.5),0)
    probe=fb.box('former latch land probe',(1,1,p['back_thickness']-.2),(x,y,(d['back_front']+d['depth'])/2))
    tray_land=intersection(probe,tray);rail_posts=sum(intersection(probe,o) for o in rails)
    former.append({'xy_mm':[x,y],'tray_land_mm3':round(tray_land,6),'frame_post_mm3':round(rail_posts,6),
                   'pass':tray_land>=p['back_thickness']-.21 and rail_posts<=.02})
    bpy.data.objects.remove(probe,do_unlink=True)
removed_pass=not any('LATCH' in o.name for o in parts) and len(parts)==12 and all(t['pass'] for t in former)
result['revision_checks']['latches_removed_and_tray_restored']={'checks':former,'pass':removed_pass}

# With all four screws removed, the tray must lift straight out.
release_checks=[]
obstacles=[o for o in parts if 'RAIL_' in o.name or 'KEY_' in o.name]
for delta in [0,.5,2,5,10]:
    tray.matrix_world=Matrix.Translation(Vector((0,0,delta)))@tray_original
    collisions=[]
    for other in obstacles:
        if may_overlap(tray,other):
            v=intersection(tray,other)
            if v>.02:collisions.append([other.name,round(v,5)])
    release_checks.append({'tray_lift_z_mm':delta,'collisions':collisions})
tray.matrix_world=tray_original
release_pass=all(not x['collisions'] for x in release_checks)
result['revision_checks']['back_tray_removal']={'screws_removed':4,'lift_checks':release_checks,'pass':release_pass}
result['pass']=not result['interferences'] and all(not t['collisions'] for t in result['panel_tests']+result['stand_tests']+result['clamp_endpoint_tests']+result['alternate_stand_tests']) and integral_pass and fixing_pass and fastener_pass and pressure_nut_pass and removed_pass and release_pass
(ROOT/'checks'/'hi3d-assembly_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
if not result['pass']:raise RuntimeError('Assembly interference check failed')
