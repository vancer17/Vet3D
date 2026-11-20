"""Interrupted multi-result downloads resume without regenerating or overwriting bytes."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
scripts = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(scripts / 'runtime' if (scripts / 'runtime' / 'hi3d_api.py').is_file() else scripts))
from hi3d_artifacts import download_job
from hi3d_storage import load, save

class Client:
    def check_job(self, job): pass

class RecoveryTests(unittest.TestCase):
    def test_partial_download_reuses_completed_results_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'SPARC3D_TOOL_WORKSPACE': str(Path(temp).resolve())}):
            root=Path(temp).resolve();job=root/'job.json';save(job,{'state':'success'})
            data={'resultImageUrls':['https://example.test/a.png?signature=hidden','https://example.test/b.png?signature=hidden']}
            calls=[]
            def fetch(url,target):
                calls.append(url)
                if len(calls)==2:raise OSError('second download failed')
                target.write_bytes(b'fixture')
            def query(*_):return load(job),data
            with patch('hi3d_artifacts.query_job',side_effect=query):
                with self.assertRaises(OSError):download_job(Client(),job,root/'out',fetch)
                result=download_job(Client(),job,root/'out',fetch)
                self.assertEqual(len(calls),3)
                self.assertEqual(len(result['artifact']['files']),2)
                self.assertNotIn('hidden',job.read_text())
                self.assertFalse(list((root/'out').glob('.download-stage-*')))
                Path(result['artifact']['files'][0]['path']).write_bytes(b'user edit')
                with self.assertRaises(ValueError):download_job(Client(),job,root/'out',fetch)
                self.assertEqual(len(calls),3)

    def test_interrupted_publication_reuses_matching_published_files(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'SPARC3D_TOOL_WORKSPACE': str(Path(temp).resolve())}):
            root=Path(temp).resolve();job=root/'job.json';save(job,{'state':'success'})
            data={'resultImageUrls':['https://example.test/a.png']}
            def fetch(url,target):target.write_bytes(b'fixture')
            with patch('hi3d_artifacts.query_job',side_effect=lambda *_:(load(job),data)):
                result=download_job(Client(),job,root/'out',fetch)
                record=load(job);record.pop('artifact');save(job,record)
                marker=root/'out/hi3d-result-0/.download.json'
                state=load(marker);state['complete']=False;save(marker,state)
                Path(result['artifact']['path']).unlink()
                resumed=download_job(Client(),job,root/'out',fetch)
                self.assertEqual(Path(resumed['artifact']['path']).read_bytes(),b'fixture')
                self.assertTrue(load(marker)['complete'])

if __name__=='__main__':unittest.main()
