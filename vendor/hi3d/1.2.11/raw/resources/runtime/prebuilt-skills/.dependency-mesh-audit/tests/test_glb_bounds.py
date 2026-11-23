import sys,unittest,tempfile,json,struct,copy
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from glb_bounds import inspect
from glb_clips import read_glb


def container(doc,binary,extra=()):
    raw=json.dumps(doc).encode();raw+=b' '*(-len(raw)%4)
    chunks=[(b'JSON',raw),(b'BIN\x00',binary),*extra]
    payload=b''.join(struct.pack('<I4s',len(data),kind)+data for kind,data in chunks)
    return struct.pack('<4sII',b'glTF',2,12+len(payload))+payload

class GLBBounds(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'fixture.glb'
        self.binary=b'\0'*4+b''.join(struct.pack('<4f',*v,99) for v in [(1,2,3),(4,5,6),(-1,-2,-3)])
        self.doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':len(self.binary)}],
            'bufferViews':[{'buffer':0,'byteOffset':4,'byteLength':48,'byteStride':16}],
            'accessors':[{'bufferView':0,'componentType':5126,'type':'VEC3','count':3}],
            'meshes':[{'primitives':[{'attributes':{'POSITION':0}}]}],
            'nodes':[{'children':[1],'translation':[.5,1,-.5]},
                     {'mesh':0,'matrix':[2,0,0,0,0,3,0,0,0,0,4,0,10,-1,5,1]}],
            'scenes':[{'nodes':[0]}],'scene':0,'animations':[{'name':'fixture'}]}
    def test_interleaved_positions_parent_matrix_and_unknown_chunk(self):
        data=container(self.doc,self.binary,[(b'TEST',b'abcd')]);self.path.write_bytes(data)
        r=inspect(self.path);np.testing.assert_allclose(r['scene_dimensions_xyz_m'],[10,21,36])
        np.testing.assert_allclose(r['width_depth_height_mm'],[10000,36000,21000])
        self.assertEqual(r['mesh_vertex_instances'],3);self.assertEqual(r['animations'],['fixture'])
        self.assertEqual(data,self.path.read_bytes());self.assertEqual(read_glb(data)[1][-1],(b'TEST',b'abcd'))
    def test_corrupt_containers_fail_before_measurement(self):
        data=container(self.doc,self.binary)
        wrong_version=bytearray(data);struct.pack_into('<I',wrong_version,4,1)
        invalid=[b'glTF',data[:-1],bytes(wrong_version),container(self.doc,self.binary,[(b'JSON',b'{}  ')]),container(self.doc,self.binary,[(b'TEST',b'x')])]
        for raw in invalid:
            with self.subTest(raw_length=len(raw)):
                self.path.write_bytes(raw)
                with self.assertRaises(ValueError):inspect(self.path)
    def test_external_sparse_and_out_of_view_positions_fail(self):
        for mutate in [lambda d:d['buffers'][0].update(uri='external.bin'),lambda d:d['accessors'][0].update(sparse={}),
                       lambda d:d['bufferViews'][0].update(byteLength=12),lambda d:d['accessors'][0].update(count=4)]:
            d=copy.deepcopy(self.doc);mutate(d);self.path.write_bytes(container(d,self.binary))
            with self.assertRaises(ValueError):inspect(self.path)
        self.path.write_bytes(container(self.doc,self.binary,[(b'BIN\x00',b'\0'*4)]))
        with self.assertRaises(ValueError):inspect(self.path)

if __name__=='__main__':unittest.main()
