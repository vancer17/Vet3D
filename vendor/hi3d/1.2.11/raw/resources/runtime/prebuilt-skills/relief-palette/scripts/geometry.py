"""Millimetre input primitives. Objects are linked only to the supplied collection."""
import math
import bpy
from mathutils import Vector
from primitive_core import rounded_rectangle, extrude_polygon, cylinder_mesh
from scene_io import create_mesh_object

MM = 0.001


from preview_scene import fit_orthographic_camera
from material_nodes import principled_material

def linear_rgb(value):
    value = value.lstrip('#')
    if len(value) != 6:
        raise ValueError('Expected six RGB hex digits')
    channels = [int(value[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels)


def shader(material):
    return next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def material(name, color, *, metallic=0, roughness=.4, coat=0):
    return principled_material(name,linear_rgb(color),metallic=metallic,roughness=roughness,inputs={'Coat Weight':coat})


def powder_material(name, color, *, grain_mm=.09, bump_mm=.035, metallic=.35, roughness=.5):
    """Physical-scale grain in object metres, shared by cake and embossed mesh."""
    if grain_mm <= 0 or bump_mm < 0:
        raise ValueError('Invalid grain scale or bump distance')
    mat = material(name, color, metallic=metallic, roughness=roughness)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coords = nodes.new('ShaderNodeTexCoord')
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 1 / (grain_mm * MM)
    noise.inputs['Detail'].default_value = 2
    links.new(coords.outputs['Object'], noise.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Distance'].default_value = bump_mm * MM
    bump.inputs['Strength'].default_value = .5
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], shader(mat).inputs['Normal'])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*[c * .72 for c in linear_rgb(color)], 1)
    ramp.color_ramp.elements[1].color = (*[min(c * 1.15, 1) for c in linear_rgb(color)], 1)
    links.new(noise.outputs['Fac'], ramp.inputs[0])
    links.new(ramp.outputs[0], shader(mat).inputs['Base Color'])
    return mat


def mesh(collection, name, vertices_mm, faces, mat=None):
    return create_mesh_object(name,[Vector(v)*MM for v in vertices_mm],faces,collection=collection,material=mat)


def bevel(obj, width_mm, segments=3):
    if width_mm < 0:
        raise ValueError('Negative bevel width')
    if width_mm:
        mod = obj.modifiers.new('Edge finish', 'BEVEL')
        mod.width, mod.segments = width_mm * MM, segments
        obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj


def rounded_points(width, depth, radius, segments=10):
    return rounded_rectangle(width,depth,radius,segments)


def plate(collection, name, center_mm, size_mm, radius_mm, mat=None, edge_mm=.1):
    w,d,h=size_mm
    if h<=0:raise ValueError('Plate thickness must be positive')
    vertices,faces=extrude_polygon(rounded_points(w,d,radius_mm),-h/2,h/2,center=center_mm)
    return bevel(mesh(collection,name,vertices,faces,mat),edge_mm)


def ring(collection, name, center_mm, outer_mm, inner_mm, radii_mm, height_mm, mat=None, edge_mm=.1):
    if height_mm <= 0 or any(i >= o for i, o in zip(inner_mm, outer_mm)):
        raise ValueError('Ring needs positive wall and height')
    outlines = [rounded_points(*dims, r) for dims, r in zip((outer_mm, inner_mm), radii_mm)]
    n = len(outlines[0])
    x0, y0, z0 = center_mm
    vs = [(x+x0, y+y0, z+z0) for z in (-height_mm/2, height_mm/2) for outline in outlines for x, y in outline]
    fs = []
    for i in range(n):
        j = (i+1)%n
        fs += [(i,j,2*n+j,2*n+i), (n+j,n+i,3*n+i,3*n+j),
               (2*n+i,2*n+j,3*n+j,3*n+i), (j,i,n+i,n+j)]
    return bevel(mesh(collection, name, vs, fs, mat), edge_mm)


def cylinder(collection, name, center_mm, radius_mm, length_mm, mat=None, axis='X', segments=64):
    return mesh(collection,name,*cylinder_mesh(center_mm,radius_mm,length_mm,axis,segments),mat)


def difference(obj, cutter):
    """Bake the target's current modifier stack, triangulate, then cut; retain cutter."""
    if obj.type != 'MESH' or cutter.type != 'MESH':
        raise ValueError('Boolean participants must be meshes')
    obj.data = obj.data.copy() if obj.data.users > 1 else obj.data
    old_active = bpy.context.view_layer.objects.active
    try:
        bpy.context.view_layer.objects.active = obj
        for mod in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=mod.name)
        tri = obj.modifiers.new('Stable pre-cut tessellation', 'TRIANGULATE')
        bpy.ops.object.modifier_apply(modifier=tri.name)
        mod = obj.modifiers.new('Mechanical clearance', 'BOOLEAN')
        mod.operation, mod.object = 'DIFFERENCE', cutter
        bpy.ops.object.modifier_apply(modifier=mod.name)
    finally:
        bpy.context.view_layer.objects.active = old_active
    return obj


def parent_keep_world(obj, parent):
    bpy.context.view_layer.update()
    matrix = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = matrix


def aim(camera, target_mm):
    camera.rotation_euler = (Vector(target_mm)*MM-camera.location).to_track_quat('-Z', 'Y').to_euler()


def fit_camera(camera, objects, resolution, margin=1.15):
    fit_orthographic_camera(camera,objects,resolution,evaluated=True,margin=margin)


def ellipsoid(collection, name, center_mm, size_mm, mat, segments=32, rings=16):
    if min(size_mm) <= 0:
        raise ValueError('Positive ellipsoid dimensions required')
    vs = [tuple(center_mm[i] + (size_mm[i]/2 if i==2 else 0) for i in range(3))]
    for r in range(1, rings):
        theta = math.pi*r/rings
        for j in range(segments):
            phi = 2*math.pi*j/segments
            vs.append((center_mm[0]+size_mm[0]/2*math.sin(theta)*math.cos(phi),
                       center_mm[1]+size_mm[1]/2*math.sin(theta)*math.sin(phi),
                       center_mm[2]+size_mm[2]/2*math.cos(theta)))
    vs.append((center_mm[0],center_mm[1],center_mm[2]-size_mm[2]/2))
    fs = [(0,1+j,1+(j+1)%segments) for j in range(segments)]
    for r in range(rings-2):
        a,b = 1+r*segments,1+(r+1)*segments
        fs += [(a+j,b+j,b+(j+1)%segments,a+(j+1)%segments) for j in range(segments)]
    last = 1+(rings-2)*segments
    fs += [(last+(j+1)%segments,last+j,len(vs)-1) for j in range(segments)]
    obj = mesh(collection,name,vs,fs,mat)
    for face in obj.data.polygons:
        face.use_smooth=True
    return obj


def applicator(collection, name, center_mm, length_mm, width_mm, ends, materials):
    """Removable double-ended assembly; foam/bristle-head envelopes, no simulated hairs."""
    if length_mm <= 6*width_mm or width_mm <= 0 or len(ends)!=2 or any(e not in ('foam','bristle') for e in ends):
        raise ValueError('Invalid applicator proportions or end types')
    root = bpy.data.objects.new(name, None)
    collection.objects.link(root)
    x,y,z=center_mm
    parts=[plate(collection,name+' handle',(x,y,z),(length_mm*.52,width_mm*.75,width_mm*.55),width_mm*.2,materials['handle'])]
    for side, kind in zip((-1,1), ends):
        parts.append(plate(collection,name+f' ferrule {side}',(x+side*length_mm*.29,y,z),
                           (length_mm*.075,width_mm*.8,width_mm*.6),width_mm*.14,materials['metal']))
        parts.append(ellipsoid(collection,name+f' {kind} {side}',(x+side*length_mm*.405,y,z),
                               (length_mm*.19,width_mm,width_mm*.7),materials[kind]))
    for obj in parts:
        parent_keep_world(obj,root)
    return root,parts
