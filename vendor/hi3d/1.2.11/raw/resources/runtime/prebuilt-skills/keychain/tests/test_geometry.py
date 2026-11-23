"""Portable geometric invariants; no Blender, network or files required."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import math
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from geometry import frame, validate, torus, split_ring

FRAME = {'center_mm': [10, 30.5, 32], 'normal': [1, 0, 0], 'up': [0, 0, 1]}
SPEC = {'mode': 'tunnel', 'frame': FRAME, 'major_radius_mm': 4, 'tube_radius_mm': 1.6,
        'connector': {'major_radius_mm': 4, 'wire_radius_mm': .3, 'pitch_mm': .7, 'turns': 2.02}}


def properties(vertices, faces):
    edges = Counter()
    volume = 0
    for face in faces:
        for i, a in enumerate(face):
            b = face[(i+1)%len(face)]
            edges[tuple(sorted((a,b)))] += 1
        for j in range(1, len(face)-1):
            a,b,c = vertices[[face[0], face[j], face[j+1]]]
            volume += np.dot(a,np.cross(b,c))/6
    return set(edges.values()), volume


class GeometryTests(unittest.TestCase):
    def test_frame_and_units(self):
        source=deepcopy(SPEC)
        center, axes=frame(source['frame'])
        np.testing.assert_allclose(axes.T@axes, np.eye(3), atol=1e-12)
        self.assertAlmostEqual(np.linalg.det(axes),1)
        validate(source)
        self.assertEqual(source,SPEC)
        vertices,faces=torus(source)
        edges,vol=properties(vertices,faces)
        self.assertEqual(edges,{2})
        self.assertAlmostEqual(vol/(2*math.pi**2*4*1.6**2),1,delta=.01)
        local=(vertices-center)@axes
        self.assertAlmostEqual(local[:,2].max(),1.6)
        self.assertAlmostEqual(np.linalg.norm(local[:,:2],axis=1).max(),5.6)

    def test_split_ring_is_closed_solid_with_positive_volume(self):
        vertices,faces=split_ring(SPEC['connector'],FRAME)
        edges,vol=properties(vertices,faces)
        self.assertEqual(edges,{2})
        expected=math.pi*.3**2*2.02*math.sqrt((2*math.pi*4)**2+.7**2)
        self.assertAlmostEqual(vol/expected,1,delta=.025)

    def test_reject_invalid_geometry(self):
        for field,value in [('major_radius_mm',True),('tube_radius_mm',float('nan')),
                            ('tube_radius_mm',4),('segments',12),('mode','unknown')]:
            with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                source=deepcopy(SPEC); source[field]=value; validate(source)
        for normal,up in [([0,0,0],[0,0,1]),([1,0,0],[2,0,0])]:
            with self.assertRaises(ValueError):
                frame(dict(FRAME,normal=normal,up=up))
        source=deepcopy(SPEC); source['connector']['pitch_mm']=.6
        with self.assertRaises(ValueError): validate(source)
        source=deepcopy(SPEC); source['mode']='lug'
        with self.assertRaises(ValueError): validate(source)
        with self.assertRaises(ValueError): split_ring(SPEC['connector'],FRAME,samples=1)


if __name__=='__main__': unittest.main()
