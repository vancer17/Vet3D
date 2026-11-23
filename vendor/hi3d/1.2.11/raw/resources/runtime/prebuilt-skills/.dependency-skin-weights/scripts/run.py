"""CLI compatibility adapter for the independent numerical weight solver."""
import argparse
from rigging.weight_graph import main as solve


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["weight_graph"])
    args, remaining = parser.parse_known_args(argv)
    return solve(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
