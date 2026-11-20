from pathlib import Path
import json

def load_request(input_path,config_path,output_path, *, package_root):
    inp=Path(input_path).resolve();cfg=Path(config_path).resolve();out=Path(output_path).resolve();package=Path(package_root).resolve()
    if not inp.is_file():raise FileNotFoundError(inp)
    if not cfg.is_file():raise FileNotFoundError(cfg)
    if out==package or package in out.parents:raise ValueError('Task outputs must be outside the skill package')
    if out==inp.parent or out==cfg.parent:raise ValueError('Use a distinct output directory, not the input directory')
    if out.exists() and any(out.iterdir()):raise FileExistsError('Output is nonempty; use a new revision directory')
    config=json.loads(cfg.read_text())
    if not isinstance(config,dict):raise ValueError('Config must be a JSON object')
    return inp,config,out
