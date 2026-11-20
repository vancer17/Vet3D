"""Export fixed Hi3D originals without executing upstream code."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from vet3d.infrastructure.hi3d_reference.bundle import main_export

if __name__ == "__main__":
    raise SystemExit(main_export())
