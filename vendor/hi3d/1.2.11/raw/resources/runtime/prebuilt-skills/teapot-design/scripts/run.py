import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib
from build_stage import run_build
"""Offline CLI; input validation and orchestration only. No API or credential access."""
from pathlib import Path
import argparse,json,sys,time,uuid
from datetime import datetime,timezone


from request_inputs import load_request as read_request

def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--geometry-only',action='store_true')
    return p.parse_args(argv)


def load_request(input_path, config_path, output_path):
    return read_request(input_path, config_path, output_path, package_root=Path(__file__).resolve().parents[1])


def run(input_path, config_path, output_path, geometry_only=True):
    return run_build(input_path, config_path, output_path, geometry_only, package_root=Path(__file__).resolve().parents[1], loader=lambda: importlib.import_module("teapot_model.build").build)


def main(argv=None):
    args=parse_args(argv);run(args.input,args.config,args.output,geometry_only=args.geometry_only)
    print(json.dumps({'output':str(Path(args.output).resolve()),'status':'local-stage-completed','business_acceptance':'requires independent checks and requested media/web delivery'}))


if __name__=='__main__':
    main(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:])
