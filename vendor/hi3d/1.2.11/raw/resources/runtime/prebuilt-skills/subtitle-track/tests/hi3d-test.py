import copy,importlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
m=importlib.import_module('hi3d-subtitle-track')
example=json.loads((Path(__file__).resolve().parents[1]/'examples/hi3d-spec.json').read_text())
class ContractTests(unittest.TestCase):
    def test_example(self):
        before=copy.deepcopy(example)
        if 'hi3d-subtitle-track'=='hi3d-svg-edit':m.edit(copy.deepcopy(example))
        else:m.validate(copy.deepcopy(example))
        self.assertEqual(example,before)
    def test_unknown_field(self):
        bad={**example,'executeArbitraryScript':'bad'}
        with self.assertRaises(ValueError):
            m.edit(bad) if 'hi3d-subtitle-track'=='hi3d-svg-edit' else m.validate(bad)
    def test_wrong_schema(self):
        bad={**example,'schemaVersion':2}
        with self.assertRaises(ValueError):
            m.edit(bad) if 'hi3d-subtitle-track'=='hi3d-svg-edit' else m.validate(bad)
    def test_unicode_and_rounding(self):
        s=copy.deepcopy(example);s['cues'][0]['text']='你好世界';s['maxLineChars']=2
        srt,ass=m.render(s);self.assertIn('你好\n世界',srt);self.assertIn('你好\\N世界',ass)
        self.assertEqual(m.timestamp(59.9999),'00:01:00,000')
    def test_overlap_and_controls(self):
        s=copy.deepcopy(example);s['cues'].append({'start':.5,'end':2,'text':'bad'})
        with self.assertRaises(ValueError):m.validate(s)
        s=copy.deepcopy(example);s['cues'][0]['text']='{bad}'
        with self.assertRaises(ValueError):m.validate(s)

if __name__=='__main__':unittest.main()
