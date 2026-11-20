import sys,unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from checkpoints import digest
from stage_events import record_stage
from profiles import screw_bottle_timing as screw,twisty_fidget_timing as twisty

class Profiles(unittest.TestCase):
    def test_digest_empty_and_multiblock(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'payload'
            for content in [b'',b'public fixture'*250000]:
                path.write_bytes(content);self.assertEqual(digest(path),hashlib.sha256(content).hexdigest());self.assertEqual(path.read_bytes(),content)
            with self.assertRaises(FileNotFoundError):digest(Path(root)/'absent')
    def test_profile_events_and_exceptions(self):
        for profile,field in [(screw,'stage_id'),(twisty,'stage')]:
            for error,status in [(None,'completed'),(ValueError('private body'),'failed'),(KeyboardInterrupt(),'interrupted'),(SystemExit(3),'interrupted')]:
                with self.subTest(profile=profile.__name__,status=status),tempfile.TemporaryDirectory() as root:
                    path=Path(root)/'events.jsonl'
                    with patch.object(profile,'utc_now',side_effect=['start','end']),patch.object(profile.time,'monotonic',side_effect=[10.,12.5]):
                        try:
                            with profile.stage(path,'task','attempt','build','prior'):
                                if error:raise error
                        except BaseException as caught:self.assertIs(caught,error)
                    events=[json.loads(x) for x in path.read_text().splitlines()]
                    self.assertEqual(len(events),2);running,terminal=events
                    self.assertEqual(running,dict(task_id='task',attempt_id='attempt',previous_attempt_id='prior',**{field:'build'},started_at='start',ended_at=None,elapsed_seconds=None,status='running',timing_method='monotonic'))
                    self.assertEqual(terminal,dict(task_id='task',attempt_id='attempt',previous_attempt_id='prior',**{field:'build'},started_at='start',ended_at='end',elapsed_seconds=2.5,status=status,timing_method='monotonic',error_type=type(error).__name__ if error else None))
                    self.assertNotIn('private body',path.read_text())
    def test_skipped_and_core_order(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'events';screw.skipped(path,'t','a','s','cached')
            event=json.loads(path.read_text());self.assertEqual(event['status'],'skipped')
            self.assertIsNone(event['elapsed_seconds']);self.assertIsNone(event['started_at'])
        for wall_first,expected in [(True,['wall','clock']),(False,['clock','wall'])]:
            calls=[]
            def wall():calls.append('wall');return 'UTC'
            def clock():calls.append('clock');return 10
            records=[];events=[]
            with record_stage('s',lambda r:events.append(dict(r)),records,now=wall,clock=clock,wall_first=wall_first):pass
            self.assertEqual(calls[:2],expected);self.assertEqual(records[0]['status'],'completed')
            self.assertIn('missing_reason',events[0]);self.assertNotIn('missing_reason',events[1])

if __name__=='__main__':unittest.main()
