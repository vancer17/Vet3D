import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from make_fixture import create
from spec import read_spec,validate_spec
from timing import Recorder


class SpecificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=create(Path(self.tmp.name)/'fixture',Path(__file__).resolve().parents[1])
        self.data=json.loads(self.path.read_text())

    def test_three_pans_and_relative_input_resolution(self):
        data=read_spec(self.path)
        self.assertEqual(len(data['pans']),3)
        self.assertTrue(Path(data['pans'][0]['relief']).is_absolute())

    def test_duplicate_colors_and_variants_are_rejected(self):
        for field in ['color','variant_id','id']:
            data=copy.deepcopy(self.data);data['pans'][1][field]=data['pans'][0][field]
            with self.assertRaises(ValueError):validate_spec(data)

    def test_embed_and_height_cannot_erase_relief(self):
        self.data['pans'][0]['embed_mm']=.8
        with self.assertRaises(ValueError):validate_spec(self.data)

    def test_margin_and_unknown_axis_are_rejected(self):
        for field,value in [('margin_mm',30),('axes',[0,0,2]),('depth_sign',0)]:
            data=copy.deepcopy(self.data);data['pans'][0][field]=value
            with self.assertRaises(ValueError):validate_spec(data)

    def test_bad_motion_is_rejected(self):
        for keys in [[[1,0],[20,111],[50,0]],[[1,10],[20,110],[50,0]],[[1,0],[20,110],[20,0]]]:
            data=copy.deepcopy(self.data);data['keyframes']=keys
            with self.assertRaises(ValueError):validate_spec(data)

    def test_invalid_powder_finish_is_rejected(self):
        for finish in ({'grain_mm':0},{'bump_mm':-1},{'metallic':2},{'roughness':float('nan')},{'unknown':1}):
            data=copy.deepcopy(self.data);data['powder_finish']=finish
            with self.assertRaises(ValueError):validate_spec(data)

    def test_missing_asset_does_not_generate_a_substitute(self):
        (self.path.parent/'0.stl').unlink()
        with self.assertRaises(ValueError):read_spec(self.path)

    def test_failure_and_interruption_timing_remain_visible(self):
        recorder=Recorder(self.path.parent,'test')
        for error in (ValueError,KeyboardInterrupt):
            with self.assertRaises(error):
                with recorder.stage(error.__name__):raise error()
        recorder.skip('render','Not requested')
        report=recorder.finish('failed')
        self.assertEqual([r['status'] for r in report['stages']],['failed','interrupted','skipped'])
        self.assertIsNone(report['stages'][-1]['elapsed_seconds'])
        events=[json.loads(line) for line in (self.path.parent/'timings.jsonl').read_text().splitlines()]
        self.assertEqual(events[0]['status'],'running')
        self.assertIsNone(events[0]['ended_at'])
        self.assertIn('+00:00',report['started_at'])


if __name__=='__main__':unittest.main()
