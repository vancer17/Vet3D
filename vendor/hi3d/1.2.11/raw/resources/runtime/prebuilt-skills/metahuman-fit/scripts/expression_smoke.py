"""Evaluate explicit raw-control poses using Epic OpenRigLogic and CPU linear skinning."""

import json, sys, time
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from dna_io import load_dna, positions


def world_matrices(neutral, delta, parents):
    """OpenRigLogic quaternion layout: T(3), quaternion XYZW(4), scale(3)."""
    count = len(parents)
    base = Rotation.from_quat(neutral[:, 3:7])
    rotation = (base * Rotation.from_quat(delta[:, 3:7])).as_matrix()
    local = np.tile(np.eye(4), (count, 1, 1))
    local[:, :3, :3] = rotation * (neutral[:, 7:10] + delta[:, 7:10])[:, None, :]
    local[:, :3, 3] = neutral[:, :3] + delta[:, :3]
    world = np.empty_like(local)
    for i, p in enumerate(parents):
        if p == i or p < 0:
            world[i] = local[i]
        elif p < i:
            world[i] = world[p] @ local[i]
        else:
            raise ValueError("Joint hierarchy is not parent-first")
    return world


def skin_points(vertices, transforms, indices, weights):
    result = np.zeros_like(vertices, dtype=float)
    if not np.allclose(weights.sum(1), 1, atol=2e-4):
        raise ValueError("Skin weights are not normalized")
    for column in range(weights.shape[1]):
        m = transforms[indices[:, column]]
        result += weights[:, column, None] * (
            np.einsum("nij,nj->ni", m[:, :3, :3], vertices) + m[:, :3, 3]
        )
    return result


def run(config):
    import riglogic

    start = time.monotonic()
    root = Path(config["output"])
    dna_path = root / "MetaHuman_Review.dna"
    reader = load_dna(dna_path)
    cfg = riglogic.Configuration()
    cfg.rotationType = riglogic.RotationType_Quaternions
    cfg.floatingPointType = riglogic.FloatingPointType_Float
    logic = riglogic.RigLogic(reader, cfg)
    instance = riglogic.RigInstance(logic)
    instance.setLOD(0)
    names = [reader.getRawControlName(i) for i in range(reader.getRawControlCount())]
    presets = [dict(name="neutral", controls={})] + config["expression_presets"]
    pose_names = [p["name"] for p in presets]
    if len(set(pose_names)) != len(pose_names):
        raise ValueError("Expression pose names must be unique")
    for pose in presets:
        for name, value in pose["controls"].items():
            if name not in names or not np.isfinite(value):
                raise ValueError("Unknown control or non-finite value: " + name)
    parents = np.array(
        [reader.getJointParentIndex(i) for i in range(reader.getJointCount())]
    )
    neutral = np.asarray(logic.getNeutralJointValues()).reshape(-1, 10)
    zero = np.zeros_like(neutral)
    zero[:, 6] = 1
    inverse_bind = np.linalg.inv(world_matrices(neutral, zero, parents))
    registered = np.load(root / "registered.npz", allow_pickle=False)
    meshes = []
    for mi in reader.getMeshIndicesForLOD(0):
        name = reader.getMeshName(mi)
        if not name.startswith(("head_", "eyeLeft_", "eyeRight_", "teeth_")):
            continue
        vertices = positions(reader, mi).astype(float)
        values = [reader.getSkinWeightsValues(mi, i) for i in range(len(vertices))]
        ids = [reader.getSkinWeightsJointIndices(mi, i) for i in range(len(vertices))]
        width = max(map(len, values))
        weights = np.zeros((len(vertices), width))
        indices = np.zeros((len(vertices), width), int)
        for i, (j, w) in enumerate(zip(ids, values)):
            indices[i, : len(j)] = j
            weights[i, : len(w)] = w
        targets = []
        for bi in range(reader.getBlendShapeTargetCount(mi)):
            target_ids = np.asarray(
                reader.getBlendShapeTargetVertexIndices(mi, bi), int
            )
            delta = np.column_stack(
                [
                    getattr(reader, "getBlendShapeTargetDelta" + c + "s")(mi, bi)
                    for c in "XYZ"
                ]
            )
            targets.append(
                (reader.getBlendShapeChannelIndex(mi, bi), target_ids, delta)
            )
        meshes.append((name, vertices, indices, weights, targets))
    data = {name + "_poses": [] for name, *_ in meshes}
    reports = []
    for pose in presets:
        for i in range(len(names)):
            instance.setRawControl(i, 0)
        for name, value in pose["controls"].items():
            instance.setRawControl(names.index(name), float(value))
        tick = time.monotonic()
        logic.calculate(instance)
        solver_seconds = time.monotonic() - tick
        joint_delta = np.asarray(instance.getJointOutputs()).reshape(-1, 10)
        transforms = world_matrices(neutral, joint_delta, parents) @ inverse_bind
        channels = np.asarray(instance.getBlendShapeOutputs())
        maximum = 0
        for name, vertices, indices, weights, targets in meshes:
            shaped = vertices.copy()
            for channel, ids, delta in targets:
                if abs(channels[channel]) > 1e-7:
                    shaped[ids] += channels[channel] * delta
            posed = skin_points(shaped, transforms, indices, weights)
            if not np.isfinite(posed).all():
                raise ValueError("Non-finite skinned expression")
            target = posed @ registered["linear"].T + registered["offset"]
            data[name + "_poses"].append(target.astype(np.float32))
            if name.startswith("head_"):
                maximum = float(
                    np.linalg.norm(target - registered["vertices"], axis=1).max()
                )
        reports.append(
            dict(
                name=pose["name"],
                controls=pose["controls"],
                solver_seconds=solver_seconds,
                active_blendshape_channels=int(np.count_nonzero(channels)),
                head_maximum_displacement=maximum,
            )
        )
    if reports[0]["head_maximum_displacement"] > 1e-5:
        raise ValueError("Neutral skinning does not match the registered head")
    np.savez_compressed(
        root / "expression_poses.npz",
        pose_names=np.asarray(pose_names),
        **{name: np.stack(values) for name, values in data.items()}
    )
    report = dict(
        seconds=time.monotonic() - start,
        poses=reports,
        backend="Epic OpenRigLogic",
        skinning="CPU linear blend skinning; neutral rotation multiplied by delta quaternion; corrective deltas before skinning",
        scope="LOD0 sampled poses only. Native solver executed; UE auto-rig, engine parity, animated wrinkle maps and production collision/closure acceptance not verified.",
        status="evaluated_for_visual_review",
        raw_controls=len(names),
        joints=len(parents),
    )
    (root / "expression_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    run(json.loads(Path(sys.argv[1]).read_text()))
