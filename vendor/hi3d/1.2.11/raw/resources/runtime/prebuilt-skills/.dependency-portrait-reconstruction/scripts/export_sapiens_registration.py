"""Export registered MetaHuman skin in source GLB coordinates and landmark QA."""

import json, sys, hashlib
from pathlib import Path
import numpy as np, trimesh
from PIL import Image, ImageDraw


def export(config):
    out = Path(config["output"])
    skill = Path(__file__).resolve().parents[1]
    fit_path = Path(config["export_fit"])
    d = dict(np.load(fit_path))
    if (
        str(d["source_sha256"])
        != hashlib.sha256(Path(config["source"]).read_bytes()).hexdigest()
    ):
        raise ValueError("Fitted prior belongs to a different source")
    if any(
        (out / name).exists()
        for name in [
            "registered_glb_coordinates.npz",
            "registered.glb",
            "export_report.json",
        ]
    ):
        raise FileExistsError("Use a new export revision")
    template = dict(np.load(skill / "assets/taro/template.npz"))
    if not (
        np.array_equal(d["quads"], template["quads"])
        and np.array_equal(d["quad_uvs"], template["quad_uvs"])
    ):
        raise ValueError("Invalid input: export_sapiens_registration contract")
    if not (np.isfinite(d["vertices"]).all()):
        raise ValueError("Invalid input: export_sapiens_registration contract")
    # GLB Y-up -> Blender Z-up was x,-z,y; its inverse is x,z,-y.
    transform = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
    g = dict(d)
    g["source_sha256"] = np.array(
        hashlib.sha256(Path(config["source"]).read_bytes()).hexdigest()
    )
    for key in ["vertices", "rest"]:
        g[key] = np.einsum("ij,jk->ik", d[key], transform)
    g["linear"] = transform.T @ d["linear"]
    g["offset"] = d["offset"] @ transform
    np.savez_compressed(out / "registered_glb_coordinates.npz", **g)
    f = np.concatenate([g["quads"][:, [0, 1, 2]], g["quads"][:, [0, 2, 3]]])
    mesh = trimesh.Trimesh(g["vertices"], f, process=False)
    mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=[160, 160, 160, 255])
    mesh.export(out / "registered.glb")
    settings = json.loads((out / "settings.json").read_text())
    camera = json.loads((out / "camera.json").read_text())
    mat = np.array(camera["camera_matrix_world"])
    points = np.array([x["target"] for x in settings["landmarks"]])
    p = np.einsum("ij,jk->ik", points - mat[:3, 3], mat[:3, :3])
    uv = np.column_stack(
        [
            (p[:, 0] / camera["ortho_scale"] + 0.5) * 1024,
            (0.5 - p[:, 1] / camera["ortho_scale"]) * 1024,
        ]
    )
    image = Image.open(out / "front.png").convert("RGB")
    draw = ImageDraw.Draw(image)
    for row, (x, y) in zip(settings["landmarks"], uv):
        draw.ellipse(
            (x - 2, y - 2, x + 2, y + 2),
            fill={"left_eye": "#36c9ed", "right_eye": "#ffbb55", "lips": "#ef64aa"}[
                row["group"]
            ],
        )
    image.save(out / "landmarks.png")
    stats = {
        "template_vertices": len(g["vertices"]),
        "quads": len(g["quads"]),
        "triangles": len(f),
        "source_units_retained": True,
        "template_topology_uv_unchanged": True,
        "landmarks": len(points),
        "groups": {
            k: sum(x["group"] == k for x in settings["landmarks"])
            for k in ["left_eye", "right_eye", "lips"]
        },
        "automatic_target_landmarks": True,
        "manual_target_landmarks": False,
        "source_sha256": hashlib.sha256(
            Path(config["source"]).read_bytes()
        ).hexdigest(),
        "registered_sha256": hashlib.sha256(
            (out / "registered.glb").read_bytes()
        ).hexdigest(),
    }
    (out / "export_report.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats))


if __name__ == "__main__":
    export(json.loads(Path(sys.argv[1]).read_text()))
