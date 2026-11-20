"""Blender-specific shape adapters; coordinates are already in scene units."""
import math
import bpy


def cylinder_object(name, center, radius, depth, *, collection, axis='Z', segments=64):
    """Preserve Blender operator tessellation, pivot, and un-applied axis rotation."""
    if axis not in ('X','Y','Z') or min(radius,depth)<=0 or segments<3:
        raise ValueError('Positive cylinder dimensions, valid axis and segment count required')
    bpy.ops.mesh.primitive_cylinder_add(vertices=segments,radius=radius,depth=depth,location=center)
    obj=bpy.context.object;obj.name=name
    if axis=='Y':obj.rotation_euler.x=math.pi/2
    if axis=='X':obj.rotation_euler.y=math.pi/2
    for old in list(obj.users_collection):old.objects.unlink(obj)
    collection.objects.link(obj)
    return obj


def curve_tube(name, points, radius, *, collection, material=None, spline='BEZIER', resolution=12, bevel_resolution=3, fill_caps=True):
    """Create an editable curve, with explicit sampling/cap policy; never convert it."""
    points=list(points)
    if len(points)<2 or radius<=0 or spline not in ('BEZIER','POLY'):
        raise ValueError('At least two points, positive radius and BEZIER/POLY required')
    curve=bpy.data.curves.new(name,'CURVE');obj=None
    try:
        curve.dimensions='3D';curve.resolution_u=resolution;curve.bevel_depth=radius
        curve.bevel_resolution=bevel_resolution;curve.use_fill_caps=fill_caps
        path=curve.splines.new(spline)
        if spline=='BEZIER':
            path.bezier_points.add(len(points)-1)
            for p,co in zip(path.bezier_points,points):
                p.co=co;p.handle_left_type=p.handle_right_type='AUTO'
        else:
            path.points.add(len(points)-1)
            for p,co in zip(path.points,points):p.co=(*co,1)
        if material is not None:curve.materials.append(material)
        obj=bpy.data.objects.new(name,curve);collection.objects.link(obj)
        return obj
    except BaseException:
        if obj is not None:bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.curves.remove(curve)
        raise
