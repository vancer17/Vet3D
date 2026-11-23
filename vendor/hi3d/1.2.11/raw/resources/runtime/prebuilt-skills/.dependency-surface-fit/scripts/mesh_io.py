"""Vertex-order preserving OBJ output in template-native coordinates."""

from pathlib import Path


def write_obj(path, vertices, quads, uvs=None):
    with Path(path).open("w") as out:
        for v in vertices:
            out.write("v " + " ".join(f"{x:.9g}" for x in v) + "\n")
        if uvs is not None:
            for uv in uvs.reshape(-1, 2):
                out.write(f"vt {uv[0]:.9g} {uv[1]:.9g}\n")
        for i, q in enumerate(quads):
            out.write(
                "f "
                + " ".join(
                    str(int(v) + 1) + (f"/{i*4+j+1}" if uvs is not None else "")
                    for j, v in enumerate(q)
                )
                + "\n"
            )
