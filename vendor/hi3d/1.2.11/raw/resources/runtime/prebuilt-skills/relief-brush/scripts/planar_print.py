from pathlib import Path
if __package__:
    from .blender_stl import evaluated_triangles, stl_bytes
else:
    from blender_stl import evaluated_triangles, stl_bytes

def export_stl_legacy(path, objects):
    Path(path).write_bytes(stl_bytes(evaluated_triangles(objects), header=b'Millimetres | evaluated independent printable part'))
