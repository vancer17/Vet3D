from pathlib import Path
if __package__:
    from .blender_stl import evaluated_triangles, stl_bytes
else:
    from blender_stl import evaluated_triangles, stl_bytes

def stl(o, path):
    Path(path).write_bytes(stl_bytes(evaluated_triangles([o]), header=b'Astra authored STL; millimeters', padding=b"\0"))
