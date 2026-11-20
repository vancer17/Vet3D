"""Build an open sculptural shell with explicit circular liner and integral supports."""
from .product_print import export_parts
from pathlib import Path
import json, math
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from . import media, validation
from .product_core import boolean as _g_boolean, clean as _g_clean, cube as _g_cube, cyl as _g_cyl, lathe as _g_lathe, mat as _g_mat, remove_numerical_islands as _g_remove_numerical_islands
from .product_source import import_source as _g_import_source


def validate_config(config):
    required=['height_mm','source_ratio','liner','support','extraction_offset_mm','hardware_policy']
    for key in required:
        if key not in config:raise ValueError(f'Missing configuration: {key}')
    c=dict(config);d=c['liner'];p=c['support']
    for key in ['outer_diameter_mm','inner_diameter_mm','length_mm','bottom_mm','axis_mm','source']:
        if key not in d:raise ValueError('Missing liner.'+key)
    for key in ['base_top_mm','pedestal_radius_mm','guide_z_mm','guide_height_mm','guide_wall_mm','radial_clearance_mm','spoke_width_mm','angles_degrees']:
        if key not in p:raise ValueError('Missing support.'+key)
    if not 0<d['inner_diameter_mm']<d['outer_diameter_mm'] or d['length_mm']<=d['outer_diameter_mm']:raise ValueError('Liner requires positive ID < OD and length > OD')
    if not 0<p['base_top_mm']<d['bottom_mm']<p['guide_z_mm']<d['bottom_mm']+d['length_mm']:raise ValueError('Base, liner bottom and guide elevations are inconsistent')
    if min(p[k] for k in ['pedestal_radius_mm','guide_height_mm','guide_wall_mm','radial_clearance_mm','spoke_width_mm'])<=0:raise ValueError('Support dimensions must be positive')
    if len(p['angles_degrees'])<3:raise ValueError('Integral guide needs at least three explicit spokes')
    if c['hardware_policy'] not in ['standard','print_preferred','printed_only']:raise ValueError('Unknown hardware_policy')
    if len(c['extraction_offset_mm'])!=3 or c['extraction_offset_mm'][2]<d['length_mm']:raise ValueError('Vertical extraction offset must clear the full liner length')
    if not d['source']:raise ValueError('Liner dimension source or explicit assumption required')
    return c


def make_liner(liner,material):
    """Create a separate rounded-bottom open vessel reference from explicit nominal dimensions."""
    r=liner['outer_diameter_mm']/2000;ri=liner['inner_diameter_mm']/2000;b=liner['bottom_mm']/1000;t=b+liner['length_mm']/1000;cx,cy=np.asarray(liner['axis_mm'])/1000
    prof=[(0,b),(r*.5,b),(r*.9,b+r*.22),(r,b+r*.6),(r,t),(ri,t),(ri,b+r*.7),(ri*.8,b+r*.5),(0,b+r*.5)]
    return _g_lathe('Removable liner reference',prof,material,center=(cx,cy))


def cut_liner_clearance(shell,liner,support,material):
    """Cut continuous axial clearance up through mouth; original input remains separate."""
    cx,cy=np.asarray(liner['axis_mm'])/1000;r=(liner['outer_diameter_mm']/2+support['radial_clearance_mm'])/1000;b=liner['bottom_mm']/1000;top=(liner['bottom_mm']+liner['length_mm']+100)/1000
    cutter=_g_cyl('Liner extraction clearance',(cx,cy,(b+top)/2),r,top-b,material);_g_boolean(shell,cutter)


def add_integral_supports(shell,liner,support,material):
    """Build wide pedestal and radial guide spokes anchored to actual source wall ray hits."""
    p=support;cx,cy=np.asarray(liner['axis_mm'])/1000;b=liner['bottom_mm']/1000;base=p['base_top_mm']/1000;r=p['pedestal_radius_mm']/1000
    pedestal=_g_cyl('Integral wide pedestal',(cx,cy,(base+b)/2),r,b-base+.0004,material);_g_boolean(shell,pedestal,'UNION')
    z=p['guide_z_mm']/1000;hh=p['guide_height_mm']/1000;ri=(liner['outer_diameter_mm']/2+p['radial_clearance_mm'])/1000;ro=ri+p['guide_wall_mm']/1000
    bm=bmesh.new();bm.from_mesh(shell.data);tree=BVHTree.FromBMesh(bm);contacts=[]
    try:
        for degrees in p['angles_degrees']:
            an=math.radians(degrees);direction=Vector((math.cos(an),math.sin(an),0));point=Vector((cx,cy,z+hh/2));hit,_,_,distance=tree.ray_cast(point,direction,.5)
            if hit is None or distance<=ro:raise ValueError('Guide spoke misses a suitable source wall; reposition guide or change architecture')
            endpoint=distance+.001;start=ro-(ro-ri)/2;sp=_g_cube('Integral radial guide spoke',point+direction*(start+endpoint)/2,(endpoint-start,p['spoke_width_mm']/1000,hh),material,.0004);sp.rotation_euler.z=an;_g_boolean(shell,sp,'UNION');contacts.append({'angle_degrees':degrees,'wall_distance_mm':distance*1000})
    finally:bm.free()
    ring=_g_lathe('Integral hidden guide',[(ri,z),(ro,z),(ro,z+hh),(ri,z+hh),(ri,z)],material,center=(cx,cy));_g_boolean(shell,ring,'UNION');_g_clean(shell)
    return contacts


def build(input_path,config,output,geometry_only=True):
    """Orchestrate explicit input → structure → exports; no source theme, device or path defaults."""
    c=validate_config(config);out=Path(output);out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.read_factory_settings(use_empty=True)
    shell,original=_g_import_source(input_path,height=c['height_mm']/1000,ratio=c['source_ratio']);shell.name='Sculptural vase structural shell';clay=_g_mat('Neutral ceramic',(.52,.49,.43),0,.6);shell.data.materials.clear();shell.data.materials.append(clay)
    cut_liner_clearance(shell,c['liner'],c['support'],clay);contacts=add_integral_supports(shell,c['liner'],c['support'],clay)
    removed=_g_remove_numerical_islands(shell,c['numerical_island_limit_mm']) if 'numerical_island_limit_mm' in c else []
    liner=make_liner(c['liner'],_g_mat('Glass liner reference',(.85,.94,.97),0,.08,.9));parts={'shell':shell};objects=[shell,liner]
    metrics=export_parts(out/'print',parts);models=[media.export_glb(out/'model.glb',objects)]
    liner.location=Vector(c['extraction_offset_mm'])/1000;models.append(media.export_glb(out/'exploded.glb',objects));liner.location=(0,0,0)
    models.append(media.export_section(out/'section.glb',shell,[liner],1,0,True));media.setup_studio(objects)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'source.blend'))
    if not geometry_only:media.render_views(out,objects)
    motion=media.author_lift_animation(out/'cleaning.blend',objects,[liner],c['extraction_offset_mm'])
    report={'configuration':c,'units':{'native':'metre','stl':'millimetre'},'parts':metrics,'models':models,'contacts':contacts,'removed_numerical_islands':removed,'animation':motion,'source_ratio':c['source_ratio'],'hardware':'Integral printed supports; separate liner remains nonprinted functional material; no detachable DIY lock is generated','status':'Digital candidate; check exterior, actual export, full extraction, support load and water test separately','print_reimport':validation.check_stl(out/'print/shell.stl')}
    (out/'measurement.json').write_text(json.dumps(report,indent=2));validation.require_print_topology(report['print_reimport']);return report
