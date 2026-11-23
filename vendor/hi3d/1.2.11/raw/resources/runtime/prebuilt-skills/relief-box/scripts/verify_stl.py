"""CLI orchestration around the independent binary STL inspector."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,json
from types import SimpleNamespace
from frame_runtime import cli_arguments, validate_paths
from frame_stl import inspect_binary_stl

def validate(*, input, output):
    a=SimpleNamespace(input=input,output=output);validate_paths(a)
    paths=[a.input] if a.input.is_file() else sorted((a.input/'print' if (a.input/'print').is_dir() else a.input).glob('*.stl'))
    if not paths:raise ValueError('No binary STL inputs')
    rows=[]
    for p in paths:
        try:rows.append(inspect_binary_stl(p))
        except (ValueError,OSError) as e:rows.append({'file':str(p),'passed':False,'error':str(e)})
    result={'method':'Exact-coordinate independent binary STL import; no geometry edits; one connected positive-volume manifold per file required','passed':all(r['passed'] for r in rows),'parts':rows}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2));return result

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    return 0 if validate(**vars(p.parse_args(cli_arguments(argv))))['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
