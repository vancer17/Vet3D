import argparse
from pathlib import Path

def product_parser(description):
    p = argparse.ArgumentParser(description=description)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--work-dir', type=Path, required=True)
    p.add_argument('--blender', required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--stage', choices=['geometry', 'full'], default='full')
    video = p.add_mutually_exclusive_group()
    video.add_argument('--render-video', dest='no_video', action='store_false', help='Render/encode video only when explicitly requested')
    video.add_argument('--no-video', dest='no_video', action='store_true', help='Keep video disabled (the default)')
    p.set_defaults(no_video=True)
    p.add_argument('--skip-source-views', action='store_true')
    p.add_argument('--skip-stills', action='store_true')
    return p
