"""Merge simultaneous, equal-timeline weights clips without touching GLB mesh data."""
import argparse
import json
from pathlib import Path
from glb_clips import merge_file


def synchronize(path):
    return merge_file(path, path, clips='all', name='Synchronized relief application',
                      timeline='shared_accessor', allowed_paths=['weights'], in_place=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = synchronize(args.input)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
