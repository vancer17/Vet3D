"""Verify fixed Hi3D reference originals and their byte identities."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from vet3d.infrastructure.hi3d_reference.bundle import main_verify

if __name__ == "__main__":
    raise SystemExit(main_verify())
