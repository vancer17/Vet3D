"""Load a caller-selected JSON configuration; no environment or account lookup."""

# Local package bootstrap for Blender --python; imports only this package.
import sys as _sys
from pathlib import Path as _Path
_script_dir = str(_Path(__file__).resolve().parent)
if _script_dir not in _sys.path:
    _sys.path.insert(0, _script_dir)

import json
from pathlib import Path
def config(path):
    return json.loads(Path(path).read_text())
