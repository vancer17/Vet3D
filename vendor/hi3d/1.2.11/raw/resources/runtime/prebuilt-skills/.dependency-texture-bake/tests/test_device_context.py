import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bpy,numpy as np
from texture_bake import bake_image,bake_context

class BakeDevice(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.objects=[]
        for name,z in [('target',0),('source',.01)]:
            bpy.ops.mesh.primitive_plane_add(size=2,location=(0,0,z));obj=bpy.context.object;obj.name=name
            mat=bpy.data.materials.new(name);mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.7,.1,.2,1)
            obj.data.materials.append(mat);self.objects.append(obj)
        self.target,self.source=self.objects
    def state(self):
        scene=bpy.context.scene;p=bpy.context.preferences.addons['cycles'].preferences
        return (scene.render.engine,scene.cycles.samples,scene.cycles.use_denoising,scene.cycles.device,p.compute_device_type,
                [(d.id,d.type,d.use) for d in p.devices],[(o.name,o.select_get(),o.hide_get(),o.hide_render) for o in self.objects],
                bpy.context.view_layer.objects.active.name)
    def test_cpu_bake_and_exception_restore(self):
        before=self.state();uv=[d.uv[:] for d in self.target.data.uv_layers.active.data]
        with tempfile.TemporaryDirectory() as td:
            for kind in ['DIFFUSE','EMIT','NORMAL']:
                tree=self.source.data.materials[0].node_tree;emission=None
                if kind=='EMIT':
                    emission=tree.nodes.new('ShaderNodeEmission');emission.inputs['Color'].default_value=(.7,.1,.2,1)
                    tree.links.new(emission.outputs[0],tree.nodes['Material Output'].inputs['Surface'])
                try:
                    path=Path(td)/(kind.lower()+'.png')
                    image,report=bake_image([self.source],self.target,path=path,name=kind,size=16,kind=kind,
                        colorspace='Non-Color' if kind=='NORMAL' else 'sRGB',normal_16=kind=='NORMAL',
                        cage=.02,ray=.1,margin=1,use_clear=True)
                    self.assertEqual(report['device'],'CPU');self.assertEqual(list(image.size),[16,16]);self.assertTrue(path.exists())
                    pixels=np.asarray(image.pixels[:]).reshape(-1,4);self.assertGreater(float(pixels[:,:3].max()),.1)
                    if kind=='NORMAL':self.assertEqual(path.read_bytes()[24],16)
                finally:
                    if emission:
                        tree.nodes.remove(emission);tree.links.new(tree.nodes['Principled BSDF'].outputs[0],tree.nodes['Material Output'].inputs['Surface'])
        self.assertEqual(before,self.state());self.assertEqual(uv,[d.uv[:] for d in self.target.data.uv_layers.active.data])
        with self.assertRaises(RuntimeError):
            with bake_context([self.source],self.target,cage=.02,ray=.1,margin=1,use_clear=True):raise RuntimeError('fixture')
        self.assertEqual(before,self.state())

if __name__=='__main__':unittest.main(argv=[__file__])
