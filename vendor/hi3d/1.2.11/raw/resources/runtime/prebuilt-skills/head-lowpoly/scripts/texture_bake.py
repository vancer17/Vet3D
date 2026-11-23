"""Local selected-to-active Cycles baking, with explicit geometry and UVs."""
from contextlib import contextmanager
from pathlib import Path
import math
import time
import bpy
from cycles_device import select_cycles_device, cycles_device_context


def _device(scene, device, fallback_cpu):
    return select_cycles_device(scene, device, fallback_cpu=fallback_cpu)['backend']


@contextmanager
def bake_context(sources, target, *, cage, ray, margin, use_clear, device='CPU', fallback_cpu=False):
    """Configure and restore bake/render/device/selection/visibility state."""
    sources = list(sources)
    scene = bpy.context.scene
    if bpy.context.mode != 'OBJECT' or not sources or target in sources:
        raise ValueError('Distinct source meshes and target in Object mode required')
    objects = [target, *sources]
    if any(o.type != 'MESH' or o.name not in scene.objects for o in objects) or not target.data.uv_layers.active:
        raise ValueError('Scene meshes and an active target UV map required')
    if (any(not math.isfinite(x) or x < 0 for x in [cage,ray]) or type(margin) is not int or margin < 0):
        raise ValueError('Finite nonnegative cage/ray and integer margin required')
    if not target.data.materials or any(m is None or not m.use_nodes for m in target.data.materials):
        raise ValueError('Target material slots must have node materials')
    if any(m in list(target.data.materials) for o in sources for m in o.data.materials):
        raise ValueError('Source and target must not share bake materials')
    bake = scene.render.bake
    attributes = dict(use_selected_to_active=True,cage_extrusion=cage,max_ray_distance=ray,margin=margin,
                      use_clear=use_clear,normal_space='TANGENT',normal_r='POS_X',normal_g='POS_Y',normal_b='POS_Z',
                      use_pass_direct=False,use_pass_indirect=False,use_pass_color=True)
    old_bake = {k:getattr(bake,k) for k in attributes}
    old_cycles = {k:getattr(scene.cycles,k) for k in ['samples','use_denoising']}
    engine = scene.render.engine
    selected = list(bpy.context.selected_objects); active = bpy.context.view_layer.objects.active
    visibility = [(o,o.hide_get(),o.hide_render) for o in objects]
    with cycles_device_context(scene, device, fallback_cpu=fallback_cpu) as device_report:
        try:
            scene.render.engine = 'CYCLES'; scene.cycles.samples = 1; scene.cycles.use_denoising = False
            actual_device = device_report['backend']
            for k,v in attributes.items():setattr(bake,k,v)
            bpy.ops.object.select_all(action='DESELECT')
            for o in objects:o.hide_set(False);o.hide_render=False;o.select_set(True)
            bpy.context.view_layer.objects.active = target
            yield {'device':actual_device,'cage':cage,'ray':ray,'margin':margin,'use_clear':use_clear}
        finally:
            for k,v in old_bake.items():setattr(bake,k,v)
            for k,v in old_cycles.items():setattr(scene.cycles,k,v)
            scene.render.engine = engine
            bpy.ops.object.select_all(action='DESELECT')
            for o,hidden,render in visibility:o.hide_set(hidden);o.hide_render=render
            for o in selected:o.select_set(True)
            bpy.context.view_layer.objects.active = active


def save_png(image, path, *, normal_16=False, pack=True):
    """Write PNG; Raw/16-bit tangent normals, restoring scene color settings."""
    scene = bpy.context.scene
    view, settings = scene.view_settings, scene.render.image_settings
    before = (view.view_transform,view.look,settings.color_depth,settings.color_mode,settings.file_format)
    image.filepath_raw=str(path);image.file_format='PNG'
    try:
        if normal_16:
            view.view_transform='Raw';view.look='None';settings.file_format='PNG';settings.color_depth='16';settings.color_mode='RGB'
            image.save_render(str(path),scene=scene)
        else:image.save()
        if pack:image.pack()
    finally:
        view.view_transform=before[0];view.look=before[1]
        settings.file_format=before[4];settings.color_depth=before[2];settings.color_mode=before[3]


def bake_image(sources, target, *, path, name, size, kind, colorspace, cage, ray, margin,
               use_clear, fill=None, normal_16=False, device='CPU', fallback_cpu=False, overwrite=False):
    """Bake one image, remove temporary nodes, return packed image and report.

    Source shading is caller-owned. DIFFUSE records color only; EMIT requires the
    caller's emission adapter. Geometry, UVs and permanent target bindings stay put.
    """
    if type(size) is not int or size < 1 or kind not in ('DIFFUSE','EMIT','NORMAL'):
        raise ValueError('Positive integer size and DIFFUSE/EMIT/NORMAL pass required')
    path=Path(path)
    if path.suffix.lower() != '.png':raise ValueError('PNG output required')
    if path.exists() and not overwrite:raise FileExistsError(path)
    started=time.monotonic();image=None;nodes=[]
    with bake_context(sources,target,cage=cage,ray=ray,margin=margin,use_clear=use_clear,device=device,fallback_cpu=fallback_cpu) as settings:
        try:
            image=bpy.data.images.new(name,width=size,height=size,alpha=False,float_buffer=normal_16)
            if fill is not None:image.generated_color=fill
            image.colorspace_settings.name=colorspace
            for material in dict.fromkeys(target.data.materials):
                tree=material.node_tree;old_active=tree.nodes.active;old_select=[(n,n.select) for n in tree.nodes]
                node=tree.nodes.new('ShaderNodeTexImage');nodes.append((tree,node,old_active,old_select))
                node.image=image;tree.nodes.active=node
                for n in tree.nodes:n.select=n==node
            result=bpy.ops.object.bake(type=kind)
            if 'FINISHED' not in result:raise RuntimeError('Bake did not finish')
            path.parent.mkdir(parents=True,exist_ok=True)
            save_png(image,path,normal_16=normal_16)
            return image, dict(settings,path=str(path),kind=kind,resolution=size,colorspace=colorspace,
                               seconds=time.monotonic()-started,normal_convention='OpenGL tangent +Y' if kind=='NORMAL' else None)
        except BaseException:
            if image is not None:bpy.data.images.remove(image)
            raise
        finally:
            for tree,node,active,select in nodes:
                tree.nodes.remove(node);tree.nodes.active=active
                for n,value in select:n.select=value
