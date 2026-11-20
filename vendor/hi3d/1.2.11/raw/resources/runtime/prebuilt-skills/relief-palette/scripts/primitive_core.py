"""Pure coordinate primitives; inputs and outputs use the same explicit units."""
import math

def rounded_rectangle(width, depth, radius, segments=10):
    if min(width, depth, radius) <= 0 or radius >= min(width, depth)/2 or segments < 2:
        raise ValueError('Invalid rounded rectangle')
    result = []
    for x, y, a in [(width/2-radius, depth/2-radius, 0),
                    (-width/2+radius, depth/2-radius, 90),
                    (-width/2+radius, -depth/2+radius, 180),
                    (width/2-radius, -depth/2+radius, 270)]:
        for k in range(segments+1):
            angle = math.radians(a + k*90/segments)
            result.append((x + radius*math.cos(angle), y + radius*math.sin(angle)))
    return result


def cylinder_mesh(center, radius, length, axis='X', segments=64):
    if min(radius, length) <= 0 or axis not in ('X','Y','Z') or not isinstance(segments,int) or segments<3:
        raise ValueError('Invalid cylinder')
    index = 'XYZ'.index(axis)
    others = [i for i in range(3) if i != index]
    vs = []
    for end in (-length/2, length/2):
        for j in range(segments):
            v = list(center)
            v[index] += end
            v[others[0]] += radius * math.cos(j*2*math.pi/segments)
            v[others[1]] += radius * math.sin(j*2*math.pi/segments)
            vs.append(v)
    fs = [tuple(reversed(range(segments))), tuple(range(segments, 2*segments))]
    fs += [(j, (j+1)%segments, (j+1)%segments+segments, j+segments) for j in range(segments)]
    if axis == 'Y':
        fs = [tuple(reversed(f)) for f in fs]
    return vs, fs


def extrude_polygon(outline, start, end, *, axis='Z', center=(0,0,0), orient_y=True):
    """Extrude ordered 2D vertices with outward winding for a CCW outline."""
    if axis not in ('X','Y','Z') or len(outline)<3 or not math.isfinite(start+end) or end<=start:
        raise ValueError('Polygon and increasing finite extrusion interval required')
    index='XYZ'.index(axis);others=[i for i in range(3) if i!=index]
    vertices=[];n=len(outline)
    for endpoint in (start,end):
        for point in outline:
            value=list(center);value[index]+=endpoint
            for i,k in enumerate(others):value[k]+=point[i]
            vertices.append(tuple(value))
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    if axis=='Y' and orient_y:faces=[tuple(reversed(face)) for face in faces]
    return vertices,faces
