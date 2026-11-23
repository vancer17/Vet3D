"""Run with Blender --background --factory-startup --python-exit-code 1 --python FILE.
Uses synthetic geometry and temporary outputs, never cloud APIs or personal models.
"""
import json
import sys
import tempfile
from pathlib import Path
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import mask_geometry as g


def check(value, message):
    if not value:
        raise AssertionError(message)


def close_dimensions(actual, expected, tolerance=.03):
    check(all(abs(a-b)<tolerance for a,b in zip(actual, expected)), str((actual, expected)))


def main():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for label, dims in [('nominal',(4.6,22,3.2)), ('small',(2,10,2)), ('large',(8,30,6))]:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            report = g.coupon(root/label, *dims)
            check(report['topology']['closed_oriented_topology'], 'closed coupon')
            c = report['coupon']
            close_dimensions([c['midplane_hole_min_sampled_diameter_mm']]+c['midplane_slot_axial_span_mm'], dims)
            check(all(c['centre_passages_open']), 'real holes')
            before = (root/label/'strap_coupon.glb').read_bytes()
            try:
                g.coupon(root/label, *dims)
            except FileExistsError:
                pass
            else:
                raise AssertionError('overwrite accepted')
            check((root/label/'strap_coupon.glb').read_bytes()==before, 'original preserved')
        for filename, importer in [('strap_coupon.glb', bpy.ops.import_scene.gltf), ('strap_coupon_mm.stl', bpy.ops.wm.stl_import)]:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.context.scene.unit_settings.scale_length = 1 if filename.endswith('.glb') else .001
            importer(filepath=str(root/'nominal'/filename))
            ob = next(o for o in bpy.context.scene.objects if o.type=='MESH')
            me = g.mesh_mm(ob)
            try:
                bounds = g.topology(me)['bounds_mm']
                close_dimensions([hi-lo for lo,hi in bounds], [80,30,4])
            finally:
                bpy.data.meshes.remove(me)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        g.mm_scene()
        patch = g.make_object('FacePatch', [(-20,-20,0),(20,-20,0),(20,20,0),(-20,20,0)], [(0,1,2,3)])
        source = root/'prepared.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(source))
        report = g.run_liner(source, root/'liner.blend', 'FacePatch', 4, 2.8)
        check(report['topology']['closed_oriented_topology'], 'liner closed')
        shell = bpy.data.objects['Mask_Shell']
        bounds = report['topology']['bounds_mm']
        close_dimensions([bounds[2][0], bounds[2][1]], [4,6.8])
        check(report['global_collision']=='not_tested', 'no false global fit claim')
        g.run_audit(root/'liner.blend', root/'audit.json', 'Mask_Shell', count=100)
        check(json.loads((root/'audit.json').read_text())['topology']['closed_oriented_topology'], 'audit file')
        # Invalid pairing must fail without leaking evaluated mesh datablocks.
        count = len(bpy.data.meshes)
        try:
            g.stl_mm(bpy.data.objects['Mask_Shell'], root/'missing'/'output.stl')
        except OSError:
            pass
        else:
            raise AssertionError('missing export directory unexpectedly accepted')
        check(len(bpy.data.meshes)==count, 'failed export leaked mesh')
        try:
            g.audit(bpy.data.objects['Mask_Shell'], head=bpy.data.objects['FacePatch'])
        except ValueError:
            pass
        else:
            raise AssertionError('incomplete clearance pair accepted')
        check(len(bpy.data.meshes)==count, 'no mesh leak')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        try:
            g.build_coupon(1,22,3.2)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid coupon size accepted')
    print('MASK_GEOMETRY_TESTS_PASSED')


if __name__ == '__main__':
    main()
