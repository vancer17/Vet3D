# -*- coding: utf-8 -*-
"""读取 Rhino 5–8 的运行时元数据，供探针与验收脚本共享并由 prepare 内联。"""
import platform
import sys
import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc


def runtime_info():
    # Version 从 5 SR9 提供，RuntimeSerialNumber 从 6 提供；缺失时保留兼容路径。
    version = getattr(Rhino.RhinoApp, 'Version', None)
    serial_source = ('RuntimeSerialNumber' if hasattr(sc.doc, 'RuntimeSerialNumber')
                     else 'DocumentId')
    return {'rhino_major': int(rs.ExeVersion()),
            'rhino_service_release': int(rs.ExeServiceRelease()),
            'rhino_build': str(version) if version is not None else None,
            'python': sys.version, 'implementation': platform.python_implementation(),
            'document_serial': int(getattr(sc.doc, serial_source)),
            'document_serial_source': serial_source}
