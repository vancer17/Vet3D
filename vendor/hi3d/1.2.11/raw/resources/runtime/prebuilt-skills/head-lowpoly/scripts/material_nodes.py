"""Construct a basic Principled material from explicitly linear RGBA values."""
import bpy


def principled_material(name, color, *, metallic=0, roughness=.5, inputs=None):
    rgba=tuple(color)+(1,) if len(color)==3 else tuple(color)
    if len(rgba)!=4:raise ValueError('Linear RGB or RGBA color required')
    material=bpy.data.materials.new(name)
    try:
        material.use_nodes=True;material.diffuse_color=rgba
        node=material.node_tree.nodes.get('Principled BSDF')
        values={'Base Color':rgba,'Metallic':metallic,'Roughness':roughness,**(inputs or {})}
        for key,value in values.items():node.inputs[key].default_value=value
        return material
    except BaseException:
        bpy.data.materials.remove(material)
        raise
