import copy,importlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
m=importlib.import_module('hi3d-stroke-animate')
example=json.loads((Path(__file__).resolve().parents[1]/'examples/hi3d-spec.json').read_text())
class ContractTests(unittest.TestCase):
    def test_example(self):
        before=copy.deepcopy(example)
        if 'hi3d-stroke-animate'=='hi3d-svg-edit':m.edit(copy.deepcopy(example))
        else:m.validate(copy.deepcopy(example))
        self.assertEqual(example,before)
    def test_unknown_field(self):
        bad={**example,'executeArbitraryScript':'bad'}
        with self.assertRaises(ValueError):
            m.edit(bad) if 'hi3d-stroke-animate'=='hi3d-svg-edit' else m.validate(bad)
    def test_wrong_schema(self):
        bad={**example,'schemaVersion':2}
        with self.assertRaises(ValueError):
            m.edit(bad) if 'hi3d-stroke-animate'=='hi3d-svg-edit' else m.validate(bad)
    def test_bad_point(self):
        s=copy.deepcopy(example);s['layers'][0]['drawings'][0]['strokes'][0]['points'][0]=[0,float('nan')]
        with self.assertRaises(ValueError):m.validate(s)
    def test_duplicate_frame(self):
        s=copy.deepcopy(example);s['layers'][0]['drawings']*=2
        with self.assertRaises(ValueError):m.validate(s)

if __name__=='__main__':unittest.main()
