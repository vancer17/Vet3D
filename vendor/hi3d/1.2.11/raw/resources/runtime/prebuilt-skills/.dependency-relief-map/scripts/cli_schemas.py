"""Shared local CLI schemas; business callables and argv adapter are explicit."""
import argparse
import json
from pathlib import Path
from stage_cli import StageFinished

def directory_stage(execute, cli_arguments, argv=None):
    try:
        arguments = cli_arguments(argv)
        if len(arguments) != 1:
            raise ValueError("Expected one output directory")
        return execute(arguments[0])
    except StageFinished as done:
        return done

def json_config_stage(execute, cli_arguments, argv=None):
    try:
        import argparse, json
        from pathlib import Path
        p = argparse.ArgumentParser()
        p.add_argument('--config', type=Path, required=True)
        a = p.parse_args(cli_arguments(argv))
        return execute(json.loads(a.config.read_text()))
    except StageFinished as done:
        return done

def heightfield_stage(build, cli_arguments, argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--heightfields', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--no-render', action='store_true')
    options=p.parse_args(cli_arguments(argv))
    return build(**vars(options))

def animate_stage(animate, cli_arguments, argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--scene', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--render', action='store_true')
    options=p.parse_args(cli_arguments(argv))
    return animate(**vars(options))

def preview_stage(build, cli_arguments, argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--heightfield', required=True)
    p.add_argument('--config', required=True)
    p.add_argument('--preview', action='store_true')
    p.add_argument('--no-render', action='store_true')
    options=p.parse_args(cli_arguments(argv))
    return build(**vars(options))

def inspection_stage(inspect_motion, cli_arguments, argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    options=p.parse_args(cli_arguments(argv))
    return inspect_motion(**vars(options))

def relief_stage(extract, cli_arguments, argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--axes', nargs=3, type=int, default=[0,1,2])
    p.add_argument('--front-sign',type=int,choices=[-1,1],default=1)
    p.add_argument('--pit-threshold',type=float,default=.2)
    p.add_argument('--median-floor',type=float,default=.3)
    p.add_argument('--no-render',action='store_true')
    p.add_argument('--resolution', nargs=2, type=int, default=[769, 769])
    options=p.parse_args(cli_arguments(argv))
    return extract(**vars(options))
