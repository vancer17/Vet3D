"""Rigid column-vector poses in caller-specified units; pure NumPy."""
import math
import numpy as np


def axis_pose(center, axis, angle_rad, axial_travel=0):
    """Rotate around an arbitrary world axis, then translate along that axis."""
    center=np.asarray(center,dtype=float);axis=np.asarray(axis,dtype=float)
    if center.shape!=(3,) or axis.shape!=(3,) or not np.isfinite([*center,*axis,angle_rad,axial_travel]).all():
        raise ValueError('Finite center/axis three-vectors and angle/travel required')
    length=np.linalg.norm(axis)
    if length<1e-12:raise ValueError('Axis must be nonzero')
    axis=axis/length;x,y,z=axis;c=math.cos(angle_rad);s=math.sin(angle_rad)
    cross=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    rotation=c*np.eye(3)+(1-c)*np.outer(axis,axis)+s*cross
    matrix=np.eye(4);matrix[:3,:3]=rotation
    matrix[:3,3]=center+axis*axial_travel-rotation@center
    return matrix


def is_rigid(matrix):
    """Return whether a finite 4x4 matrix is a proper rigid column-vector transform."""
    m=np.asarray(matrix,dtype=float)
    return (m.shape==(4,4) and np.isfinite(m).all()
            and np.allclose(m[3],[0,0,0,1],atol=1e-6)
            and np.allclose(m[:3,:3].T@m[:3,:3],np.eye(3),atol=1e-6)
            and abs(np.linalg.det(m[:3,:3])-1)<1e-6)
