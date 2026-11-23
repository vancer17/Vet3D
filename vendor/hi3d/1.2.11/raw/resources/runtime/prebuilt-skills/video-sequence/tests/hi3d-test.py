import copy,importlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
m=importlib.import_module('hi3d-video-sequence')
example=json.loads((Path(__file__).resolve().parents[1]/'examples/hi3d-spec.json').read_text())
class ContractTests(unittest.TestCase):
    def test_example(self):
        before=copy.deepcopy(example)
        if 'hi3d-video-sequence'=='hi3d-svg-edit':m.edit(copy.deepcopy(example))
        else:m.validate(copy.deepcopy(example))
        self.assertEqual(example,before)
    def test_unknown_field(self):
        bad={**example,'executeArbitraryScript':'bad'}
        with self.assertRaises(ValueError):
            m.edit(bad) if 'hi3d-video-sequence'=='hi3d-svg-edit' else m.validate(bad)
    def test_wrong_schema(self):
        bad={**example,'schemaVersion':2}
        with self.assertRaises(ValueError):
            m.edit(bad) if 'hi3d-video-sequence'=='hi3d-svg-edit' else m.validate(bad)
    def test_overlap(self):
        s=copy.deepcopy(example);s['strips'][1]['channel']=1
        with self.assertRaises(ValueError):m.validate(s)
    def test_outside_range(self):
        s=copy.deepcopy(example);s['strips'][0]['duration']=99
        with self.assertRaises(ValueError):m.validate(s)

if __name__=='__main__':unittest.main()
