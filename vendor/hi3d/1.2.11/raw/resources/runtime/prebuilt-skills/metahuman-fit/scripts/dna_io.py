"""Extract a version-bound head template or recalibrate existing DNA using its runtime.

Run with the Python interpreter and dna/dnacalib libraries matching the input DNA.
No model, runtime, account or credential is downloaded by this script.
"""

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
import numpy as np


def load_dna(path):
    import dna

    stream = dna.FileStream(
        str(path), dna.FileStream.AccessMode_Read, dna.FileStream.OpenMode_Binary
    )
    reader = dna.BinaryStreamReader(stream, dna.DataLayer_All)
    reader.read()
    if not dna.Status.isOk():
        raise ValueError(dna.Status.get().message)
    if reader.getDBName() != "DHI":
        raise ValueError(
            "This experimental adapter supports legacy DHI DNA only; use a matching adapter for other rig definitions"
        )
    return reader


def positions(reader, mesh):
    return np.column_stack(
        [getattr(reader, "getVertexPosition" + c + "s")(mesh) for c in "XYZ"]
    )


def extract(source, output, mesh_name):
    reader = load_dna(source)
    matches = [
        i for i in reader.getMeshIndicesForLOD(0) if reader.getMeshName(i) == mesh_name
    ]
    if len(matches) != 1:
        raise ValueError("Select an exact LOD0 head mesh name from the DNA")
    mi = matches[0]
    vertices = positions(reader, mi)
    pos = np.array(reader.getVertexLayoutPositionIndices(mi))
    tex = np.array(reader.getVertexLayoutTextureCoordinateIndices(mi))
    uv = np.column_stack(
        [
            reader.getVertexTextureCoordinateUs(mi),
            reader.getVertexTextureCoordinateVs(mi),
        ]
    )
    layouts = [
        reader.getFaceVertexLayoutIndices(mi, i) for i in range(reader.getFaceCount(mi))
    ]
    if any(len(f) != 4 for f in layouts):
        raise ValueError("This adapter requires the intact quad head template")
    layouts = np.array(layouts)
    weights = [reader.getSkinWeightsValues(mi, i) for i in range(len(vertices))]
    indices = [reader.getSkinWeightsJointIndices(mi, i) for i in range(len(vertices))]
    width = max(map(len, weights))
    wi = np.zeros((len(vertices), width), np.int32)
    wv = np.zeros_like(wi, np.float32)
    for i, (ids, values) in enumerate(zip(indices, weights)):
        wi[i, : len(ids)] = ids
        wv[i, : len(values)] = values
    count = reader.getJointCount()
    data = dict(
        vertices=vertices.astype(np.float32),
        quads=pos[layouts].astype(np.int32),
        quad_uvs=uv[tex[layouts]].astype(np.float32),
        weight_indices=wi,
        weight_values=wv,
        joint_names=np.array([reader.getJointName(i) for i in range(count)]),
        joint_parent_indices=np.array(
            [reader.getJointParentIndex(i) for i in range(count)]
        ),
        joint_translations=np.array(
            [reader.getNeutralJointTranslation(i) for i in range(count)]
        ),
        joint_rotations=np.array(
            [reader.getNeutralJointRotation(i) for i in range(count)]
        ),
        dna_sha256=np.array(hashlib.sha256(Path(source).read_bytes()).hexdigest()),
        mesh_index=np.array(mi),
        rig_definition=np.array(reader.getDBName()),
        native_blendshape_count=np.array(reader.getBlendShapeTargetCount(mi)),
    )
    np.savez_compressed(output, **data)
    print(
        json.dumps(
            dict(
                vertices=len(vertices),
                quads=len(layouts),
                joints=count,
                rig_definition=reader.getDBName(),
                native_blendshapes=reader.getBlendShapeTargetCount(mi),
            )
        )
    )


def calibrate(source, fitted, output):
    import dna
    from transport import Transport, local_jacobians, joint_world, joint_local

    if Path(source).resolve() == Path(output).resolve():
        raise ValueError("Output must not overwrite the source DNA")
    reader = load_dna(source)
    data = dict(np.load(fitted, allow_pickle=False))
    mesh = next(
        i
        for i in reader.getMeshIndicesForLOD(0)
        if reader.getMeshName(i) == "head_lod0_mesh"
    )
    rest = positions(reader, mesh).astype(float)
    registered = data["native_vertices"]
    if rest.shape != registered.shape or not np.isfinite(registered).all():
        raise ValueError("Registered head does not match DNA topology")
    layout = np.asarray(reader.getVertexLayoutPositionIndices(mesh))
    faces = np.asarray(
        [
            layout[np.asarray(reader.getFaceVertexLayoutIndices(mesh, i), int)]
            for i in range(reader.getFaceCount(mesh))
        ]
    )
    if not np.array_equal(data["quads"], faces):
        raise ValueError("Registered quad order does not match the source DNA")
    if (
        data.get("dna_sha256", np.array("")).item()
        != hashlib.sha256(Path(source).read_bytes()).hexdigest()
    ):
        raise ValueError("Fitted head is bound to a different source DNA")
    transport = Transport(rest, registered)
    jacobian = local_jacobians(rest, registered, data["quads"])
    # Serialize into RAM, then copy once. FileStream otherwise issues tiny writes per value.
    stream = dna.MemoryStream()
    writer = dna.BinaryStreamWriter(stream)
    writer.setFrom(reader)
    mesh_count = reader.getMeshCount()
    updated = []
    preview = {}
    for mi in range(mesh_count):
        vertices = positions(reader, mi).astype(float)
        name = reader.getMeshName(mi)
        if mi == mesh:
            new = registered
        elif any(x in name.lower() for x in ["eyeleft", "eyeright", "teeth", "saliva"]):
            new = vertices + transport.offsets(vertices).mean(
                0
            )  # preserve rigid internal part shape
        else:
            new = transport(vertices)
        writer.setVertexPositions(mi, new.tolist())
        if mi in reader.getMeshIndicesForLOD(0):
            layout = np.asarray(reader.getVertexLayoutPositionIndices(mi))
            face_layouts = [
                np.asarray(reader.getFaceVertexLayoutIndices(mi, fi), int)
                for fi in range(reader.getFaceCount(mi))
            ]
            faces = [layout[f] for f in face_layouts]
            tex = np.asarray(reader.getVertexLayoutTextureCoordinateIndices(mi))
            uv = np.column_stack(
                [
                    reader.getVertexTextureCoordinateUs(mi),
                    reader.getVertexTextureCoordinateVs(mi),
                ]
            )
            uv_faces = [uv[tex[f]] for f in face_layouts]
            triangles = np.asarray(
                [[f[0], f[j], f[j + 1]] for f in faces for j in range(1, len(f) - 1)],
                np.int32,
            )
            preview[name + "_vertices"] = (
                new @ data["linear"].T + data["offset"]
            ).astype(np.float32)
            preview[name + "_triangles"] = triangles
            preview[name + "_triangle_uvs"] = np.asarray(
                [
                    [f[0], f[j], f[j + 1]]
                    for f in uv_faces
                    for j in range(1, len(f) - 1)
                ],
                np.float32,
            )
        _, nearest = transport.tree.query(vertices)
        local = jacobian if mi == mesh else jacobian[nearest]
        for bi in range(reader.getBlendShapeTargetCount(mi)):
            ids = np.array(reader.getBlendShapeTargetVertexIndices(mi, bi), int)
            delta = np.column_stack(
                [
                    getattr(reader, "getBlendShapeTargetDelta" + c + "s")(mi, bi)
                    for c in "XYZ"
                ]
            )
            if any(
                x in name.lower() for x in ["eyeleft", "eyeright", "teeth", "saliva"]
            ):
                warped = delta
            else:
                warped = np.einsum("nij,nj->ni", local[ids], delta)
            writer.setBlendShapeTargetDeltas(mi, bi, warped.tolist())
        updated.append(
            dict(
                mesh=name,
                vertices=len(vertices),
                blendshapes=reader.getBlendShapeTargetCount(mi),
            )
        )
    n = reader.getJointCount()
    parents = np.array([reader.getJointParentIndex(i) for i in range(n)])
    trans = np.array([reader.getNeutralJointTranslation(i) for i in range(n)])
    rot = np.array([reader.getNeutralJointRotation(i) for i in range(n)])
    world, rotation = joint_world(trans, rot, parents)
    writer.setNeutralJointTranslations(
        joint_local(transport(world), rotation, parents).tolist()
    )
    writer.write()
    if not dna.Status.isOk():
        raise ValueError(dna.Status.get().message)
    temporary = Path(output).with_name(Path(output).name + ".tmp")
    file_stream = dna.FileStream(
        str(temporary), dna.FileStream.AccessMode_Write, dna.FileStream.OpenMode_Binary
    )
    try:
        file_stream.open()
        stream.seek(0)
        size = stream.size()
        written = stream.read(file_stream, size)
        if written != size or not dna.Status.isOk():
            raise ValueError("Incomplete DNA serialization")
    finally:
        file_stream.close()
    temporary.replace(output)
    del writer, stream
    check = load_dna(output)
    error = float(np.max(abs(positions(check, mesh) - registered)))
    if error > 1e-4 or check.getJointCount() != n or check.getMeshCount() != mesh_count:
        raise ValueError("DNA roundtrip changed structure or neutral coordinates")
    if any(
        check.getMeshName(i) != reader.getMeshName(i)
        or check.getBlendShapeTargetCount(i) != reader.getBlendShapeTargetCount(i)
        or check.getFaceCount(i) != reader.getFaceCount(i)
        for i in range(mesh_count)
    ):
        raise ValueError("DNA roundtrip changed mesh or corrective structure")
    report = dict(
        rig_definition=reader.getDBName(),
        meshes=updated,
        joints=n,
        neutral_roundtrip_max=error,
        source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        output_sha256=hashlib.sha256(Path(output).read_bytes()).hexdigest(),
        behavior_policy="Original RigLogic behavior tables, joint names/rotations, topology, UV and skin weights retained. Neutral joints/meshes and corrective deltas transported.",
        runtime_validation="not_performed; validate eyelids, jaw and controls in the matching MetaHuman runtime before production use",
    )
    Path(output).with_suffix(".json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    np.savez_compressed(Path(output).with_suffix(".preview.npz"), **preview)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)
    e = sub.add_parser("extract")
    e.add_argument("source")
    e.add_argument("output")
    e.add_argument("--mesh", default="head_lod0_mesh")
    c = sub.add_parser("calibrate")
    c.add_argument("source")
    c.add_argument("fitted")
    c.add_argument("output")
    args = p.parse_args()
    if args.mode == "extract":
        record = dict(
            stage="template_extract",
            task_id=str(Path(args.output).resolve()),
            attempt_id=uuid4().hex,
            started_at=datetime.now(timezone.utc).isoformat(),
            status="running",
        )
        start = time.monotonic()
        try:
            extract(args.source, args.output, args.mesh)
            record["status"] = "completed"
        except BaseException as exc:
            record["status"] = (
                "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            )
            raise
        finally:
            record.update(
                ended_at=datetime.now(timezone.utc).isoformat(),
                seconds=time.monotonic() - start,
            )
            with Path(args.output).with_suffix(".timings.jsonl").open("a") as stream:
                stream.write(json.dumps(record) + "\n")
    else:
        calibrate(args.source, args.fitted, args.output)


if __name__ == "__main__":
    main()
