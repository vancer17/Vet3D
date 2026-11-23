import json,os,signal,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import process_run
from config_runtime import resolve_file_request

class LocalProcess(unittest.TestCase):
    def test_explicit_environment_streaming_failure_and_existing_log_mode(self):
        with patch.object(process_run,'os',SimpleNamespace(environ={'PATH':'fixture','UNSELECTED':'private fixture'})):
            self.assertEqual(process_run.child_environment(inherit=('PATH','ABSENT'),overrides={'MODE':'local'}),{'PATH':'fixture','MODE':'local'})
        self.assertIsNone(process_run.run_checked([sys.executable,'-c','pass'],env={}))
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            process_run.run_checked([sys.executable,'-c','raise SystemExit(7)'],env={})
        self.assertEqual(caught.exception.returncode,7)
        with tempfile.TemporaryDirectory() as td:
            log=Path(td)/'combined.log'
            with self.assertRaises(RuntimeError):
                process_run.run_process([sys.executable,'-c','import sys;print("out",flush=True);print("err",file=sys.stderr);raise SystemExit(3)'],log,env={})
            self.assertEqual(log.read_text().splitlines(),['out','err'])
    @unittest.skipUnless(os.name=='posix','POSIX parent-interrupt fixture')
    def test_parent_interrupt_reaps_real_child(self):
        with tempfile.TemporaryDirectory() as td:
            marker=Path(td)/'child.pid'
            script='import os,signal,sys,time;from pathlib import Path;Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(.2);os.kill(os.getppid(),signal.SIGINT);time.sleep(5)'
            with self.assertRaises(KeyboardInterrupt):
                process_run.run_checked([sys.executable,'-c',script,str(marker)],env={},terminate_timeout=1)
            pid=int(marker.read_text())
            with self.assertRaises(ProcessLookupError):os.kill(pid,0)
    def test_budget_timeout_writes_heartbeat_and_reaps_child(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);log=root/'run.log';beat=root/'progress.json';marker=root/'child.pid'
            script='import os,sys,time;from pathlib import Path;Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(8)'
            with self.assertRaises(process_run.BudgetTimeout) as caught:
                process_run.run_budgeted(
                    [sys.executable,'-c',script,str(marker)],log,env={},
                    max_wall_seconds=0.4,heartbeat_path=beat,heartbeat_seconds=0.1,terminate_timeout=1)
            self.assertGreater(caught.exception.elapsed_s,0)
            payload=json.loads(beat.read_text())
            self.assertEqual(payload['schema'],'run-tools.budget.v1')
            self.assertEqual(payload['status'],'timeout')
            self.assertEqual(process_run.popup_reason(payload),'timeout')
            self.assertIsNone(process_run.popup_reason(payload,asked=('timeout',)))
            pid=int(marker.read_text())
            if os.name=='posix':
                with self.assertRaises(ProcessLookupError):os.kill(pid,0)
    def test_budgeted_success_marks_completed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);log=root/'run.log';beat=root/'progress.json'
            process_run.run_budgeted(
                [sys.executable,'-c','print("ok")'],log,env={},
                max_wall_seconds=5,heartbeat_path=beat,heartbeat_seconds=1)
            payload=json.loads(beat.read_text())
            self.assertEqual(payload['status'],'completed')
            self.assertIsNone(process_run.popup_reason(payload))
            self.assertIn('ok',log.read_text())
    def test_heartbeat_cycles_and_popup_reasons(self):
        with tempfile.TemporaryDirectory() as td:
            beat=Path(td)/'progress.json'
            first=process_run.write_heartbeat(beat,status='running',phase='wait',elapsed_s=1,budget_s=10)
            self.assertEqual(first['phase_unchanged_cycles'],1)
            second=process_run.write_heartbeat(beat,status='running',phase='wait',elapsed_s=4.1,budget_s=10)
            self.assertEqual(second['phase_unchanged_cycles'],2)
            self.assertEqual(process_run.popup_reason(second),'stall')
            third=process_run.write_heartbeat(beat,status='running',phase='start',elapsed_s=8.1,budget_s=10)
            self.assertEqual(third['phase_unchanged_cycles'],1)
            self.assertEqual(process_run.popup_reason(third),'exhausting')
            self.assertIsNone(process_run.popup_reason(third,asked=('exhausting',)))
            early={'schema':'run-tools.budget.v1','status':'running','phase':'wait','elapsed_s':1,'budget_s':10,'phase_unchanged_cycles':3}
            self.assertIsNone(process_run.popup_reason(early))
            with self.assertRaises(ValueError):
                process_run.popup_reason({'schema':'other'})
    def test_preflight_protects_every_input_and_allows_safe_continuation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'source.glb';source.write_bytes(b'fixture');config=root/'settings.json';config.write_text('{}')
            out=root/'output';out.mkdir();(out/'previous.txt').write_text('preserve')
            inputs,writes=resolve_file_request({'source':source,'config':config},{'output':out,'work':out/'work'},package_root=root/'package')
            self.assertEqual(writes['output'],out.resolve());self.assertEqual(inputs['config'],config.resolve())
            self.assertEqual((out/'previous.txt').read_text(),'preserve');self.assertFalse((out/'work').exists())
            for invalid in [source,config,root,root/'package/new']:
                with self.assertRaises(ValueError):resolve_file_request({'source':source,'config':config},{'output':invalid},package_root=root/'package')
            with self.assertRaises(FileNotFoundError):resolve_file_request({'missing':root/'missing'},{'output':out},package_root=root/'package')

if __name__=='__main__':unittest.main()
