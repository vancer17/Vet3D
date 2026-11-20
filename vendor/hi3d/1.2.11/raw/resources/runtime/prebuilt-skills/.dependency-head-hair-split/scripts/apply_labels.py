"""Transfer per-triangle labels to the original textured GLB and export two parts.

The label mesh is the geometry returned by Hi3D texture-only generation. Labels
must be a NumPy array in that mesh's triangle order: 0=head, 1=hair, -1=drop.
The source texture, vertex attributes and node transforms are preserved.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from checkpoints import digest as sha256

from partition import access, arrays, read, validate, write_partition


def face_geometry(vertices, faces):
    triangle = np.asarray(vertices[faces], dtype=np.float64)
    centers = triangle.mean(axis=1)
    cross = np.cross(triangle[:, 1] - triangle[:, 0], triangle[:, 2] - triangle[:, 0])
    area2 = np.linalg.norm(cross, axis=1)
    normals = cross / np.maximum(area2[:, None], 1e-30)
    return centers, normals, area2


def verify_triangle_vertices(sv, sf, lv, lf, tolerance):
    """Check actual triangle corners, allowing reversed or cyclic ordering."""
    for start in range(0, len(sf), 100000):
        a = sv[sf[start:start + 100000]].astype(np.float64)
        b = lv[lf[start:start + 100000]].astype(np.float64)
        distance = np.linalg.norm(a[:, :, None] - b[:, None, :], axis=-1)
        if np.any(distance.min(axis=1) > tolerance) or np.any(distance.min(axis=2) > tolerance):
            raise ValueError("triangle centers matched but actual corners changed")


def transfer_labels(source_vertices, source_faces, label_vertices, label_faces, labels, tolerance):
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("transfer tolerance must be positive and finite")
    if len(label_faces) != len(labels):
        raise ValueError("label count does not match the Hi3D label mesh triangle count")
    if np.array_equal(source_vertices, label_vertices) and np.array_equal(source_faces, label_faces):
        return labels.copy(), {"mode": "exact_vertices_and_indices", "max_center_distance": 0.0}
    source_centers, source_normals, source_area2 = face_geometry(source_vertices, source_faces)
    label_centers, label_normals, label_area2 = face_geometry(label_vertices, label_faces)
    diagonal = float(np.linalg.norm(source_vertices.max(0) - source_vertices.min(0)))
    absolute_tolerance = tolerance * max(diagonal, 1e-12)

    if len(source_faces) == len(label_faces):
        delta = np.linalg.norm(source_centers - label_centers, axis=1)
        normal_agreement = np.abs(np.einsum("ij,ij->i", source_normals, label_normals))
        area_ratio = np.maximum(source_area2, label_area2) / np.maximum(
            np.minimum(source_area2, label_area2), 1e-30
        )
        if (
            float(delta.max(initial=0.0)) <= absolute_tolerance
            and float(normal_agreement.min(initial=1.0)) >= 0.999
            and float(area_ratio.max(initial=1.0)) <= 1.001
        ):
            verify_triangle_vertices(source_vertices, source_faces, label_vertices, label_faces, absolute_tolerance)
            return labels.copy(), {
                "mode": "triangle_order",
                "max_center_distance": float(delta.max(initial=0.0)),
                "tolerance": absolute_tolerance,
            }

    if len(source_faces) != len(label_faces):
        raise ValueError("Hi3D changed the triangle count; automatic label transfer is unsafe")

    tree = cKDTree(label_centers)
    distance, index = tree.query(source_centers, k=1, workers=-1)
    if float(distance.max(initial=0.0)) > absolute_tolerance:
        raise ValueError("Hi3D changed vertex positions beyond the transfer tolerance")
    counts = np.bincount(index, minlength=len(label_faces))
    if not np.all(counts == 1):
        raise ValueError("triangle-center mapping is not one-to-one")
    agreement = np.abs(np.einsum("ij,ij->i", source_normals, label_normals[index]))
    area_ratio = np.maximum(source_area2, label_area2[index]) / np.maximum(
        np.minimum(source_area2, label_area2[index]), 1e-30
    )
    if float(agreement.min(initial=1.0)) < 0.999 or float(area_ratio.max(initial=1.0)) > 1.001:
        raise ValueError("nearest triangles do not have matching orientation and area")
    verify_triangle_vertices(source_vertices, source_faces, label_vertices, label_faces[index], absolute_tolerance)
    return labels[index], {
        "mode": "triangle_centers",
        "max_center_distance": float(distance.max(initial=0.0)),
        "tolerance": absolute_tolerance,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="original textured GLB")
    parser.add_argument("--label-mesh", type=Path, required=True, help="Hi3D black/white textured GLB")
    parser.add_argument("--labels", type=Path, required=True, help="graph-cut .npy labels")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=1e-6, help="fraction of source bounding-box diagonal")
    return parser.parse_args()


def run(args):
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("output directory must be new or empty")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source_doc, source_binary = read(args.source)
    label_doc, label_binary = read(args.label_mesh)
    source_vertices, source_faces = validate(source_doc, source_binary)
    label_vertices, label_faces = validate(label_doc, label_binary)
    raw_labels = np.load(args.labels, allow_pickle=False)
    if raw_labels.ndim != 1 or not set(np.unique(raw_labels)).issubset({-1, 0, 1}):
        raise ValueError("labels must be a one-dimensional array containing only -1, 0 and 1")
    transferred, mapping = transfer_labels(
        source_vertices,
        source_faces,
        label_vertices,
        label_faces,
        raw_labels,
        args.tolerance,
    )
    if np.any(transferred < 0):
        raise ValueError("graph cut dropped triangles; refusing to alter the original textured surface")
    if set(np.unique(transferred)) != {0, 1}:
        raise ValueError("both head and hair must have nonempty triangle sets")

    combined = args.output_dir / "head_hair_textured.glb"
    head = args.output_dir / "head_textured.glb"
    hair = args.output_dir / "hair_textured.glb"
    write_partition(combined, source_doc, source_binary, source_faces, transferred, ["Head", "Hair"])
    write_partition(head, source_doc, source_binary, source_faces, (transferred != 0).astype(np.uint8), ["Head"])
    write_partition(hair, source_doc, source_binary, source_faces, (transferred != 1).astype(np.uint8), ["Hair"])

    # Independently reopen the exports and compare the actual index sets and
    # unchanged attribute/image bytes against the original file.
    for path, expected in ((combined, {"Head": 0, "Hair": 1}), (head, {"Head": 0}), (hair, {"Hair": 1})):
        doc, binary = read(path)
        if not (binary[:len(source_binary)] == source_binary):
            raise ValueError('Export integrity verification failed')
        for key in ("materials", "images", "textures", "samplers"):
            if not (doc.get(key) == source_doc.get(key)):
                raise ValueError('Export integrity verification failed')
        if not (len(doc["meshes"]) == len(expected)):
            raise ValueError('Export integrity verification failed')
        for mesh in doc["meshes"]:
            label = expected[mesh["name"]]
            primitive = mesh["primitives"][0]
            if not (primitive["attributes"] == source_doc["meshes"][0]["primitives"][0]["attributes"]):
                raise ValueError('Export integrity verification failed')
            if not (np.array_equal(access(doc, binary, primitive["indices"]).reshape(-1, 3), source_faces[transferred == label])):
                raise ValueError('Export integrity verification failed')
        for original, exported in zip(source_doc["nodes"], doc["nodes"]):
            for key in ("matrix", "translation", "rotation", "scale"):
                if not (original.get(key) == exported.get(key)):
                    raise ValueError('Export integrity verification failed')
    np.save(args.output_dir / "source_face_labels.npy", transferred)

    report = {
        "source": str(args.source.resolve()),
        "source_sha256": sha256(args.source),
        "label_mesh": str(args.label_mesh.resolve()),
        "label_mesh_sha256": sha256(args.label_mesh),
        "mapping": mapping,
        "labels_sha256": sha256(args.labels),
        "verified_original_binary_and_materials": True,
        "verified_every_triangle_exactly_once": True,
        "triangles": {
            "total": int(len(source_faces)),
            "head": int(np.count_nonzero(transferred == 0)),
            "hair": int(np.count_nonzero(transferred == 1)),
        },
        "preserved": ["source vertex attributes", "source materials", "source textures", "source node transforms"],
        "outputs": {path.stem: {"path": str(path), "sha256": sha256(path)} for path in (combined, head, hair)},
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run(parse_args())
