import sys,tempfile,unittest,json
from pathlib import Path
import numpy as np
import trimesh
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_support import execute

class SupportAdapter(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'print').mkdir()
        (self.root/'construction.json').write_text(json.dumps({'board':{'wheelbase_mm':40,'wheel_centers':[{'center_mm':[20,10,0]}]}}))
    def part(self,name,center,size):
        mesh=trimesh.creation.box(extents=[size]*3);mesh.apply_translation(center)
        path=self.root/'print'/name;path.write_bytes(trimesh.exchange.stl.export_stl(mesh));return path
    def test_unequal_volumes_use_solid_centroid_and_preserve_source(self):
        a=self.part('a.stl',[0,0,5],2);b=self.part('b.stl',[9,0,5],1);before=[a.read_bytes(),b.read_bytes()]
        execute(self.root);r=json.loads((self.root/'support-centroid-check.json').read_text())
        np.testing.assert_allclose(r['combined_solid_volume_centroid_mm'],[1,0,5],atol=1e-12)
        np.testing.assert_allclose(r['projection_margin_to_rectangle_mm'],[19,10],atol=1e-12)
        self.assertTrue(r['static_projection_inside']);self.assertEqual(before,[a.read_bytes(),b.read_bytes()])
        self.assertEqual([p['volume_mm3'] for p in r['parts']],[8,1])
    def test_boundary_outside_empty_and_truncated_fail_before_report(self):
        with self.assertRaises(ValueError):execute(self.root)
        for x in [20,21]:
            p=self.part('a.stl',[x,0,5],2)
            with self.assertRaises(ValueError):execute(self.root)
        p.write_bytes(b'invalid STL')
        with self.assertRaises(ValueError):execute(self.root)
        self.assertFalse((self.root/'support-centroid-check.json').exists())

if __name__=='__main__':unittest.main()
