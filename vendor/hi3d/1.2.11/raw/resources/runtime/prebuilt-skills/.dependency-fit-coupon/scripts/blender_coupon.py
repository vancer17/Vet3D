"""Blender crop lifecycle; caller explicitly supplies boolean/cleanup profile."""
import bpy


def crop_object(source, cutter, *, name, intersect, prepare):
    """Copy source and ROI, use basis shape, run callbacks, return owned mesh.

    intersect(copy,roi) may consume roi; prepare(copy) may perform the caller's
    declared numerical cleanup. Original source and cutter stay intact.
    """
    if source.type!='MESH' or cutter.type!='MESH' or source==cutter:
        raise ValueError('Distinct mesh source and cutter required')
    made=[];success=False
    try:
        for original in (source,cutter):
            obj=original.copy();obj.data=original.data.copy();bpy.context.collection.objects.link(obj);made.append((obj,obj.data))
            world=original.matrix_world.copy();obj.parent=None;obj.matrix_world=world
            if obj.data.shape_keys:obj.shape_key_clear()
        result,roi=[o for o,data in made];result.name=name
        intersect(result,roi);prepare(result)
        if not result.data.polygons:raise ValueError('Empty cropped coupon')
        success=True;return result
    finally:
        for index,(obj,data) in enumerate(made):
            if success and index==0:continue
            try:
                bpy.data.objects.remove(obj,do_unlink=True)
            except ReferenceError:pass  # consuming boolean already removed its ROI
            if data.users==0:bpy.data.meshes.remove(data)
