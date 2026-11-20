"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, sys, argparse
from pathlib import Path
from types import SimpleNamespace
from functools import partial
from render_scene import render_scene
from frame_runtime import cli_arguments, validate_paths

def render_frames(*, scene, output, frames='1,100,120'):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(scene=scene, output=output, frames=frames)
    validate_paths(a)
    numbers = list(range(int(a.frames.split('-')[0]), int(a.frames.split('-')[1])+1)) if '-' in a.frames else [int(x) for x in a.frames.split(',')]
    return render_scene(a.scene, a.output, numbers, engine='BLENDER_EEVEE',
                        resolution=(960,720), prefix='frame-')

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--scene', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--frames', default='1,100,120')
    options=p.parse_args(cli_arguments(argv))
    return render_frames(**vars(options))

if __name__ == "__main__":
    main()
