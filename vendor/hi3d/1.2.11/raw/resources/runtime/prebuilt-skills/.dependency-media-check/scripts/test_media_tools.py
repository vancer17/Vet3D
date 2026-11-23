import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from media_tools import find_ffmpeg, find_ffprobe

class LocatorTests(unittest.TestCase):
    def test_explicit_paths_win_without_searching(self):
        with patch('media_tools.shutil.which', side_effect=AssertionError('must not search')):
            self.assertEqual(find_ffmpeg('/chosen/ffmpeg'),'/chosen/ffmpeg')
            self.assertEqual(find_ffprobe('/chosen/ffprobe'),'/chosen/ffprobe')
    def test_packaged_probe_and_imageio_fallback(self):
        with tempfile.TemporaryDirectory() as temp, patch('media_tools.sys.prefix',temp):
            p=Path(temp)/'media-tools/ffprobe.exe';p.parent.mkdir();p.write_bytes(b'fixture')
            self.assertEqual(find_ffprobe(),str(p))
        with patch.dict(sys.modules,{'imageio_ffmpeg':None}), patch('media_tools.shutil.which',return_value='/bin/ffmpeg'):
            self.assertEqual(find_ffmpeg(),'/bin/ffmpeg')
