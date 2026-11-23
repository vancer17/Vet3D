# -*- coding: utf-8 -*-
"""Rhino 进程内只读探针；兼容 IronPython 2.7 与 Rhino 8 CPython。"""
from __future__ import print_function
import json
import rhinoscriptsyntax as rs
from runtime_compat import runtime_info


def probe():
    value = runtime_info()
    value.update({'objects': len(rs.AllObjects() or []), 'unit_system': rs.UnitSystem(),
                  'absolute_tolerance': rs.UnitAbsoluteTolerance()})
    return value


def run(output):
    value = probe()
    # 只写新的结果文件，保留此前调用证据。
    import os
    if os.path.exists(output):
        raise ValueError('Probe output already exists')
    with open(output, 'w') as stream:
        json.dump(value, stream, indent=2)
    print(json.dumps(value))
    return value
