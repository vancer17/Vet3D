"""Finite round side-handle teapot. Pure profile solver and separately callable body/lid stages."""
from .product_print import export_parts
from pathlib import Path
import json, math
import numpy as np, bpy
from .product_core import boolean, clean, cyl, lathe, mat
from .product_preview import aim
from .surfaces import pchip,surface_of_revolution,swept_ellipse,smooth_junctions,blend_spout_root
from .relief import apply_metric_relief
from . import media, validation


def validate_config(C):
    required = ['capacity_ml','wall_mm','floor_mm','fill_height_mm','body_height_mm','body_profile_zr_mm','handle_curve_mm','handle_sections_mm','spout_curve_mm','spout_outer_sections_mm','spout_inner_curve_mm','spout_inner_sections_mm','outer_voxel_mm','junction_smooth_iterations','spout_root_blend_mm','vent_xy_mm','vent_diameter_mm','motif_width_mm','motif_height_mm','motif_angle_degrees','motif_center_z_mm','relief_height_mm','subdivide_edge_threshold_mm','subdivision_cuts','hardware_policy']
    for k in required:
        if k not in C:raise ValueError('Missing configuration: '+k)
    if C['hardware_policy'] not in ['standard','print_preferred','printed_only']:raise ValueError('Unknown hardware_policy')
    for prefix in ['handle','spout','spout_inner']:
        pk=prefix+'_curve_mm';sk={'handle':'handle_sections_mm','spout':'spout_outer_sections_mm','spout_inner':'spout_inner_sections_mm'}[prefix]
        p=np.asarray(C[pk],float);d=np.asarray(C[sk],float)
        if p.ndim!=2 or p.shape[1]!=3 or len(p)<3 or d.shape!=(len(p),2) or not np.isfinite(p).all() or not np.isfinite(d).all() or min(d.ravel())<=0 or np.any(np.linalg.norm(np.diff(p,axis=0),axis=1)<1e-5):raise ValueError('Invalid '+prefix+' sweep points/diameters')
    if not 0 < C['outer_voxel_mm'] <= 1 or not 1 <= C['subdivision_cuts'] <= 8:raise ValueError('Invalid topology resolution')
    if C['vent_diameter_mm']<=0 or min(C[k] for k in ['motif_width_mm','motif_height_mm','relief_height_mm','subdivide_edge_threshold_mm'])<=0:raise ValueError('Relief and vent dimensions must be positive')
    return dict(C)


def solve_profile(C):
    """Pure capacity-constrained profile; reject unsupported or unreachable dimensions."""
    target = C['capacity_ml']
    wall = C['wall_mm']
    floor = C['floor_mm']
    fill = C['fill_height_mm']
    h = C['body_height_mm']
    if not all((np.isfinite(x) for x in [target, wall, floor, fill, h])):
        raise ValueError('Capacity and dimension values must be finite.')
    if not 0 < floor < fill < h:
        raise ValueError('Require 0 < floor_mm < fill_height_mm < body_height_mm.')
    if target <= 0 or wall <= 0:
        raise ValueError('capacity_ml and wall_mm must be positive.')
    if h != 66:
        raise ValueError('This bounded side-handle family supports body_height_mm=66 only; other heights require redesigning the fixed lid and swept interfaces.')
    if not 2.5 <= wall <= 3.5:
        raise ValueError('This bounded side-handle family bounds wall_mm to 2.5–3.5; other walls require interface revalidation.')
    knots = np.array(C['body_profile_zr_mm'], dtype=float, copy=True)
    if knots.ndim != 2 or knots.shape[1] != 2 or len(knots)<3: raise ValueError('profile needs Z/radius pairs')
    knots[:, 0] *= h / 66
    zz = np.linspace(0, h, 300)
    shape = np.sin(np.pi * np.clip((knots[:, 0] - 6) / (h - 6), 0, 1)) ** 0.7
    shape[knots[:, 0] < 6] = 0
    if knots.ndim != 2 or knots.shape[1] != 2 or (not np.isfinite(knots).all()) or (not (np.diff(knots[:, 0]) > 0).all()):
        raise ValueError('body_profile_zr_mm must be finite, strictly increasing Z/radius pairs.')
    if knots[0, 0] != 0 or knots[-1, 0] != 66 or abs(knots[-1, 1] - 32) > 1e-06:
        raise ValueError('Profile must start at Z0, end at Z66 and preserve the 32mm mouth outer radius for the bounded lid seat.')
    if min(knots[:, 1]) <= wall:
        raise ValueError('Profile radii must exceed wall thickness.')

    def reachable_capacity(adjust):
        radius = pchip(knots[:, 0], knots[:, 1] + adjust * shape, zz)
        z = np.linspace(floor, fill, 1600)
        return float(np.trapezoid(math.pi * (np.interp(z, zz, radius) - wall) ** 2, z) / 1000)
    reachable = [reachable_capacity(-5.0), reachable_capacity(8.0)]
    if not reachable[0] <= target <= reachable[1]:
        raise ValueError(f'Requested {target}mL is outside the reachable range {reachable[0]:.3f}–{reachable[1]:.3f}mL for this bounded profile; redesign the profile rather than silently clamping.')
    lo, hi = (-5.0, 8.0)
    for _ in range(45):
        adjust = (lo + hi) / 2
        rr = pchip(knots[:, 0], knots[:, 1] + adjust * shape, zz)
        iz = np.linspace(floor, fill, 1600)
        ir = np.interp(iz, zz, rr) - wall
        capacity = np.trapezoid(math.pi * ir ** 2, iz) / 1000
        if capacity < target:
            lo = adjust
        else:
            hi = adjust
    if abs(capacity - target) > 0.05:
        raise ValueError(f'Capacity solver did not converge within 0.05mL: got {capacity}, requested {target}.')
    return {'z_mm':zz,'radius_mm':rr,'capacity_ml':float(capacity),'reachable_capacity_ml':reachable}

def build_body(C, profile, clay):
    """Connected outer body/roots, followed by separate precise cavity and lumen booleans."""
    zz=profile['z_mm'];rr=profile['radius_mm'];floor=C['floor_mm'];h=C['body_height_mm'];wall=C['wall_mm']
    body = surface_of_revolution('Teapot outer solid', zz / 1000, rr / 1000, clay, n=384)
    hp = C['handle_curve_mm']
    hd = C['handle_sections_mm']
    handle, hpath, hr = swept_ellipse('Closed flowing side handle', hp, hd, clay, count=130, n=72, closed_tip=True)
    boolean(body, handle, 'UNION')
    sp = C['spout_curve_mm']
    sd = C['spout_outer_sections_mm']
    spout, spath, sr = swept_ellipse('Continuous ascending spout outer', sp, sd, clay, count=150, n=80)
    boolean(body, spout, 'UNION')
    junction = smooth_junctions(body, [([0, -48, 34], [23, 24, 22]), ([48, 0, 37], [24, 24, 23])], C['outer_voxel_mm'], C['junction_smooth_iterations'])
    junction['spout_fillet'] = blend_spout_root(body, zz / 1000, rr / 1000, spath, sr, C['spout_root_blend_mm'])
    iz = np.r_[np.linspace(floor, h, 240), h + 15]
    ir = np.r_[np.interp(iz[:-1], zz, rr) - wall, rr[-1] - wall]
    inner = surface_of_revolution('Precise fluid cavity', iz / 1000, ir / 1000, clay, n=320)
    boolean(body, inner)
    bp = np.array(C['spout_inner_curve_mm'], float)
    bd = C['spout_inner_sections_mm']
    bore, bpath, br = swept_ellipse('True common-path liquid lumen', bp.tolist(), bd, clay, count=180, n=80)
    boolean(body, bore)
    body.name = 'Teapot body'
    return body, {'spout_centerline_m':bpath.tolist(),'spout_half_sections_m':br.tolist(),'junction':junction}

def build_lid(C,clay):
    """Matched bounded 66 mm family lid, bridge and real vent."""
    h=C['body_height_mm']
    lidprof = [(0, h - 3.5), (28.4, h - 3.5), (28.4, h + 0.3), (34.3, h + 0.3), (34.6, h + 1.0), (34.3, h + 1.8), (33, h + 2.5), (29, h + 3.5), (23, h + 4.6), (15, h + 5.3), (7, h + 5.6), (0, h + 5.7)]
    lid = lathe('Teapot bridge lid', [(r / 1000, z / 1000) for r, z in lidprof], clay, n=256)
    bridgepts = [[-12, 0, h + 3], [-13, 0, h + 8], [-9, 0, h + 14.5], [0, 0, h + 16], [9, 0, h + 14.5], [13, 0, h + 8], [12, 0, h + 3]]
    bridge, bridgepath, bridgeR = swept_ellipse('Bamboo bridge handle', bridgepts, [[6.5, 6], [6, 5.5], [5.8, 5.3], [6, 5.5], [5.8, 5.3], [6, 5.5], [6.5, 6]], clay, count=120, n=48)
    boolean(lid, bridge, 'UNION')
    clean(lid)
    ventxy = C['vent_xy_mm']
    ventdiam = C['vent_diameter_mm']
    vent = cyl('Actual vent', (*[v / 1000 for v in ventxy], (h + 3) / 1000), ventdiam / 2000, 0.035, clay)
    boolean(lid, vent)

    clean(lid)
    return lid


def author_use_motion(path,body,lid):
    """Finite round-side-handle demonstration; real pouring still requires retaining the lid."""
    s=bpy.context.scene;cam=s.camera;starts={body:body.location.copy(),lid:lid.location.copy()}
    bpy.ops.object.empty_add();pivot=bpy.context.object;pivot.name='Teapot use pivot';body.parent=pivot;lid.parent=pivot;s.frame_start=1;s.frame_end=144;s.render.fps=24
    for f,z in [(1,0),(10,0),(28,.04),(34,.04),(52,0),(144,0)]:lid.location.z=z;lid.keyframe_insert(data_path='location',frame=f)
    for f,x,z,angle in [(1,0,0,0),(58,0,0,0),(76,.015,.08,0),(94,.015,.08,42),(108,.015,.08,42),(124,.015,.08,0),(144,0,0,0)]:
        pivot.location=(x,0,z);pivot.rotation_euler=(0,math.radians(angle),0);pivot.keyframe_insert(data_path='location',frame=f);pivot.keyframe_insert(data_path='rotation_euler',frame=f)
    cam.location=(.38,-.43,.25);aim(cam,(.025,-.016,.084));cam.data.ortho_scale=.36
    framing=media.check_framing(s,cam,[body,lid],range(1,145));s.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(path))
    for ob in [body,lid]:ob.parent=None;ob.animation_data_clear();ob.location=starts[ob]
    bpy.data.objects.remove(pivot,do_unlink=True)
    return {'fps':24,'frames':[1,144],'lid_lift_mm':40,'pour_degrees':42,'whole_body_lift_mm':80,'framing':framing,'physical_status':'Authored poses, not pouring simulation. User retains lid. New geometry requires motion clearance review.'}


def build(input_path,config,output,geometry_only=True):
    """Compose actual source sampling, body/lid, metric relief, exports and use scene."""
    from .sampling import sample_relief
    C=validate_config(config);profile=solve_profile(C);out=Path(output);out.mkdir(parents=True,exist_ok=True);inp=Path(input_path)
    if not inp.is_file():raise FileNotFoundError(inp)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if inp.suffix.lower()=='.stl':
        sample=out/'source-relief.npz';sampling=sample_relief(inp,sample,C.get('sampling_resolution',1024))
    elif inp.suffix.lower()=='.npz':sample=inp;sampling={'input':'Caller supplied metric heightfield; validate source provenance separately'}
    else:raise ValueError('Relief input must be front-facing STL or metric height/mask/bounds NPZ')
    clay=mat('Neutral low reflection ceramic',(.35,.36,.35),0,.65);body,structure=build_body(C,profile,clay);lid=build_lid(C,clay)
    relief=apply_metric_relief(body,sample,profile['z_mm']/1000,profile['radius_mm']/1000,C);clean(body)
    objects=[body,lid];part_stats=export_parts(out/'print',{'body':body,'lid':lid});models=[media.export_glb(out/'model-full.glb',objects),media.export_glb(out/'model.glb',objects,C.get('compress_web',False))]
    lid.location.z=.04;models.append(media.export_glb(out/'exploded.glb',objects,C.get('compress_web',False)));lid.location.z=.018;models.append(media.export_section(out/'section.glb',body,[lid],1,0,True));lid.location.z=0
    media.setup_studio(objects);bpy.ops.wm.save_as_mainfile(filepath=str(out/'source.blend'))
    if not geometry_only:media.render_views(out,objects)
    motion=author_use_motion(out/'animation.blend',body,lid)
    meta={'configuration':C,'capacity_target_ml':C['capacity_ml'],'capacity_profile_ml':profile['capacity_ml'],'reachable_capacity_ml':profile['reachable_capacity_ml'],'capacity_definition':'Rotational main cavity up to fill_height_mm; excludes spout, lid and tea displacement','profile_z_mm':profile['z_mm'].tolist(),'profile_outer_radius_mm':profile['radius_mm'].tolist(),'body_object_name':body.name,'lid_object_name':lid.name,'units':{'native':'metre','stl':'millimetre'},'structure':structure,'relief':relief,'sampling':sampling,'parts':part_stats,'models':models,'animation':motion,'vent_path_mm':[[*C['vent_xy_mm'],C['body_height_mm']-6],[*C['vent_xy_mm'],C['body_height_mm']+16]],'lid_lift_path_mm':[[0,0,0],[0,0,10],[0,0,25],[0,0,40]],'filter':'No integrated leaf filter; separate strainer/manufacturing adaptation required','physical_status':'FDM cold-form prototype only. Food contact, heat, ceramic shrinkage, strength and real pouring untested','print_reimport':{name:validation.check_stl(out/'print'/name) for name in ['body.stl','lid.stl']}}
    (out/'measurement.json').write_text(json.dumps(meta,indent=2));validation.require_print_topology(meta['print_reimport']);return meta
