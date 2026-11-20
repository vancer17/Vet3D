"""Timed local build adapter with explicit package root and deferred callable loader."""
from pathlib import Path
import json,sys,time,uuid
from datetime import datetime,timezone
from request_inputs import load_request

def run_build(input_path,config_path,output_path,geometry_only=True, *, package_root, loader):
    """Run local geometry stage; report its wall time only, not the whole design workflow."""
    inp,config,out=load_request(input_path,config_path,output_path,package_root=package_root);out.mkdir(parents=True,exist_ok=True)
    attempt=str(uuid.uuid4());started=datetime.now(timezone.utc).isoformat();clock=time.monotonic();status='failed'
    try:
        sys.path.insert(0, str(Path(package_root).resolve() / "scripts"))
        build=loader()
        result=build(inp,config,out,geometry_only);status='completed';return result
    except KeyboardInterrupt:
        status='interrupted';raise
    finally:
        row={'task_id':None,'task_id_reason':'Associate this local attempt with the business task in its external progress record','stage':'offline-build-export','attempt_id':attempt,'status':status,'started_at':started,'ended_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-clock,'coverage':'Starts after path/JSON preflight; includes module import and build/export. Preflight timing is not captured here. Other business stages and task totals are recorded externally'}
        (out/'stage-time.json').write_text(json.dumps(row,indent=2))
