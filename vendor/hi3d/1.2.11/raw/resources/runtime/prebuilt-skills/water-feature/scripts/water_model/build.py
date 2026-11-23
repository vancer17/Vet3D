"""Sculptural circulating water feature; all device, water and support geometry is explicit."""
from .product_print import export_parts
from pathlib import Path
import json
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from . import media, validation
from .product_core import active as _g_active, boolean as _g_boolean, clean as _g_clean, copy_obj as _g_copy_obj, cube as _g_cube, cyl as _g_cyl, hollow_pipe as _g_hollow_pipe, lathe as _g_lathe, mat as _g_mat, pipe as _g_pipe
from .product_source import import_source as _g_import_source


def validate_config(config):
    required=['source_width_mm','source_ratio','depth_factor','sculpture_offset_mm','channels','basin_profile_rz_mm','basin_y_factor','supports','pump','hose','waterline_mm','return_volume_ml','hardware_policy','service_offset_mm']
    for key in required:
        if key not in config:raise ValueError('Missing configuration: '+key)
    if config['hardware_policy'] not in ['standard','print_preferred','printed_only']:raise ValueError('Unknown hardware_policy')
    for key in ['source_width_mm','depth_factor','basin_y_factor']:
        if not np.isfinite(config[key]) or config[key]<=0:raise ValueError(key+' must be positive finite')
    pump=config['pump'];hose=config['hose']
    for key in ['dimensions_mm','location_mm','source','port_diameter_mm','port_location_mm','voltage','operating_point_status']:
        if key not in pump:raise ValueError('Missing pump.'+key)
    if not pump['source'] or min(pump['dimensions_mm'])<=0:raise ValueError('Pump needs source/assumption and positive dimensions')
    if not 0<hose['inner_diameter_mm']<hose['outer_diameter_mm']:raise ValueError('Hose requires positive ID < OD')
    if not hose.get('source'):raise ValueError('Hose specification needs source or explicit assumption')
    for channel in config['channels']:
        p=np.asarray(channel['points_mm'],float)
        if p.ndim!=2 or p.shape[1]!=3 or len(p)<2 or channel['radius_mm']<=0:raise ValueError('Invalid channel path/radius')
        if np.any(np.linalg.norm(np.diff(p,axis=0),axis=1)<1e-6):raise ValueError('Repeated channel points')
    if config['waterline_mm']<=0 or config['return_volume_ml']<0:raise ValueError('Invalid waterline or return volume')
    return dict(config)


def carve_channels(sculpture,channels,material):
    """Cut actual positive-radius lumens or open troughs; paths are local sculpture millimetres."""
    records=[]
    for channel in channels:
        points=np.asarray(channel['points_mm'],float)/1000;r=channel['radius_mm']/1000
        cutter,center,radii=_g_pipe('Water channel cutter',points,[r]*len(points),material,res=12,n=64);_g_boolean(sculpture,cutter);records.append({'name':channel['name'],'centerline_local_mm':(np.asarray(center)*1000).tolist(),'radius_mm':r*1000})
    return records


def make_basin(profile_rz_mm,y_factor,material):
    """Closed material lathe profile defines bottom, wall, rim and cavity; scaling affects Y only."""
    profile=np.asarray(profile_rz_mm,float)/1000
    if profile.ndim!=2 or profile.shape[1]!=2 or len(profile)<6 or min(profile[:,0])<0:raise ValueError('Basin needs explicit closed material R/Z outline')
    ob=_g_lathe('Reservoir and integral supports',profile,material,n=160)
    for p in ob.data.vertices:p.co.y*=y_factor
    return ob


def add_supports(basin,sculpture,supports,material):
    """Ray-measured posts with explicit top fitting stock; positive stock is interference, not fit approval."""
    bpy.context.view_layer.update();bm=bmesh.new();bm.from_mesh(sculpture.data);bm.transform(sculpture.matrix_world);tree=BVHTree.FromBMesh(bm);records=[]
    try:
        for p in supports:
            x,y=np.asarray(p['xy_mm'])/1000;base=p['base_mm']/1000;hit=tree.ray_cast(Vector((x,y,base)),Vector((0,0,1)),1)[0]
            if hit is None:raise ValueError('Support misses actual sculpture underside')
            top=hit.z+p['fitting_stock_mm']/1000
            if top<=base:raise ValueError('Support height must be positive')
            post=_g_cyl('Sculpture support',(x,y,(base+top)/2),p['radius_mm']/1000,top-base,material);_g_boolean(basin,post,'UNION');records.append({'xy_mm':p['xy_mm'],'underside_mm':hit.z*1000,'post_top_mm':top*1000,'fitting_stock_mm':p['fitting_stock_mm']})
    finally:bm.free()
    return records


def make_device(pump,hose,material):
    """Nominal pump envelope and truly hollow hose, retaining caller's device assumptions."""
    body=_g_cube('Pump reference envelope',np.asarray(pump['location_mm'])/1000,np.asarray(pump['dimensions_mm'])/1000,material,.001)
    hp=np.asarray(hose['points_mm'])/1000
    ob=_g_hollow_pipe('Hollow supply hose',hp,hose['outer_diameter_mm']/2000,hose['inner_diameter_mm']/2000,material)
    return body,ob


def make_print_derivative(sculpture,channels,voxel_mm,material):
    """Close a separate print mesh, then recut exact lumens; preserve visual original."""
    if not 0.1<=voxel_mm<=2:raise ValueError('print_voxel_mm must be 0.1–2 mm')
    ob=_g_copy_obj(sculpture,'Printable closed sculpture');_g_active(ob);m=ob.modifiers.new('Print closure','REMESH');m.mode='VOXEL';m.voxel_size=voxel_mm/1000;bpy.ops.object.modifier_apply(modifier=m.name)
    # Channels are local to the mesh; the cutter must inherit the same world transform.
    for channel in channels:
        pts=np.asarray(channel['points_mm'])/1000;r=channel['radius_mm']/1000;c,_,_=_g_pipe('Recut precise print lumen',pts,[r]*len(pts),material);c.matrix_world=ob.matrix_world.copy();_g_boolean(ob,c)
    _g_clean(ob);return ob


def clean_print_mesh(ob,tolerance_mm,fragment_limit_mm=0):
    """Explicit numerical cleanup and bounded detached-fragment removal on print derivative only."""
    if not 0<tolerance_mm<=.05 or fragment_limit_mm<0:raise ValueError('Invalid print cleanup tolerances')
    bm=bmesh.new();bm.from_mesh(ob.data);removed=[]
    try:
        bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=tolerance_mm/2000);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=tolerance_mm/1000)
        seen=set();components=[]
        for v in bm.verts:
            if v in seen:continue
            stack=[v];seen.add(v);part=[]
            while stack:
                q=stack.pop();part.append(q)
                for e in q.link_edges:
                    other=e.other_vert(q)
                    if other not in seen:seen.add(other);stack.append(other)
            components.append(part)
        largest=max(components,key=len)
        for part in components:
            if part is largest:continue
            xyz=np.asarray([v.co[:] for v in part]);extent=np.ptp(xyz,axis=0)*1000
            if fragment_limit_mm>0 and extent.max()<=fragment_limit_mm:
                removed.append({'vertices':len(part),'dimensions_mm':extent.tolist()});bmesh.ops.delete(bm,geom=part,context='VERTS')
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data)
    finally:bm.free()
    return removed


def basin_storage(profile_rz_mm,y_factor,waterline_mm):
    """Volume from inner-wall branch of a caller-supplied material outline; require explicit inner profile separately for capacity claims."""
    # Deliberately do not guess which branch is wetted from a potentially multi-valued outline.
    return {'waterline_mm':waterline_mm,'capacity_status':'Requires inner_profile_zr_mm integration or actual exported cavity sectioning'}


def build(input_path,config,output,geometry_only=True):
    c=validate_config(config);out=Path(output);out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.read_factory_settings(use_empty=True)
    sculpture,original=_g_import_source(input_path,width=c['source_width_mm']/1000,ratio=c['source_ratio']);sculpture.name='Water-bearing sculptural derivative'
    for p in sculpture.data.vertices:p.co.y*=c['depth_factor']
    stone=_g_mat('Sculpture neutral stone',(.22,.25,.22),0,.7);sculpture.data.materials.clear();sculpture.data.materials.append(stone);channels=carve_channels(sculpture,c['channels'],stone);sculpture.location=Vector(c['sculpture_offset_mm'])/1000
    basin=make_basin(c['basin_profile_rz_mm'],c['basin_y_factor'],_g_mat('Reservoir ceramic',(.13,.16,.14),0,.6));contacts=add_supports(basin,sculpture,c['supports'],basin.data.materials[0]);pump,hose=make_device(c['pump'],c['hose'],_g_mat('Device reference',(.035,.04,.045),0,.7));objects=[sculpture,basin,pump,hose]
    pr=make_print_derivative(sculpture,c['channels'],c['print_voxel_mm'],stone) if 'print_voxel_mm' in c else _g_copy_obj(sculpture,'Printable exact derivative')
    if 'final_print_voxel_mm' in c:
        pitch=c['final_print_voxel_mm']
        if not .1<=pitch<=1:raise ValueError('final_print_voxel_mm must be .1–1mm')
        _g_active(pr);q=pr.modifiers.new('Final disclosed print closure after channel cuts','REMESH');q.mode='VOXEL';q.voxel_size=pitch/1000;bpy.ops.object.modifier_apply(modifier=q.name)
    removed=clean_print_mesh(pr,c['print_cleanup_mm'],c.get('print_fragment_limit_mm',0)) if 'print_cleanup_mm' in c else []
    parts=export_parts(out/'print',{'sculpture':pr,'reservoir':basin})
    if pr!=sculpture:pr.hide_render=True;pr.hide_set(True)
    models=[media.export_glb(out/'model.glb',objects)];offset=np.asarray(c['service_offset_mm'])/1000;sculpture.location+=Vector(offset);models.append(media.export_glb(out/'exploded.glb',objects));sculpture.location-=Vector(offset)
    models.append(media.export_section(out/'section.glb',basin,[pump,hose],1,0,True));media.setup_studio(objects);bpy.ops.wm.save_as_mainfile(filepath=str(out/'source.blend'))
    if not geometry_only:media.render_views(out,objects)
    motion=media.author_lift_animation(out/'maintenance.blend',objects,[sculpture],offset*1000)
    storage=basin_storage(c['basin_profile_rz_mm'],c['basin_y_factor'],c['waterline_mm'])
    if 'inner_profile_zr_mm' in c:
        q=np.asarray(c['inner_profile_zr_mm'],float)
        if np.any(np.diff(q[:,0])<=0) or not q[0,0]<c['waterline_mm']<q[-1,0]:raise ValueError('Inner basin profile requires increasing Z spanning waterline to rim')
        z=np.linspace(c['waterline_mm'],q[-1,0],500);r=np.interp(z,q[:,0],q[:,1]);headroom=float(np.trapezoid(np.pi*r*r*c['basin_y_factor'],z)/1000);storage.update({'available_return_headroom_ml':headroom,'return_volume_ml':c['return_volume_ml'],'nominal_return_margin_ml':headroom-c['return_volume_ml'],'limitation':'Subtract submerged device/sculpture displacement separately; profile volume is not leak or working-flow verification'})
    report={'configuration':c,'units':{'native':'metre','stl':'millimetre'},'channels':channels,'parts':parts,'models':models,'supports':contacts,'storage':storage,'animation':motion,'status':'Digital candidate. Verify actual finite fluid passage, hose/port connection, supports, device removal, seal and working point before use. Positive support stock requires physical fitting.','print_derivative_voxel_mm':c.get('print_voxel_mm'),'removed_print_fragments':removed,'final_print_voxel_mm':c.get('final_print_voxel_mm'),'print_channel_dimension_status':'Nominal source cutter dimensions; final voxel option alters walls and channels, require actual exported passage measurements','print_reimport':{name:validation.check_stl(out/'print'/name) for name in ['sculpture.stl','reservoir.stl']}}
    (out/'measurement.json').write_text(json.dumps(report,indent=2));validation.require_print_topology(report['print_reimport']);return report
