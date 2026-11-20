"""Explicit selected-object GLB export with bounded temporary state."""
from pathlib import Path
import bpy


def export_glb(path, objects, *, convert_curves=False, unhide=False, exporter=None, **options):
    objects=list(objects)
    if not objects or len(set(objects))!=len(objects) or any(o.name not in bpy.context.view_layer.objects for o in objects):
        raise ValueError('Explicit unique objects in the active view layer required')
    if {'filepath','export_format','use_selection'} & options.keys():
        raise ValueError('GLB path, format and object selection are fixed by this interface')
    if bpy.context.mode!='OBJECT':raise ValueError('Export requires Object mode')
    exporter=exporter or bpy.ops.export_scene.gltf
    state=[(o,o.select_get(),o.hide_get()) for o in bpy.context.view_layer.objects]
    active=bpy.context.view_layer.objects.active;copies=[];meshes=[]
    scene=bpy.context.scene;frame=(scene.frame_current,scene.frame_subframe)
    try:
        bpy.ops.object.select_all(action='DESELECT')
        deps=bpy.context.evaluated_depsgraph_get()
        for obj in objects:
            if unhide:obj.hide_set(False)
            if convert_curves and obj.type=='CURVE':
                mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(deps));meshes.append(mesh)
                copy=bpy.data.objects.new(obj.name+' static mesh',mesh);copies.append(copy)
                bpy.context.collection.objects.link(copy);copy.matrix_world=obj.matrix_world.copy();copy.select_set(True)
            else:obj.select_set(True)
        bpy.context.view_layer.objects.active=copies[0] if copies else objects[0]
        result=exporter(filepath=str(path),export_format='GLB',use_selection=True,**options)
        if 'FINISHED' not in result:raise RuntimeError('GLB exporter did not finish')
    finally:
        for obj in copies:bpy.data.objects.remove(obj,do_unlink=True)
        for mesh in meshes:bpy.data.meshes.remove(mesh)
        for obj,selected,hidden in state:
            obj.hide_set(False);obj.select_set(selected);obj.hide_set(hidden)
        bpy.context.view_layer.objects.active=active
        scene.frame_set(frame[0],subframe=frame[1]);bpy.context.view_layer.update()
    return Path(path)
