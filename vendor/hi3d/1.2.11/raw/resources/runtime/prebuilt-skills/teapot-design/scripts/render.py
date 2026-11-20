"""Render a bounded explicit animation range; CLI contains no scene logic."""
import argparse,sys
from pathlib import Path

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--start',type=int);p.add_argument('--end',type=int);p.add_argument('--resolution',type=int,default=720);p.add_argument('--samples',type=int,default=32);a=p.parse_args(argv)
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from teapot_model.media import render_frames
    render_frames(a.input,a.output,a.start,a.end,a.resolution,a.samples)

if __name__=='__main__':main(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:])
