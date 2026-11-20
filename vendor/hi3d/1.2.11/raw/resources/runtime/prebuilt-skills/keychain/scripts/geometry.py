"""Pure millimetre geometry: local frames, torus and split-ring meshes."""
import math
import numpy as np


def number(value, name, minimum=None, strict=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + ' must be a finite number')
    if minimum is not None and (value <= minimum if strict else value < minimum):
        raise ValueError(name + ' is too small')
    return float(value)


def vector(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(name + ' must contain three numbers')
    return np.array([number(v, name) for v in value], dtype=float)


def frame(spec):
    center = vector(spec['center_mm'], 'center_mm')
    normal = vector(spec['normal'], 'normal')
    up = vector(spec['up'], 'up')
    if np.linalg.norm(normal) < 1e-12:
        raise ValueError('normal must be nonzero')
    normal /= np.linalg.norm(normal)
    up = up - normal * np.dot(up, normal)
    if np.linalg.norm(up) < 1e-12:
        raise ValueError('up must not be parallel to normal')
    up /= np.linalg.norm(up)
    return center, np.column_stack((np.cross(up, normal), up, normal))


def validate(spec):
    if not isinstance(spec, dict) or spec.get('mode') not in ('tunnel', 'lug'):
        raise ValueError('mode must be tunnel or lug')
    allowed = {'mode', 'frame', 'major_radius_mm', 'tube_radius_mm', 'segments',
               'sides', 'connector', 'audit_padding_mm', 'solver'}
    if set(spec) - allowed:
        raise ValueError('Unknown fields: ' + ', '.join(sorted(set(spec) - allowed)))
    frame(spec['frame'])
    radius = number(spec['major_radius_mm'], 'major_radius_mm', 0, True)
    wire = number(spec['tube_radius_mm'], 'tube_radius_mm', 0, True)
    if wire >= radius:
        raise ValueError('tube_radius_mm must be less than major_radius_mm')
    for key, default, lo, hi in [('segments', 160, 24, 1024), ('sides', 40, 8, 128)]:
        value = spec.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
            raise ValueError(key + ' outside supported integer range')
    number(spec.get('audit_padding_mm', 1), 'audit_padding_mm', 0)
    if spec.get('solver', 'MANIFOLD') not in ('MANIFOLD', 'EXACT'):
        raise ValueError('solver must be MANIFOLD or EXACT')
    ring = spec.get('connector')
    if ring is not None:
        if not isinstance(ring, dict) or set(ring) - {'frame', 'major_radius_mm', 'wire_radius_mm', 'pitch_mm', 'turns', 'phase_deg'}:
            raise ValueError('Invalid connector fields')
        if spec['mode'] == 'lug' and 'frame' not in ring:
            raise ValueError('A lug connector needs its own perpendicular mounting frame')
        frame(ring.get('frame', spec['frame']))
        rr = number(ring['major_radius_mm'], 'connector.major_radius_mm', 0, True)
        rw = number(ring['wire_radius_mm'], 'connector.wire_radius_mm', 0, True)
        pitch = number(ring['pitch_mm'], 'connector.pitch_mm', 0)
        turns = number(ring['turns'], 'connector.turns', 0, True)
        number(ring.get('phase_deg', 90), 'connector.phase_deg')
        if rw >= rr or turns > 4 or turns < 1:
            raise ValueError('Connector requires radius > wire radius and 1..4 turns')
        if turns > 1 and pitch <= 2 * rw:
            raise ValueError('Adjacent turns need pitch greater than wire diameter')
    return spec


def torus(spec):
    """Return world-mm vertex/face arrays; winding is outward."""
    center, axes = frame(spec['frame'])
    radius, wire = spec['major_radius_mm'], spec['tube_radius_mm']
    n, m = spec.get('segments', 160), spec.get('sides', 40)
    vertices, faces = [], []
    for i in range(n):
        t = math.tau * i / n
        for j in range(m):
            f = math.tau * j / m
            v = ((radius + wire * math.cos(f)) * math.cos(t),
                 (radius + wire * math.cos(f)) * math.sin(t), wire * math.sin(f))
            vertices.append(center + axes @ np.array(v))
    for i in range(n):
        for j in range(m):
            faces.append((i*m+j, ((i+1)%n)*m+j, ((i+1)%n)*m+(j+1)%m, i*m+(j+1)%m))
    return np.array(vertices), faces


def split_ring(spec, default_frame, samples=512, sides=20):
    """Capped helical wire with stable radial frames; no spring simulation."""
    if any(isinstance(v, bool) or not isinstance(v, int) or v < lo for v, lo in ((samples, 2), (sides, 3))):
        raise ValueError('Split ring needs integer samples >= 2 and sides >= 3')
    center, axes = frame(spec.get('frame', default_frame))
    radius, wire, pitch, turns = (spec[k] for k in ('major_radius_mm', 'wire_radius_mm', 'pitch_mm', 'turns'))
    vertices, faces = [], []
    phase = math.radians(spec.get('phase_deg', 90))
    for i in range(samples):
        f = i / (samples-1); t = phase + math.tau * turns * f
        radial = np.array([math.cos(t), math.sin(t), 0.])
        tangent = np.array([-radius*math.sin(t), radius*math.cos(t), pitch/math.tau])
        tangent /= np.linalg.norm(tangent)
        side = np.cross(tangent, radial)
        path = radius * radial + np.array([0, 0, pitch * turns * (f-.5)])
        for j in range(sides):
            phi = math.tau*j/sides
            vertices.append(center + axes @ (path + wire*(radial*math.cos(phi)+side*math.sin(phi))))
    for i in range(samples-1):
        for j in range(sides):
            faces.append((i*sides+j, i*sides+(j+1)%sides, (i+1)*sides+(j+1)%sides, (i+1)*sides+j))
    faces.extend([tuple(reversed(range(sides))), tuple((samples-1)*sides+j for j in range(sides))])
    return np.array(vertices), faces
