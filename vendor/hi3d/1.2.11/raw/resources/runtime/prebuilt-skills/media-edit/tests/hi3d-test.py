import copy,importlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
m=importlib.import_module('hi3d-media-edit')
example=json.loads((Path(__file__).resolve().parents[1]/'examples/hi3d-spec.json').read_text())
class ContractTests(unittest.TestCase):
    def test_example(self):
        before=copy.deepcopy(example)
        if 'hi3d-media-edit'=='hi3d-svg-edit':m.edit(copy.deepcopy(example))
        else:m.validate(copy.deepcopy(example))
        self.assertEqual(example,before)
    def test_unknown_field(self):
        bad={**example,'executeArbitraryScript':'bad'}
        with self.assertRaises(ValueError):
            m.edit(bad) if 'hi3d-media-edit'=='hi3d-svg-edit' else m.validate(bad)
    def test_wrong_schema(self):
        bad={**example,'schemaVersion':2}
        with self.assertRaises(ValueError):
            m.edit(bad) if 'hi3d-media-edit'=='hi3d-svg-edit' else m.validate(bad)
    def test_fraction_and_speed(self):
        s=copy.deepcopy(example);s['fps']='30000/1001';s['clips'][0]['end']=2;s['clips'][0]['speed']=2
        rate,frames=m.validate(s);self.assertEqual(str(rate),'30000/1001');self.assertEqual(frames,30)
    def test_empty_clip_and_nan(self):
        for end in (0,float('nan')):
            s=copy.deepcopy(example);s['clips'][0]['end']=end
            with self.assertRaises(ValueError):m.validate(s)

if __name__=='__main__':unittest.main()
