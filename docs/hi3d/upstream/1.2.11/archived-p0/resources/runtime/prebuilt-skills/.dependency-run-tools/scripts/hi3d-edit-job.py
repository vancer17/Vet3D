"""Explicit local editing jobs: immutable inputs, bounded execution, verified reuse."""
from pathlib import Path
import hashlib
import json
import math
import os
import signal
import shutil
import subprocess
from process_run import run_budgeted, write_heartbeat, BudgetTimeout
from path_safety import validate_write_roots


def number(value, name, minimum=0, strict=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (value <= minimum if strict else value < minimum):
        raise ValueError(name + " is outside its finite range")
    return value


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''): h.update(chunk)
    return h.hexdigest()


def dump(path, data):
    path=Path(path)
    tmp=path.with_name('.'+path.name+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    tmp.replace(path)


def local_file(value, base):
    if not isinstance(value,str) or not value or '://' in value:
        raise ValueError('require local file path')
    p=(Path(base)/value).resolve(strict=True)
    if not p.is_file(): raise ValueError('input must be a file')
    return p


def probe(executable, args=('--version',), timeout=10):
    """Explicit binary only; version availability is not feature/license certification."""
    found=shutil.which(str(executable)) if executable else None
    if not found: return {'available':False,'reason':'executable_not_found'}
    try:
        r=subprocess.run([found,*args],capture_output=True,text=True,timeout=timeout)
        return {'available':r.returncode==0,'executable':found,'version':(r.stdout or r.stderr)[:1500], 'returncode':r.returncode}
    except subprocess.TimeoutExpired:
        return {'available':False,'reason':'probe_timeout'}


class EditJob:
    """New directory per attempt. Successful reuse is read-only after hashes match."""
    def __init__(self, output, spec, inputs, package_root, budget=120):
        number(budget,'budget',0,True)
        self.root=validate_write_roots({'output':output},package_root=package_root,protected_inputs=inputs)['output']
        self.inputs={str(Path(p).resolve()):digest(p) for p in inputs}
        self.budget=budget
        code={str(p.relative_to(package_root)):digest(p) for p in sorted(Path(package_root).rglob('*')) if p.is_file() and p.suffix in ('.py','.js','.mjs','.cjs','.jsx','.tsx','.json') and 'node_modules' not in p.parts and '__pycache__' not in p.parts}
        self.fingerprint=hashlib.sha256(json.dumps([spec,self.inputs,code],sort_keys=True,allow_nan=False).encode()).hexdigest()
        self.reused=False
        if self.root.exists():
            report=json.loads((self.root/'hi3d-result.json').read_text())
            if report['status']!='completed' or report['fingerprint']!=self.fingerprint:
                raise ValueError('existing attempt is incomplete or changed; choose a new output')
            for a in report['artifacts']:
                p=(self.root/a['path']).resolve()
                if self.root not in p.parents or digest(p)!=a['sha256']: raise ValueError('artifact changed')
            self.reused=True
            self.result=report
            return
        self.root.mkdir(parents=True,exist_ok=False)
        dump(self.root/'hi3d-budget.json',{'max_wall_seconds':budget})
        self.state('running')
        write_heartbeat(self.root/'hi3d-progress.json',status='running',phase='preflight',elapsed_s=0,budget_s=budget)

    def __enter__(self):
        self.previous_term = signal.getsignal(signal.SIGTERM)
        def cancelled(signum, frame):
            raise KeyboardInterrupt("task cancelled")
        signal.signal(signal.SIGTERM, cancelled)
        return self

    def __exit__(self,kind,value,tb):
        signal.signal(signal.SIGTERM, self.previous_term)
        if kind is not None:
            self.state("interrupted" if issubclass(kind,(BudgetTimeout,KeyboardInterrupt,SystemExit)) else "failed",error=kind.__name__)
        return False

    def state(self,status,**fields):
        dump(self.root/'hi3d-result.json',dict(schemaVersion=1,status=status,fingerprint=self.fingerprint,**fields))

    def run(self,argv,phase):
        """One bounded direct child per phase. Exceptions never publish success."""
        if self.reused: raise ValueError('cannot execute a reused job')
        if not phase.replace('-','').isalnum(): raise ValueError('invalid phase')
        try:
            run_budgeted([str(x) for x in argv],self.root/f'hi3d-{phase}.log',max_wall_seconds=self.budget,heartbeat_path=self.root/'hi3d-progress.json',kill_tree=(os.name=='posix'))
        except BaseException as exc:
            self.state('interrupted' if isinstance(exc,(BudgetTimeout,KeyboardInterrupt,SystemExit)) else 'failed',error=type(exc).__name__,phase=phase)
            raise

    def finish(self, files, checks):
        if any(digest(p)!=h for p,h in self.inputs.items()): raise ValueError('source changed during operation')
        artifacts=[]
        for p in files:
            p=Path(p).resolve()
            if self.root not in p.parents or not p.is_file() or p.stat().st_size==0: raise ValueError('invalid artifact')
            artifacts.append({'path':str(p.relative_to(self.root)),'sha256':digest(p),'bytes':p.stat().st_size})
        if not artifacts: raise ValueError('no artifacts')
        self.state('completed',artifacts=artifacts,checks=checks)
        self.result=json.loads((self.root/'hi3d-result.json').read_text())
        return self.result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Probe one explicitly selected local editing executable; never install it.')
    parser.add_argument('--probe',required=True)
    parser.add_argument('--version-arg',default='--version')
    args=parser.parse_args()
    print(json.dumps(probe(args.probe,(args.version_arg,)),ensure_ascii=False))
