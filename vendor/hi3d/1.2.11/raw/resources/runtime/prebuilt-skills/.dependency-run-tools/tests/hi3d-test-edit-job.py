import sys,unittest,tempfile,json,os,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import importlib
_job_api=importlib.import_module('hi3d-edit-job')
EditJob=_job_api.EditJob
probe=_job_api.probe
class JobTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.pkg=self.root/'pkg';self.pkg.mkdir();(self.pkg/'hi3d-code.py').write_text('code=1');self.src=self.root/'source';self.src.write_text('original')
 def job(self,name='out'):return EditJob(self.root/name,{'op':'test'},[self.src],self.pkg,budget=.1)
 def completed(self):
  j=self.job();p=j.root/'hi3d-result.txt';p.write_text('output');j.finish([p],{'parsed':True});return j,p
 def test_reuse_and_tamper(self):
  j,p=self.completed();self.assertTrue(self.job().reused);p.write_text('changed')
  with self.assertRaises(ValueError):self.job()
 def test_source_and_code_invalidate(self):
  self.completed();self.src.write_text('changed')
  with self.assertRaises(ValueError):self.job()
  self.src.write_text('original');(self.pkg/'hi3d-code.py').write_text('code=2')
  with self.assertRaises(ValueError):self.job()
 def test_protect_package_and_input(self):
  for output in (self.pkg/'out',self.src):
   with self.assertRaises(ValueError):EditJob(output,{},[self.src],self.pkg)
 def test_failure_record(self):
  j=self.job()
  with self.assertRaises(ValueError):
   with j:raise ValueError('bad output')
  self.assertEqual(json.loads((j.root/'hi3d-result.json').read_text())['status'],'failed')
 def test_budget_stops_child(self):
  j=self.job()
  with self.assertRaises(RuntimeError):
   with j:j.run([sys.executable,'-c','import time;time.sleep(30)'],'test')
  self.assertEqual(json.loads((j.root/'hi3d-result.json').read_text())['status'],'interrupted')
 @unittest.skipUnless(os.name=='posix','process groups require POSIX')
 def test_budget_stops_grandchild(self):
  j=self.job();marker=self.root/'leaked'
  grandchild='import time;from pathlib import Path;time.sleep(.5);Path('+repr(str(marker))+').write_text("leak")'
  child='import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(grandchild)+']);time.sleep(30)'
  with self.assertRaises(RuntimeError):
   with j:j.run([sys.executable,'-c',child],'tree')
  time.sleep(.6);self.assertFalse(marker.exists())
 def test_probe_missing(self):self.assertFalse(probe('hi3d-nonexistent-executable')['available'])
if __name__=='__main__':unittest.main()
