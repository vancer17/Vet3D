import sys,unittest,tempfile,json,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from blender_scene import check_glb_layout

class Layout(unittest.TestCase):
    def test_exact_names_clip_count_and_complete_container(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'fixture.glb'
            def write(names,clips):
                doc={'asset':{'version':'2.0'},'nodes':[{'name':n,'mesh':i} for i,n in enumerate(names)],'animations':[{}]*clips}
                raw=json.dumps(doc).encode();raw+=b' '*(-len(raw)%4)
                path.write_bytes(struct.pack('<4sIII4s',b'glTF',2,20+len(raw),len(raw),b'JSON')+raw)
            write(['Petal_A','Petal_B'],1);check_glb_layout(path,['Petal_B','Petal_A'])
            for names,clips in [(['Petal_A'],1),(['Petal_A','Petal_B','extra'],1),(['Petal_A','Petal_B'],2)]:
                write(names,clips)
                with self.assertRaises(ValueError):check_glb_layout(path,['Petal_A','Petal_B'])
            write(['Petal_A','Petal_B'],1);data=bytearray(path.read_bytes());struct.pack_into('<I',data,4,1);path.write_bytes(data)
            with self.assertRaises(ValueError):check_glb_layout(path,['Petal_A','Petal_B'])

if __name__=='__main__':unittest.main()
