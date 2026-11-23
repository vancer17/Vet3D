"""Blender geometry helpers. Coordinates and palette are supplied by the job."""
import bpy, bmesh, math
from mathutils import Vector
from scene_io import create_mesh_object
from primitive_core import extrude_polygon
from blender_primitives import cylinder_object, curve_tube

def linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def _active():
    obj = bpy.context.view_layer.objects.active
    if obj is None:
        raise RuntimeError('Primitive operator did not create an active object')
    return obj

class Context:

    def __init__(self, scene, palette):
        self.scene = scene
        self.parts = []
        self.mat = {}
        for key, color in palette.items():
            self.mat[key] = self.material(key, color.lstrip('#'))

    def material(self, name, h, rough=0.5, metal=0):
        c = tuple((linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)))
        m = bpy.data.materials.new(name)
        m.diffuse_color = (*c, 1)
        m.use_nodes = True
        bs = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'))
        bs.inputs['Base Color'].default_value = (*c, 1)
        bs.inputs['Roughness'].default_value = rough
        bs.inputs['Metallic'].default_value = metal
        return m

    def part(self, name, cn):
        if any((c.get('part_id') == name for c in self.parts)):
            raise ValueError('Duplicate part id: ' + name)
        c = bpy.data.collections.new(name)
        self.scene.collection.children.link(c)
        c['part_id'] = name
        c['label'] = cn
        self.parts.append(c)
        return c

    def add(self, o, name, matkey, coll, smooth=False):
        o.name = name
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        if matkey:
            o.data.materials.append(self.mat[matkey] if isinstance(matkey, str) else matkey)
        if o.type == 'MESH':
            for p in o.data.polygons:
                p.use_smooth = smooth
        return o

    def bevel(self, o, width=0.04, segments=3):
        if width:
            m = o.modifiers.new('精细倒角', 'BEVEL')
            m.width = width
            m.segments = segments
            m.limit_method = 'ANGLE'
            m.angle_limit = 0.35
            m.harden_normals = True
        n = o.modifiers.new('平面加权法线', 'WEIGHTED_NORMAL')
        n.keep_sharp = True
        n.weight = 50
        return o

    def apply_all(self, o):
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        for m in list(o.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)
        o.select_set(False)

    def box(self, name, pos, dims, matkey, coll, bevel=0.04, rotation=None):
        bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
        o = _active()
        o.dimensions = dims
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        if rotation:
            o.rotation_euler = rotation
        self.add(o, name, matkey, coll, True)
        self.bevel(o, bevel)
        return o

    def ellipsoid(self, name, pos, scale, matkey, coll, segments=40, rings=24):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=pos)
        o = _active()
        o.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        return self.add(o, name, matkey, coll, True)

    def cylinder(self, name, pos, radius, depth, matkey, coll, axis='Z', vertices=48, bevel=0.02):
        obj=cylinder_object(name,pos,radius,depth,collection=coll,axis=axis,segments=vertices)
        self.add(obj,name,matkey,coll,True);self.bevel(obj,bevel)
        return obj

    def tube(self, name, a, b, radius, matkey, coll, vertices=32):
        a, b = (Vector(a), Vector(b))
        o = self.cylinder(name, (a + b) / 2, radius, (b - a).length, matkey, coll, vertices=vertices, bevel=min(0.008, radius * 0.15))
        o.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler()
        return o

    def mesh(self, name, verts, faces, matkey, coll, bevel=0):
        material=self.mat[matkey] if isinstance(matkey,str) and matkey else matkey or None
        obj=create_mesh_object(name,verts,faces,collection=coll,material=material,recalculate_normals=True,smooth=bool(bevel))
        if bevel:self.bevel(obj,bevel)
        return obj

    def poly(self, name, coords, y_front, depth, matkey, coll, bevel=0.02):
        vertices,faces=extrude_polygon(coords,y_front,y_front+depth,axis='Y',orient_y=False)
        return self.mesh(name,vertices,faces,matkey,coll,bevel)

    def line(self, name, points, radius, matkey, coll):
        return curve_tube(name,points,radius,collection=coll,material=self.mat[matkey],spline='POLY',resolution=1,bevel_resolution=2)

    def torus(self, name, pos, major_radius, minor_radius, matkey, coll, axis='Y'):
        bpy.ops.mesh.primitive_torus_add(major_segments=48, minor_segments=12, location=pos, major_radius=major_radius, minor_radius=minor_radius)
        o = _active()
        if axis == 'Y':
            o.rotation_euler[0] = math.pi / 2
        if axis == 'X':
            o.rotation_euler[1] = math.pi / 2
        return self.add(o, name, matkey, coll, True)

    def boolean_difference(self, target, cutter):
        self.apply_all(target)
        self.apply_all(cutter)
        bpy.context.view_layer.objects.active = target
        target.select_set(True)
        m = target.modifiers.new('真实凹槽', 'BOOLEAN')
        m.operation = 'DIFFERENCE'
        m.solver = 'EXACT'
        m.object = cutter
        bpy.ops.object.modifier_apply(modifier=m.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
        target.select_set(False)
        return target
