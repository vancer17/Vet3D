import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from face_fit import summarize,run


class FaceFitTests(unittest.TestCase):
    def test_nose_error_is_not_hidden_by_landmarks(self):
        v=np.zeros((24049,3))
        ids=[15849,17088,2917,7193,18576]
        v[ids]=[[0,0,1],[0,-.3,.5],[0,0,0],[-.3,0,.3],[.3,0,.3]]
        target=v[ids].copy()
        landmarks=[dict(group='eyes',vertex_index=15849,target=v[15849].tolist())]
        good=summarize(v,target,landmarks,ids)
        v[17088,1]-=.1
        bad=summarize(v,target,landmarks,ids)
        self.assertEqual(good['landmark_groups'],bad['landmark_groups'])
        self.assertGreater(bad['nose_observed_surface']['rms'],good['nose_observed_surface']['rms'])

    def test_existing_donor_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'registered.glb').write_bytes(b'existing')
            c=p/'config.json';c.write_text(json.dumps(dict(output=td)))
            with self.assertRaises(FileExistsError):run(c,'not-a-blender',review_fit=True)
            self.assertEqual((p/'registered.glb').read_bytes(),b'existing')

    def test_missing_analysis_does_not_launch_blender(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);c=p/'config.json';c.write_text(json.dumps(dict(output=td)))
            with self.assertRaises(FileNotFoundError):run(c,'not-a-blender')


if __name__=='__main__':unittest.main()
