"""Fit series and provenance; no geometry, printing or physical-success inference."""
import math
from pathlib import Path
from checkpoints import digest


def clearance_series(values, *, definition):
    values=list(values)
    if (not definition or not values or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in values)
            or len(set(values))!=len(values)):
        raise ValueError('Distinct nonnegative finite clearances and their definition required')
    return [{'index':i,'clearance_mm':v,'definition':definition} for i,v in enumerate(values,1)]


def source_record(path):
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    return {'file':path.name,'sha256':digest(path)}


def pair_record(identifier, files, *, clearance_mm, definition, orientation, source):
    """Record at least two explicit mating roles; extra support roles allowed."""
    clearance_series([clearance_mm],definition=definition)
    if not identifier or not orientation or not source or len(files)<2 or len(set(files.values()))!=len(files):
        raise ValueError('Pair identity, distinct files, orientation and provenance required')
    return {'id':identifier,'files':dict(files),'clearance_mm':clearance_mm,'definition':definition,
            'orientation':orientation,'source':source,'physical_test':'not_run',
            'limit':'Local coupons change footprint, thermal history and support conditions; test the complete longest interface.'}
