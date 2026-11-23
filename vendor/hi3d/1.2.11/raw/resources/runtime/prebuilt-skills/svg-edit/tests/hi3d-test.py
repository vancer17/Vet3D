import copy,importlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
m=importlib.import_module('hi3d-svg-edit')
example=json.loads((Path(__file__).resolve().parents[1]/'examples/hi3d-spec.json').read_text())
class ContractTests(unittest.TestCase):
    def test_example(self):
        before=copy.deepcopy(example)
        if 'hi3d-svg-edit'=='hi3d-svg-edit':m.edit(copy.deepcopy(example))
        else:m.validate(copy.deepcopy(example))
        self.assertEqual(example,before)
    def test_unknown_field(self):
        bad={**example,'executeArbitraryScript':'bad'}
        with self.assertRaises(ValueError):
            m.edit(bad) if 'hi3d-svg-edit'=='hi3d-svg-edit' else m.validate(bad)
    def test_wrong_schema(self):
        bad={**example,'schemaVersion':2}
        with self.assertRaises(ValueError):
            m.edit(bad) if 'hi3d-svg-edit'=='hi3d-svg-edit' else m.validate(bad)
    def test_active_content_blocked(self):
        for attrs in ({'onclick':'evil()'},{'fill':'url(https://evil.test/a)'}):
            with self.assertRaises(ValueError):m.attributes(attrs)
    def test_update_delete_and_duplicate(self):
        s=copy.deepcopy(example);s['operations'] += [{'op':'duplicate','id':'title','newId':'copy'},{'op':'set','id':'copy','text':'Changed'},{'op':'remove','id':'title'}]
        root=m.edit(s);nodes={e.get('id'):e for e in root.iter()};self.assertNotIn('title',nodes);self.assertEqual(nodes['copy'].text,'Changed')

if __name__=='__main__':unittest.main()
