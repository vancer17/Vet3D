"""Convert binary millimetre STL to 3MF geometry; no printer/slicer profile."""
import argparse
import io
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile

NS = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'


def decode_stl(data):
    """Pure binary STL parsing: indexed vertices and triangles, no geometry repair."""
    if len(data) < 84:
        raise ValueError('Truncated binary STL')
    count = struct.unpack_from('<I', data, 80)[0]
    if count == 0 or len(data) != 84 + count * 50:
        raise ValueError('Require nonempty exact-length binary STL')
    vertices, triangles, indices = [], [], {}
    for i in range(count):
        values = struct.unpack_from('<12fH', data, 84 + i * 50)
        if not all(math.isfinite(x) for x in values[:12]):
            raise ValueError('STL contains non-finite coordinates or normals')
        tri = []
        for j in range(3):
            xyz = tuple(values[3+3*j:6+3*j])
            if xyz not in indices:
                indices[xyz] = len(vertices)
                vertices.append(xyz)
            tri.append(indices[xyz])
        if len(set(tri)) != 3:
            raise ValueError('STL contains a collapsed triangle')
        triangles.append(tri)
    return vertices, triangles


def model_xml(vertices, triangles):
    """Create a unit-explicit 3MF model document from indexed geometry."""
    ET.register_namespace('', NS)
    def tag(name): return '{' + NS + '}' + name
    model = ET.Element(tag('model'), {'unit':'millimeter', 'xml:lang':'en-US'})
    resources = ET.SubElement(model, tag('resources'))
    obj = ET.SubElement(resources, tag('object'), {'id':'1', 'type':'model'})
    mesh = ET.SubElement(obj, tag('mesh'))
    vs = ET.SubElement(mesh, tag('vertices'))
    ts = ET.SubElement(mesh, tag('triangles'))
    for xyz in vertices:
        ET.SubElement(vs, tag('vertex'), dict(zip(('x','y','z'), (format(x,'.9g') for x in xyz))))
    for tri in triangles:
        ET.SubElement(ts, tag('triangle'), dict(zip(('v1','v2','v3'), map(str,tri))))
    build = ET.SubElement(model, tag('build'))
    ET.SubElement(build, tag('item'), {'objectid':'1'})
    return ET.tostring(model, encoding='utf-8', xml_declaration=True)


def package_3mf(model):
    """Pure ZIP serialization with OPC relationships and content types."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('3D/3dmodel.model', model)
        archive.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        archive.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    return buffer.getvalue()


def convert(source, destination):
    """File adapter; reject overwrite, parse fully before creating the output."""
    destination = Path(destination)
    vertices, triangles = decode_stl(Path(source).read_bytes())
    data = package_3mf(model_xml(vertices, triangles))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as output:
        output.write(data)
    return {'vertices':len(vertices), 'triangles':len(triangles), 'units':'mm', 'slicer_profile':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input'); parser.add_argument('output')
    args = parser.parse_args()
    try:
        info = convert(args.input, args.output)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f"{args.output}: millimetres, {info['triangles']} triangles; geometry only")


if __name__ == '__main__':
    main()
