"""Explicit file adapters. No automatic repair, scale change or per-part arrangement."""
import io
from pathlib import Path
from xml.sax.saxutils import escape
import zipfile

import manifold3d as mf
import numpy as np
import trimesh


def to_trimesh(solid):
    mesh = solid.to_mesh()
    return trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts, process=False)


def read_stl_solid(path):
    """Read actual STL, weld exactly equal coordinates only, and reject invalid solids."""
    mesh = trimesh.load_mesh(Path(path), process=False)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError("Expected nonempty STL mesh")
    if not np.isfinite(mesh.vertices).all():
        raise ValueError("Non-finite STL coordinates")
    vertices, inverse = np.unique(mesh.vertices, axis=0, return_inverse=True)
    faces = inverse[mesh.faces]
    welded = trimesh.Trimesh(vertices, faces, process=False)
    if (not welded.is_watertight or not welded.is_winding_consistent
            or np.any(welded.area_faces == 0) or welded.volume <= 0):
        raise ValueError("STL fails closed, oriented, nondegenerate positive-volume checks")
    solid = mf.Manifold(mf.Mesh(np.asarray(vertices, np.float32), np.asarray(faces, np.uint32)))
    if solid.status() != mf.Error.NoError or len(solid.decompose()) != 1:
        raise ValueError("STL must contain exactly one valid solid")
    return solid


def write_3mf(path, named_solids, title):
    """Geometry-only mm 3MF: one mesh, multiple disconnected solids, positions intact."""
    if not named_solids:
        raise ValueError("No solids to export")
    meshes = [to_trimesh(solid) for solid in named_solids.values()]
    content_types = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(Path(path), 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', content_types)
        archive.writestr('_rels/.rels', rels)
        with archive.open('3D/3dmodel.model', 'w', force_zip64=True) as stream:
            text = io.TextIOWrapper(stream, encoding='utf-8', newline='\n')
            text.write('<model unit="millimeter" xml:lang="en-US" '
                       'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
                       f'<metadata name="Title">{escape(title)}</metadata>'
                       '<metadata name="Description">Geometry only; keep relative positions. '
                       'Supports and physical release require verification.</metadata>'
                       '<resources><object id="1" type="model"><mesh><vertices>\n')
            for mesh in meshes:
                text.writelines('<vertex x="%.9g" y="%.9g" z="%.9g"/>\n' % tuple(v)
                                for v in mesh.vertices)
            text.write('</vertices><triangles>\n')
            offset = 0
            for mesh in meshes:
                text.writelines('<triangle v1="%d" v2="%d" v3="%d"/>\n' % tuple(f + offset)
                                for f in mesh.faces)
                offset += len(mesh.vertices)
            text.write('</triangles></mesh></object></resources><build><item objectid="1"/></build></model>')
            text.flush()
            text.detach()
