# -*- coding: utf-8 -*-
"""Rhino 5–8 的 20 项调用验收夹具；仅在新空白模型内执行。

由 rhino.py prepare 内联运行时探针并添加一次顶层 run 调用。
保留 IronPython 2.7 兼容语法，也支持 Rhino 8 CPython；不依赖第三方包、
交互选择或 Rhino 8 专属建模 API。兼容目标标签不改变实际运行版本。
"""
from __future__ import print_function
import json
import math
import os
import time
import traceback

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from runtime_compat import runtime_info


def require(value, message):
    if not value:
        raise AssertionError(message)
    return value


def near(actual, expected, tolerance=0.001):
    require(abs(actual - expected) <= tolerance,
            'expected %s, got %s' % (expected, actual))


def rect():
    return rs.AddPolyline([(0, 0, 0), (10, 0, 0), (10, 10, 0),
                           (0, 10, 0), (0, 0, 0)])


def box(x=0, size=(10, 10, 10)):
    a, b, c = size
    return require(rs.AddBox([(x, 0, 0), (x+a, 0, 0), (x+a, b, 0), (x, b, 0),
                              (x, 0, c), (x+a, 0, c), (x+a, b, c), (x, b, c)]), 'box')


def volume(obj, expected):
    require(rs.IsObjectSolid(obj), 'expected a closed solid')
    value = require(rs.SurfaceVolume(obj), 'volume mass properties')[0]
    near(value, expected)
    return value


def layers():
    name = rs.CurrentLayer()
    obj = require(rs.AddPoint((0, 0, 0)), 'attribute fixture')
    rs.ObjectName(obj, 'attribute_probe')
    rs.ObjectColor(obj, (32, 125, 225))
    rs.SetUserText(obj, 'purpose', 'rhino-skill-test')
    require(rs.ObjectLayer(obj) == name, 'layer assignment')
    require(rs.ObjectName(obj) == 'attribute_probe', 'name readback')
    require(rs.GetUserText(obj, 'purpose') == 'rhino-skill-test', 'user text readback')
    color = rs.ObjectColor(obj)
    require((color.R, color.G, color.B) == (32, 125, 225), 'color readback')
    return {'units': rs.UnitSystem(), 'layer': name, 'attributes': True}


def point():
    obj = require(rs.AddPoint((1, 2, 3)), 'point')
    require(rs.PointCoordinates(obj).DistanceTo(Rhino.Geometry.Point3d(1, 2, 3)) < 1e-8, 'point position')
    return {'coordinates': [1, 2, 3]}


def line():
    obj = require(rs.AddLine((0, 0, 0), (10, 0, 0)), 'line')
    near(rs.CurveLength(obj), 10)
    return {'length': 10}


def polyline():
    obj = require(rect(), 'polyline')
    require(rs.IsCurveClosed(obj), 'closed polyline')
    near(rs.CurveLength(obj), 40)
    return {'length': 40, 'closed': True}


def circle():
    obj = require(rs.AddCircle(rs.WorldXYPlane(), 5), 'circle')
    near(rs.CircleRadius(obj), 5)
    near(rs.CurveLength(obj), 10 * math.pi)
    return {'radius': 5}


def arc():
    obj = require(rs.AddArc(rs.WorldXYPlane(), 5, 90), 'arc')
    near(rs.CurveLength(obj), 2.5 * math.pi)
    return {'angle_degrees': 90, 'length': rs.CurveLength(obj)}


def nurbs():
    points = [(0, 0, 0), (3, 4, 2), (7, -2, 3), (10, 0, 0)]
    obj = require(rs.AddInterpCurve(points, 3), 'interpolated NURBS')
    distances = []
    for p in points:
        t = rs.CurveClosestPoint(obj, p)
        distances.append(rs.EvaluateCurve(obj, t).DistanceTo(Rhino.Geometry.Point3d(*p)))
    require(max(distances) < 0.001, 'curve interpolates every input point')
    require(rs.CurveDegree(obj) == 3, 'cubic curve')
    return {'degree': 3, 'maximum_interpolation_error': max(distances)}


def planar():
    obj = require(rs.AddPlanarSrf([rect()]), 'planar surface')[0]
    near(rs.SurfaceArea(obj)[0], 100)
    return {'area': 100}


def solid_box():
    return {'volume': volume(box(), 1000)}


def sphere():
    obj = require(rs.AddSphere((0, 0, 5), 5), 'sphere')
    return {'volume': volume(obj, 4.0 * math.pi * 125 / 3)}


def cylinder():
    obj = require(rs.AddCylinder(rs.WorldXYPlane(), 10, 5, True), 'cylinder')
    return {'volume': volume(obj, math.pi * 250)}


def extrusion():
    obj = require(rs.ExtrudeCurveStraight(rect(), (0, 0, 0), (0, 0, 10)), 'extrusion')
    require(rs.CapPlanarHoles(obj), 'planar caps')
    return {'volume': volume(obj, 1000)}


def loft():
    curves = [rs.AddLine((0, 0, 0), (10, 0, 0)), rs.AddLine((0, 10, 0), (10, 10, 0))]
    objects = require(rs.AddLoftSrf(curves), 'loft')
    near(sum(rs.SurfaceArea(o)[0] for o in objects), 100)
    return {'area': 100, 'surfaces': len(objects)}


def revolve():
    profile = rs.AddLine((5, 0, 0), (5, 0, 10))
    obj = require(rs.AddRevSrf(profile, ((0, 0, 0), (0, 0, 10))), 'revolve')
    near(rs.SurfaceArea(obj)[0], 100 * math.pi)
    return {'area': rs.SurfaceArea(obj)[0]}


def sweep():
    profile = rs.AddCircle(rs.WorldXYPlane(), 2.5)
    rail = rs.AddLine((2.5, 0, 0), (2.5, 0, 10))
    objects = require(rs.AddSweep1(rail, [profile]), 'one-rail sweep')
    area = sum(rs.SurfaceArea(o)[0] for o in objects)
    near(area, 50 * math.pi)
    return {'area': area, 'surfaces': len(objects)}


def union():
    objects = require(rs.BooleanUnion([box(), box(5)], True), 'boolean union')
    require(len(objects) == 1, 'union object count')
    return {'volume': volume(objects[0], 1500)}


def difference():
    objects = require(rs.BooleanDifference([box()], [box(5)], True), 'boolean difference')
    require(len(objects) == 1, 'difference object count')
    return {'volume': volume(objects[0], 500)}


def intersection():
    objects = require(rs.BooleanIntersection([box()], [box(5)], True), 'boolean intersection')
    require(len(objects) == 1, 'intersection object count')
    return {'volume': volume(objects[0], 500)}


def transforms():
    original = box(size=(2, 4, 6))
    copy = require(rs.CopyObject(original), 'copy')
    require(rs.MoveObject(copy, (8, 0, 0)), 'move')
    require(rs.RotateObject(copy, (0, 0, 0), 90, (0, 0, 1)), 'rotate')
    require(rs.ScaleObject(copy, (0, 0, 0), (2, 2, 2)), 'scale')
    volume(original, 48)
    volume(copy, 384)
    center = rs.SurfaceVolumeCentroid(copy)[0]
    require(center.DistanceTo(Rhino.Geometry.Point3d(-4, 18, 6)) < 0.001, 'transformed centroid')
    return {'original_volume': 48, 'copy_volume': 384, 'centroid': [-4, 18, 6]}


def mesh():
    obj = require(rs.AddMesh([(0, 0, 0), (6, 0, 0), (0, 6, 0), (0, 0, 6)],
                            [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]), 'mesh')
    require(rs.IsMeshClosed(obj), 'closed tetrahedron')
    require(rs.MeshVertexCount(obj) == 4 and rs.MeshFaceCount(obj) == 4, 'mesh topology')
    near(rs.MeshVolume([obj])[1], 36)
    return {'vertices': 4, 'faces': 4, 'volume': 36}


CASES = [layers, point, line, polyline, circle, arc, nurbs, planar, solid_box,
         sphere, cylinder, extrusion, loft, revolve, sweep, union, difference,
         intersection, transforms, mesh]


def document_is_empty():
    # AllObjects() 默认排除灯光、控制点和参考几何，不能用于完整空模型判定。
    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.NormalObjects = True
    settings.LockedObjects = True
    settings.HiddenObjects = True
    settings.ReferenceObjects = True
    settings.IncludeLights = True
    settings.IncludeGrips = True
    return not any(sc.doc.Objects.GetObjectList(settings))


def run(output, compatibility_target=None):
    output = os.path.abspath(output)
    require(not os.path.exists(output), 'Use a fresh output directory; no automatic replay')
    require(document_is_empty(), 'Open a new empty Rhino document; existing objects are protected')
    require(int(rs.ExeVersion()) in (5, 6, 7, 8), 'Unsupported Rhino major')
    os.makedirs(output)
    report = {'runtime': runtime_info(), 'compatibility_target': compatibility_target,
              'cases': [], 'state': 'running', 'automatic_retries': 0}
    report_path = os.path.join(output, 'report.json')

    def save():
        with open(report_path, 'w') as stream:
            json.dump(report, stream, indent=2)

    save()
    prior_layer = rs.CurrentLayer()
    prior_redraw = rs.EnableRedraw(False)
    try:
        rs.UnitSystem(2, False)
        rs.UnitAbsoluteTolerance(0.001)
        require(rs.UnitSystem() == 2, 'millimeter units readback')
        near(rs.UnitAbsoluteTolerance(), 0.001, 1e-10)
        for index, case in enumerate(CASES):
            name = '%02d_%s' % (index + 1, case.__name__)
            color = (45 + index * 47 % 170, 70 + index * 31 % 150, 90 + index * 23 % 150)
            rs.CurrentLayer(require(rs.AddLayer(name, color), 'case layer'))
            before = set(rs.AllObjects() or [])
            started = time.time()
            row = {'name': name, 'attempts': 1}
            try:
                row['checks'] = case()
                created = list(set(rs.AllObjects() or []) - before)
                for obj in created:
                    require(sc.doc.Objects.Find(obj).Geometry.IsValid, 'invalid geometry')
                shift = ((index % 5) * 40, -(index // 5) * 40, 0)
                rs.MoveObjects(created, shift)
                label = rs.AddTextDot(name, (shift[0], shift[1] - 10, 0))
                group = rs.AddGroup(name)
                rs.AddObjectsToGroup(created + [label], group)
                row.update({'status': 'passed', 'object_ids': [str(o) for o in created],
                            'object_count': len(created)})
            except Exception as exc:
                row.update({'status': 'failed', 'error': str(exc), 'traceback': traceback.format_exc()})
            row['seconds'] = time.time() - started
            report['cases'].append(row)
            save()
        report['passed'] = sum(1 for row in report['cases'] if row['status'] == 'passed')
        report['failed'] = 20 - report['passed']
        require(report['passed'] == 20, 'Not all 20 modeling checks passed')
        rs.CurrentLayer(prior_layer)
        rs.EnableRedraw(True)
        for view in sc.doc.Views:
            rs.ViewDisplayMode(view.ActiveViewport.Id, 'Shaded')
            require(rs.ViewDisplayMode(view.ActiveViewport.Id) == 'Shaded', 'view display mode')
        rs.ZoomExtents(all=True)
        sc.doc.Views.Redraw()
        model = os.path.join(output, 'smoke20.3dm')
        options = Rhino.FileIO.FileWriteOptions()
        options.SuppressDialogBoxes = True
        options.WriteSelectedObjectsOnly = False
        require(sc.doc.WriteFile(model, options), 'native 3dm save')
        restored = require(Rhino.FileIO.File3dm.Read(model), '3dm readback')
        try:
            live_ids = set(str(o) for o in rs.AllObjects())
            disk_ids = set(str(o.Attributes.ObjectId) for o in restored.Objects)
            require(live_ids == disk_ids, '3dm object identity readback')
            require(all(o.Geometry.IsValid for o in restored.Objects), '3dm geometry readback')
            require(str(restored.Settings.ModelUnitSystem) == 'Millimeters', '3dm units readback')
            report['file_check'] = {'path': model, 'objects': len(disk_ids), 'ids_preserved': True,
                                    'geometry_valid': True, 'units': str(restored.Settings.ModelUnitSystem)}
        finally:
            restored.Dispose()
        report['state'] = 'passed'
    except Exception as exc:
        report['state'] = 'failed'
        report['error'] = str(exc)
        report['traceback'] = traceback.format_exc()
        raise
    finally:
        rs.CurrentLayer(prior_layer)
        rs.EnableRedraw(prior_redraw)
        save()
    print(json.dumps({'report': report_path, 'passed': report['passed'], 'state': report['state']}))
    return report
