"""Model-ready file plus a fresh framework heartbeat, not just container liveness."""
from pathlib import Path
import time


def check(root="/tmp/mdf-health", max_age=30):
    root = Path(root)
    return (root / "ready").is_file() and 0 <= time.time() - (root / "heartbeat").stat().st_mtime < max_age


if __name__ == "__main__":
    try:
        healthy = check()
    except OSError:
        healthy = False
    raise SystemExit(0 if healthy else 1)
