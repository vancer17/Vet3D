"""Locate media executables in an explicit host environment; no installers or downloads."""
from pathlib import Path
import shutil
import sys


def find_ffmpeg(explicit=None):
    if explicit:
        return str(explicit)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return shutil.which('ffmpeg')


def find_ffprobe(explicit=None):
    if explicit:
        return str(explicit)
    for name in ('ffprobe', 'ffprobe.exe'):
        candidate = Path(sys.prefix) / 'media-tools' / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which('ffprobe')
