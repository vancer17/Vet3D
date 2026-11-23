"""Local stage invocation helpers. No work is performed on import."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import sys
class StageFinished(Exception):
    def __init__(self,code=0): self.code=code

def _finish_stage(code=0):
    raise StageFinished(code)

def cli_arguments(argv=None):
    values=list(sys.argv[1:] if argv is None else argv)
    return values[values.index('--')+1:] if '--' in values else values
