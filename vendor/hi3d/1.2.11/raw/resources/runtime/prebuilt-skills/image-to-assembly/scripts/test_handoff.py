"""Exercise reviewed view handoff with an independent tool and mock transport."""

import argparse
import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import Mock

from reviewed_submit import execute, load_tool, reviewed_plan, ReviewedClient
from view_contract import API_ORDER, CAMERA_DIRECTIONS, CONVENTION, SCREEN_FRONT


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = self.root/'views.json'
        self.params = self.root/'quality.json'
        self.job = self.root/'job.json'
        self.data = {'convention':CONVENTION,'views':{}}
        def chunk(name,data):
            return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data))
        for i, slot in enumerate(API_ORDER):
            raw = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(bytes([0,i*60,100,200])))+chunk(b'IEND',b'')
            path = self.root/(slot+'.png');path.write_bytes(raw)
            self.data['views'][slot]={'path':path.name,'sha256':hashlib.sha256(raw).hexdigest(),
                'camera_position_direction':list(CAMERA_DIRECTIONS[slot]),'camera_up':[0,0,1],
                'observed_front_direction':SCREEN_FRONT[slot],'direction_reviewed':True,
                'direction_evidence':'Synthetic asymmetric view fixture'}
        self.write()
        self.params.write_text(json.dumps({'model':'hi3dv3.0','resolution':'2048quality','face':2000000,'request_type':3,'pbr':1,'shading':.5,'format':2}))
        self.client=Mock()
        self.client.request.return_value=(200,{'code':200,'data':{'task_id':'synthetic.model-id.123'}})
        self.factory=Mock(return_value=self.client)

    def write(self):
        self.manifest.write_text(json.dumps(self.data))

    def run_handoff(self,dry=False):
        return execute(TOOL,self.manifest,self.params,self.job,dry,self.factory)

    def test_dry_run_no_client_or_job(self):
        result, code=self.run_handoff(True)
        self.assertEqual(code,0); self.factory.assert_not_called()
        self.assertFalse(self.job.exists());self.assertEqual(result['plan']['parameters']['multi_images_bit'],'1111')
        self.assertEqual([v['api_slot'] for v in result['multipart_preview']['files']],list(API_ORDER))

    def test_two_views_preserve_api_order(self):
        self.data['views']={k:self.data['views'][k] for k in ['right','front']};self.write()
        result,_=self.run_handoff(True)
        self.assertEqual(result['plan']['parameters']['multi_images_bit'],'1001')
        self.assertEqual([v['api_slot'] for v in result['multipart_preview']['files']],['front','right'])

    def test_camera_reversal_stops_before_auth(self):
        self.data['views']['left']['camera_position_direction']=[1,0,0];self.write()
        with self.assertRaises(ValueError): self.run_handoff()
        self.factory.assert_not_called();self.assertFalse(self.job.exists())

    def test_missing_review_stops_before_auth(self):
        self.data['views']['right']['direction_reviewed']=False;self.write()
        with self.assertRaises(ValueError): self.run_handoff()
        self.factory.assert_not_called()

    def test_front_landmark_reversal_stops(self):
        self.data['views']['left']['observed_front_direction']='screen_left';self.write()
        with self.assertRaises(ValueError):self.run_handoff()
        self.factory.assert_not_called()

    def test_changed_bitmap_stops(self):
        self.params.write_text(json.dumps({'multi_images_bit':'1001'}))
        with self.assertRaises(ValueError):self.run_handoff()
        self.factory.assert_not_called()

    def test_changed_image_stops(self):
        (self.root/'left.png').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.run_handoff()
        self.factory.assert_not_called()

    def test_success_audits_actual_body_and_reuses_job(self):
        result,_=self.run_handoff(); self.assertEqual(result['job']['task_id'],'synthetic.model-id.123')
        audit=json.loads(Path(str(self.job)+'.views.json').read_text())
        self.assertTrue(audit['multipart']['verified'])
        self.assertEqual([v['api_slot'] for v in audit['multipart']['files']],list(API_ORDER))
        result,_=self.run_handoff();self.assertTrue(result['reused'])
        self.assertEqual(self.client.request.call_count,1);self.assertEqual(self.client.auth.call_count,1)

    def test_unknown_submission_never_reposts(self):
        self.client.request.side_effect=TimeoutError('synthetic')
        result,code=self.run_handoff();self.assertEqual(code,2)
        self.assertEqual(result['job']['state'],'submission_uncertain')
        self.run_handoff();self.assertEqual(self.client.request.call_count,1)

    def test_real_stream_reorder_is_blocked(self):
        plan,audit,_=reviewed_plan(TOOL,self.manifest,self.params)
        client=ReviewedClient(self.client,TOOL,plan,audit,self.root/'audit.json')
        files=list(reversed(plan['files']))
        with TOOL.parameters.multipart(plan['parameters'],files) as (stream,ctype,length):
            with self.assertRaises(ValueError):client.request(TOOL.client.CREATE['model'],'POST',stream,ctype,length)
        self.client.request.assert_not_called();self.assertFalse((self.root/'audit.json').exists())

    def test_bytes_changed_after_planning_never_authenticate(self):
        plan,audit,_=reviewed_plan(TOOL,self.manifest,self.params)
        (self.root/'front.png').write_bytes(b'changed after plan')
        with self.assertRaises(ValueError):
            TOOL.jobs.submit_job(ReviewedClient(self.client,TOOL,plan,audit,self.root/'audit.json'),self.job,plan)
        self.client.auth.assert_not_called();self.client.request.assert_not_called()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--hi3d-tool-dir',required=True)
    args,remaining=parser.parse_known_args()
    TOOL=load_tool(args.hi3d_tool_dir)
    unittest.main(argv=[__file__]+remaining,verbosity=2)
